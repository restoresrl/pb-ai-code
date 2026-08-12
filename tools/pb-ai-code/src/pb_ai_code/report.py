"""Every string ``install`` and ``status`` print, in one module.

One owner, so a literal cannot drift in two places and so the golden tests
have somewhere to point. Nothing here decides anything: the callers work
out *what* happened, this module says how it reads.

Stream discipline (spec §4): ``install`` writes its entire report to
**stdout**, in a fixed order, single stream. stderr carries only the fatal
one-liners at the bottom of this module and unexpected tracebacks. That
deviates from the two sibling CLIs (progress to stderr, payload to stdout)
on purpose — the report *is* the contract here, an agent parses it, and
splitting it across two streams destroys the ordering when they are
redirected separately. ``status --json`` restores the convention.

Colour vanishes when the stream is not a TTY, exactly as the PowerShell
host's ``-ForegroundColor`` did when redirected, and also when the console
will not render SGR escapes or ``NO_COLOR`` is set. The report stream is
made lossy on the way in so that a character the console code page cannot
encode degrades to an escape instead of killing the run - see
:func:`make_lossy` and :func:`ansi_is_understood`, the two places where
this module knows that ``Write-Host`` did something Python does not.

Two strings in this file have a near-twin in :mod:`pb_ai_code.marker` and
they are **deliberately different**: :data:`DIRTY_SOURCE_WARNING` is
present tense on stdout ("has uncommitted changes"), the marker's is past
tense ("had uncommitted changes at install time"). Do not unify them.
"""

from __future__ import annotations

import contextlib
import os
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal, TextIO

from . import REPO_URL

# --- The line primitive ------------------------------------------------------

Style = Literal["plain", "cyan", "yellow", "green"]

_ANSI: dict[Style, str] = {
    "plain": "",
    "cyan": "\x1b[36m",
    "yellow": "\x1b[33m",
    "green": "\x1b[32m",
}
_RESET = "\x1b[0m"


@dataclass(frozen=True)
class Line:
    """One line of report output, with the colour the PowerShell script used."""

    text: str
    style: Style = "plain"


#: The empty line. The report's blank lines are load-bearing: several
#: blocks are specified as "wrapped in blanks".
BLANK = Line("")


# --- The stream (ledger 64, 74, 62) ------------------------------------------
# Two things the PowerShell host did for us that Python does not do for a
# `sys.stdout` obtained from the C runtime: it never died on a character it
# could not encode, and it coloured a console without emitting escape bytes.


def make_lossy(stream: TextIO) -> None:
    """Stop an unencodable character from killing a report in progress.

    A redirected ``sys.stdout`` on Windows is opened with the ANSI code
    page - cp1252 on the machines this kit targets - and a strict error
    handler, so one character outside it (a Japanese target path, a
    preserved server key, an accented user name) raises
    ``UnicodeEncodeError`` from the middle of the report. Worse than the
    traceback is *when* it lands: raised while printing the outcome of the
    MCP merge, it aborts after the skills are copied and ``.mcp.json`` is
    rewritten but before the marker is written, which is exactly the
    fully-populated-target-with-no-marker state ledger 62 exists to forbid.

    ``Write-Host`` was lossy but alive - verified, not assumed: a
    redirected ``pwsh -NoProfile -Command 'Write-Host <non-cp1252 text>'``
    writes ``???`` and exits 0. This restores lossy-but-alive and picks
    ``backslashreplace`` over the ``replace`` that would reproduce ``???``
    byte for byte, because the report names paths the reader has to act
    on: an escaped path still says which one it is, ``???-target`` does
    not. It is also the handler Python already gives ``sys.stderr``.

    The *encoding* is deliberately left alone. Forcing UTF-8 would override
    an explicit ``PYTHONIOENCODING`` and silently change the bytes of every
    redirected report; ``PYTHONIOENCODING=utf-8`` or ``PYTHONUTF8=1``
    remains the way to ask for real UTF-8.
    """
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:  # io.StringIO, or anything not a TextIOWrapper
        return
    with contextlib.suppress(ValueError, OSError):  # detached, closed, broken pipe
        reconfigure(errors="backslashreplace")


#: ``ENABLE_VIRTUAL_TERMINAL_PROCESSING``: the console flag that turns an SGR
#: escape into colour instead of into four visible characters.
_ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004


