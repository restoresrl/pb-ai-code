"""The marker file: what was installed here, from what, when.

``_installed-from-pb-ai-code.txt`` is a ``#``-comment file with values
aligned at column 14, all ASCII, hyphens and never em dashes. It is
written **last** and, unlike the script's version, atomically: a temp file
in the same directory and ``os.replace``, so a failure leaves the previous
marker rather than a truncated one.

Bytes: UTF-8 **without** a BOM, CRLF throughout including the trailing
newline, on every platform. Parity beats platform-nativeness here — the
marker is a generated file inside a gitignored bundle, and two harnesses
on two machines should produce the same bytes.

The line that is read by hand is ``# Source:``. ``skills/pb-review``
copies it into a plan header's ``source skill`` field and
``docs/wiki-notes.md`` into ``observed-against``, and "n/d" is explicitly
forbidden there. This port changes its shape — a tag is strictly better
than a sha for ``observed-against`` — and adds ``# Version:`` as the
machine-readable single token. Both documents were rewritten in the same
commit, and
``tests/test_install_marker.py::test_ledger57_the_two_documented_readers_agree_with_the_marker``
keeps them honest: they are instructions to an agent reading by eye, so a
document naming a line this file no longer writes makes that agent report
the kit as broken.

The dirty-source line here is past tense; the one on stdout is present
tense (``report.DIRTY_SOURCE_WARNING``). They are deliberately different
and must not be unified: one describes the repository while the installer
is looking at it, the other describes a fact about an install that already
happened.
"""

from __future__ import annotations

import os
import re
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import DIST_NAME, REPO_URL, VCS_URL
from .harness import MARKER_FILENAME, Adapter
from .provenance import SourceIdentity

__all__ = [
    "CONTENTS_HEADER",
    "CONTENTS_INDENT",
    "DEFAULT_HARNESS_ID",
    "DIRTY_MARKER_WARNING",
    "FOOTER_LINES",
    "HEADER_LINES",
    "MARKER_FILENAME",
    "SNAPSHOT_LINES",
    "MarkerFields",
    "find",
    "format_timestamp",
    "install_flags",
    "parse",
    "render",
    "settings_replaced_warning",
    "source_value",
    "update_recipe",
    "write",
]

#: Values start at column 14 (1-indexed), so every key is padded to 13.
KEY_WIDTH = 13

HEADER_LINES: tuple[str, ...] = (
    "# Skills, commands, knowledge base and MCP config installed from pb-ai-code.",
    "# Generated - do not edit. Change things in pb-ai-code and re-run.",
    "#",
)

#: Past tense, and it sits after ``# Appeon:`` (ledger 5).
DIRTY_MARKER_WARNING = "# WARN: source repo had uncommitted changes at install time."

CONTENTS_HEADER = "# Contents:"

#: ``#`` plus three spaces, then the destination relative to the target,
#: backslash-separated on Windows, in plan order. Trees are listed as
#: directories; ``.mcp.json``, the marker itself and the per-file contents
#: of a tree are not listed.
CONTENTS_INDENT = "#   "

SNAPSHOT_LINES: tuple[str, ...] = (
    "#",
    "# The knowledge base above is a SNAPSHOT. The skills grow it as they meet",
    "# undocumented cases - do that in pb-ai-code, not here, or the next",
    "# install discards it.",
)

FOOTER_LINES: tuple[str, ...] = (
    "#",
    f"# Source of truth: {REPO_URL}",
)

#: Printed under the recipe when the running build is not a release, so
#: nobody pins a project to a commit that only existed on one machine.
DEV_BUILD_NOTE = "# (installed from a development build; pin a tag for a real install)"

FOOTER_TAIL = "# Make changes in pb-ai-code, not here."

#: The harness ``--harness`` defaults to, and so the one the recipe names
#: by saying nothing. Duplicated from ``__main__._DEFAULT_HARNESS`` on
#: purpose: this module decides what the recipe *prints*, and the
#: claude-code line has to stay byte-identical to the spec's text.
DEFAULT_HARNESS_ID = "claude-code"

#: The one harness whose layout comes from the two directory flags rather
#: than from a fixed table.
_CONFIGURABLE_HARNESS_ID = "generic"


