"""Finding the Appeon documentation index, and saying so either way.

A missing MCP server is an error nowhere: nothing fails, the PowerScript
reference lookups just quietly degrade to web fetches costing thousands of
tokens a page. That is why both branches report, why the same note goes into
the marker, and why this file tests the branch that finds nothing as hard as
the branch that finds something.

The database is **referenced, never copied**. Copying it gave N stale copies
instead of one live file (CHANGELOG 0.4.0), so rebuilding the index once has
to update every project already configured, with no re-install.

The discovery order is per-machine, so the unit tests own the home directory
they read: `os.path.expanduser` consults `USERPROFILE`/`HOME` on every call,
and a test that did not set them would answer differently on the machine of
anyone who has built an index.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

import pb_ai_code
from pb_ai_code import REPO_URL, VCS_URL, appeon, kit, marker, mcpconfig, report

CLAUDE_MARKER = (".claude", "_installed-from-pb-ai-code.txt")

REPO_ROOT = Path(__file__).resolve().parents[3]

#: The package under test, wherever it is installed from - a staged kit
#: carries *this* one, so the tests follow the code they run.
PACKAGE_DIR = Path(pb_ai_code.__file__).resolve().parent

#: Everything the wheel's force-include table maps into the payload.
#: Duplicated from the sibling test modules on purpose: three test packages
#: in this repository are called `tests`, so a relative import binds to
#: whichever one pytest imported first, and a conftest.py here is shared
#: ground. A short copy is the cheaper of the two evils.
PAYLOAD_TREES = ("skills", "commands", "harness", "docs/pb-antipatterns", "docs/pb-source-format")
PAYLOAD_FILES = ("docs/wiki-notes.md",)


def _stage_kit(root: Path) -> Path:
    """A throwaway checkout: the payload, plus the package under test.

    The third step of the discovery order reads
    ``<checkout>/docs/appeon-index/index.db``, and on a developer's machine
    that file exists - the index is gitignored, built locally, and no flag
    turns the step off. Pointing the run at a checkout that has no index is
    the only way to reach the branch that finds nothing, and it is why this
    module stages one instead of skipping.
    """
    for rel in PAYLOAD_TREES:
        shutil.copytree(REPO_ROOT / rel, root.joinpath(*rel.split("/")))
    for rel in PAYLOAD_FILES:
        dst = root.joinpath(*rel.split("/"))
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / rel, dst)
    shutil.copytree(
        PACKAGE_DIR,
        root / "tools" / "pb-ai-code" / "src" / "pb_ai_code",
        ignore=shutil.ignore_patterns("__pycache__", "_kit"),
    )
    return root


def _run(
    *args: str, env: dict[str, str] | None = None, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pb_ai_code", *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=None if cwd is None else str(cwd),
    )


def _install(
    target: Path, *extra: str, env: dict[str, str] | None = None, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    result = _run("install", "--target", str(target), *extra, env=env, cwd=cwd)
    assert result.returncode == 0, f"install failed:\n{result.stdout}\n{result.stderr}"
    return result


def _fields(target: Path) -> marker.MarkerFields:
    return marker.parse(target.joinpath(*CLAUDE_MARKER).read_text(encoding="utf-8-sig"))


def _servers(config: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(config.read_text(encoding="utf-8-sig"))
    servers: dict[str, Any] = document["mcpServers"]
    return servers


def _env(**overrides: str) -> dict[str, str]:
    """The current environment plus overrides, for a subprocess."""
    return {**os.environ, **overrides}


def _own_the_home(monkeypatch: pytest.MonkeyPatch, home: Path) -> None:
    """Point ``Path.home()`` at a directory the test owns."""
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("HOMEDRIVE", raising=False)
    monkeypatch.delenv("HOMEPATH", raising=False)


def _plant(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"SQLite format 3\x00")
    return path


# --- Discovery (ledger 49) ---------------------------------------------------


def test_ledger49_an_explicit_database_beats_every_guess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ledger 49: `PB_APPEON_INDEX_DB` is answered verbatim, and answered first."""
    home = tmp_path / "home"
    _own_the_home(monkeypatch, home)
    _plant(home.joinpath(*appeon.USER_DB_REL))
    checkout = tmp_path / "checkout"
    _plant(checkout.joinpath(*appeon.CHECKOUT_DB_REL))
    explicit = _plant(tmp_path / "elsewhere" / "index.db")

    found = appeon.find_index_db(
        kit.Kit(root=checkout, is_checkout=True), environ={appeon.ENV_VAR: str(explicit)}
    )
    assert found == explicit