def ansi_is_understood(stream: TextIO) -> bool:
    """Will SGR escapes written to *stream* be rendered, or printed?

    Off Windows a TTY is taken at its word. On Windows it is *asked*, and
    the answer is not the obvious one: conhost - cmd.exe, and the
    PowerShell console window this kit is run from - starts without
    ENABLE_VIRTUAL_TERMINAL_PROCESSING, so a green ``Installed`` row
    appears on screen as its escape characters. ``Write-Host
    -ForegroundColor`` never had the problem: it goes through the console
    API and writes no escape bytes at all.

    So the flag is set, and then **read back**, because a host may accept
    ``SetConsoleMode`` and ignore the bit; a console that will not confirm
    it gets plain text. Measured on the Windows Server 2019 machine this
    port was verified on: the console starts at mode ``0x3``, and
    ``SetConsoleMode`` moves it to ``0x7`` - so on the very platform where
    the escapes were garbage, they now render, and the alternative of
    dropping colour everywhere would have been a regression for nothing.

    Enabling VT outlives the process, as it does for every tool that does
    this. That is the point: it is a capability of the console, not a mode
    we are borrowing.
    """
    if sys.platform != "win32":
        return True

    import ctypes
    import msvcrt

    try:
        handle = ctypes.c_void_p(msvcrt.get_osfhandle(stream.fileno()))
    except (AttributeError, OSError, ValueError):  # no fileno, or not a real fd
        return False

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    before = ctypes.c_uint32()
    if not kernel32.GetConsoleMode(handle, ctypes.byref(before)):
        return False  # a pipe or a file: isatty() lied, or the handle is dead
    if before.value & _ENABLE_VIRTUAL_TERMINAL_PROCESSING:
        return True
    kernel32.SetConsoleMode(handle, before.value | _ENABLE_VIRTUAL_TERMINAL_PROCESSING)
    after = ctypes.c_uint32()
    if not kernel32.GetConsoleMode(handle, ctypes.byref(after)):
        return False
    return bool(after.value & _ENABLE_VIRTUAL_TERMINAL_PROCESSING)


def want_color(stream: TextIO) -> bool:
    """``NO_COLOR``, then a TTY, then a terminal that renders the escapes.

    ``NO_COLOR`` is honoured on presence with any non-empty value, per
    no-color.org. It is checked first so that it holds whatever the console
    would have said.
    """
    if os.environ.get("NO_COLOR", ""):
        return False
    try:
        if not stream.isatty():
            return False
    except (AttributeError, ValueError):  # closed or not a real stream
        return False
    return ansi_is_understood(stream)


class Reporter:
    """Writes :class:`Line` objects to a stream that cannot die on them.

    Colour goes only to a TTY that has confirmed it will render SGR
    escapes; an explicit ``color=`` is a caller's override and skips the
    whole question, ``NO_COLOR`` included.
    """

    def __init__(self, stream: TextIO | None = None, *, color: bool | None = None) -> None:
        self._stream: TextIO = sys.stdout if stream is None else stream
        make_lossy(self._stream)
        self._color = want_color(self._stream) if color is None else color

    @property
    def color(self) -> bool:
        return self._color

    def line(self, item: Line) -> None:
        if self._color and item.style != "plain" and item.text:
            self._stream.write(f"{_ANSI[item.style]}{item.text}{_RESET}\n")
        else:
            self._stream.write(f"{item.text}\n")

    def block(self, items: Iterable[Line]) -> None:
        for item in items:
            self.line(item)

    def blank(self) -> None:
        self.line(BLANK)


def as_lines(text: str, style: Style = "plain") -> list[Line]:
    """Split a rendered block (the MCP JSON) into report lines."""
    return [Line(part, style) for part in text.splitlines()]


# --- Path abbreviation (ledger 65) -------------------------------------------

SRC_PLACEHOLDER = "<src>"
DST_PLACEHOLDER = "<dst>"


def abbreviate(path: str, root: str, placeholder: str) -> str:
    """Textual replacement of a root by ``<src>``/``<dst>``, as ps1:403-404.

    Deliberately literal ``str.replace``: it is what the script does, and a
    path-aware version would differ on case and on trailing separators.
    """
    return path.replace(root, placeholder)


# --- Header (ledger 4, 64) ---------------------------------------------------

DIRTY_SOURCE_WARNING = (
    "WARN: source repo has uncommitted changes; the install may include unversioned work."
)


