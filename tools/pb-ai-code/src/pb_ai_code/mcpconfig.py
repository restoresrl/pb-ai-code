"""The MCP server block: canonical source, merge, outcomes, duplicate scan.

``harness/mcp-servers.json`` is the single source of truth for the server
set, whatever the dialect. The owned-key set is *data*, not code: adding a
second key to that file makes it appear in the target and in the outcome
list with no change here.

The merge is the most defensive code in the installer, and every defence
has a history:

* the target document is rewritten **whole** — every top-level key, every
  unowned server and both insertion orders survive; owned keys are
  replaced in place, new owned keys appended;
* the file is validated **strictly before parsing**, and anything that
  fails leaves it byte-for-byte untouched while the block is printed for a
  hand merge — because ``{ "mcpServers": { "broken": , } }`` was once
  rewritten with the user's half-typed value coerced away. ``json.loads``
  already rejects trailing commas and comments but **accepts**
  ``NaN``/``Infinity``, so :func:`strict_loads` passes a
  ``parse_constant`` that raises;
* whitespace-only content short-circuits to ``{}`` *ahead* of the strict
  parse, so a missing file, a zero-byte file and ``{"mcpServers": null}``
  all behave the same and none of them produces a "not valid JSON"
  warning;
* the target's **byte-order mark picks the decoding**, and the answer
  goes back as UTF-8 without one whatever went in. ``Get-Content -Raw``
  hands the bytes to a .NET reader with BOM detection on, so the script
  merged a UTF-8-BOM, UTF-16LE/BE or UTF-32LE/BE file cleanly and rewrote
  it UTF-8 - verified against pwsh 7.6 for all five marks.
  ``open(encoding="utf-8")`` would see ``\\ufeff`` and ``utf-8-sig`` alone
  sees NULs; either way a file with nothing wrong with it is refused,
  which is the failure this refuse-to-write path exists to avoid, one
  encoding over. ``>`` and ``Out-File`` in Windows PowerShell 5.1 default
  to UTF-16LE, so the shape is not hypothetical: it is what the shell
  these shops still have produces unless you ask it not to;
* owned keys are matched **casefolded** and rewritten to the canonical
  spelling. PowerShell's ordered dictionaries are case-insensitive by
  accident, and that accident is what stopped an existing ``PB-Orca``
  becoming a second ORCA server. A Python dict does the opposite. The
  canonical spelling matters too: ``harness/claude-code/settings.json``
  hard-codes ``mcp__pb-orca__*``, and a differently-cased key silently
  loses every permission allowance.

Only ``mcp_json`` is implemented. The other three dialects are listed so
whoever adds a harness has somewhere to put the emitter.
"""

from __future__ import annotations

import codecs
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

from . import PbAiCodeError
from . import report as report_mod

#: The only dialect implemented today.
DIALECT_MCP_JSON = "mcp_json"

#: Every dialect the adapter table names. The three unimplemented ones
#: raise ``NotImplementedError`` from :func:`emit` and :func:`merge`.
DIALECTS: tuple[str, ...] = ("mcp_json", "codex_toml", "opencode_json", "continue_yaml")

#: Top-level key of an ``mcp_json`` document.
SERVERS_KEY = "mcpServers"

#: Packages a *preserved* server may be running that we also install.
#: ``pb-appeon-index`` joins the list the script only ever had
#: ``pb-orca-mcp`` in: the loop shape already supported it, and the
#: allowlist argument applies to both.
OUR_PACKAGES: tuple[str, ...] = ("pb-orca-mcp", "pb-appeon-index")

#: The subset of :data:`OUR_PACKAGES` that ships *in this distribution*
#: rather than in ``harness/mcp-servers.json`` — ``pyproject.toml`` declares
#: ``pb-appeon-index`` as one of this project's console scripts, and the
#: entry :func:`pb_ai_code.appeon.server_entry` writes runs that script out
#: of this same repository. Ledger 42's self-check asks "does this kit still
#: install the package"; for these it is answered here, because the run's
#: own block is the wrong place to ask. ``pb-appeon-index`` reaches that
#: block only when the machine happens to have an index database (ledger
#: 49), so gating on it made the identical target warn on a machine with an
#: index and stay silent on the machine most likely to still be running a
#: hand-configured copy. Ledger 44's assert is unconditional; so is this.
ALWAYS_SHIPPED: frozenset[str] = frozenset({"pb-appeon-index"})

