"""Is the bundle we just wrote ignored by the target's git?

The bundle is generated, not work product: a PowerBuilder project should
commit nothing agentic, and the way to update it is to re-run the
installer. So when the target's git does not already ignore what was
written, say so — easy to miss on a harness whose directory nobody has
added a rule for yet.

Two details are load-bearing:

**No trailing slash on the query.** ``git check-ignore -q -- '.agent/'``
can match a **blank line** in a ``.gitignore`` and report the path
ignored when it is not; verified against a real file, where it claimed
line 45 while line 45 was empty and ``git status`` disagreed. CRLF
``.gitignore`` files are the norm on the Windows PB repositories this kit
targets, and the hint silently never fired because of it. Without the
slash git answers correctly — which is only safe *after* the copy,
because the directory now exists.

**A missing git is silent here.** The whole block is best-effort: the
install has already succeeded, and a machine without git on PATH should
not be told about its ``.gitignore``.

``git rev-parse --is-inside-work-tree`` answers true for a plain
directory nested inside an enclosing repository, so the advice would be
about the *parent's* ``.gitignore`` while the text said "in this project".
Comparing ``--show-toplevel`` against the target is what makes the note
name the repository it is actually talking about.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


def _same_path(left: Path, right: Path) -> bool:
    """Case-insensitively on Windows, exactly everywhere else."""
    return os.path.normcase(str(left)) == os.path.normcase(str(right))


@dataclass(frozen=True)
class IgnoreStatus:
    """What the target's git says about the bundle root.

    ``repo_root`` is the enclosing repository's top level; when it differs
    from the target, the note names it. ``ignored`` is meaningful only
    when ``is_repo`` is true. ``target`` is kept so
    :attr:`encloses_target` can answer without being handed it again.
    """

    is_repo: bool
    repo_root: Path | None
    ignored: bool
    target: Path | None = None
    git_available: bool = True

    @property
    def encloses_target(self) -> bool:
        """True when the repository root is above the target, not the target."""
        if self.repo_root is None or self.target is None:
            return False
        return not _same_path(self.repo_root, self.target)


def _git(target: Path, *args: str) -> tuple[int, str] | None:
    """``git -C <target> …``; ``None`` when there is no git to run."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(target), *args],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:  # git not on PATH
        return None
    return proc.returncode, proc.stdout


def check(target: Path, bundle_root: str) -> IgnoreStatus:
    """Run ``git -C <target>`` rather than changing the process CWD.

    Returns ``IgnoreStatus(is_repo=False, repo_root=None, ignored=False)``
    for a non-repository target and for a machine with no git — both are
    reasons to print nothing, not to fail.
    """
    # Resolved on both sides before they are compared: git reports the
    # long form of a path the caller may hold in its 8.3 short form, and
    # two spellings of one directory would read as a nested repository.
    target = target.resolve()
    silent = IgnoreStatus(
        is_repo=False, repo_root=None, ignored=False, target=target, git_available=False
    )

    # `--show-toplevel` answers both questions at once: it fails outside a
    # work tree, and inside one it names the repository the advice is
    # really about, which is not always the target.
    toplevel = _git(target, "rev-parse", "--show-toplevel")
    if toplevel is None:
        # No git on PATH. Nothing true can be said about a .gitignore, so
        # nothing is said.
        return silent
    if toplevel[0] != 0:
        # Git works and this is not a repository. That is not the same as
        # not knowing, and the difference is worth a line: the bundle and
        # the MCP config are generated, one of them carries an absolute
        # path with a username in it, and `git init` here at any point in
        # the future would sweep both into a commit with nothing to stop
        # it. A file we wrote into the project could stop it, and is not
        # ours to write: a team that vendors the bundle deliberately has
        # the opposite convention.
        return IgnoreStatus(
            is_repo=False, repo_root=None, ignored=False, target=target, git_available=True
        )
    top = toplevel[1].strip()
    repo_root = Path(top).resolve() if top else None

    # No trailing slash. `git check-ignore -q -- '.agent/'` can match a
    # BLANK line in a CRLF .gitignore and report the path ignored when it
    # is not, which is how this hint silently stopped firing. Without the
    # slash git answers correctly - and it can only be asked after the
    # copy, because the answer relies on the directory existing.
    ignore = _git(target, "check-ignore", "-q", "--", bundle_root)
    # 0 is "ignored", 1 is "not ignored", 128 is a git error - and an error
    # is not a reason to claim the bundle is ignored.
    ignored = ignore is not None and ignore[0] == 0
    return IgnoreStatus(is_repo=True, repo_root=repo_root, ignored=ignored, target=target)