def test_ledger49_an_environment_variable_naming_nothing_falls_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ledger 49: a stale variable must not disable the two locations behind it."""
    home = tmp_path / "home"
    _own_the_home(monkeypatch, home)
    user_db = _plant(home.joinpath(*appeon.USER_DB_REL))
    checkout = tmp_path / "checkout"
    _plant(checkout.joinpath(*appeon.CHECKOUT_DB_REL))

    found = appeon.find_index_db(
        kit.Kit(root=checkout, is_checkout=True),
        environ={appeon.ENV_VAR: str(tmp_path / "gone.db")},
    )
    assert found == user_db, "the per-user database is the second step of the order"


def test_ledger49_the_checkout_is_the_last_resort_and_only_from_a_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ledger 49: a wheel installed by uvx has no clone, so branch three is gated."""
    _own_the_home(monkeypatch, tmp_path / "empty-home")
    checkout = tmp_path / "checkout"
    checkout_db = _plant(checkout.joinpath(*appeon.CHECKOUT_DB_REL))

    assert appeon.find_index_db(kit.Kit(root=checkout, is_checkout=True), environ={}) == checkout_db
    assert appeon.find_index_db(kit.Kit(root=checkout, is_checkout=False), environ={}) is None


def test_ledger49_a_tilde_or_a_relative_value_is_expanded_not_taken_verbatim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ledger 49: the block spells the value `<abs db>`, so verbatim is not enough.

    Two shapes, one cause. A `~` value named no file at all and fell silently
    through to the per-user location behind it; a relative one was answered as
    given and written into a server entry that an MCP client launches with a
    working directory nobody here chooses. The script could not produce
    either - it joined the path onto `$source` (ps1:481).
    """
    home = tmp_path / "home"
    _own_the_home(monkeypatch, home)
    tilde_db = _plant(home / "indexes" / "index.db")
    nowhere = kit.Kit(root=tmp_path / "kit", is_checkout=False)

    found = appeon.find_index_db(nowhere, environ={appeon.ENV_VAR: "~/indexes/index.db"})
    assert found == tilde_db

    monkeypatch.chdir(tmp_path)
    relative_db = _plant(tmp_path / "beside-me" / "index.db")
    answer = appeon.find_index_db(nowhere, environ={appeon.ENV_VAR: "beside-me/index.db"})
    assert answer is not None
    assert answer.is_absolute(), "a relative path resolves against a cwd we do not own"
    assert answer.samefile(relative_db)


def test_ledger49_nothing_anywhere_is_a_none_not_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ledger 49: absence is the normal case on a fresh machine, not an error."""
    _own_the_home(monkeypatch, tmp_path / "empty-home")
    empty = kit.Kit(root=tmp_path / "kit", is_checkout=True)
    assert appeon.find_index_db(empty, environ={}) is None


# --- The written entry (ledger 49, 50) ---------------------------------------


def test_ledger49_50_the_server_entry_points_at_the_database_it_found(tmp_path: Path) -> None:
    """Ledger 49, 50: `uvx` runs `serve-mcp`, and the path is the one found.

    The entry is written into the target's generated, gitignored `.mcp.json`
    - which is per-machine by construction, so an absolute path belongs in it.
    `harness/mcp-servers.json` could not carry this server for exactly that
    reason: it is committed and shared.
    """
    db = _plant(tmp_path / "index.db")

    assert appeon.server_entry(db) == {
        "command": "uvx",
        "args": ["--from", VCS_URL, "pb-appeon-index", "serve-mcp"],
        "env": {appeon.ENV_VAR: str(db)},
    }
    pinned = appeon.server_entry(db, "v9.9.9")
    assert pinned["args"][1] == VCS_URL + "@v9.9.9"
    assert pinned["env"][appeon.ENV_VAR] == str(db)


def test_ledger49_50_a_relative_variable_reaches_the_target_absolute(tmp_path: Path) -> None:
    """Ledger 49: `"env": {"PB_APPEON_INDEX_DB": "<abs db>"}`, end to end.

    A relative value written through verbatim is a server that starts, looks
    for the database wherever the client happens to be, finds nothing, and
    reports nothing - and it quietly voids ledger 50's "one file serves every
    project" at the same time. The stdout line and the marker have to name
    the same absolute path the entry does.
    """
    workdir = tmp_path / "work"
    db = _plant(workdir / "docs" / "appeon-index" / "index.db")
    target = tmp_path / "project"
    target.mkdir()

    relative = str(Path("docs") / "appeon-index" / "index.db")
    result = _install(target, cwd=workdir, env=_env(**{appeon.ENV_VAR: relative}))

    written = Path(_servers(target / ".mcp.json")[appeon.SERVER_KEY]["env"][appeon.ENV_VAR])
    assert written.is_absolute(), f"a relative database path was written: {written}"
    assert written.samefile(db)
    assert f"Appeon index      {written}" in result.stdout
    assert _fields(target).appeon == report.appeon_configured_note(str(written))


# --- The note, on all three branches (ledger 51, 52, 53) ---------------------


