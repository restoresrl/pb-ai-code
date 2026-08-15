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
from dataclasses import dataclass
from pathlib import Path


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


def sources_protected(target: Path) -> bool | None:
    """Is there a ``.gitattributes`` rule keeping git off the ``.sr*`` sources?

    ``None`` when nothing true can be said: no git, or not a repository.

    Asked through ``git check-attr`` rather than by reading
    ``.gitattributes``, because git's own rule engine is the thing that
    decides — precedence between files, negation, the last matching pattern
    winning. A reimplementation would answer differently on exactly the
    repositories that need the answer most.

    The probe path does not have to exist: ``check-attr`` applies the
    patterns to a name, not to a file. So this can be asked before the
    install writes anything, and on a workspace whose projection lives
    somewhere this function never looks.

    ``unset`` is the protected answer — it is what ``*.sr* -text`` produces.
    ``unspecified`` means no rule matched, which is the hazard: git holds LF,
    hands back CRLF, and a change that lands in both the ``.pbl`` and its
    projection leaves ``git status`` clean.
    """
    probe = "ws_objects/probe.srw"
    answer = _git(target, "check-attr", "text", "--", probe)
    if answer is None or answer[0] != 0:
        return None
    # `<path>: text: <value>` — take the last field, the value.
    line = answer[1].strip()
    if not line:
        return None
    return line.rsplit(":", 1)[-1].strip() == "unset"
