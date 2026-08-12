"""The MCP merge, decision by decision: what it preserves and what it refuses.

Two incidents paid for this file. ``{ "mcpServers": { "broken": , } }`` was
once rewritten with the user's half-typed value coerced away, so the strict
parse now runs before anything is touched and a file that fails it is left
byte for byte alone (CHANGELOG 0.2.0, commit 5e16e6c). And the duplicate-ORCA
warning matched the hyphenated package name inside a server's *value* only,
so it missed the two spellings that actually occur - a Python entry point
invoked as ``-m pb_orca_mcp`` and a stale config keyed ``pb-orca-mcp`` - and
silently stopped firing on the very project it was written for (commit
0d9035c). A warning that stops firing is worse than no warning.

The merge is a pure function over bytes and dicts, so it is driven directly
here. The end-to-end ports, which cross the process boundary the way ``uvx``
will, live in ``test_mcp_install.py`` - with one exception at the bottom of
this file: the refusal block's *shape on stdout* cannot be seen from inside
the merge, which returns no text at all on that path, and the block is the
one the user has to read carefully because it is the hand-merge instruction.
It belongs next to ``test_ledger36_a_malformed_config_is_left_byte_identical``
and should move there.
"""

from __future__ import annotations

import codecs
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from pb_ai_code import appeon, kit, mcpconfig, report

# A stand-in for the canonical block: the same shape and the same package
# name, on a host that does not exist. Not the real URL, because
# `tests/test_pins_in_sync.py` reads every `github.com/restoresrl/<repo>@<ref>`
# in the tree - this file included - as a pin that must agree with every other
# one, and a pin written into a test breaks the day the real pin moves.
ORCA_ENTRY: dict[str, Any] = {
    "command": "uvx",
    "args": ["--from", "git+https://example.invalid/pb-orca-mcp", "pb-orca-mcp"],
}

#: What the installer owns, in the canonical block's key order.
OWNED: dict[str, Any] = {"pb-orca": ORCA_ENTRY}

POSTGRES: dict[str, Any] = {"command": "uvx", "args": ["mcp-server-postgres"]}
NODE: dict[str, Any] = {"command": "node", "args": ["server.js"]}

#: Every byte-order mark ``Get-Content -Raw`` decodes, with the codec that
#: produced it. Probed against pwsh 7.6.3: all five files parse.
BOMS: list[tuple[bytes, str, str]] = [
    (codecs.BOM_UTF8, "utf-8", "utf-8-bom"),
    (codecs.BOM_UTF16_LE, "utf-16-le", "utf-16le"),
    (codecs.BOM_UTF16_BE, "utf-16-be", "utf-16be"),
    (codecs.BOM_UTF32_LE, "utf-32-le", "utf-32le"),
    (codecs.BOM_UTF32_BE, "utf-32-be", "utf-32be"),
]


def _document(payload: dict[str, Any]) -> bytes:
    """A target ``.mcp.json`` as bytes, insertion order preserved."""
    return json.dumps(payload, indent=2).encode("utf-8")


def _written(result: mcpconfig.MergeResult) -> dict[str, Any]:
    assert result.text is not None, "the merge refused to write"
    return json.loads(result.text)


# --- The canonical source (ledger 31) ----------------------------------------


def test_ledger31_the_server_set_is_data_not_code(tmp_path: Path) -> None:
    """Ledger 31: the servers come from `harness/mcp-servers.json`, and only there.

    Adding a key to that one file is the entire procedure for adding a
    server: it reaches the target and the outcome list with no code change.
    """
    servers = mcpconfig.load_servers(kit.load_kit().mcp_servers_file)
    assert "pb-orca" in servers

    extended = tmp_path / "mcp-servers.json"
    extended.write_text(
        json.dumps({"mcpServers": {**servers, "second": NODE}}, indent=2), encoding="utf-8"
    )
    loaded = mcpconfig.load_servers(extended)
    assert list(loaded) == [*servers, "second"]

    result = mcpconfig.merge(None, loaded)
    assert result.outcomes == tuple(report.outcome_added(name) for name in loaded)
    assert list(_written(result)["mcpServers"]) == list(loaded)


