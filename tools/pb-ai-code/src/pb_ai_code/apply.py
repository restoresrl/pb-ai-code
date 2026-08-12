"""Copy semantics, and the one rewrite applied to what was copied.

Three rules here exist because something went wrong once:

**Trees are deleted before they are copied.** ``Remove-Item -Recurse``
then ``Copy-Item -Recurse`` is what the script did, for two verified
reasons: PowerShell's recursive copy into an *existing* directory nests
(``dst/tree/tree/…``), and a fresh slate is what makes an upstream
deletion propagate to an already-installed bundle. Do **not** reach for
``shutil.copytree(dirs_exist_ok=True)``: it dodges the nesting bug and
silently reintroduces the staleness bug.

**Read-only destinations are cleared, not refused.** ``Remove-Item
-Force`` deletes read-only files and ``Copy-Item -Force`` overwrites
them; ``shutil.rmtree`` and ``shutil.copyfile`` raise ``PermissionError``.
A target checked out read-only, or a bundle somebody committed, would
break the port where the script worked.

**Copies are byte-exact.** No newline translation, no re-encoding, no BOM
introduced. The tree legitimately mixes line endings — ``wiki-notes.md``
is CRLF in the working tree, the skills are LF — and the bundle
reproduces that mix. So: ``shutil.copy2`` only, and the rewrite reads and
writes **bytes**. Python's text mode would CRLF-ify exactly the five
rewritten ``SKILL.md`` files on Windows and leave the other two alone.

Deletion is scoped to the destinations about to be written, and nothing
else: a stale skill, a stale doc tree, a user's own skill, a loose user
file at the docs root and a user command all survive a re-install.
"""

from __future__ import annotations

import contextlib
import shutil
import stat
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from .plan import Plan, PlanRow

#: What the link rewrite looks for, and what it writes in its place. The
#: match is ordinal, case-sensitive, literal (not a regex, not link-aware
#: — it rewrites inside fenced code blocks too) and applies to every
#: occurrence.
REWRITE_FROM = "../../docs/"


def rewrite_to(docs_folder_name: str) -> str:
    return f"../../{docs_folder_name}/"


@dataclass(frozen=True)
class ApplyOutcome:
    """What one row did.

    ``replaced_differing_file`` is true only for a single-file row that
    overwrote an existing destination whose bytes differed. It is how the
    settings overwrite stops being silent.
    """

    row: PlanRow
    replaced_differing_file: bool


def clear_readonly(path: Path) -> None:
    """Drop the read-only bit so the next write can land.

    Best effort on purpose: when the bit cannot be cleared, the write that
    follows is what raises, and its message names the operation that
    actually failed rather than this one.
    """
    with contextlib.suppress(OSError):
        path.chmod(path.stat().st_mode | stat.S_IWRITE)


def _retry_after_clearing_readonly(func: Callable[..., object], path: str, _exc: object) -> None:
    """``rmtree``'s error hook: clear the read-only bit, run that call again.

    ``_exc`` is the exception in 3.12's ``onexc`` and an ``exc_info`` tuple
    in the older ``onerror``; neither is looked at, so one handler serves
    both. A retry that fails again raises out of ``rmtree``, which is what
    should happen — a destination that cannot be cleared is not a
    destination we can install into.
    """
    clear_readonly(Path(path))
    func(path)


def remove_tree(path: Path) -> None:
    """``rmtree`` that clears read-only files and retries, then re-raises."""
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_retry_after_clearing_readonly)
    else:  # pragma: no cover - 3.12 renamed the hook; the handler is the same
        shutil.rmtree(path, onerror=_retry_after_clearing_readonly)


def copy_tree(src: Path, dst: Path) -> None:
    """Delete ``dst`` outright, then copy ``src`` onto it.

    Not ``copytree(dirs_exist_ok=True)``. That looks like the same thing
    and is not: it dodges the nesting bug this delete was written for, and
    it silently reintroduces the staleness bug the delete also fixes — a
    file dropped upstream would live on in every installed bundle forever.
    """
    if dst.is_dir():
        remove_tree(dst)
    elif dst.exists():
        # A file sitting where a tree goes. `Remove-Item -Force` took it;
        # so does this.
        clear_readonly(dst)
        dst.unlink()
    shutil.copytree(src, dst)


def copy_file(src: Path, dst: Path) -> None:
    """Byte-exact overwrite, clearing a read-only destination first.

    No pre-delete: an unrelated file living in the same directory is the
    user's, and it survives.
    """
    if dst.exists():
        clear_readonly(dst)
    shutil.copy2(src, dst)


def apply_row(row: PlanRow) -> ApplyOutcome:
    """Create the parent, then copy according to :attr:`PlanRow.is_tree`."""
    row.dst.parent.mkdir(parents=True, exist_ok=True)
    if row.is_tree:
        copy_tree(row.src, row.dst)
        return ApplyOutcome(row=row, replaced_differing_file=False)
    # Read before the copy or the answer is always "identical".
    replaced = row.dst.is_file() and row.dst.read_bytes() != row.src.read_bytes()
    copy_file(row.src, row.dst)
    return ApplyOutcome(row=row, replaced_differing_file=replaced)


def apply_plan(plan: Plan) -> list[ApplyOutcome]:
    """Apply every row in plan order. The caller prints as it goes."""
    return [apply_row(row) for row in plan.rows]


def rewrite_links(skills_target: Path, skill_names: Sequence[str], docs_folder_name: str) -> int:
    """Repoint the knowledge-base links, returning how many files changed.

    Scope is ``<skills>/<name>/SKILL.md`` and nothing else: not nested
    skill files, not the commands, not the doc trees, not
    ``wiki-notes.md``. Write back only when the bytes changed.

    In the repository a skill reaches the docs as ``../../docs/``, because
    two levels up from ``skills/<name>/`` is the repository root.
    Installed, two levels up is the bundle directory instead. That is true
    of an install into the checkout itself exactly as much as of a
    consumer install — the installed tree is one level deeper either way —
    so this is unconditional. Two stale comments in the PowerShell script
    claim otherwise; the commit that wrote them recanted them.
    """
    old = REWRITE_FROM.encode()
    new = rewrite_to(docs_folder_name).encode()
    rewritten = 0
    for name in skill_names:
        path = skills_target / name / "SKILL.md"
        if not path.is_file():
            continue
        before = path.read_bytes()
        after = before.replace(old, new)
        if after == before:
            continue
        # `copy2` brought the source's mode bits along with the bytes.
        clear_readonly(path)
        path.write_bytes(after)
        rewritten += 1
    return rewritten
