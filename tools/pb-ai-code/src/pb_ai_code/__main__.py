"""CLI entry point.

Subcommands::

    install [--target PATH] [--harness {claude-code,generic}]
            [--skills-dir REL] [--commands-dir REL]
            [--skip-mcp-config] [--dry-run]
    status  [--target PATH] [--json]

Long options only — the house rule is that not one short flag exists in
either sibling CLI. ``--harness`` takes ``type=str.lower`` so
``--harness CLAUDE-CODE`` succeeds and the marker records the normalised
spelling rather than the user's. ``--target`` defaults to the current
directory: this is run from *inside* the consumer repo, and the script's
"no target means install into the source" concept does not survive the
port.

``pb-ai-code --version`` prints the distribution version and exits 0.

Stream discipline (spec §4): ``install`` writes its **entire report to
stdout**, in a fixed order, single stream. That deviates from the two
sibling CLIs (progress to stderr, payload to stdout) deliberately — the
report *is* the contract here, an agent parses it, and splitting it over
two streams destroys the ordering when they are redirected separately.
stderr carries only the fatal one-liners and unexpected tracebacks.
``status --json`` restores the convention.

Nothing is printed until every decision that can fail has been made: the
target is validated, the adapter resolved, the payload found, and the
whole plan built and existence-checked before the first line of the
report. A run that exits non-zero therefore leaves stdout empty and the
target untouched.

Exit codes (spec §4): 0 on success **including every warning path**, 2 on
a usage error (one line on stderr, no traceback), 3 when ``status`` finds
no marker, 1 for anything unexpected — where an anticipated failure is one
line and an unanticipated one keeps its traceback.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from . import EXIT_OK, NotInstalled, PbAiCodeError, UsageError
from . import agentsmd as agentsmd_mod
from . import appeon as appeon_mod
from . import apply as apply_mod
from . import gitignore as gitignore_mod
from . import harness as harness_mod
from . import kit as kit_mod
from . import marker as marker_mod
from . import mcpconfig as mcp_mod
from . import pbversion as pbversion_mod
from . import plan as plan_mod
from . import provenance as provenance_mod
from . import report as report_mod
from .harness import Adapter
from .kit import Kit
from .plan import Plan
from .provenance import SourceIdentity
from .report import Reporter

PROG = "pb-ai-code"

_DEFAULT_TARGET = "."
_DEFAULT_HARNESS = "generic"
_DEFAULT_JSON = False

#: What ``status`` prints for a marker value that is not there. Every
#: marker the PowerShell installer wrote lacks ``# Version:``, and a
#: missing value is a fact worth showing rather than a reason to fail.
#: ``--json`` reports the same absence as ``null``.
_UNKNOWN = "unknown"


def _native(rel: str) -> str:
    """A ``/``-separated target-relative path in the platform's spelling."""
    return str(Path(*rel.split("/")))


# --- install -----------------------------------------------------------------


@dataclass(frozen=True)
class _McpInputs:
    """Everything the merge needs, decided before it runs.

    The Appeon entry has to be in ``servers`` *before* the merge, and the
    question it answers — does the target already carry an entry? — can
    only be asked *after* the target has been read. So both happen here,
    once, and the dry run and the real run share the result.
    """

    servers: dict[str, Any]
    path: Path | None
    existing: bytes | None
    db: Path | None
    note: str


@dataclass(frozen=True)
class _McpResult:
    """What the marker records about the MCP step, and about Appeon."""

    marker_value: str
    appeon_note: str
    appeon_db: Path | None


