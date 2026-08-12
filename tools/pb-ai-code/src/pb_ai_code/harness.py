"""Harness adapters: where a given assistant reads skills, commands and MCP.

The PowerShell script was a ``switch ($Harness)`` setting five scalars.
That shape cannot express Codex (TOML ``[mcp_servers.<name>]``, no
project-scoped commands directory, a trust gate), OpenCode (top-level key
``mcp``, ``command`` fused into a single array, ``environment`` where
everyone else writes ``env``), Continue (YAML with a ``name`` field inside
the entry, one file per server), Aider (no skills and no MCP at all) or a
dual ``.claude`` + ``.agents`` install. So the shape here is *a list of
roots plus an MCP emitter* — and only what exists today is implemented:
``claude-code`` and ``generic``. The table of verified paths for the
others lives in ``harness/README.md``.

Three places in this repository still say the MCP block is identical for
every client. It is not, and the four dialects above are why
:class:`McpTarget` carries a ``dialect`` and a ``write_mode`` rather than
a path alone. A harness with no MCP configuration at all sets ``mcp=None``
and names the shortfall in ``gaps``; a harness whose file is written but
may be inert (a trust gate, a user-scoped path) says so in
``McpTarget.note``.

What this shape still does *not* express, for whoever needs it first: a
commands directory whose files want a different suffix. Continue reads
``.continue/prompts/*.prompt`` while the kit's canonical commands are
``.md``, and ``plan.py`` installs each file under its own name.

For ``claude-code`` every derived path is byte-identical to what the
script produced: ``parent(".claude/skills")`` is ``.claude``, so both
``docs_rel`` and ``marker_rel`` reproduce ps1:296 exactly.

Never written by any adapter: ``AGENTS.md``, ``CLAUDE.md``,
``.cursor/rules/``, ``.windsurf/rules/``, ``.continue/rules/``. Those are
the project's own committed prose, and the kit's rule is that a consumer
commits nothing agentic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from . import UsageError
from . import report as report_mod

#: Deliberately not ``docs/``: that name belongs to the host project, and a
#: bundle that took it would collide with it (ledger 20).
DOCS_FOLDER_NAME = "pb-ai-code-docs"

#: One marker per skills root, in the root's *parent* — the bundle
#: directory, which is what ``skills/pb-review/SKILL.md`` and
#: ``docs/wiki-notes.md`` already promise their readers (ledger 54).
MARKER_FILENAME = "_installed-from-pb-ai-code.txt"

#: The harness ids ``--harness`` accepts.
HARNESS_IDS: tuple[str, ...] = ("claude-code", "generic")

#: The last segment every skills directory must have. 13 links in the
#: payload spell the segment out — ``../skills/<name>/SKILL.md`` in the two
#: commands and in ``wiki-notes.md``, ``../../skills/<name>/SKILL.md`` in
#: the two doc trees — and ledger 28 says nothing but ``../../docs/`` is
#: rewritten, so the name is an invariant rather than a preference.
SKILLS_SEGMENT = "skills"

_DRIVE_RE = re.compile(r"^[A-Za-z]:")


# --- Messages -----------------------------------------------------------------
# These two belong beside their siblings in ``report.py``; they are here only
# because that module was being edited elsewhere when they were written. Moving
# them is a cut-and-paste: same names, same shape as ``report.err_*``.


def err_dir_component_has_whitespace(flag: str, value: str) -> str:
    """A path component padded with whitespace is refused, never trimmed.

    Windows resolves ``sk `` and ``sk`` to *different* directories
    depending on which API creates them, so the script produced both: an
    empty ``sk\\`` from ``New-Item`` and the whole bundle in ``sk \\``,
    exit 0, no warning. Trimming silently would be the same trap in the
    other direction — the caller asked for a directory nothing else on the
    machine can type.
    """
    return f"{flag} must not have leading or trailing whitespace in a path component: {value!r}"


def err_skills_dir_last_segment(skills_rel: str) -> str:
    """The bundle's cross-links spell ``skills`` out; the flag must too."""
    last = skills_rel.split("/")[-1]
    return (
        f"--skills-dir must end in a segment named '{SKILLS_SEGMENT}' - the installed "
        "commands and knowledge base link to ../skills/<name>/SKILL.md and nothing "
        f"rewrites those: {skills_rel} ends in {last!r}"
    )


# --- Directory flags ----------------------------------------------------------


def absent_if_blank(value: str | None) -> str | None:
    """A whitespace-only directory flag means the flag was not given.

    This is the one place the kit decides what blank means, and it says
    what ``[string]::IsNullOrWhiteSpace`` said in the two places the script
    asked: ps1:298 turns a blank ``-SkillsDir`` into the "generic requires
    -SkillsDir" refusal, and ps1:348 turns a blank ``-CommandsDir`` into
    "no commands directory for this harness" — a notice, and an install
    that completes (ledger 12).

    The other half of the decision is :func:`validate_relative_dir`, which
    refuses a component that is *partly* whitespace. Between them there is
    no value that reaches the copy step as a directory name the caller did
    not mean: ledger 14 wants everything validated before the first write,
    and until now ``--commands-dir "  "`` copied seven skill trees and then
    died in ``shutil.copy2`` with a traceback and a half-installed target.
    """
    if value is None or not value.strip():
        return None
    return value