def source_summary(version: str, origin: str | None) -> str:
    """``pb-ai-code 0.5.0 (git+https://github.com/restoresrl/pb-ai-code)``.

    ``origin`` is the VCS URL for a wheel installed from git, ``local
    checkout <path>`` when running from a checkout, and ``None`` when
    neither could be established — in which case the version stands alone,
    which is still a well-formed answer.
    """
    if origin is None:
        return f"pb-ai-code {version}"
    return f"pb-ai-code {version} ({origin})"


def checkout_origin(root: str) -> str:
    """``local checkout C:\\proj\\pb-ai-code`` — the origin of a dev-loop run."""
    return f"local checkout {root}"


def header(source: str, target: str, harness: str, *, dirty: bool) -> list[Line]:
    """The first block: blank, Source, optional WARN, Target, Harness, blank.

    The dirty warning sits immediately after ``Source:`` and nowhere else
    (ledger 4). ``source`` comes from :func:`source_summary`.
    """
    lines = [BLANK, Line(f"Source:  {source}", "cyan")]
    if dirty:
        lines.append(Line(DIRTY_SOURCE_WARNING, "yellow"))
    lines.append(Line(f"Target:  {target}"))
    lines.append(Line(f"Harness: {harness}"))
    lines.append(BLANK)
    return lines


# --- No commands directory (ledger 12) ---------------------------------------

COMMANDS_FALLBACK_LINE = "      Every flow is also reachable as a skill of the same name."


def no_commands_directory(count: int) -> list[Line]:
    """Two yellow lines and a blank. A notice, never an error."""
    return [
        Line(
            f"Note: no commands directory for this harness; skipping {count} command file(s).",
            "yellow",
        ),
        Line(COMMANDS_FALLBACK_LINE, "yellow"),
        BLANK,
    ]


# --- The plan table (ledger 65) ----------------------------------------------

#: The op field is left-aligned in nine columns, then one space.
OP_WIDTH = 9

#: Literal the rewrite looks for; the plan row quotes it (ledger 28).
REWRITE_FROM = "../../docs/"


def plan_row(op: str, src: str, dst: str) -> Line:
    return Line(f"{op:<{OP_WIDTH}} {src} -> {dst}")


def plan_mcp_skipped() -> Line:
    return Line(f"{'mcp':<{OP_WIDTH}} skipped (--skip-mcp-config)")


def plan_mcp_merged(src: str, dst: str) -> Line:
    """Two spaces before the parenthesis — ps1:412."""
    return Line(f"{'mcp':<{OP_WIDTH}} {src} -> {dst}  (merged; other servers preserved)")


def plan_mcp_printed(src: str) -> Line:
    return Line(f"{'mcp':<{OP_WIDTH}} {src} -> printed below (location is client-specific)")


def plan_marker(dst: str) -> Line:
    return Line(f"{'marker':<{OP_WIDTH}} {dst}")


def plan_rewrite(docs_folder_name: str) -> Line:
    """Two spaces before ``in the installed skills`` — ps1:419."""
    return Line(
        f"{'rewrite':<{OP_WIDTH}} {REWRITE_FROM} -> ../../{docs_folder_name}/"
        "  in the installed skills"
    )


# --- Dry run (ledger 75) -----------------------------------------------------

DRY_RUN_LINE = "Dry run. No changes written."


def dry_run() -> Line:
    return Line(DRY_RUN_LINE, "yellow")


def dry_run_appeon_configured(db: str) -> Line:
    return Line(f"Would configure pb-appeon-index -> {db}")


def dry_run_appeon_note(note: str) -> Line:
    return Line(f"Note: {note}", "yellow")


def would_add(name: str) -> str:
    return f"would add {name}"


def would_update(name: str) -> str:
    return f"would update {name}"


def would_leave(name: str) -> str:
    return f"would leave {name}"


def dry_run_mcp(actions: Sequence[str]) -> Line:
    """``MCP: would add pb-orca; would leave postgres``."""
    return Line(f"MCP: {'; '.join(actions)}")


# --- Applying the plan (ledger 66, 22, 28) -----------------------------------


def installed_row(op: str, leaf: str) -> Line:
    """``Installed skill     appeon-query`` — leaf only, never the full path."""
    return Line(f"Installed {op:<{OP_WIDTH}} {leaf}", "green")


def settings_replaced_warning(rel: str) -> Line:
    """NEW (ledger 22): the overwrite stays silent no longer.

    ``harness/claude-code/settings.json`` is copied over the target's file
    verbatim — no merge, no backup. Keeping the behaviour and saying so is
    the whole of the change.
    """
    return Line(f"WARN: replaced an existing {rel} whose content differed.", "yellow")