def test_ledger31_a_missing_or_keyless_source_names_the_file(tmp_path: Path) -> None:
    """Ledger 31: both failures name the path, and the second names the key."""
    missing = tmp_path / "nowhere.json"
    with pytest.raises(mcpconfig.McpConfigError) as absent:
        mcpconfig.load_servers(missing)
    assert str(absent.value) == report.err_mcp_config_missing(str(missing))

    keyless = tmp_path / "mcp-servers.json"
    keyless.write_text('{"servers": {}}', encoding="utf-8")
    with pytest.raises(mcpconfig.McpConfigError) as no_key:
        mcpconfig.load_servers(keyless)
    assert str(no_key.value) == report.err_mcp_config_has_no_servers_key(str(keyless))


# --- What survives a merge (ledger 34, 35, 45) -------------------------------


def test_ledger34_every_top_level_key_and_both_orders_survive() -> None:
    """Ledger 34: the whole document is rewritten and nothing in it moves.

    A target's `.mcp.json` is the user's file. The merge replaces owned keys
    in place, appends new ones, and touches nothing else - including the
    position of a sibling top-level key that sat ahead of `mcpServers`.
    """
    existing = _document(
        {
            "someTopLevelKey": {"kept": True},
            "mcpServers": {"postgres": POSTGRES},
            "zed": 1,
        }
    )
    result = mcpconfig.merge(existing, OWNED)
    assert result.wrote

    document = _written(result)
    assert list(document) == ["someTopLevelKey", "mcpServers", "zed"]
    assert document["someTopLevelKey"] == {"kept": True}
    assert document["zed"] == 1
    assert list(document["mcpServers"]) == ["postgres", "pb-orca"]
    assert document["mcpServers"]["postgres"] == POSTGRES


def test_ledger35_an_owned_key_is_matched_casefolded_and_written_canonically() -> None:
    """Ledger 35 / C9: `PB-Orca` is updated in place and respelled `pb-orca`.

    A Python dict would have manufactured a second ORCA server - the exact
    fault the duplicate warning exists to catch - and the canonical spelling
    is load-bearing on its own: `harness/claude-code/settings.json` hard-codes
    `mcp__pb-orca__*`, so a differently-cased key voids every allowance.
    """
    existing = _document({"mcpServers": {"PB-Orca": {"command": "old"}, "keepme": NODE}})
    result = mcpconfig.merge(existing, OWNED)

    servers = _written(result)["mcpServers"]
    assert list(servers) == ["pb-orca", "keepme"]
    assert "PB-Orca" not in servers
    assert servers["pb-orca"] == ORCA_ENTRY
    assert report.join_outcomes(result.outcomes) == "pb-orca (updated); kept: keepme"

    assert mcpconfig.canonical_key("PB-ORCA", tuple(OWNED)) == "pb-orca"
    assert mcpconfig.canonical_key("postgres", tuple(OWNED)) is None


def test_ledger45_a_foreign_server_on_our_key_is_replaced_in_silence() -> None:
    """Ledger 45: only `(updated)` shows; the duplicate scan walks kept keys only.

    The asymmetry is intended and worth pinning: a copy of our server under a
    *different* key earns five lines and survives, a stranger under *our* key
    is destroyed without a word.
    """
    existing = _document({"mcpServers": {"pb-orca": {"command": "node", "args": ["mine.js"]}}})
    result = mcpconfig.merge(existing, OWNED)

    assert result.outcomes == (report.outcome_updated("pb-orca"),)
    assert result.warnings == ()
    assert _written(result)["mcpServers"]["pb-orca"] == ORCA_ENTRY


# --- Files that are not really files (ledger 37, 38) -------------------------