def _collect_mcp_inputs(
    kit: Kit,
    adapter: Adapter,
    target: Path,
    identity: SourceIdentity,
) -> _McpInputs:
    """Read the canonical block, the target's file, and probe for the index.

    Reads only, which is why ``--dry-run`` walks it too: the two decisions
    a user wants previewed are what the merge would do and whether the
    Appeon index was found.
    """
    mcp = adapter.mcp
    servers = mcp_mod.load_servers(kit.mcp_servers_file)
    path = target.joinpath(*mcp.rel_path.split("/")) if mcp is not None and mcp.rel_path else None
    existing = mcp_mod.read_config(path) if path is not None else None
    db = appeon_mod.find_index_db(kit)
    if db is not None:
        # `harness/mcp-servers.json` cannot carry this server: it is
        # committed and shared, and the entry needs an absolute database
        # path. The file being written is neither.
        servers[appeon_mod.SERVER_KEY] = appeon_mod.server_entry(db, identity.update_ref)
    note = appeon_mod.note(
        db,
        existing_entry_in_target=appeon_mod.SERVER_KEY in mcp_mod.existing_server_names(existing),
    )
    return _McpInputs(servers=servers, path=path, existing=existing, db=db, note=note)


def _print_plan(
    reporter: Reporter,
    plan: Plan,
    kit: Kit,
    adapter: Adapter,
    *,
    skip_mcp_config: bool,
) -> None:
    """The plan table: one row per copy, then the three pseudo-rows."""
    src_root = str(kit.root)
    dst_root = str(plan.target)
    for row in plan.rows:
        reporter.line(
            report_mod.plan_row(
                row.op,
                report_mod.abbreviate(str(row.src), src_root, report_mod.SRC_PLACEHOLDER),
                report_mod.abbreviate(str(row.dst), dst_root, report_mod.DST_PLACEHOLDER),
            )
        )
    mcp_src = report_mod.abbreviate(str(kit.mcp_servers_file), src_root, report_mod.SRC_PLACEHOLDER)
    if skip_mcp_config:
        reporter.line(report_mod.plan_mcp_skipped())
    elif adapter.mcp is None:
        # No adapter in the phase-1 registry has this shape; aider will be
        # the first. Nothing to plan, so nothing to print.
        pass
    elif adapter.mcp.rel_path is None:
        reporter.line(report_mod.plan_mcp_printed(mcp_src))
    else:
        reporter.line(
            report_mod.plan_mcp_merged(
                mcp_src,
                os.path.join(report_mod.DST_PLACEHOLDER, _native(adapter.mcp.rel_path)),
            )
        )
    # One marker per root (spec §5); today there is exactly one.
    for root in plan.roots:
        reporter.line(
            report_mod.plan_marker(
                report_mod.abbreviate(str(root.marker_path), dst_root, report_mod.DST_PLACEHOLDER)
            )
        )
    reporter.line(report_mod.plan_rewrite(harness_mod.DOCS_FOLDER_NAME))
    reporter.blank()


def _dry_run(
    reporter: Reporter,
    kit: Kit,
    adapter: Adapter,
    plan: Plan,
    identity: SourceIdentity,
    *,
    skip_mcp_config: bool,
) -> int:
    """Print what would happen and return, having created nothing.

    Wider than the script's dry run, which was silent about exactly the two
    decisions worth previewing: whether the Appeon index was found, and
    what the merge would do to the servers already in the target.
    """
    reporter.line(report_mod.dry_run())
    if not skip_mcp_config:
        inputs = _collect_mcp_inputs(kit, adapter, plan.target, identity)
        if inputs.db is not None:
            reporter.line(report_mod.dry_run_appeon_configured(str(inputs.db)))
        else:
            reporter.line(report_mod.dry_run_appeon_note(inputs.note))
        if inputs.path is not None:
            actions = mcp_mod.preview(inputs.existing, inputs.servers)
            if actions:
                reporter.line(report_mod.dry_run_mcp(actions))
    # Both of these happen after the copy in a real install, which is why the
    # preview used to end above and stay silent about them. They are the two
    # effects that touch files the project owns rather than the generated
    # bundle, so they are exactly the ones somebody reads a dry run to catch.
    reporter.line(
        report_mod.dry_run_agents_md(
            agentsmd_mod.FILE_NAME,
            exists=(plan.target / agentsmd_mod.FILE_NAME).exists(),
        )
    )
    reporter.line(
        report_mod.dry_run_gitignore(is_repo=gitignore_mod.check(plan.target, ".").is_repo)
    )
    return EXIT_OK