def rewrote_links(count: int) -> Line:
    return Line(f"Rewrote knowledge-base links in {count} skill file(s).", "green")


# --- MCP configuration -------------------------------------------------------

MCP_SKIPPED_LINE = (
    "Skipped MCP config (--skip-mcp-config). The skills expect the pb_* tools to be reachable."
)
MCP_PRINT_INTRO_1 = "MCP config: add these servers to your client's MCP configuration."
MCP_PRINT_INTRO_2 = "Same JSON for every MCP client; only the file it goes in differs."
MCP_UNPARSEABLE_HAND_MERGE = "      Merge this into its 'mcpServers' object by hand:"


def mcp_skipped() -> Line:
    return Line(MCP_SKIPPED_LINE, "yellow")


def mcp_installed(rel: str, outcomes: str) -> Line:
    """``Installed mcp       .mcp.json  [pb-orca (added); kept: postgres]``.

    Two spaces before the bracket — ps1:522.
    """
    return Line(f"Installed {'mcp':<{OP_WIDTH}} {rel}  [{outcomes}]", "green")


def mcp_unparseable(path: str, block: str) -> list[Line]:
    """The file is left byte-for-byte untouched and the block is printed.

    A project's MCP config may hold servers unrelated to PowerBuilder;
    overwriting them because the file has a stray comma is a poor trade for
    saving the user one merge. The run continues and exits 0.
    """
    return [
        BLANK,
        Line(f"WARN: {path} is not valid JSON - leaving it untouched.", "yellow"),
        Line(MCP_UNPARSEABLE_HAND_MERGE, "yellow"),
        *as_lines(block),
        BLANK,
    ]


def mcp_printed_block(block: str) -> list[Line]:
    """The ``generic`` harness has no known on-disk location for the config.

    Printing the block and saying so beats writing it somewhere invented,
    which would look like it worked.
    """
    return [
        BLANK,
        Line(MCP_PRINT_INTRO_1, "cyan"),
        Line(MCP_PRINT_INTRO_2, "cyan"),
        *as_lines(block),
        BLANK,
    ]


# --- The duplicate-ORCA warning (ledger 42) ----------------------------------

_DUPLICATE_LINE_3 = (
    "      competing for a single-session ORCA library, duplicate tools under different"
)
_DUPLICATE_LINE_4 = "      prefixes, and only one of them matching the permission allowlist."


def owned_keys_phrase(names: Iterable[str]) -> str:
    """``pb-orca', 'pb-appeon-index`` — sits inside one pair of quotes."""
    return "', '".join(names)


def duplicate_server_warning(name: str, package: str, owned_keys: str) -> list[Line]:
    """Five yellow lines wrapped in blanks. Never removes anything.

    Fires when a *preserved* server runs one of our packages under a key we
    do not own. Two of them means two processes competing for a
    single-session ORCA library and only one key prefix matching the
    permission allowlist. ``owned_keys`` comes from
    :func:`owned_keys_phrase`.
    """
    return [
        BLANK,
        Line(
            f"WARN: the target already has a server '{name}' that runs {package}, which is what",
            "yellow",
        ),
        Line(
            f"      this kit installs as '{owned_keys}'. Two of them means two processes", "yellow"
        ),
        Line(_DUPLICATE_LINE_3, "yellow"),
        Line(_DUPLICATE_LINE_4, "yellow"),
        Line(
            f"      Left in place - it is your file. Remove '{name}' unless you meant to keep it.",
            "yellow",
        ),
        BLANK,
    ]


# --- Outcome vocabulary (ledger 40, 58) --------------------------------------
# One token per owned key, in the canonical block's key order, plus a single
# trailing `kept: a, b` in merged order. The same tokens go on stdout and into
# the marker's `# MCP:` line, which is why they live here and not in either.


def outcome_added(name: str) -> str:
    return f"{name} (added)"


def outcome_updated(name: str) -> str:
    return f"{name} (updated)"


def outcome_already_current(name: str) -> str:
    return f"{name} (already current)"


def outcome_kept(names: Sequence[str]) -> str:
    return "kept: " + ", ".join(names)


def join_outcomes(tokens: Sequence[str]) -> str:
    return "; ".join(tokens)