def key_line(key: str, value: str) -> str:
    """``# Installed: 2026-08-12 17:02:56 +02:00`` — value at column 14."""
    return f"# {key + ':':<{KEY_WIDTH - 2}}{value}"


def settings_replaced_warning(rel: str) -> str:
    """Marker twin of ``report.settings_replaced_warning`` (ledger 22).

    The stdout line is a report of what just happened; this one is the
    record a reader finds months later next to a settings file they do not
    recognise.
    """
    return f"# WARN: an existing {rel} was replaced; its content differed."


def format_timestamp(when: datetime) -> str:
    """``2026-08-12 17:02:56 +02:00`` — local time, colon in the offset.

    ``%z`` gives ``+0200``; the script's ``zzz`` gave ``+02:00``, and the
    line is read by people. Splice the colon rather than reformat.
    """
    stamped = when.strftime("%Y-%m-%d %H:%M:%S %z")
    if len(stamped) >= 5 and stamped[-5] in "+-":
        stamped = f"{stamped[:-2]}:{stamped[-2:]}"
    return stamped


def source_value(identity: SourceIdentity) -> str:
    """The ``# Source:`` value, preserving the ``pb-ai-code @ `` prefix.

    Three shapes, one per provenance branch::

        pb-ai-code @ 0.5.0 (git+https://github.com/restoresrl/pb-ai-code, c26d4b6)
        pb-ai-code @ 0.5.1.dev1+gc26d4b6 (local checkout C:\\src\\pb-ai-code, c26d4b6 on main)
        pb-ai-code @ 0.5.0
    """
    detail: list[str] = []
    if identity.origin:
        detail.append(identity.origin)
    if identity.sha:
        detail.append(f"{identity.sha} on {identity.branch}" if identity.branch else identity.sha)
    base = f"{DIST_NAME} @ {identity.version}"
    if not detail:
        return base
    return f"{base} ({', '.join(detail)})"


def _flag_value(value: str) -> str:
    """Quote a flag value that would not survive being pasted into a shell.

    ``--skills-dir`` is whatever the caller typed, and a directory with a
    space in it is a Windows habit. The recipe is meant to be copied and
    run, so an unquoted ``.agent/my skills`` would be a recipe that
    installs into ``.agent/my``.
    """
    return f'"{value}"' if any(char.isspace() for char in value) else value


def install_flags(adapter: Adapter) -> tuple[str, ...]:
    """The flags that reproduce *this* layout, for the update recipe.

    The script's recipe named ``-Harness $Harness`` (ps1:583); a recipe
    with no flags at all tells the reader of a ``generic`` bundle to run
    the command that installs the *claude-code* layout beside it —
    silently, where the PowerShell recipe at least failed loudly, since
    ``-Harness generic`` without ``-SkillsDir`` throws.

    Only flags :func:`pb_ai_code.harness.resolve_adapter` accepts for this
    harness: ``claude-code`` *refuses* the two directory flags, so naming
    them would print a recipe that exits 2, and it is the default harness,
    so it names nothing at all and its line stays byte-identical.
    """
    if adapter.id == DEFAULT_HARNESS_ID:
        return ()
    flags = ["--harness", adapter.id]
    if adapter.id == _CONFIGURABLE_HARNESS_ID and adapter.roots:
        # One root today; a future dual-bundle adapter would not take its
        # layout from the flags at all, which is why this is keyed on the
        # harness id rather than on "does it have roots".
        root = adapter.roots[0]
        flags += ["--skills-dir", _flag_value(root.skills_rel)]
        if root.commands_rel is not None:
            flags += ["--commands-dir", _flag_value(root.commands_rel)]
    return tuple(flags)


def update_recipe(ref: str | None, flags: tuple[str, ...] = ()) -> tuple[str, ...]:
    """The ``To update:`` block, which no longer names a checkout.

    ``scripts\\install-skills.ps1 -Target <this-project>`` required a clone
    on the machine; this runs from inside the project. A release pins the
    tag it came from; a development build prints the command with no ref
    and says why, because there is no tag to name.

    ``flags`` comes from :func:`install_flags` and is what keeps the recipe
    an *update* rather than a second, different install.
    """
    url = VCS_URL if ref is None else f"{VCS_URL}@{ref}"
    command = " ".join(("uvx", "--from", url, "pb-ai-code", "install", *flags))
    lines = [
        "# To update: from inside this project, run",
        f"#   {command}",
    ]
    if ref is None:
        lines.append(DEV_BUILD_NOTE)
    lines.append(FOOTER_TAIL)
    return tuple(lines)