def _apply(reporter: Reporter, plan: Plan) -> str | None:
    """Copy every row, reporting as it goes; return the replaced settings rel.

    Printed inside the loop rather than after it, so a failure halfway
    still shows what had been done. The WARN is scoped to the settings row:
    that overwrite is verbatim, unmerged and unbacked, and saying so is the
    whole of the change to it.
    """
    settings_replaced: str | None = None
    for row in plan.rows:
        outcome = apply_mod.apply_row(row)
        reporter.line(report_mod.installed_row(row.op, row.dst.name))
        if outcome.replaced_differing_file and row.op == "settings":
            settings_replaced = str(row.dst.relative_to(plan.target))
            reporter.line(report_mod.settings_replaced_warning(settings_replaced))
    return settings_replaced


def _configure_mcp(
    reporter: Reporter,
    kit: Kit,
    adapter: Adapter,
    plan: Plan,
    identity: SourceIdentity,
    *,
    skip_mcp_config: bool,
) -> _McpResult:
    """Exactly one of four branches: skipped, printed, refused, merged."""
    if skip_mcp_config:
        reporter.line(report_mod.mcp_skipped())
        # The note reports what was *computed*, and under this flag nothing
        # was: the script still claimed `configured` here.
        return _McpResult(
            marker_value=report_mod.MCP_MARKER_SKIPPED,
            appeon_note=report_mod.APPEON_NOTE_SKIPPED,
            appeon_db=None,
        )
    if adapter.mcp is None:
        # Unreachable in phase 1, and deliberately loud: a harness with no
        # MCP configuration at all (aider) needs a `# MCP:` value and a
        # "Note:" line for its `gaps`, neither of which report.py owns a
        # string for yet. Same shape as the three unimplemented dialects.
        raise NotImplementedError(f"harness {adapter.id} declares no MCP target")
    inputs = _collect_mcp_inputs(kit, adapter, plan.target, identity)
    if inputs.path is None:
        # No known on-disk location. Printing the block and saying so beats
        # writing it somewhere invented, which would look like it worked.
        reporter.block(report_mod.mcp_printed_block(mcp_mod.render_block(inputs.servers)))
        return _McpResult(
            marker_value=report_mod.MCP_MARKER_PRINTED,
            appeon_note=inputs.note,
            appeon_db=inputs.db,
        )
    rel = _native(adapter.mcp.rel_path or "")
    result = mcp_mod.merge(inputs.existing, inputs.servers)
    if result.text is None:
        # A project's MCP config may hold servers unrelated to
        # PowerBuilder; overwriting them because the file has a stray comma
        # is a poor trade for saving one hand merge. The run continues and
        # exits 0.
        reporter.block(
            report_mod.mcp_unparseable(str(inputs.path), mcp_mod.render_block(inputs.servers))
        )
        return _McpResult(
            marker_value=report_mod.mcp_marker_not_written(rel),
            appeon_note=inputs.note,
            appeon_db=inputs.db,
        )
    # The duplicate warnings print before the `Installed mcp` line, exactly
    # as they did from inside the script's merge.
    owned = report_mod.owned_keys_phrase(inputs.servers)
    for duplicate in result.warnings:
        reporter.block(
            report_mod.duplicate_server_warning(duplicate.name, duplicate.package, owned)
        )
    mcp_mod.write_config(inputs.path, result.text, existing=inputs.existing)
    outcomes = report_mod.join_outcomes(result.outcomes)
    reporter.line(report_mod.mcp_installed(rel, outcomes))
    return _McpResult(
        marker_value=report_mod.mcp_marker_merged(rel, outcomes),
        appeon_note=inputs.note,
        appeon_db=inputs.db,
    )