#: The four shapes of the marker's ``# MCP:`` value (ledger 58). Note the
#: two spaces before ``[`` in :func:`mcp_marker_merged`.
MCP_MARKER_SKIPPED = "skipped (--skip-mcp-config)"
MCP_MARKER_PRINTED = "printed (location is client-specific)"


def mcp_marker_merged(rel: str, outcomes: str) -> str:
    return f"{rel}  [{outcomes}]"


def mcp_marker_not_written(rel: str) -> str:
    return f"NOT written - {rel} could not be parsed; merge by hand"


# --- The Appeon index (ledger 49, 51, 52, 53) --------------------------------

APPEON_NOTE_MISSING_DB = "pb-appeon-index NOT configured - missing the index database"
APPEON_NOTE_EXISTING_ENTRY = (
    "pb-appeon-index NOT configured here - the target's existing entry was left in place"
)
APPEON_NOTE_SKIPPED = "not evaluated (--skip-mcp-config)"

_APPEON_REFERENCED = (
    "                  referenced, not copied - rebuilding it once updates every project"
)
_APPEON_RECIPE_VENV = (
    "        .venv\\Scripts\\pb-appeon-index update --db %USERPROFILE%\\.pb-appeon-index\\index.db"
)


def appeon_configured_note(db: str) -> str:
    return f"pb-appeon-index configured -> {db}"


def appeon_configured(db: str) -> list[Line]:
    """The database is referenced, never copied: one file serves every project."""
    return [Line(f"Appeon index      {db}", "green"), Line(_APPEON_REFERENCED)]


def appeon_missing(note: str) -> list[Line]:
    """Say what is missing and how to get it.

    A missing MCP server is an error nowhere: the failure is silent by
    nature, so the gap gets an actionable answer instead of a server that
    every new session reports as a mystery. The recipe clones — the old
    ``cd <source>`` assumed an installer running from a checkout, which is
    exactly what this port removed.
    """
    return [
        BLANK,
        Line(f"Note: {note}", "yellow"),
        Line("      The PowerScript reference lookups degrade to reading the"),
        Line("      database directly, or to web fetches. To build the index:"),
        Line(f"        git clone {REPO_URL}"),
        Line('        cd pb-ai-code ; uv venv ; uv pip install -e ".[dev]"'),
        Line(_APPEON_RECIPE_VENV),
        Line("      Then re-run this installer and the server is configured."),
    ]


# --- Tail (ledger 68) --------------------------------------------------------

DONE_LINE = "Done."
RESTART_HINT = (
    "Restart your assistant to pick up the MCP config, "
    "then confirm the pb_* tools are listed (/mcp)."
)


def done() -> list[Line]:
    return [BLANK, Line(DONE_LINE, "green")]


def restart_hint(hint: str) -> Line:
    """The adapter owns the text; :data:`RESTART_HINT` is claude-code's."""
    return Line(hint)


# --- The gitignore hint (ledger 71, 73) --------------------------------------

_GITIGNORE_BODY_1 = (
    "      The bundle is generated - update it by re-running pb-ai-code install, not by"
)
_GITIGNORE_BODY_2 = "      editing it - so it does not want committing. Suggested .gitignore lines:"


def gitignore_note(
    bundle_root: str,
    *,
    enclosing_repo: str | None = None,
    include_mcp_json: bool = False,
) -> list[Line]:
    """Five or six lines; only the ``Note:`` line is coloured.

    The suggested rule is printed **with** a trailing slash while the check
    that produced it queried **without** one — that asymmetry is the fix
    for the bug where ``git check-ignore -q -- '.claude/'`` matched a blank
    line in a CRLF ``.gitignore`` and silently reported the path ignored.

    ``enclosing_repo`` is set when the target is not itself the repository
    root: the advice is then about a parent's ``.gitignore``, and saying so
    is the difference between correct advice and confusing advice.
    """
    if enclosing_repo is None:
        first = f"Note: '{bundle_root}' is not ignored by git in this project."
    else:
        first = (
            f"Note: '{bundle_root}' is not ignored by git in {enclosing_repo}, "
            "the repository this target sits inside."
        )
    lines = [
        BLANK,
        Line(first, "yellow"),
        Line(_GITIGNORE_BODY_1),
        Line(_GITIGNORE_BODY_2),
        Line(f"        {bundle_root}/"),
    ]
    if include_mcp_json:
        lines.append(Line("        .mcp.json"))
    return lines


# --- status (ledger 77) ------------------------------------------------------


