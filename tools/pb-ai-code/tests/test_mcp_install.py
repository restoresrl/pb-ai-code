"""The MCP step of a real install, driven across the process boundary.

The unit tests in ``test_mcp_merge.py`` prove the merge; these prove that the
installer wires it to a file, prints what it did, and records the same words
in the marker. They run ``python -m pb_ai_code`` in a subprocess on purpose:
the house rule from the mcp 2.0.0 incident is that a test which does not cross
the boundary does not prove the boundary works, and a subprocess also
exercises the entry point ``uvx`` will use.

Two of them are ports of ``tests/test_installer_mcp_merge.py``, which pins the
same contract against the PowerShell installer. Their shapes are the ones a
real project was found in: a stale server keyed ``pb-orca-mcp`` and one keyed
``orca``, both running a second copy of a single-session ORCA library.
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
from pb_ai_code import harness, kit, marker, plan, report

CLAUDE_MARKER = (".claude", "_installed-from-pb-ai-code.txt")

NODE: dict[str, Any] = {"command": "node", "args": ["server.js"]}
POSTGRES: dict[str, Any] = {"command": "uvx", "args": ["mcp-server-postgres"]}


def _run(
    *args: str, cwd: Path | None = None, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pb_ai_code", *args],
        capture_output=True,
        text=True,
        cwd=None if cwd is None else str(cwd),
        env=None if env is None else {**os.environ, **env},
    )


def _stage_wheel_payload(root: Path) -> tuple[Path, dict[str, str]]:
    """Build the layout a wheel has, and return ``(payload, env)``.

    The kit travels inside the distribution at ``pb_ai_code/_kit/``, which is
    what `kit_root()` resolves through `importlib.resources` before it ever
    considers a checkout. Staging it is the only way to ask what happens when
    a payload input is not there - the real payload is this repository, and no
    test may edit it - and it exercises the packaged branch that `uvx` takes.

    The environment also gives the run a home with no index in it, so the
    Appeon probe answers the same on a developer's machine as on CI.
    """
    source = kit.load_kit().root
    src = root / "src"
    shutil.copytree(
        Path(pb_ai_code.__file__).parent,
        src / "pb_ai_code",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    payload = src / "pb_ai_code" / "_kit"
    for rel in ("skills", "commands", "harness", "docs/pb-antipatterns", "docs/pb-source-format"):
        shutil.copytree(source.joinpath(*rel.split("/")), payload.joinpath(*rel.split("/")))
    shutil.copy2(source / "docs" / "wiki-notes.md", payload / "docs" / "wiki-notes.md")

    home = root / "home"
    home.mkdir()
    env = {
        "PYTHONPATH": str(src),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PB_APPEON_INDEX_DB": str(home / "no-such-index.db"),
        "USERPROFILE": str(home),
        "HOME": str(home),
    }
    return payload, env


def _install(target: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    """Install into ``target``; every warning path still has to exit 0."""
    result = _run("install", "--target", str(target), *extra)
    assert result.returncode == 0, f"install failed:\n{result.stdout}\n{result.stderr}"
    return result


def _marker(target: Path, *rel: str) -> marker.MarkerFields:
    path = target.joinpath(*(rel or CLAUDE_MARKER))
    return marker.parse(path.read_text(encoding="utf-8-sig"))


def _servers(config: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(config.read_text(encoding="utf-8-sig"))
    servers: dict[str, Any] = document["mcpServers"]
    return servers


def _line(stdout: str, prefix: str) -> str:
    matches = [line for line in stdout.splitlines() if line.startswith(prefix)]
    assert len(matches) == 1, f"expected exactly one {prefix!r} line in:\n{stdout}"
    return matches[0]


def _write_config(target: Path, payload: dict[str, Any]) -> Path:
    config = target / ".mcp.json"
    config.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return config


# --- The duplicate-ORCA warning (ledger 42, 43, 67) --------------------------


@pytest.mark.parametrize(
    ("stale_key", "stale_args"),
    [
        # The key is the old one and the module is spelled the only way Python
        # spells it. This is the shape a real project was found in.
        pytest.param("pb-orca-mcp", ["-m", "pb_orca_mcp"], id="underscored-module"),
        # A key nobody would guess, with the package named in the path instead.
        pytest.param(
            "orca",
            ["--from", "git+https://example.invalid/pb-orca-mcp", "pb-orca-mcp"],
            id="package-in-a-url",
        ),
    ],
)
def test_ledger42_43_67_a_second_copy_of_our_server_is_reported(
    tmp_path: Path, stale_key: str, stale_args: list[str]
) -> None:
    """Ledger 42, 43, 67: five yellow lines, before `Installed mcp`, on stdout.

    Ported from `tests/test_installer_mcp_merge.py`, which asserts the same
    contract against the PowerShell installer. The warning removes nothing,
    changes no exit code, and the duplicate stays under `kept:`.
    """
    config = _write_config(
        tmp_path,
        {
            "mcpServers": {
                "some-other-server": NODE,
                stale_key: {"command": "python.exe", "args": stale_args},
            }
        },
    )

    result = _install(tmp_path)

    assert "competing for a single-session ORCA library" in result.stdout, (
        f"no duplicate-server warning for key {stale_key!r}:\n{result.stdout}"
    )
    assert f"Remove '{stale_key}' unless you meant to keep it." in result.stdout
    # Single stream: the whole report is stdout, and a warning is not stderr.
    assert result.stderr == ""

    merged = _servers(config)
    assert "pb-orca" in merged, "the kit's own server was not written"
    assert stale_key in merged, "the duplicate was removed; it must be left in place"
    assert "some-other-server" in merged, "an unrelated server was lost in the merge"

    installed = _line(result.stdout, "Installed mcp")
    assert "kept: " in installed and stale_key in installed

    lines = result.stdout.splitlines()
    warn = next(i for i, line in enumerate(lines) if line.startswith("WARN: the target already"))
    assert warn < lines.index(installed), "the warning printed after the line it explains"
    assert lines[warn - 1] == "" and lines[warn + 5] == "", "the block is wrapped in blank lines"


def test_ledger42_unrelated_servers_do_not_trigger_the_warning(tmp_path: Path) -> None:
    """Ledger 42: the warning must not fire on a project that has other servers."""
    config = _write_config(
        tmp_path, {"mcpServers": {"some-other-server": NODE, "postgres": POSTGRES}}
    )

    result = _install(tmp_path)

    assert "competing for a single-session ORCA library" not in result.stdout

    merged = _servers(config)
    # Not an exact-set assertion: `pb-appeon-index` is configured only when
    # this machine has the documentation index built, and the index is
    # gitignored - present on a developer's box, absent on CI.
    assert {"some-other-server", "postgres", "pb-orca"} <= set(merged)
    assert set(merged) - {"some-other-server", "postgres", "pb-orca"} <= {"pb-appeon-index"}


# --- Refusing to write (ledger 36, 39) ---------------------------------------


def test_ledger36_a_malformed_config_is_left_byte_identical(tmp_path: Path) -> None:
    """Ledger 36: a config that does not parse is never overwritten, only reported.

    `{ "mcpServers": { "broken": , } }` was rewritten once, with the
    half-typed value coerced away. The run still exits 0 - a target's MCP
    config is the user's file and a stray comma is not this installer's
    emergency.
    """
    config = tmp_path / ".mcp.json"
    original = '{ "mcpServers": { "broken": , } }'
    config.write_text(original, encoding="utf-8")

    result = _install(tmp_path)

    assert config.read_bytes() == original.encode("utf-8"), "an unparseable config was modified"
    assert "not valid JSON" in result.stdout
    assert report.MCP_UNPARSEABLE_HAND_MERGE in result.stdout
    assert '"pb-orca"' in result.stdout, "the block to merge by hand was not printed"
    assert _marker(tmp_path).mcp == report.mcp_marker_not_written(".mcp.json")


def test_ledger39_a_non_object_servers_key_is_left_byte_identical(tmp_path: Path) -> None:
    """Ledger 39: it parses, so nothing warned - and the sibling keys were kept.

    That made it the one route by which a *parseable* file lost data, which
    is exactly what the strict-parse work defends against.
    """
    config = tmp_path / ".mcp.json"
    original = '{"mcpServers": "oops", "other": 1}'
    config.write_text(original, encoding="utf-8")

    result = _install(tmp_path)

    assert config.read_bytes() == original.encode("utf-8")
    assert "not valid JSON" in result.stdout


# --- What a merge preserves and says (ledger 34, 40, 46) ---------------------


def test_ledger34_40_the_projects_own_config_survives_and_is_reported(tmp_path: Path) -> None:
    """Ledger 34, 40, 46: order preserved, outcomes named, bytes as specified."""
    config = _write_config(
        tmp_path,
        {"someTopLevelKey": {"kept": True}, "mcpServers": {"postgres": POSTGRES}},
    )

    result = _install(tmp_path)

    document = json.loads(config.read_text(encoding="utf-8-sig"))
    assert list(document) == ["someTopLevelKey", "mcpServers"]
    assert document["someTopLevelKey"] == {"kept": True}
    assert next(iter(document["mcpServers"])) == "postgres", "an existing server lost its place"
    assert document["mcpServers"]["postgres"] == POSTGRES

    installed = _line(result.stdout, "Installed mcp")
    assert installed.startswith("Installed mcp       .mcp.json  [")
    assert report.outcome_added("pb-orca") in installed
    assert installed.endswith("kept: postgres]")
    assert _marker(tmp_path).mcp == installed.split("Installed mcp       ", 1)[1]

    raw = config.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert raw.count(b"\n") == raw.count(b"\r\n")
    assert raw.endswith(b"\r\n") and not raw.endswith(b"\r\n\r\n")

    second = _install(tmp_path)
    assert report.outcome_already_current("pb-orca") in _line(second.stdout, "Installed mcp")


# --- --skip-mcp-config (ledger 32, 33, 48, 53) -------------------------------


def test_ledger48_53_skip_mcp_config_suppresses_everything_it_promises(tmp_path: Path) -> None:
    """Ledger 48, 53: the target's config, the Appeon block and the restart hint.

    Entirely untested before this. The flag exists for a project whose MCP
    configuration is managed elsewhere, so touching the file anyway - or
    telling the user to restart for a config that was not written - is the
    whole failure.
    """
    config = _write_config(tmp_path, {"mcpServers": {"postgres": POSTGRES}})
    original = config.read_bytes()

    result = _install(tmp_path, "--skip-mcp-config")

    assert config.read_bytes() == original
    assert report.MCP_SKIPPED_LINE in result.stdout
    assert "mcp       skipped (--skip-mcp-config)" in result.stdout
    assert "Installed mcp" not in result.stdout
    assert "Appeon index" not in result.stdout
    assert "pb-appeon-index NOT configured" not in result.stdout
    assert report.RESTART_HINT not in result.stdout

    fields = _marker(tmp_path)
    assert fields.mcp == report.MCP_MARKER_SKIPPED
    assert fields.appeon == report.APPEON_NOTE_SKIPPED


def test_ledger48_71_the_gitignore_hint_drops_the_mcp_rule_when_skipped(tmp_path: Path) -> None:
    """Ledger 48, 71: the `.mcp.json` line is claude-code's, and only when written."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)

    written = _install(tmp_path)
    assert "        .claude/" in written.stdout
    assert "        .mcp.json" in written.stdout

    skipped = _install(tmp_path, "--skip-mcp-config")
    assert "        .claude/" in skipped.stdout
    assert "        .mcp.json" not in skipped.stdout