@dataclass(frozen=True)
class MarkerFields:
    """A parsed marker. Every value is exactly as it was written."""

    installed_at: str | None
    version: str | None
    source: str | None
    sha: str | None
    branch: str | None
    harness: str | None
    mcp: str | None
    appeon: str | None
    contents: tuple[str, ...]
    dirty: bool
    raw: str


def render(
    *,
    installed_at: str,
    identity: SourceIdentity,
    adapter: Adapter,
    mcp_outcome: str,
    appeon_note: str,
    contents: tuple[str, ...],
    settings_replaced: str | None = None,
) -> str:
    """Assemble the marker, ``\\n``-joined; :func:`write` supplies the CRLF.

    Order: header, ``# Installed:``, ``# Version:``, ``# Source:``,
    ``# Harness:``, ``# MCP:``, ``# Appeon:``, then the two optional WARN
    lines, then ``#``, ``# Contents:`` and one indented destination per
    plan row, then the snapshot paragraph and the footer.
    """
    lines: list[str] = [
        *HEADER_LINES,
        key_line("Installed", installed_at),
        key_line("Version", identity.version),
        key_line("Source", source_value(identity)),
        key_line("Harness", adapter.id),
        key_line("MCP", mcp_outcome),
        key_line("Appeon", appeon_note),
    ]
    # The dirty line is the first of the two optional WARNs: ledger 5 puts
    # it immediately after the Appeon line, and the settings one is new.
    if identity.dirty:
        lines.append(DIRTY_MARKER_WARNING)
    if settings_replaced is not None:
        lines.append(settings_replaced_warning(settings_replaced))
    # A bare comment line separates the keys from the Contents block.
    lines.append("#")
    lines.append(CONTENTS_HEADER)
    # Plan order, and only the plan destinations: the MCP config, the
    # marker itself and the per-file contents of a tree are not plan rows
    # and are not listed here.
    lines.extend(f"{CONTENTS_INDENT}{entry}" for entry in contents)
    lines.extend(SNAPSHOT_LINES)
    lines.extend(FOOTER_LINES)
    lines.extend(update_recipe(identity.update_ref, install_flags(adapter)))
    return "\n".join(lines)


