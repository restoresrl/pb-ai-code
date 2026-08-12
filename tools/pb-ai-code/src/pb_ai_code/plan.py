"""What will be copied where — built and validated before anything is written.

The whole plan is assembled, and every source existence-checked, *before*
the first copy. That is deliberate twice over: a missing input stops the
run with the target still untouched, and ``--dry-run`` catches the same
problem because it walks the same code.

The copy set is closed. ``docs/install.md``, ``docs/appeon-index/``
(including ``index.db``), ``plan-self-bootstrap.md``,
``harness/README.md``, the root ``README``/``AGENTS``/``CHANGELOG``/
``PLAN``/``LICENSE``, ``tools/``, ``tests/`` and ``scripts/`` never reach
a target. What *is* copied is enumerated at run time, not listed in code:
every immediate subdirectory of ``skills/`` as a whole tree, every
``commands/*.md`` flat, the two doc trees, the loose doc files.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import PbAiCodeError, UsageError
from . import report as report_mod
from .harness import Adapter, SkillRoot
from .kit import Kit

#: Documentation trees the skills link to, vendored so the bundle is
#: self-contained. Mandatory as a pair.
DOC_TREES: tuple[str, ...] = ("pb-antipatterns", "pb-source-format")

#: Loose documentation files, copied into the docs **root** rather than
#: into a tree. ``wiki-notes.md`` is the one a consumer needs most: it
#: explains how a discovery made *there* travels back here, and omitting
#: it produced exactly five dead links once.
DOC_FILES: tuple[str, ...] = ("wiki-notes.md",)

#: Plan operations, in the order they are emitted.
OPS: tuple[str, ...] = ("skill", "command", "docs", "docfile", "settings")


class SourceMissing(PbAiCodeError):
    """A payload input the plan needs is not there."""


@dataclass(frozen=True)
class PlanRow:
    """One copy. ``op`` decides the semantics.

    ``skill`` and ``docs`` are trees: the destination is removed first and
    then copied whole. Everything else is a plain single-file overwrite.
    """

    op: str
    src: Path
    dst: Path

    @property
    def is_tree(self) -> bool:
        return self.op in ("skill", "docs")


@dataclass(frozen=True)
class RootPaths:
    """The absolute destinations one :class:`SkillRoot` resolves to."""

    root: SkillRoot
    skills_target: Path
    commands_target: Path | None
    docs_target: Path
    marker_path: Path


@dataclass(frozen=True)
class Plan:
    """Everything the apply step and the marker need, decided up front."""

    target: Path
    adapter: Adapter
    rows: tuple[PlanRow, ...]
    roots: tuple[RootPaths, ...]
    #: Command files that will not be installed because a root has no
    #: commands directory. Zero when every root has one.
    skipped_command_count: int
    #: Skill directory names, in plan order; the rewrite walks them.
    skill_names: tuple[str, ...]

    def destinations(self) -> tuple[Path, ...]:
        """Row destinations in plan order — the marker's Contents list.

        ``.mcp.json`` and the marker itself are not rows and never appear
        here; neither do the per-file contents of a tree.
        """
        return tuple(row.dst for row in self.rows)


def validate_target(value: str) -> Path:
    """The target must be an existing directory. It is never created."""
    path = Path(value)
    if not path.is_dir():
        raise UsageError(report_mod.err_target_not_a_directory(value))
    return path.resolve()


def _require(src: Path, message: Callable[[str], str]) -> None:
    """Every source is existence-checked while the plan is being built.

    Not where it is copied: a missing input has to stop the run with the
    target still untouched, and ``--dry-run`` has to report it too.
    """
    if not src.exists():
        raise SourceMissing(message(str(src)))


def _skill_sources(kit: Kit) -> list[Path]:
    if not kit.skills_dir.is_dir():
        raise SourceMissing(report_mod.err_source_skill_missing(str(kit.skills_dir)))
    return kit.iter_skills()


def _command_sources(kit: Kit) -> list[Path]:
    # Enumerated even when no root has a commands directory: the count is
    # what the "no commands directory for this harness" notice reports.
    if not kit.commands_dir.is_dir():
        raise SourceMissing(report_mod.err_source_command_missing(str(kit.commands_dir)))
    return kit.iter_command_files()


def build_plan(kit: Kit, adapter: Adapter, target: Path, *, skip_mcp_config: bool) -> Plan:
    """Enumerate the payload, resolve every destination, check every source.

    Emission order, per :data:`OPS` and per root: skills (case-insensitively
    sorted), commands, doc trees, loose doc files, then the adapter's extra
    files. Raises :class:`SourceMissing` naming the absent input — the
    messages are ``report.err_source_*`` — and, when ``skip_mcp_config`` is
    false, checks ``harness/mcp-servers.json`` exists here rather than
    where it is read, so a missing file stops the run before anything has
    been copied and ``--dry-run`` reports it too.
    """
    skill_sources = _skill_sources(kit)
    command_sources = _command_sources(kit)

    rows: list[PlanRow] = []
    roots: list[RootPaths] = []
    skipped_command_count = 0

    for root in adapter.roots:
        skills_target = root.join(target, root.skills_rel)
        commands_target = (
            root.join(target, root.commands_rel) if root.commands_rel is not None else None
        )
        docs_target = root.join(target, root.docs_rel)
        roots.append(
            RootPaths(
                root=root,
                skills_target=skills_target,
                commands_target=commands_target,
                docs_target=docs_target,
                marker_path=root.join(target, root.marker_rel),
            )
        )

        # Every skill, as a whole tree. A skill left out is a dangling
        # cross-reference in the ones that ship, and 59 `../<skill>/SKILL.md`
        # links exist today.
        for src in skill_sources:
            _require(src, report_mod.err_source_skill_missing)
            rows.append(PlanRow("skill", src, skills_target / src.name))

        # Commands are flat, `.md` only, and overwritten without a
        # pre-delete, so an unrelated file in that directory survives.
        if commands_target is not None:
            for src in command_sources:
                _require(src, report_mod.err_source_command_missing)
                rows.append(PlanRow("command", src, commands_target / src.name))
        elif command_sources:
            skipped_command_count = len(command_sources)

        # The two doc trees are mandatory as a pair; the loose doc files go
        # into the docs root rather than into a tree of their own.
        for tree in DOC_TREES:
            src = kit.docs_dir / tree
            _require(src, report_mod.err_source_docs_tree_missing)
            rows.append(PlanRow("docs", src, docs_target / tree))
        for docfile in DOC_FILES:
            src = kit.docs_dir / docfile
            _require(src, report_mod.err_source_docs_file_missing)
            rows.append(PlanRow("docfile", src, docs_target / docfile))

    # Harness-specific files, once per install rather than once per root:
    # today that is `.claude/settings.json` and nothing else.
    for extra in adapter.extra_files:
        src = kit.root.joinpath(*extra.src_rel.split("/"))
        _require(src, report_mod.err_harness_settings_missing)
        rows.append(PlanRow("settings", src, target.joinpath(*extra.dst_rel.split("/"))))

    # Checked here rather than where it is read, so a missing file stops the
    # run before anything has been copied. `--skip-mcp-config` does not need
    # it at all: in the script the preflight was skipped but the late read
    # was not, so a missing file aborted *after* everything was copied and
    # *before* the marker was written.
    if not skip_mcp_config and adapter.mcp is not None:
        _require(kit.mcp_servers_file, report_mod.err_mcp_config_missing)

    return Plan(
        target=target,
        adapter=adapter,
        rows=tuple(rows),
        roots=tuple(roots),
        skipped_command_count=skipped_command_count,
        skill_names=tuple(src.name for src in skill_sources),
    )