def test_ledger32_33_the_server_file_is_checked_early_and_read_late(tmp_path: Path) -> None:
    """Ledger 32, 33: `--skip-mcp-config` must not need `harness/mcp-servers.json`.

    The latent bug: the preflight was skipped but the late read was not, so a
    missing file aborted the run *after* everything had been copied and
    *before* the marker was written - a populated target with no record of
    what put it there. The plan is where the check belongs, because
    `--dry-run` walks the same code.
    """
    staged = _staged_kit(tmp_path / "kit")
    target = tmp_path / "target"
    target.mkdir()
    assert not staged.mcp_servers_file.exists()

    skipped = plan.build_plan(staged, harness.CLAUDE_CODE, target, skip_mcp_config=True)
    assert skipped.rows, "the plan was not built"

    with pytest.raises(plan.SourceMissing) as exc:
        plan.build_plan(staged, harness.CLAUDE_CODE, target, skip_mcp_config=False)
    assert str(exc.value) == report.err_mcp_config_missing(str(staged.mcp_servers_file))


def test_ledger33_an_install_that_skips_the_config_never_reads_the_file(tmp_path: Path) -> None:
    """Ledger 33: delete the payload file, pass the flag, and it still exits 0.

    The bug this replaces: the preflight was skipped but `Get-McpServerBlock`
    still ran, so the run died *after* copying everything and *before* writing
    the marker. Without the flag the same missing file has to stop the run
    with the target still empty.
    """
    payload, env = _stage_wheel_payload(tmp_path / "wheel")
    (payload / "harness" / "mcp-servers.json").unlink()

    skipped = tmp_path / "skipped"
    skipped.mkdir()
    result = _run("install", "--target", str(skipped), "--skip-mcp-config", env=env)
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    assert (skipped / ".claude" / "_installed-from-pb-ai-code.txt").is_file(), (
        "the marker is the last write; without it nothing records what landed here"
    )

    demanded = tmp_path / "demanded"
    demanded.mkdir()
    refused = _run("install", "--target", str(demanded), env=env)
    assert refused.returncode != 0
    assert list(demanded.iterdir()) == [], "the run wrote before it validated"
    assert "Traceback" not in refused.stderr
    assert refused.stdout == ""