def _write_markers(
    plan: Plan,
    adapter: Adapter,
    identity: SourceIdentity,
    mcp: _McpResult,
    settings_replaced: str | None,
    pb_version: str | None = None,
) -> None:
    """The last write of the run: one marker per root, each atomic.

    Contents is the plan destinations relative to the target, in plan
    order. The MCP file and the marker itself are not plan rows, so they
    cannot appear there.
    """
    contents = tuple(str(dst.relative_to(plan.target)) for dst in plan.destinations())
    text = marker_mod.render(
        installed_at=marker_mod.format_timestamp(datetime.now().astimezone()),
        identity=identity,
        adapter=adapter,
        mcp_outcome=mcp.marker_value,
        appeon_note=mcp.appeon_note,
        contents=contents,
        settings_replaced=settings_replaced,
        pb_version=pb_version,
    )
    for root in plan.roots:
        marker_mod.write(root.marker_path, text)


def _gitignore_hint(
    reporter: Reporter,
    adapter: Adapter,
    target: Path,
    *,
    skip_mcp_config: bool,
) -> None:
    """Say so when the bundle just written is not ignored by the target's git.

    Silent for a target that is not a repository and for a machine with no
    git: the install has already succeeded, and neither is a reason to fail
    or to nag. Run after the copy, because the no-trailing-slash query that
    avoids the blank-line bug relies on the directory existing.
    """
    mcp = adapter.mcp
    mcp_rel = None if skip_mcp_config or mcp is None else mcp.rel_path
    roots_to_check: list[str] = []
    for root in adapter.roots:
        if root.bundle_root not in roots_to_check:
            roots_to_check.append(root.bundle_root)
    if (
        mcp_rel is not None
        and mcp_rel.split("/")[0] not in roots_to_check
        and mcp_rel.split("/")[0] != ".mcp.json"
    ):
        roots_to_check.append(mcp_rel.split("/")[0])
    for bundle_root in roots_to_check:
        status = gitignore_mod.check(target, bundle_root)
        if not status.is_repo:
            # Git present and this is not a repository: say so once. Git
            # absent: say nothing, because nothing is known.
            if status.git_available:
                reporter.block(report_mod.not_a_repository_note(bundle_root, mcp_path=mcp_rel))
            continue
        if status.ignored:
            continue
        reporter.block(
            report_mod.gitignore_note(
                bundle_root,
                enclosing_repo=str(status.repo_root) if status.encloses_target else None,
                mcp_path=mcp_rel,
            )
        )