ProtectionStatus = Literal[
    "protected",
    "unprotected",
    "nondiffable",
    "mixed",
    "unknown",
    "no_projection",
    "no_git",
]


@dataclass(frozen=True)
class SourceProtection:
    """Effective Git treatment of the projection files that actually exist."""

    status: ProtectionStatus
    checked_files: int
    unprotected_files: tuple[str, ...] = ()
    nondiffable_files: tuple[str, ...] = ()


def _projection_dirs(target: Path) -> tuple[Path, ...]:
    """Projection directories at the two depths the installer surveys."""
    found = [
        path for path in (*target.glob("ws_objects"), *target.glob("*/ws_objects")) if path.is_dir()
    ]
    return tuple(sorted(found, key=lambda path: str(path).lower()))


def _source_files(projections: Sequence[Path]) -> tuple[Path, ...]:
    """Every existing PowerBuilder source under the discovered projections."""
    files = [path for projection in projections for path in projection.rglob("*.sr*")]
    return tuple(sorted((path for path in files if path.is_file()), key=lambda path: str(path)))


def _attribute_values(target: Path, files: Sequence[Path]) -> dict[str, dict[str, str]] | None:
    """Ask Git for ``text`` and ``diff`` on real files, in bounded chunks."""
    values: dict[str, dict[str, str]] = {}
    relative = [path.relative_to(target).as_posix() for path in files]
    for start in range(0, len(relative), 64):
        chunk = relative[start : start + 64]
        answer = _git(target, "check-attr", "-z", "text", "diff", "--", *chunk)
        if answer is None or answer[0] != 0:
            return None
        parts = answer[1].split("\0")
        if parts and parts[-1] == "":
            parts.pop()
        if len(parts) % 3 != 0:
            return None
        for index in range(0, len(parts), 3):
            path, attribute, value = parts[index : index + 3]
            values.setdefault(path, {})[attribute] = value
    return values


def _git_will_treat_as_binary(path: Path) -> bool:
    """Git's built-in diff treats UTF-16 and NUL-bearing OLE exports as binary."""
    try:
        data = path.read_bytes()
    except OSError:
        return True
    return data.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\x00" in data


def source_protection(target: Path, projections: Sequence[Path] | None = None) -> SourceProtection:
    """Classify byte protection and diffability on actual ``.sr*`` files.

    No project file is written. ``git check-attr`` decides effective rules,
    including nested ``.gitattributes`` files and later overrides. Checking
    real paths avoids the old synthetic ``ws_objects/probe.srw`` answer,
    which was wrong for scoped rules and projections below ``src/``.
    """
    if not check(target, ".").is_repo:
        return SourceProtection(status="no_git", checked_files=0)
    selected = tuple(projections) if projections is not None else _projection_dirs(target)
    if not selected:
        return SourceProtection(status="no_projection", checked_files=0)
    files = _source_files(selected)
    if not files:
        return SourceProtection(status="unknown", checked_files=0)
    attributes = _attribute_values(target, files)
    if attributes is None:
        return SourceProtection(status="unknown", checked_files=0)

    unprotected: list[str] = []
    nondiffable: list[str] = []
    for path in files:
        relative = path.relative_to(target).as_posix()
        effective = attributes.get(relative, {})
        if effective.get("text") != "unset":
            unprotected.append(relative)
            continue
        if effective.get("diff") == "unset" or _git_will_treat_as_binary(path):
            nondiffable.append(relative)

    if unprotected:
        status: ProtectionStatus = "unprotected" if len(unprotected) == len(files) else "mixed"
    elif nondiffable:
        status = "nondiffable"
    else:
        status = "protected"
    return SourceProtection(
        status=status,
        checked_files=len(files),
        unprotected_files=tuple(unprotected),
        nondiffable_files=tuple(nondiffable),
    )


def sources_protected(target: Path) -> bool | None:
    """Compatibility answer for callers that only care about byte translation."""
    result = source_protection(target)
    if result.status in {"no_git", "no_projection", "unknown"}:
        return None
    return result.status in {"protected", "nondiffable"}
