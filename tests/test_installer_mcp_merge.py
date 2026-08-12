"""The installer's MCP merge, run for real against a planted config.

Two behaviours are load-bearing and neither is visible from reading the JSON
the installer writes:

* servers the project already had must survive the merge, because a target's
  `.mcp.json` is the user's file and may hold things unrelated to PowerBuilder;
* a *second copy of our own server under a different key* must be reported,
  because two processes driving a single-session ORCA library is a real fault
  and only one of the two key prefixes matches the permission allowlist.

The second one is the reason this file exists. Its detection was matching the
hyphenated package name inside the server's definition only — so it missed the
two spellings that actually occur in the wild: a Python entry point invoked as
`-m pb_orca_mcp` (underscores, because that is the module name) and a stale
config whose *key* is `pb-orca-mcp` from before the key settled. A warning that
silently stops firing is worse than no warning, so it gets a test that crosses
the boundary into PowerShell rather than one that reasons about the source.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _pwsh() -> str:
    found = shutil.which("pwsh") or shutil.which("powershell")
    if found is None:
        pytest.skip("no PowerShell available to run the installer")
    return found


def _install(target: Path) -> str:
    result = subprocess.run(
        [
            _pwsh(),
            "-NoProfile",
            "-File",
            str(REPO_ROOT / "scripts" / "install-skills.ps1"),
            "-Target",
            str(target),
            "-Harness",
            "claude-code",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"installer failed:\n{result.stdout}\n{result.stderr}"
    return result.stdout + result.stderr


@pytest.mark.parametrize(
    ("stale_key", "stale_args"),
    [
        # The key is the old one and the module is spelled the only way Python
        # spells it. This is the shape a real project was found in.
        ("pb-orca-mcp", ["-m", "pb_orca_mcp"]),
        # A key nobody would guess, with the package named in the path instead.
        ("orca", ["--from", "git+https://example.invalid/pb-orca-mcp", "pb-orca-mcp"]),
    ],
)
def test_second_copy_of_our_server_is_reported(
    tmp_path: Path, stale_key: str, stale_args: list[str]
) -> None:
    config = tmp_path / ".mcp.json"
    config.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "some-other-server": {"command": "node", "args": ["server.js"]},
                    stale_key: {"command": "python.exe", "args": stale_args},
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    output = _install(tmp_path)

    assert stale_key in output, "the duplicate server was not named in the output"
    assert "competing for a single-session ORCA library" in output, (
        f"no duplicate-server warning for key {stale_key!r} with args {stale_args!r}:\n{output}"
    )

    merged = json.loads(config.read_text(encoding="utf-8"))["mcpServers"]
    assert "pb-orca" in merged, "the kit's own server was not written"
    assert stale_key in merged, "the duplicate was removed; it must be left in place"
    assert "some-other-server" in merged, "an unrelated server was lost in the merge"


def test_unrelated_servers_do_not_trigger_the_warning(tmp_path: Path) -> None:
    """The warning must not fire on a project that simply has other servers."""
    config = tmp_path / ".mcp.json"
    config.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "some-other-server": {"command": "node", "args": ["server.js"]},
                    "postgres": {"command": "uvx", "args": ["mcp-server-postgres"]},
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    output = _install(tmp_path)

    assert "competing for a single-session ORCA library" not in output, (
        f"false positive on unrelated servers:\n{output}"
    )

    merged = json.loads(config.read_text(encoding="utf-8"))["mcpServers"]
    assert set(merged) == {"some-other-server", "postgres", "pb-orca"}


def test_malformed_config_is_left_alone(tmp_path: Path) -> None:
    """A config that does not parse is never overwritten, only reported."""
    config = tmp_path / ".mcp.json"
    original = '{ "mcpServers": { "broken": , } }'
    config.write_text(original, encoding="utf-8")

    output = _install(tmp_path)

    assert config.read_text(encoding="utf-8") == original, (
        "a config that could not be parsed was modified"
    )
    assert "not valid JSON" in output
    assert "pb-orca" in output, "the block to merge by hand was not printed"