# --- Write mechanics (ledger 46). Bytes, exactly these. ----------------------
INDENT = 2
LINE_ENDING = "\r\n"
READ_ENCODING = "utf-8-sig"
WRITE_ENCODING = "utf-8"

#: Byte-order marks the *target's* file may carry, and the codec that
#: consumes each (ledger 38). Longest first: ``BOM_UTF32_LE`` starts with
#: ``BOM_UTF16_LE``, so testing UTF-16 first would decode a UTF-32LE file
#: into NULs and then refuse it. Unmarked bytes are UTF-8, which is what
#: :data:`READ_ENCODING` says.
_BOM_ENCODINGS: tuple[tuple[bytes, str], ...] = (
    (codecs.BOM_UTF32_LE, "utf-32"),
    (codecs.BOM_UTF32_BE, "utf-32"),
    (codecs.BOM_UTF16_LE, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16"),
)


class McpConfigError(PbAiCodeError):
    """The kit's own ``harness/mcp-servers.json`` is missing or malformed."""


class StrictJsonError(ValueError):
    """The *target's* config failed the strict parse. Never fatal."""


@dataclass(frozen=True)
class DuplicateServer:
    """A preserved server that runs one of our packages under another key."""

    name: str
    package: str


@dataclass(frozen=True)
class MergeResult:
    """The outcome of merging our block into a target document.

    ``text`` is the complete document to write, ``None`` when the existing
    file could not be parsed and must be left alone. ``wrote`` says
    whether the caller should write ``text``; it is false on exactly that
    refusal path. ``outcomes`` are the ``report.outcome_*`` tokens in the
    canonical block's key order, plus a single trailing ``kept:`` token in
    merged order when anything was preserved. ``warnings`` are the
    duplicate-server findings, which change neither the outcome list nor
    the exit code.
    """

    text: str | None
    outcomes: tuple[str, ...]
    warnings: tuple[DuplicateServer, ...]
    wrote: bool


def _require_mcp_json(dialect: str) -> None:
    """Only ``mcp_json`` exists. The other three are documented, not written."""
    if dialect != DIALECT_MCP_JSON:
        raise NotImplementedError(f"MCP dialect not implemented: {dialect}")


def load_servers(path: Path) -> dict[str, Any]:
    """Read ``harness/mcp-servers.json`` and return the ``mcpServers`` value.

    Raises :class:`McpConfigError` with ``report.err_mcp_config_missing``
    when the file is absent and ``report.err_mcp_config_has_no_servers_key``
    when the key is not there. Loaded lazily: ``--skip-mcp-config`` must
    not need this file at all, which is the fix for a latent bug where a
    missing file aborted the run *after* everything had been copied and
    *before* the marker was written.
    """
    if not path.is_file():
        raise McpConfigError(report_mod.err_mcp_config_missing(str(path)))
    document = json.loads(path.read_text(encoding=READ_ENCODING))
    servers = document.get(SERVERS_KEY) if isinstance(document, dict) else None
    # A key that is present but does not hold an object is the same failure
    # as an absent one, and it names the same file and the same key.
    if not isinstance(servers, dict):
        raise McpConfigError(report_mod.err_mcp_config_has_no_servers_key(str(path)))
    return dict(servers)


def _reject_constant(name: str) -> NoReturn:
    raise StrictJsonError(f"non-standard JSON constant: {name}")


def strict_loads(text: str) -> Any:
    """``json.loads`` with ``NaN``/``Infinity``/``-Infinity`` rejected.

    Raises :class:`StrictJsonError` for anything the strict grammar
    refuses: trailing commas, ``//`` and ``/* */`` comments, and the three
    non-standard constants Python accepts by default.
    """
    try:
        # object_pairs_hook=dict is explicit rather than incidental: the
        # merge preserves the target's insertion order, and that guarantee
        # should not rest on which hook json happens to default to.
        return json.loads(text, object_pairs_hook=dict, parse_constant=_reject_constant)
    except StrictJsonError:
        raise
    except ValueError as exc:  # json.JSONDecodeError and friends
        raise StrictJsonError(str(exc)) from exc


def _dumps(value: Any, *, ascii_only: bool = False) -> str:
    """The house serialisation: 2-space indent, arrays one element per line.

    ``ascii_only`` is **off** for the document written to disk. Ledger 46's
    promise is that a preserved server survives *verbatim*, and
    ``ensure_ascii=True`` breaks that where a user can see it: PowerShell
    wrote back ``C:/Users/Niccolo/tools/srv.exe`` with the accent it was
    given, this wrote ``Niccol\\u00f2``. The JSON value is identical and the
    file is still valid - and the user's own file has still changed shape
    under them, over a profile directory shaped like a good half of the
    machines this kit installs on.
    """
    return json.dumps(value, indent=INDENT, ensure_ascii=ascii_only)


def _compact(value: Any) -> str:
    """The blob the duplicate scan searches: no whitespace, key order kept."""
    return json.dumps(value, separators=(",", ":"))


def render_block(servers: Mapping[str, Any], dialect: str = DIALECT_MCP_JSON) -> str:
    """The block as printed on stdout: ``{"mcpServers": …}``, indent 2.

    Used by the ``generic`` harness's print-only path and by the
    hand-merge instruction after a strict-parse refusal - both of which a
    human copies off a console and pastes into a file of their own. It is
    the one caller that keeps ``ensure_ascii``, and the Appeon entry is why:
    it carries a database path, which on Windows is as likely as not to sit
    under an accented profile name, and ``\\u00f2`` survives a console
    codepage that the character itself does not. Same JSON value, and the
    block is still paste-able after the trip.
    """
    _require_mcp_json(dialect)
    return _dumps({SERVERS_KEY: dict(servers)}, ascii_only=True)


def _encode(text: str) -> bytes:
    """CRLF throughout, exactly one trailing newline, UTF-8 without a BOM."""
    body = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", LINE_ENDING)
    if not body.endswith(LINE_ENDING):
        body += LINE_ENDING
    return body.encode(WRITE_ENCODING)


def emit(servers: Mapping[str, Any], dialect: str = DIALECT_MCP_JSON) -> bytes:
    """The block as written to disk.

    ``mcp_json``: 2-space indent, arrays exploded one element per line,
    CRLF throughout, UTF-8 **without** a BOM, one trailing newline. No
    depth cap — the PowerShell serializer capped at 10 and silently
    truncated a deeply nested preserved server to a type-name string.

    Deliberately not :func:`render_block` encoded: what goes into a *file*
    is written verbatim, non-ASCII and all, exactly as the merged document
    is. The two differ in that one respect and in no other.
    """
    _require_mcp_json(dialect)
    return _encode(_dumps({SERVERS_KEY: dict(servers)}))


def read_config(path: Path) -> bytes | None:
    """The target's existing document, or ``None`` when there is no file."""
    if not path.is_file():
        return None
    return path.read_bytes()


def _decode(raw: bytes) -> str:
    """Decode the target's bytes the way ``Get-Content -Raw`` did (ledger 38).

    Raises ``UnicodeDecodeError`` for bytes no candidate codec accepts,
    which :func:`_parse_target` turns into the refuse-and-print path.
    """
    for bom, encoding in _BOM_ENCODINGS:
        if raw.startswith(bom):
            return raw.decode(encoding)
    return raw.decode(READ_ENCODING)


def _parse_target(existing: bytes | None) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """``(document, its mcpServers)``, or ``None`` to leave the file alone.

    ``None`` is the refusal path: undecodable bytes, a strict-parse
    failure, a document that is not an object, or a ``mcpServers`` that is
    not an object. The last one parses perfectly well and is still a
    refusal, because overwriting it is the one route by which a
    *parseable* file loses data.
    """
    if existing is None:
        return {}, {}
    try:
        text = _decode(existing)
    except UnicodeDecodeError:
        return None
    # Whitespace-only short-circuits ahead of the strict parse, so a zero-byte
    # file is not a "not valid JSON" warning.
    if not text.strip():
        return {}, {}
    try:
        document = strict_loads(text)
    except StrictJsonError:
        return None
    if not isinstance(document, dict):
        return None
    servers = document.get(SERVERS_KEY)
    if servers is None:
        # Absent and explicitly null behave identically.
        return document, {}
    if not isinstance(servers, dict):
        return None
    return document, dict(servers)


def _merge_servers(
    existing_servers: Mapping[str, Any],
    servers: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return ``(merged, previous)``.

    ``merged`` holds every preserved server in its original position, every
    owned key replaced **in place and under the canonical spelling**, and
    every new owned key appended. ``previous`` maps a canonical key to the
    value it displaced, so the caller can pick the outcome word.
    """
    by_fold = {name.casefold(): name for name in servers}
    merged: dict[str, Any] = {}
    previous: dict[str, Any] = {}
    for name, value in existing_servers.items():
        canonical = by_fold.get(name.casefold())
        if canonical is None:
            merged[name] = value
            continue
        if canonical in previous:
            # A second differently-cased copy of a key we own. Canonicalising
            # both would collide; the first position wins and the rest go.
            continue
        previous[canonical] = value
        merged[canonical] = servers[canonical]
    for name, value in servers.items():
        if name not in previous:
            merged[name] = value
    return merged, previous


def merge(
    existing: bytes | None,
    servers: Mapping[str, Any],
    dialect: str = DIALECT_MCP_JSON,
) -> MergeResult:
    """Pure merge. Decides the outcome words; writes nothing.

    ``already current`` is decided by **dict equality**, not by comparing
    compressed JSON strings: a server whose keys were reordered by hand is
    identical, the file is rewritten either way, and the honest word is
    ``already current``.

    ``{"mcpServers": "oops"}`` parses but is not an object. It routes to
    the untouched-and-print path rather than being overwritten — it is the
    one route by which a *parseable* file loses data, which is precisely
    what the strict parse defends against.

    A foreign server sitting on one of our keys is replaced with no
    warning; only ``(updated)`` shows. The duplicate scan walks the
    preserved keys only, so it cannot fire there. That asymmetry is
    intended: a copy under a *different* key earns five lines and
    survives, a foreign server under *our* key is destroyed in silence.
    """
    _require_mcp_json(dialect)
    parsed = _parse_target(existing)
    if parsed is None:
        return MergeResult(text=None, outcomes=(), warnings=(), wrote=False)
    document, existing_servers = parsed
    merged, previous = _merge_servers(existing_servers, servers)

    outcomes: list[str] = []
    for name in servers:
        if name not in previous:
            outcomes.append(report_mod.outcome_added(name))
        elif previous[name] == servers[name]:
            outcomes.append(report_mod.outcome_already_current(name))
        else:
            outcomes.append(report_mod.outcome_updated(name))
    kept = {name: value for name, value in merged.items() if name not in servers}
    if kept:
        outcomes.append(report_mod.outcome_kept(tuple(kept)))

    warnings = scan_for_duplicates(kept, servers)

    # Assigning back keeps `mcpServers` in its original position when the
    # target already had it, and appends it when it did not — which is what
    # preserves a sibling top-level key that sat ahead of it.
    document[SERVERS_KEY] = merged
    return MergeResult(
        text=_dumps(document),
        outcomes=tuple(outcomes),
        warnings=warnings,
        wrote=True,
    )


def preview(
    existing: bytes | None,
    servers: Mapping[str, Any],
    dialect: str = DIALECT_MCP_JSON,
) -> tuple[str, ...] | None:
    """What :func:`merge` would do, as ``report.would_*`` tokens.

    ``--dry-run`` was silent about exactly the two decisions a user wants
    previewed; this is one of them. An owned key that is already identical
    and every preserved server alike report ``would leave``, because
    neither changes.

    ``None`` is the refusal path, and it is deliberately **not** ``()``. An
    empty tuple means "the merge would do nothing worth a line"; ``None``
    means "the merge would decline to touch this file and print five lines
    saying so". Collapsing the two is how a dry run came to be silent about
    MCP against an unparseable target while the run it previews printed a
    WARN block and recorded a hand-merge instruction in the marker - the
    one shape where preview and outcome disagree most. The caller owes the
    user a line here; see :func:`pb_ai_code.report.mcp_unparseable` for the
    wording the real run uses.
    """
    _require_mcp_json(dialect)
    parsed = _parse_target(existing)
    if parsed is None:
        return None
    _, existing_servers = parsed
    merged, previous = _merge_servers(existing_servers, servers)
    actions: list[str] = []
    for name in servers:
        if name not in previous:
            actions.append(report_mod.would_add(name))
        elif previous[name] == servers[name]:
            actions.append(report_mod.would_leave(name))
        else:
            actions.append(report_mod.would_update(name))
    actions.extend(report_mod.would_leave(name) for name in merged if name not in servers)
    return tuple(actions)


def existing_server_names(existing: bytes | None) -> tuple[str, ...]:
    """The server keys the target already has, in file order.

    ``()`` when there is no file and when the file cannot be parsed — in
    the second case the merge refuses to touch it and nothing here is
    knowable. The Appeon report is the caller: an entry from an earlier
    install falls into ``kept`` and is written back untouched, so "NOT
    configured" alone would be a misleading thing to say about it.
    """
    parsed = _parse_target(existing)
    if parsed is None:
        return ()
    return tuple(parsed[1])


def _fold(text: str) -> str:
    """``_`` and ``-`` are the same character here, and case does not count."""
    return text.replace("_", "-").casefold()


def scan_for_duplicates(
    kept: Mapping[str, Any],
    owned: Mapping[str, Any],
) -> tuple[DuplicateServer, ...]:
    """Find preserved servers that run one of :data:`OUR_PACKAGES`.

    The blob searched is the compact JSON of the server's value **plus its
    key**, with ``_`` folded to ``-`` on both sides of the comparison, and
    the match is a plain case-insensitive substring. Both edits matter: a
    Python entry point is invoked as ``-m pb_orca_mcp``, with underscores,
    because that is the module name, and the stale configurations this
    warning exists for are the ones keyed ``pb-orca-mcp`` from before the
    key settled. Looking only for the hyphenated spelling inside the value
    misses both shapes that actually occur — and a warning that silently
    stops firing is worse than no warning.

    A guard checks this kit still installs the package, so the scan cannot
    fire on a kit that has stopped shipping it. For ``pb-orca-mcp`` that
    question is answered by ``owned`` - it comes from
    ``harness/mcp-servers.json``, which is where it can be removed. For the
    packages in :data:`ALWAYS_SHIPPED` it is answered by
    ``pyproject.toml``, so ``owned`` is not consulted: whether *this run*
    configured a server for them turns on whether the machine has an index
    database, which is not a fact about the kit.
    """
    ours = _fold(" ".join(_compact(value) for value in owned.values()))
    findings: list[DuplicateServer] = []
    for name, value in kept.items():
        blob = _fold(_compact(value) + " " + name)
        for package in OUR_PACKAGES:
            folded = _fold(package)
            if folded in blob and (package in ALWAYS_SHIPPED or folded in ours):
                findings.append(DuplicateServer(name=name, package=package))
    return tuple(findings)


def write_config(path: Path, text: str) -> None:
    """Write the merged document, creating the parent directory on demand."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_encode(text))


def canonical_key(name: str, owned: Sequence[str]) -> str | None:
    """The owned spelling of ``name``, matched casefolded; ``None`` if unowned."""
    folded = name.casefold()
    for candidate in owned:
        if candidate.casefold() == folded:
            return candidate
    return None