@pytest.mark.parametrize(
    "existing",
    [
        pytest.param(None, id="no-file"),
        pytest.param(b"", id="zero-byte"),
        pytest.param(b"   \r\n\t  \r\n", id="whitespace-only"),
        pytest.param(b'{"mcpServers": null}', id="null-servers"),
    ],
)
def test_ledger37_absent_empty_and_null_configs_all_merge(existing: bytes | None) -> None:
    """Ledger 37: none of the three is a parse failure, and none warns.

    Whitespace-only content short-circuits to `{}` *ahead* of the strict
    parse, which is why a zero-byte file does not print `not valid JSON` at a
    user who has an empty file and no problem.
    """
    result = mcpconfig.merge(existing, OWNED)
    assert result.wrote
    assert list(_written(result)["mcpServers"]) == ["pb-orca"]
    assert result.outcomes == (report.outcome_added("pb-orca"),)


def test_ledger37_a_null_servers_key_keeps_its_siblings() -> None:
    """Ledger 37: an explicit null behaves exactly like an absent key."""
    result = mcpconfig.merge(_document({"other": 1, "mcpServers": None}), OWNED)
    document = _written(result)
    assert document["other"] == 1
    assert list(document["mcpServers"]) == ["pb-orca"]


@pytest.mark.parametrize(
    ("bom", "codec"),
    [pytest.param(bom, codec, id=name) for bom, codec, name in BOMS],
)
def test_ledger38_the_bom_picks_the_decoding_and_never_survives(
    bom: bytes, codec: str, tmp_path: Path
) -> None:
    """Ledger 38: a marked but perfectly good config merges, and comes back bare.

    ``Get-Content -Raw`` hands the bytes to a reader with BOM detection on, so
    all five of these merged in PowerShell and were rewritten as UTF-8.
    ``open(encoding="utf-8")`` would see the UTF-8 mark and fail; ``utf-8-sig``
    alone gets past that one and sees NULs for the other four. Either way the
    installer refuses a file with nothing wrong with it - the exact failure
    this path exists to prevent, one encoding over. ``>`` and ``Out-File`` in
    Windows PowerShell 5.1 write UTF-16LE by default, which is the shell the
    shops running this kit still have.
    """
    payload = _document({"mcpServers": {"postgres": POSTGRES}}).decode("utf-8")
    result = mcpconfig.merge(bom + payload.encode(codec), OWNED)

    assert result.wrote, "a good config was refused over the encoding it was saved in"
    assert list(_written(result)["mcpServers"]) == ["postgres", "pb-orca"]

    path = tmp_path / ".mcp.json"
    assert result.text is not None
    mcpconfig.write_config(path, result.text)

    raw = path.read_bytes()
    assert raw.startswith(b"{"), "a byte-order mark was written back"
    assert json.loads(raw.decode("utf-8"))["mcpServers"]["postgres"] == POSTGRES


def test_ledger38_bytes_no_codec_accepts_are_still_a_refusal() -> None:
    """Ledger 38: the BOM promises an encoding; broken bytes keep the old answer.

    A truncated UTF-16 file is undecodable, not unparseable, and it has to
    land on the same refuse-and-print path rather than raise out of the merge.
    """
    result = mcpconfig.merge(codecs.BOM_UTF16_LE + b"{", OWNED)
    assert result.text is None
    assert not result.wrote


# --- The strict parse (ledger 36, 39) ----------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param('{ "mcpServers": { "broken": , } }', id="half-typed-value"),
        pytest.param('{"mcpServers": {"a": {"command": "node"},}}', id="trailing-comma"),
        pytest.param('{\n  // mine\n  "mcpServers": {}\n}', id="line-comment"),
        pytest.param('{ /* mine */ "mcpServers": {} }', id="block-comment"),
        pytest.param('{"mcpServers": {"a": {"weight": NaN}}}', id="nan"),
        pytest.param('{"mcpServers": {"a": {"weight": -Infinity}}}', id="infinity"),
    ],
)
def test_ledger36_a_file_that_fails_the_strict_parse_is_never_written(raw: str) -> None:
    """Ledger 36: refuse, print, continue. The file is the user's, not ours.

    The half-typed case is the one that happened: the value was coerced away
    and the file rewritten. Trailing commas and comments `json.loads` already
    refuses; `NaN` and `Infinity` it accepts, which is why there is a
    `parse_constant` guard to lose.
    """
    result = mcpconfig.merge(raw.encode("utf-8"), OWNED)
    assert result.text is None
    assert not result.wrote
    assert result.outcomes == ()
    assert result.warnings == ()