def normalise_rel(value: str) -> str:
    """``a\\b/c`` -> ``a/b/c``, with ``.`` dropped and ``..`` collapsed.

    Both separators are accepted on every platform: the script took
    whichever the caller typed, and a PowerBuilder developer types
    backslashes.

    ``..`` is collapsed because the result is what every derived path is
    computed from: ``a/../b`` left intact would put the docs at
    ``a/../pb-ai-code-docs``, the marker one directory above the bundle it
    describes, and would name ``a`` — a directory nothing was installed
    into — as the subject of the gitignore hint. A leading ``..`` that
    cannot be collapsed is *kept*, so this never quietly turns an escaping
    value into an innocent-looking one; :func:`validate_relative_dir`
    refuses those before they reach here.
    """
    parts: list[str] = []
    for part in value.replace("\\", "/").split("/"):
        if part in ("", "."):
            continue
        if part == ".." and parts and parts[-1] != "..":
            parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def validate_relative_dir(flag: str, value: str) -> str:
    """Refuse anything that is not strictly below the target. Returns the rel.

    The PowerShell help promised absolute paths; ``Join-Path`` concatenated
    them into ``C:\\tgt\\D:\\abs\\skills`` and nobody noticed because
    nothing downstream looked. Python's ``Path`` join would silently
    *implement* the promise and install outside the target instead, which
    is the worse of the two failures. Neither the docs nor the code ever
    described an intended behaviour, so this refuses: absolute paths,
    drive-qualified paths and any value that escapes upward exit 2.

    Whitespace-padded components exit 2 too, and that is the second half of
    the decision :func:`absent_if_blank` starts. A value that is *entirely*
    blank has already become "flag not given" by the time it gets here; a
    value with a blank component (``a/ /b``) or a padded one (``sk ``) has
    no such reading, and Windows answers it by creating two directories and
    filling the one nothing else can name.
    """
    raw = value.replace("\\", "/")
    if raw.startswith("/") or _DRIVE_RE.match(value) or value.startswith("\\\\"):
        raise UsageError(report_mod.err_dir_must_be_target_relative(flag, value))
    depth = 0
    for part in raw.split("/"):
        if part in ("", "."):
            continue
        if part != part.strip():
            raise UsageError(err_dir_component_has_whitespace(flag, value))
        if part == "..":
            depth -= 1
            if depth < 0:
                raise UsageError(report_mod.err_dir_escapes_target(flag, value))
            continue
        depth += 1
    rel = normalise_rel(value)
    if not rel or depth <= 0:
        raise UsageError(report_mod.err_dir_must_name_a_directory(flag, value))
    return rel


@dataclass(frozen=True)
class SkillRoot:
    """One installed bundle: a skills directory and, optionally, commands.

    ``skills_rel`` and ``commands_rel`` are target-relative and always
    ``/``-separated; join them to the target with :meth:`join`, which
    yields native separators for the report and the marker.
    """

    skills_rel: str
    commands_rel: str | None = None

    @property
    def _parent(self) -> str:
        """``.claude/skills`` -> ``.claude``; ``skills`` -> ``""``.

        Not ``str(...).strip(".")``: that would eat the leading dot of
        every dot-directory there is, which is all of them.
        """
        parent = str(PurePosixPath(self.skills_rel).parent)
        return "" if parent == "." else parent

    @property
    def docs_rel(self) -> str:
        """``parent(skills_rel)/pb-ai-code-docs``, bare when there is no parent.

        A skill at ``<skills>/<name>/SKILL.md`` reaches it as
        ``../../pb-ai-code-docs/``, which is exactly what the link rewrite
        writes.
        """
        parent = self._parent
        return f"{parent}/{DOCS_FOLDER_NAME}" if parent else DOCS_FOLDER_NAME

    @property
    def marker_rel(self) -> str:
        """``parent(skills_rel)/_installed-from-pb-ai-code.txt``.

        Never *inside* the skills directory: a stray ``.txt`` sitting where
        a skill loader enumerates skills is a hazard, and both documents
        that tell a reader where to look already say the bundle root.
        """
        parent = self._parent
        return f"{parent}/{MARKER_FILENAME}" if parent else MARKER_FILENAME

    @property
    def bundle_root(self) -> str:
        """First path segment — the subject of the gitignore hint."""
        return self.skills_rel.split("/")[0]

    def join(self, target: Path, rel: str) -> Path:
        """Target-relative rel -> a native path under ``target``."""
        return target.joinpath(*rel.split("/"))