def _cmd_install(args: argparse.Namespace) -> int:
    """Run the install, printing the whole report to stdout in fixed order."""
    skip_mcp_config = bool(args.skip_mcp_config)
    # Everything that can fail happens before the first line is printed.
    target = plan_mod.validate_target(args.target)
    adapter = harness_mod.resolve_adapter(
        args.harness, skills_dir=args.skills_dir, commands_dir=args.commands_dir
    )
    kit = kit_mod.load_kit()
    identity = provenance_mod.resolve(kit)
    plan = plan_mod.build_plan(kit, adapter, target, skip_mcp_config=skip_mcp_config)
    # Before the first byte is written and before the first line is printed:
    # a bad --pb-version is a usage error, and an interactive question asked
    # halfway through a report reads as an interruption of it.
    pb_version = _resolve_pb_version(args, target)

    reporter = Reporter()
    reporter.block(
        report_mod.header(identity.summary, str(target), adapter.id, dirty=identity.dirty)
    )
    if plan.skipped_command_count:
        reporter.block(report_mod.no_commands_directory(plan.skipped_command_count))
    _print_plan(reporter, plan, kit, adapter, skip_mcp_config=skip_mcp_config)

    if args.dry_run:
        return _dry_run(reporter, kit, adapter, plan, identity, skip_mcp_config=skip_mcp_config)

    settings_replaced = _apply(reporter, plan)
    # Per root: the links are relative to the root they live in.
    rewritten = sum(
        apply_mod.rewrite_links(root.skills_target, plan.skill_names, harness_mod.DOCS_FOLDER_NAME)
        for root in plan.roots
    )
    reporter.line(report_mod.rewrote_links(rewritten))

    mcp = _configure_mcp(reporter, kit, adapter, plan, identity, skip_mcp_config=skip_mcp_config)
    if not skip_mcp_config:
        if mcp.appeon_db is not None:
            reporter.block(report_mod.appeon_configured(str(mcp.appeon_db)))
        else:
            reporter.block(report_mod.appeon_missing(mcp.appeon_note))

    _write_agents_md(reporter, target, pb_version)

    _write_markers(plan, adapter, identity, mcp, settings_replaced, pb_version)

    reporter.block(report_mod.done())
    if adapter.restart_hint is not None and not skip_mcp_config:
        reporter.line(report_mod.restart_hint(adapter.restart_hint))
    _gitignore_hint(reporter, adapter, target, skip_mcp_config=skip_mcp_config)
    return EXIT_OK


def _resolve_pb_version(args: argparse.Namespace, target: Path) -> str | None:
    """The flag, else the person, else what a previous install recorded.

    Never the sources. An object carries the release it was last saved
    under rather than the release of the IDE working on it, so a 2022
    project can hold release 6 DataWindows and a sniffed answer is
    plausible, specific and sometimes four majors wrong.
    """
    if args.pb_version:
        try:
            return pbversion_mod.parse(args.pb_version).value
        except pbversion_mod.InvalidPbVersion as exc:
            # Ledger 14: everything that can fail fails before the first
            # copy. A traceback here would leave a half-installed target.
            raise UsageError(str(exc)) from exc
    previous = agentsmd_mod.read_version(target)
    answer = pbversion_mod.ask(previous)
    if answer is not None:
        return answer.value
    return previous


def _write_agents_md(reporter: Reporter, target: Path, pb_version: str | None) -> None:
    """Create the project's own instruction file, or print what it should say.

    Never both, and never an edit: an existing AGENTS.md is hand-maintained,
    it is read by every agent that opens the project, and an installer that
    appended to it on each update would corrupt instructions a little at a
    time.
    """
    is_git = gitignore_mod.check(target, ".").is_repo
    protection = gitignore_mod.source_protection(target)
    facts = agentsmd_mod.survey(
        target,
        pb_version=pb_version,
        is_git=is_git,
        is_svn=(target / ".svn").is_dir(),
        source_protection=protection.status,
    )
    rel = agentsmd_mod.FILE_NAME
    recorded_pb_version = agentsmd_mod.read_version(target)
    try:
        created = agentsmd_mod.create(target, facts)
    except OSError as exc:
        # The install has already succeeded; a target that will not take
        # one more file is a thing to report, not to fail on.
        reporter.block(report_mod.agents_md_unwritable(rel, str(exc)))
        return
    if created:
        reporter.block(report_mod.agents_md_written(rel, pb_version))
        return
    reporter.block(
        report_mod.agents_md_exists(
            rel,
            pb_version,
            recorded_pb_version=recorded_pb_version,
        )
    )
    reporter.block(report_mod.quoted_block(agentsmd_mod.block(facts)))


# --- status ------------------------------------------------------------------