def test_ledger51_52_the_note_has_exactly_three_shapes(tmp_path: Path) -> None:
    """Ledger 51, 52: configured, missing, and "yours is still there".

    The third exists because an entry from an earlier install falls into
    `kept` and is written back untouched while the installer simultaneously
    reported the server NOT configured - possibly naming a checkout that no
    longer exists. The preservation was right; the report was not.
    """
    db = _plant(tmp_path / "index.db")
    assert appeon.note(db) == report.appeon_configured_note(str(db))
    assert appeon.note(None) == report.APPEON_NOTE_MISSING_DB
    assert appeon.note(None, existing_entry_in_target=True) == report.APPEON_NOTE_EXISTING_ENTRY
    # A found database always wins the sentence, whatever the target holds.
    assert appeon.note(db, existing_entry_in_target=True) == report.appeon_configured_note(str(db))


def test_ledger52_a_stale_entry_survives_the_merge_and_changes_the_note() -> None:
    """Ledger 52: preserved untouched, and the note stops claiming otherwise."""
    stale = {"command": "C:/gone/.venv/Scripts/python.exe", "args": ["-m", "pb_appeon_index"]}
    existing = json.dumps({"mcpServers": {appeon.SERVER_KEY: stale}}, indent=2).encode("utf-8")
    owned = {"pb-orca": {"command": "uvx", "args": ["pb-orca-mcp"]}}

    result = mcpconfig.merge(existing, owned)
    assert result.text is not None
    assert json.loads(result.text)["mcpServers"][appeon.SERVER_KEY] == stale

    names = mcpconfig.existing_server_names(existing)
    assert appeon.SERVER_KEY in names
    assert (
        appeon.note(None, existing_entry_in_target=appeon.SERVER_KEY in names)
        == report.APPEON_NOTE_EXISTING_ENTRY
    )


# --- The install, end to end (ledger 49, 50, 51, 53) -------------------------


def test_ledger49_50_51_a_database_is_configured_referenced_and_never_copied(
    tmp_path: Path,
) -> None:
    """Ledger 49, 50, 51: the server points at the database and nothing is copied.

    The environment variable makes this deterministic on a machine with no
    index built, which is what CI is.
    """
    db = _plant(tmp_path / "elsewhere" / "index.db")
    target = tmp_path / "project"
    target.mkdir()

    result = _install(target, env=_env(**{appeon.ENV_VAR: str(db)}))

    assert f"Appeon index      {db}" in result.stdout
    assert "referenced, not copied - rebuilding it once updates every project" in result.stdout

    entry = _servers(target / ".mcp.json")[appeon.SERVER_KEY]
    assert entry["env"][appeon.ENV_VAR] == str(db)
    assert entry["command"] == "uvx"
    assert "serve-mcp" in entry["args"]

    assert list(target.rglob("*.db")) == [], "the database was copied into the target"
    assert _fields(target).appeon == report.appeon_configured_note(str(db))


def test_ledger51_the_missing_database_branch_prints_a_recipe(tmp_path: Path) -> None:
    """Ledger 51: say what is missing and how to get it, and configure nothing.

    The failure is silent by nature, so the gap gets an actionable answer
    instead of a server every new session reports as a mystery.

    Run against a staged checkout with no index in it. This test used to skip
    itself on any machine whose clone had one built - which is every machine
    that has ever used the skill this server exists for, and every machine
    where the branch would be changed. A test that cannot run where the code
    is written is a test that rots.
    """
    staged = _stage_kit(tmp_path / "kit")
    target = tmp_path / "project"
    target.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    env = _env(
        **{
            appeon.ENV_VAR: str(tmp_path / "gone.db"),
            "USERPROFILE": str(home),
            "HOME": str(home),
            "PYTHONPATH": str(staged / "tools" / "pb-ai-code" / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )

    result = _install(target, env=env)

    assert "Note: pb-appeon-index NOT configured - missing the index database" in result.stdout
    assert "To build the index" in result.stdout
    # One command, and no clone: building an index used to require one, which
    # is why machines that had the tool did not have an index.
    assert f"uvx --from git+{REPO_URL} pb-appeon-index update --all" in result.stdout
    assert "git clone" not in result.stdout
    assert "Then re-run this installer and the server is configured." in result.stdout

    assert appeon.SERVER_KEY not in _servers(target / ".mcp.json")
    assert _fields(target).appeon == report.APPEON_NOTE_MISSING_DB


def test_ledger53_skip_mcp_config_reports_the_outcome_not_the_computation(
    tmp_path: Path,
) -> None:
    """Ledger 53: the note said `configured` for a server it had not written.

    It reported what was *computed*. Under `--skip-mcp-config` nothing is
    computed and nothing is written, and the marker now says so.
    """
    db = _plant(tmp_path / "elsewhere" / "index.db")
    target = tmp_path / "project"
    target.mkdir()

    result = _install(target, "--skip-mcp-config", env=_env(**{appeon.ENV_VAR: str(db)}))

    assert "Appeon index" not in result.stdout
    assert str(db) not in result.stdout
    assert _fields(target).appeon == report.APPEON_NOTE_SKIPPED