def test_ledger36_the_non_standard_constants_are_the_ones_python_accepts() -> None:
    """Ledger 36: the stdlib parses `NaN`; the strict wrapper must not."""
    assert math.isnan(json.loads('{"a": NaN}')["a"])
    with pytest.raises(mcpconfig.StrictJsonError):
        mcpconfig.strict_loads('{"a": NaN}')


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param('{"mcpServers": "oops", "other": 1}', id="servers-is-a-string"),
        pytest.param('{"mcpServers": [1, 2], "other": 1}', id="servers-is-an-array"),
        # The same failure one level up: PowerShell iterated the keys of an
        # array, found none, and rewrote the document as `{"mcpServers": ...}`
        # with the user's array gone.
        pytest.param("[1, 2]", id="document-is-an-array"),
        pytest.param('"a string"', id="document-is-a-string"),
    ],
)
def test_ledger39_a_parseable_document_that_is_not_a_config_is_left_alone(raw: str) -> None:
    """Ledger 39: the one route by which a *parseable* file could lose data."""
    result = mcpconfig.merge(raw.encode("utf-8"), OWNED)
    assert result.text is None
    assert not result.wrote


# --- The outcome vocabulary (ledger 40, 41) ----------------------------------


def test_ledger40_added_then_already_current_then_updated_then_kept() -> None:
    """Ledger 40: one token per owned key, plus one trailing `kept:`.

    The four words are what an agent reads to find out what happened, and
    nothing asserted any of them before this test.
    """
    first = mcpconfig.merge(None, OWNED)
    assert first.outcomes == ("pb-orca (added)",)
    assert first.text is not None

    second = mcpconfig.merge(first.text.encode("utf-8"), OWNED)
    assert second.outcomes == ("pb-orca (already current)",)

    stale = _document(
        {
            "mcpServers": {
                "pb-orca": {"command": "uvx", "args": ["--from", "old", "pb-orca-mcp"]},
                "postgres": POSTGRES,
            }
        }
    )
    third = mcpconfig.merge(stale, OWNED)
    assert third.outcomes == ("pb-orca (updated)", "kept: postgres")
    assert report.join_outcomes(third.outcomes) == "pb-orca (updated); kept: postgres"


def test_ledger41_a_key_reordered_server_reports_already_current() -> None:
    """Ledger 41 / C8: dict equality, not a compressed-string comparison.

    The file is rewritten either way; the comparison only picks a word, and
    the honest word for a server somebody reformatted is `already current`.
    """
    document = _written(mcpconfig.merge(None, OWNED))
    entry = document["mcpServers"]["pb-orca"]
    reordered = dict(reversed(list(entry.items())))
    assert list(reordered) != list(entry)
    document["mcpServers"]["pb-orca"] = reordered

    result = mcpconfig.merge(json.dumps(document, indent=2).encode("utf-8"), OWNED)
    assert result.outcomes == (report.outcome_already_current("pb-orca"),)


def test_ledger75_preview_says_what_the_merge_would_do() -> None:
    """Ledger 75: `--dry-run` was silent about the one decision worth previewing."""
    assert mcpconfig.preview(None, OWNED) == (report.would_add("pb-orca"),)

    current = mcpconfig.merge(None, OWNED)
    assert current.text is not None
    assert mcpconfig.preview(current.text.encode("utf-8"), OWNED) == (
        report.would_leave("pb-orca"),
    )

    mixed = _document({"mcpServers": {"pb-orca": {"command": "old"}, "postgres": POSTGRES}})
    assert mcpconfig.preview(mixed, OWNED) == (
        report.would_update("pb-orca"),
        report.would_leave("postgres"),
    )
    # A refusal is not the same as nothing to say, and collapsing the two is
    # how `--dry-run` came to be silent about MCP against a file the real run
    # prints a five-line WARN block about. `()` means "nothing worth a line".
    assert mcpconfig.preview(None, {}) == ()
    assert mcpconfig.preview(b"{ oops", OWNED) is None
    assert mcpconfig.preview(b'{"mcpServers": "oops"}', OWNED) is None