@dataclass(frozen=True)
class McpTarget:
    """Where (and whether) this harness's MCP configuration is written.

    ``rel_path`` of ``None`` means there is no known on-disk location and
    the block is printed instead. ``dialect`` is one of ``mcp_json``,
    ``codex_toml``, ``opencode_json``, ``continue_yaml``; only ``mcp_json``
    is implemented. ``scope`` is ``project`` or ``user``; ``write_mode`` is
    ``merge``, ``own_file`` or ``print_only``. ``note`` is printed when the
    file is written but may be inert (a trust gate, a user-scoped file).
    """

    rel_path: str | None
    dialect: str
    scope: str
    write_mode: str
    note: str | None = None


@dataclass(frozen=True)
class ExtraFile:
    """A harness-specific file copied verbatim from the kit."""

    src_rel: str
    dst_rel: str
    mode: str = "overwrite"


@dataclass(frozen=True)
class Adapter:
    """Everything an install needs to know about one assistant."""

    id: str
    roots: tuple[SkillRoot, ...]
    mcp: McpTarget | None
    extra_files: tuple[ExtraFile, ...] = ()
    restart_hint: str | None = None
    #: Printed as ``Note: …`` — what this harness cannot do.
    gaps: tuple[str, ...] = ()


CLAUDE_CODE = Adapter(
    id="claude-code",
    roots=(SkillRoot(".claude/skills", ".claude/commands"),),
    mcp=McpTarget(".mcp.json", "mcp_json", "project", "merge", note=None),
    extra_files=(
        # A full, unmerged overwrite, as it has always been. The file
        # pre-approves 18 `mcp__pb-orca__*` / `mcp__pb-appeon-index__*`
        # tools and documents three deliberate omissions in `_comment*`
        # keys; it is copied as opaque bytes and never re-serialised.
        # `.claude/settings.local.json` is never touched.
        ExtraFile("harness/claude-code/settings.json", ".claude/settings.json", "overwrite"),
    ),
    restart_hint=report_mod.RESTART_HINT,
    gaps=(),
)


def build_generic(skills_dir: str, commands_dir: str | None) -> Adapter:
    """The ``generic`` harness, assembled from the two directory flags.

    Two refusals guard the same thing: the 13 links in the payload that
    spell ``skills`` out. Eleven of them are in the knowledge base and
    depend on ``--skills-dir`` alone (``../../skills/<name>/SKILL.md`` from
    a doc tree, ``../skills/<name>/SKILL.md`` from ``wiki-notes.md``), so
    the sibling rule alone never covered them: ``--skills-dir .agent/kb
    --commands-dir .agent/commands`` passed it and installed a bundle with
    13 dead links.
    """
    skills_rel = validate_relative_dir("--skills-dir", skills_dir)
    # Checked before the sibling rule: a wrongly named skills directory
    # breaks the knowledge base whatever the commands directory says, so
    # it is the more useful of the two messages to get first.
    if skills_rel.split("/")[-1] != SKILLS_SEGMENT:
        raise UsageError(err_skills_dir_last_segment(skills_rel))
    commands_rel: str | None = None
    if commands_dir is not None:
        commands_rel = validate_relative_dir("--commands-dir", commands_dir)
        # The installed commands link to ../skills/<name>/SKILL.md, which
        # resolves only because commands and skills are siblings. The
        # script neither validated nor rewrote that, so a non-sibling pair
        # produced two dead links in silence.
        if PurePosixPath(commands_rel).parent != PurePosixPath(skills_rel).parent:
            raise UsageError(report_mod.err_commands_dir_not_sibling(commands_rel, skills_rel))
    return Adapter(
        id="generic",
        roots=(SkillRoot(skills_rel, commands_rel),),
        mcp=McpTarget(None, "mcp_json", "project", "print_only", note=None),
        extra_files=(),
        restart_hint=None,
        gaps=(),
    )


def resolve_adapter(
    harness_id: str,
    *,
    skills_dir: str | None = None,
    commands_dir: str | None = None,
) -> Adapter:
    """Pick the adapter for ``--harness``, validating the directory flags.

    ``claude-code`` has a fixed layout, so the two directory flags are
    refused rather than silently ignored, which is what the script did.

    Both flags pass through :func:`absent_if_blank` first, once, before any
    harness looks at them: a blank value is the flag not given, everywhere,
    which is what the script's two ``IsNullOrWhiteSpace`` tests said.
    """
    skills_dir = absent_if_blank(skills_dir)
    commands_dir = absent_if_blank(commands_dir)
    if harness_id == "claude-code":
        if skills_dir is not None:
            raise UsageError(report_mod.err_dir_not_accepted("--skills-dir", harness_id))
        if commands_dir is not None:
            raise UsageError(report_mod.err_dir_not_accepted("--commands-dir", harness_id))
        return CLAUDE_CODE
    if harness_id == "generic":
        if skills_dir is None:
            raise UsageError(report_mod.err_generic_requires_skills_dir())
        return build_generic(skills_dir, commands_dir)
    raise UsageError(f"unknown harness: {harness_id} (choose from {', '.join(HARNESS_IDS)})")