def _cmd_status(args: argparse.Namespace) -> int:
    """Read the marker under the target and report it, text or JSON.

    No network and no git: everything printed comes out of the file. Exit 3
    when there is no marker, so an agent can branch on "installed?" without
    parsing anything.
    """
    target = plan_mod.validate_target(args.target)
    marker_path = marker_mod.find(target)
    if marker_path is None:
        raise NotInstalled(report_mod.err_no_marker(str(target)))
    # utf-8-sig: a marker written by Windows PowerShell 5.1 carries a BOM.
    fields = marker_mod.parse(marker_path.read_text(encoding="utf-8-sig"))
    running_version = provenance_mod.distribution_version()
    up_to_date = fields.version is not None and fields.version == running_version

    if args.json:
        payload: dict[str, object] = {
            "installed": True,
            "target": str(target),
            "marker_path": str(marker_path),
            "installed_at": fields.installed_at,
            "version": fields.version,
            "source": fields.source,
            "sha": fields.sha,
            "branch": fields.branch,
            "dirty": fields.dirty,
            "harness": fields.harness,
            "mcp": fields.mcp,
            "appeon": fields.appeon,
            "contents": list(fields.contents),
            "running_version": running_version,
            "up_to_date": up_to_date,
        }
        print(json.dumps(payload, indent=2))
        return EXIT_OK

    Reporter().block(
        report_mod.status_text(
            running_version=running_version,
            target=str(target),
            marker_rel=str(marker_path.relative_to(target)),
            installed_at=fields.installed_at or _UNKNOWN,
            version=fields.version or _UNKNOWN,
            source=fields.source or _UNKNOWN,
            harness=fields.harness or _UNKNOWN,
            mcp=fields.mcp or _UNKNOWN,
            appeon=fields.appeon or _UNKNOWN,
            contents_count=len(fields.contents),
            up_to_date=up_to_date,
        )
    )
    return EXIT_OK


# --- argument parsing --------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """The whole command surface. Long options only, defaults from constants."""
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Install the pb-ai-code kit into a project, and report what is there.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=provenance_mod.distribution_version(),
        help="print the running pb-ai-code version and exit",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_install = sub.add_parser(
        "install", help="copy skills, knowledge base and MCP config into the target"
    )
    p_install.add_argument(
        "--target",
        default=_DEFAULT_TARGET,
        help="project to install into; must exist and is never created (default: .)",
    )
    p_install.add_argument(
        "--harness",
        type=str.lower,
        choices=harness_mod.HARNESS_IDS,
        default=_DEFAULT_HARNESS,
        help="assistant whose layout to write (default: generic)",
    )
    p_install.add_argument(
        "--skills-dir",
        default=None,
        help="target-relative skills directory; defaults to .agents/skills for generic",
    )
    p_install.add_argument(
        "--commands-dir",
        default=None,
        help="target-relative commands directory; must be a sibling of --skills-dir",
    )
    p_install.add_argument(
        "--pb-version",
        default=None,
        help=(
            "PowerBuilder version this project is developed with (e.g. 22.0). "
            "Asked interactively when omitted and there is a terminal; never "
            "deduced from the sources"
        ),
    )
    p_install.add_argument(
        "--skip-mcp-config",
        action="store_true",
        help="do not touch the target's MCP configuration",
    )
    p_install.add_argument(
        "--dry-run",
        action="store_true",
        help="print the plan and what the merge would do; write nothing",
    )
    p_install.set_defaults(func=_cmd_install)

    p_status = sub.add_parser("status", help="report the pb-ai-code install found in the target")
    p_status.add_argument("--target", default=_DEFAULT_TARGET, help="project to inspect")
    p_status.add_argument(
        "--json",
        action="store_true",
        default=_DEFAULT_JSON,
        help="machine-readable form on stdout, and nothing else",
    )
    p_status.set_defaults(func=_cmd_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse the arguments, dispatch, and map exceptions onto exit codes.

    Anticipated failures — everything derived from
    :class:`pb_ai_code.PbAiCodeError` — print one line on stderr and return
    the class's code. Anything else keeps its traceback: an unexpected
    exception is a bug report, not a diagnostic.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except PbAiCodeError as exc:
        report_mod.fatal(str(exc))
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