def test_ledger52_existing_server_names_reads_the_target_once() -> None:
    """Ledger 52: what the Appeon note needs to know, in file order."""
    assert mcpconfig.existing_server_names(None) == ()
    assert mcpconfig.existing_server_names(b"{ broken") == ()
    assert mcpconfig.existing_server_names(
        _document({"mcpServers": {"a": NODE, "pb-appeon-index": NODE}})
    ) == ("a", "pb-appeon-index")


# --- Write mechanics (ledger 46, 47) -----------------------------------------


def test_ledger46_write_mechanics_are_bytes_not_preferences(tmp_path: Path) -> None:
    """Ledger 46: 2-space indent, CRLF, UTF-8 without a BOM, one trailing newline.

    Also: the parent directory is created on demand, because a project may
    have no `.claude/` yet when the config it names goes in beside it.
    """
    result = mcpconfig.merge(None, OWNED)
    assert result.text is not None
    path = tmp_path / "made" / "on" / "demand" / ".mcp.json"
    mcpconfig.write_config(path, result.text)

    raw = path.read_bytes()
    assert not raw.startswith(codecs.BOM_UTF8)
    assert b"\r\n" in raw
    assert raw.count(b"\n") == raw.count(b"\r\n"), "a bare LF got in"
    assert raw.endswith(b"\r\n")
    assert not raw.endswith(b"\r\n\r\n")
    assert b'\r\n  "mcpServers": {\r\n' in raw

    # Arrays exploded one element per line - the shape a human reads when the
    # merge lands in a file they own.
    text = raw.decode("utf-8")
    for arg in ORCA_ENTRY["args"]:
        assert f'\r\n        "{arg}"' in text


def test_ledger46_a_deeply_nested_preserved_server_survives_verbatim() -> None:
    """Ledger 46: the PowerShell serializer capped at depth 10 and truncated.

    Past the cap the value became the *name of its type*, silently, inside a
    server the merge had promised to preserve.
    """
    deep: dict[str, Any] = {"leaf": "bottom"}
    for level in range(12):
        deep = {f"level{level}": deep}
    existing = _document({"mcpServers": {"nested": {"command": "node", "config": deep}}})

    result = mcpconfig.merge(existing, OWNED)
    assert _written(result)["mcpServers"]["nested"]["config"] == deep


def test_ledger46_a_preserved_server_keeps_its_own_characters(tmp_path: Path) -> None:
    """Ledger 46: "survives verbatim" is about bytes a user recognises.

    ``ensure_ascii=True`` is faithful JSON and an infidelity to the promise:
    PowerShell wrote the accented path back the way it was typed, and an
    accented Windows profile directory is the normal case, not the exotic
    one. The value is identical either way; the user's own file is not.
    """
    server = {"command": "C:/Users/Niccolò/tools/srv.exe", "args": ["cafè"]}
    result = mcpconfig.merge(_document({"mcpServers": {"niccolo": server}}), OWNED)

    assert result.text is not None
    assert "Niccolò" in result.text
    assert "\\u00f2" not in result.text

    path = tmp_path / ".mcp.json"
    mcpconfig.write_config(path, result.text)
    raw = path.read_bytes()
    assert "Niccolò".encode() in raw, "the file is UTF-8; the character belongs in it"
    assert json.loads(raw.decode("utf-8"))["mcpServers"]["niccolo"] == server


def test_ledger46_the_printed_block_escapes_because_a_console_is_not_a_file() -> None:
    """Ledger 46: the one caller that keeps `ensure_ascii`, and why.

    The hand-merge block is copied off a console whose codepage is very
    probably not UTF-8 and pasted into a file by hand. The Appeon entry
    carries a database path that may well sit under an accented profile
    name, and `\\u00f2` makes that trip where the character does not.
    """
    entry = {"env": {"PB_APPEON_INDEX_DB": "C:/Users/Niccolò/index.db"}}
    block = mcpconfig.render_block({"pb-appeon-index": entry})

    assert "\\u00f2" in block
    assert "Niccolò" not in block
    assert json.loads(block) == {"mcpServers": {"pb-appeon-index": entry}}
    # What goes into a file does not escape, even through `emit`.
    assert "Niccolò".encode() in mcpconfig.emit({"pb-appeon-index": entry})