def status_text(
    *,
    running_version: str,
    target: str,
    marker_rel: str,
    installed_at: str,
    version: str,
    source: str,
    harness: str,
    mcp: str,
    appeon: str,
    contents_count: int,
    up_to_date: bool,
) -> list[Line]:
    """The human-readable form of ``pb-ai-code status``.

    ``--json`` prints ``json.dumps(obj, indent=2)`` and nothing else, which
    restores the house stream convention the install report deviates from.
    """
    return [
        Line(f"pb-ai-code {running_version} (running)"),
        Line(f"Target:    {target}"),
        Line(f"Marker:    {marker_rel}"),
        Line(f"Installed: {installed_at}"),
        Line(f"Version:   {version}"),
        Line(f"Source:    {source}"),
        Line(f"Harness:   {harness}"),
        Line(f"MCP:       {mcp}"),
        Line(f"Appeon:    {appeon}"),
        Line(f"Contents:  {contents_count} entries"),
        Line(f"Up to date: {'yes' if up_to_date else 'no'}"),
    ]


# --- Fatal messages (stderr) -------------------------------------------------
# One line, prefixed, no traceback. Everything below returns the message; the
# caller decides the exit code from the exception class.

ERROR_PREFIX = "pb-ai-code: "


def fatal(message: str, stream: TextIO | None = None) -> None:
    """Write ``pb-ai-code: <message>`` to stderr."""
    target = sys.stderr if stream is None else stream
    target.write(f"{ERROR_PREFIX}{message}\n")


def err_target_not_a_directory(path: str) -> str:
    """The target must exist. It is never created (ledger 8)."""
    return f"Target is not a directory: {path}"


def err_generic_requires_skills_dir() -> str:
    return "--harness generic requires --skills-dir (e.g. --skills-dir .agent/skills)"


def err_dir_must_be_target_relative(flag: str, value: str) -> str:
    """Absolute and drive-qualified values are refused, not "fixed".

    The PowerShell help promised absolute paths and ``Join-Path`` produced
    ``C:\\tgt\\D:\\abs\\skills``; Python's ``Path`` join would silently
    *implement* the promise and install outside the target. Neither the
    docs nor the code ever described an intended behaviour, so refusing is
    the only option that cannot surprise.
    """
    return f"{flag} must be relative to the target, not absolute: {value}"


def err_dir_escapes_target(flag: str, value: str) -> str:
    return f"{flag} must stay inside the target: {value}"


def err_dir_must_name_a_directory(flag: str, value: str) -> str:
    """``--skills-dir .`` resolves to the target itself, which has no bundle root."""
    return f"{flag} must name a directory below the target: {value!r}"


def err_dir_not_accepted(flag: str, harness: str) -> str:
    """``--skills-dir``/``--commands-dir`` are ignored by fixed layouts.

    Silently ignoring them is what the script did; refusing is the change.
    """
    return f"{flag} is not accepted with --harness {harness}, whose layout is fixed"


def err_commands_dir_not_sibling(commands_rel: str, skills_rel: str) -> str:
    """The installed commands link to ``../skills/<name>/SKILL.md``.

    That resolves only because commands and skills are siblings; a
    non-sibling pair produces two dead links that nothing validates.
    """
    return (
        f"--commands-dir must be a sibling of --skills-dir - the installed commands "
        f"link to ../skills/<name>/SKILL.md: {commands_rel} is not a sibling of {skills_rel}"
    )


def err_mcp_config_missing(path: str) -> str:
    return f"MCP server config missing: {path}"


def err_mcp_config_has_no_servers_key(path: str) -> str:
    return f"{path} has no 'mcpServers' key."


def err_source_skill_missing(path: str) -> str:
    return f"Source skill missing: {path}"


def err_source_command_missing(path: str) -> str:
    return f"Source command missing: {path}"


def err_source_docs_tree_missing(path: str) -> str:
    return f"Source docs tree missing: {path}"


def err_source_docs_file_missing(path: str) -> str:
    return f"Source docs file missing: {path}"


def err_harness_settings_missing(path: str) -> str:
    return f"Harness settings file missing: {path}"


def err_kit_not_found(searched: str) -> str:
    """Neither the packaged payload nor a checkout above this module."""
    return (
        "cannot find the pb-ai-code payload: no packaged _kit/ and no checkout "
        f"above {searched}. Reinstall the distribution, or run from a clone."
    )


def err_no_marker(target: str) -> str:
    return f"no pb-ai-code install found under {target}"