def _to_crlf_bytes(text: str) -> bytes:
    """UTF-8 without a BOM, CRLF everywhere, exactly one trailing CRLF."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and not lines[-1]:
        lines.pop()
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def _clear_readonly(path: Path) -> None:
    """Drop the read-only bit, when the file is there and carries one.

    ``os.replace`` onto a read-only destination raises ``PermissionError``
    on Windows, so a bundle somebody committed read-only could never be
    re-installed over. This is the marker's own copy of the rule
    :func:`pb_ai_code.apply.clear_readonly` applies to the plan rows; the
    marker write deliberately needs nothing from the apply step.
    """
    try:
        mode = path.stat().st_mode
    except OSError:
        return
    if not mode & stat.S_IWRITE:
        try:
            path.chmod(mode | stat.S_IWRITE)
        except OSError:
            return


def write(path: Path, text: str) -> None:
    """Write atomically: temp file beside ``path``, then ``os.replace``.

    UTF-8 without a BOM, CRLF everywhere, exactly one trailing CRLF.
    """
    data = _to_crlf_bytes(text)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f"{path.name}.", suffix=".tmp"
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        _clear_readonly(path)
        os.replace(temp_path, path)
    except BaseException:
        # The point of the temp file is that a failure leaves the previous
        # marker rather than a truncated one, so take the debris with us.
        temp_path.unlink(missing_ok=True)
        raise


#: The six keys :func:`parse` reads back. A fixed alternation rather than
#: "whatever precedes a colon", because ``# Source of truth:`` and
#: ``# To update:`` are prose, not values.
_KEY_RE = re.compile(r"^#[ \t]+(Installed|Version|Source|Harness|MCP|Appeon):[ \t]*(.*)$")

#: Enough of :data:`DIRTY_MARKER_WARNING` to recognise it, and not enough
#: to collide with the settings-replaced WARN.
_DIRTY_SIGNATURE = "source repo had uncommitted changes"

#: A short sha, optionally followed by the branch it was on.
_SHA_RE = re.compile(r"^(?P<sha>[0-9a-f]{7,40})(?: on (?P<branch>\S.*))?$")


def _split_source(value: str | None) -> tuple[str | None, str | None]:
    """Pull the sha and the branch out of a ``# Source:`` value.

    Three shapes are read, because every consumer that exists today has a
    marker written by the PowerShell installer::

        pb-ai-code @ 913e186 (main)                            # the old one
        pb-ai-code @ 0.5.0 (git+https://..., c26d4b6)
        pb-ai-code @ 0.5.1.dev1+g... (local checkout C:\\src, c26d4b6 on main)

    Anything else answers ``(None, None)``. A marker that records only a
    version is well formed, and inventing a sha for it would be worse than
    saying nothing.
    """
    if not value:
        return None, None
    text = value.strip()
    prefix = f"{DIST_NAME} @ "
    if text.startswith(prefix):
        text = text[len(prefix) :]
    head, detail = text, ""
    if text.endswith(")") and "(" in text:
        opened = text.rindex("(")
        head = text[:opened].strip()
        detail = text[opened + 1 : -1].strip()
    if detail:
        parts = [part.strip() for part in detail.split(",")]
        match = _SHA_RE.match(parts[-1])
        if match is not None:
            return match.group("sha"), match.group("branch")
        # The old shape: the token in front of the parenthesis is the sha,
        # and the parenthesis holds the branch it was on.
        if len(parts) == 1 and _SHA_RE.fullmatch(head) is not None:
            return head, parts[0] or None
        return None, None
    if _SHA_RE.fullmatch(head) is not None:
        return head, None
    return None, None


def parse(text: str) -> MarkerFields:
    """Read a marker back. ``status`` needs no network and no git."""
    values: dict[str, str] = {}
    contents: list[str] = []
    dirty = False
    in_contents = False
    # A marker this CLI wrote carries no BOM; one written by Windows
    # PowerShell 5.1 does, and a reader that opened it as plain UTF-8
    # hands that character straight through.
    for line in text.lstrip("\ufeff").splitlines():
        stripped = line.rstrip()
        if in_contents:
            if stripped.startswith(CONTENTS_INDENT):
                entry = stripped[len(CONTENTS_INDENT) :].strip()
                if entry:
                    contents.append(entry)
                continue
            # The block ends at the first line that is not indented, which
            # is what keeps the update recipe - indented the same way - out
            # of the Contents list.
            in_contents = False
        if stripped == CONTENTS_HEADER:
            in_contents = True
            continue
        if _DIRTY_SIGNATURE in stripped:
            dirty = True
            continue
        match = _KEY_RE.match(stripped)
        if match is not None:
            values.setdefault(match.group(1), match.group(2).strip())
    source = values.get("Source")
    sha, branch = _split_source(source)
    return MarkerFields(
        installed_at=values.get("Installed"),
        # Absent from every marker the PowerShell installer wrote: `status`
        # reports what is there rather than guessing a version.
        version=values.get("Version"),
        source=source,
        sha=sha,
        branch=branch,
        harness=values.get("Harness"),
        mcp=values.get("MCP"),
        appeon=values.get("Appeon"),
        contents=tuple(contents),
        dirty=dirty,
        raw=text,
    )


def find(target: Path) -> Path | None:
    """Locate a marker under ``target``, at every known harness location.

    ``.claude/`` first, then the target root — which is where
    ``--skills-dir skills`` lands, having no parent to land in — then any
    ``*/_installed-from-pb-ai-code.txt`` one and two levels down, which
    covers ``--skills-dir a/b/skills``, whose marker lands at ``a/b/``,
    and the PowerShell installer's generic location *inside* the skills
    directory.
    """
    candidates: list[Path] = [
        target / ".claude" / MARKER_FILENAME,
        target / MARKER_FILENAME,
    ]
    for depth in ("*", "*/*"):
        candidates.extend(sorted(target.glob(f"{depth}/{MARKER_FILENAME}")))
    seen: set[Path] = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        if path.is_file():
            return path
    return None