def test_ledger47_the_printed_block_is_the_written_block() -> None:
    """Ledger 47: the `generic` harness prints what the merge would have written."""
    block = mcpconfig.render_block(OWNED)
    assert json.loads(block) == {"mcpServers": OWNED}
    assert block.startswith('{\n  "mcpServers": {\n    "pb-orca": {')
    assert mcpconfig.emit(OWNED).endswith(b"\r\n")


# --- The duplicate-ORCA scan (ledger 42, 43, 44) -----------------------------


@pytest.mark.parametrize(
    ("name", "entry"),
    [
        # The two shapes `tests/test_installer_mcp_merge.py` pins against the
        # PowerShell installer, ported unchanged: the key is the old one and
        # the module is spelled the only way Python spells it, then a key
        # nobody would guess with the package named in a URL instead.
        pytest.param(
            "pb-orca-mcp",
            {"command": "python.exe", "args": ["-m", "pb_orca_mcp"]},
            id="underscored-module",
        ),
        pytest.param(
            "orca",
            {
                "command": "python.exe",
                "args": ["--from", "git+https://example.invalid/pb-orca-mcp", "pb-orca-mcp"],
            },
            id="package-in-a-url",
        ),
        # A bare path component - no package name anywhere but the filesystem.
        pytest.param(
            "py",
            {"command": "C:/tools/pb_orca_mcp/venv/python.exe", "args": []},
            id="bare-path",
        ),
        # Only the key names it; the value is unrecognisable.
        pytest.param("PB_ORCA_MCP", dict(NODE), id="key-only-and-uppercase"),
    ],
)
def test_ledger42_43_the_duplicate_scan_catches_every_shape_that_occurs(
    name: str, entry: dict[str, Any]
) -> None:
    """Ledger 42, 43: key in the blob, `_` folded to `-`, case-insensitive.

    Two ORCA servers means two processes competing for a single-session
    library, duplicate tools under different prefixes, and only one of them
    matching the permission allowlist. The duplicate is *never* removed: it
    is the user's file.
    """
    existing = _document({"mcpServers": {"some-other-server": NODE, name: entry}})
    result = mcpconfig.merge(existing, OWNED)

    assert result.warnings == (mcpconfig.DuplicateServer(name=name, package="pb-orca-mcp"),)

    servers = _written(result)["mcpServers"]
    assert servers[name] == entry, "the duplicate was modified; it must be left in place"
    assert result.outcomes == (
        report.outcome_added("pb-orca"),
        report.outcome_kept(("some-other-server", name)),
    ), "the warning changed the outcome list"


def test_ledger42_unrelated_servers_never_trigger_the_warning() -> None:
    """Ledger 42: a project that simply has other servers hears nothing."""
    existing = _document({"mcpServers": {"some-other-server": NODE, "postgres": POSTGRES}})
    assert mcpconfig.merge(existing, OWNED).warnings == ()


def test_ledger42_the_scan_is_silent_when_our_own_block_stops_naming_the_package() -> None:
    """Ledger 42: the `$ourPackages` self-check, so the warning cannot outlive the kit."""
    kept = {"orca": {"command": "python.exe", "args": ["-m", "pb_orca_mcp"]}}
    assert mcpconfig.scan_for_duplicates(kept, OWNED)
    assert mcpconfig.scan_for_duplicates(kept, {"pb-orca": dict(NODE)}) == ()