def _staged_kit(root: Path) -> kit.Kit:
    """A payload with everything the plan needs except `harness/mcp-servers.json`."""
    (root / "skills" / "pb-review").mkdir(parents=True)
    (root / "skills" / "pb-review" / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    (root / "commands").mkdir()
    (root / "commands" / "pb-review.md").write_text("# command\n", encoding="utf-8")
    for tree in plan.DOC_TREES:
        (root / "docs" / tree).mkdir(parents=True)
        (root / "docs" / tree / "index.md").write_text("# docs\n", encoding="utf-8")
    for docfile in plan.DOC_FILES:
        (root / "docs" / docfile).write_text("# notes\n", encoding="utf-8")
    (root / "harness" / "claude-code").mkdir(parents=True)
    (root / "harness" / "claude-code" / "settings.json").write_text("{}\n", encoding="utf-8")
    return kit.Kit(root=root, is_checkout=False)


# --- The generic harness (ledger 47) -----------------------------------------


def test_ledger47_the_generic_harness_prints_the_block_and_writes_no_file(tmp_path: Path) -> None:
    """Ledger 47: no known on-disk location, so the block goes to stdout.

    Writing it somewhere invented would look like it worked. The marker says
    which of the four things happened, so `status` can tell a printed block
    from a merged one months later.
    """
    result = _install(tmp_path, "--harness", "generic", "--skills-dir", ".agent/skills")

    assert list(tmp_path.rglob(".mcp.json")) == [], "the generic harness wrote an MCP config"
    assert report.MCP_PRINT_INTRO_1 in result.stdout
    assert report.MCP_PRINT_INTRO_2 in result.stdout
    assert "printed below (location is client-specific)" in result.stdout
    assert '"pb-orca"' in result.stdout
    assert report.RESTART_HINT not in result.stdout

    fields = _marker(tmp_path, ".agent", "_installed-from-pb-ai-code.txt")
    assert fields.mcp == report.MCP_MARKER_PRINTED
    assert fields.harness == "generic"


# --- --dry-run (ledger 75) ---------------------------------------------------


def test_ledger75_dry_run_previews_the_merge_and_writes_nothing(tmp_path: Path) -> None:
    """Ledger 75: the two decisions the old dry run was silent about.

    What the merge would do to the servers already there is one of them, and
    the target file has to come out byte-identical.
    """
    config = _write_config(
        tmp_path, {"mcpServers": {"pb-orca": {"command": "old"}, "postgres": POSTGRES}}
    )
    original = config.read_bytes()

    result = _install(tmp_path, "--dry-run")

    assert config.read_bytes() == original
    assert [path.name for path in tmp_path.iterdir()] == [".mcp.json"]
    assert report.DRY_RUN_LINE in result.stdout

    preview = _line(result.stdout, "MCP: ")
    assert report.would_update("pb-orca") in preview
    assert report.would_leave("postgres") in preview