def test_ledger44_the_scan_covers_the_appeon_index_too(tmp_path: Path) -> None:
    """Ledger 44: the scanned list was literally `@('pb-orca-mcp')`.

    It predates the second server; the loop shape already supported both and
    the allowlist argument applies to both.
    """
    db = tmp_path / "index.db"
    db.write_bytes(b"")
    kept = {"docs": {"command": "python", "args": ["-m", "pb_appeon_index"]}}

    with_appeon = {**OWNED, appeon.SERVER_KEY: appeon.server_entry(db)}
    assert mcpconfig.scan_for_duplicates(kept, with_appeon) == (
        mcpconfig.DuplicateServer(name="docs", package="pb-appeon-index"),
    )
    # The same target on a machine with no index database, where the entry
    # never reaches our own block. Ledger 42's self-check asks whether the kit
    # still installs the package; `pyproject.toml` answers that for this one,
    # and the answer does not change with the machine. Gating on the run's own
    # block made the identical target warn here and stay silent there - and
    # "there" is the machine most likely to still be running a hand-configured
    # copy of the server.
    assert mcpconfig.scan_for_duplicates(kept, OWNED) == (
        mcpconfig.DuplicateServer(name="docs", package="pb-appeon-index"),
    )
    assert appeon.SERVER_KEY in mcpconfig.ALWAYS_SHIPPED


# --- The refusal block on stdout (ledger 67) ---------------------------------


def _install_into(target: Path) -> subprocess.CompletedProcess[str]:
    """One real install, on a machine with no Appeon index.

    The only test in this file that crosses the process boundary: the shape
    of the refusal block is not visible from inside a merge that returns no
    text. Kept small on purpose - `test_mcp_install.py` owns the general
    end-to-end machinery and this should join it.
    """
    home = target.parent / "home"
    home.mkdir(exist_ok=True)
    result = subprocess.run(
        [sys.executable, "-m", "pb_ai_code", "install", "--target", str(target)],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PB_APPEON_INDEX_DB": str(home / "no-such-index.db"),
            "USERPROFILE": str(home),
            "HOME": str(home),
            "PYTHONIOENCODING": "utf-8",
        },
    )
    assert result.returncode == 0, f"install failed:\n{result.stdout}\n{result.stderr}"
    return result


def test_ledger67_the_refusal_block_is_wrapped_in_blanks_and_precedes_the_outcome(
    tmp_path: Path,
) -> None:
    """Ledger 67: both warning blocks print from inside the merge, on stdout.

    The duplicate-ORCA block has this pinned exactly; this one was asserted
    by substring only, so its leading blank, the blank after the JSON, its
    stream and its position could all have moved unnoticed. It is the block
    that matters most: it is a hand-merge instruction, and a user reading it
    needs to see where the JSON they must copy starts and stops.
    """
    target = tmp_path / "project"
    target.mkdir()
    (target / ".mcp.json").write_text('{ "mcpServers": { "broken": , } }', encoding="utf-8")

    result = _install_into(target)

    assert result.stderr == "", "the whole report is one stream, and a warning is not stderr"
    lines = result.stdout.splitlines()
    warn = next(i for i, line in enumerate(lines) if line.startswith("WARN: ") and "JSON" in line)

    # The whole block, both blanks included: a leading one, the WARN, the
    # hand-merge instruction, the JSON to copy, and a trailing one so the
    # closing brace is not glued to the next line of the report. The block's
    # own lines are taken from the output rather than rebuilt - `pb-appeon-index`
    # is in it only when this machine has an index - and then checked to be
    # the servers this kit installs.
    close = lines.index("}", warn)
    block = "\n".join(lines[warn + 2 : close + 1])
    assert lines[warn - 1 : close + 2] == [
        line.text for line in report.mcp_unparseable(str(target / ".mcp.json"), block)
    ]
    assert "pb-orca" in json.loads(block)[mcpconfig.SERVERS_KEY]

    # Position: inside the MCP step, where the outcome line would have been.
    # There is no `Installed mcp` line to precede here - this block stands in
    # for it, which is the whole of what "left it untouched" means.
    rewrote = next(i for i, line in enumerate(lines) if line.startswith("Rewrote knowledge-base"))
    assert rewrote < warn < lines.index("Done."), "the block moved out of the MCP step"
    assert not any(line.startswith("Installed mcp") for line in lines), (
        "an outcome line was printed for a file the merge refused to write"
    )
