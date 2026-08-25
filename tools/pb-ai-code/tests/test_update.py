"""Release checks and the update command never modify anything by surprise."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from pb_ai_code import __main__ as cli
from pb_ai_code import marker, report, update


def release_payload(tag: str = "v0.11.2") -> dict[str, object]:
    return {
        "tag_name": tag,
        "html_url": f"https://github.com/restoresrl/pb-ai-code/releases/tag/{tag}",
    }


def test_check_compares_a_published_release_and_caches_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    calls = 0

    def fetch() -> tuple[update.Release, dict[str, object]]:
        nonlocal calls
        calls += 1
        payload = release_payload()
        release = update._release_from_payload(payload)
        assert release is not None
        return release, payload

    monkeypatch.setattr(update, "_fetch_release", fetch)

    first = update.check("0.11.1")
    second = update.check("0.11.1")

    assert first.update_available is True
    assert first.from_cache is False
    assert second.from_cache is True
    assert calls == 1


def test_check_rejects_non_release_tags() -> None:
    assert update._release_from_payload(release_payload("main")) is None
    assert update._release_from_payload(release_payload("v0.11.2rc1")) is None


def test_update_check_json_reports_an_available_release(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    latest = update._release_from_payload(release_payload())
    assert latest is not None
    monkeypatch.setattr(
        update,
        "check",
        lambda version, refresh: update.CheckResult(version, latest, True, False),
    )

    assert cli.main(["update", "--target", str(tmp_path), "--check", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["latest_tag"] == "v0.11.2"
    assert payload["global_update_available"] is True
    assert payload["project_version"] is None


def test_update_check_treats_an_unavailable_network_as_nonfatal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail(version: str, *, refresh: bool) -> update.CheckResult:
        raise update.UpdateCheckError("cannot check GitHub for updates: offline")

    monkeypatch.setattr(update, "check", fail)

    assert cli.main(["update", "--target", str(tmp_path), "--check", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "running_version": cli.provenance_mod.distribution_version(),
        "update_available": False,
        "check_error": "cannot check GitHub for updates: offline",
    }


def test_update_reuses_the_installed_project_layout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "project"
    target.mkdir()
    marker_path = target / ".agents" / "_installed-from-pb-ai-code.txt"
    marker_path.parent.mkdir()
    marker_path.write_text(
        "\n".join(
            [
                "# Version:   0.11.1",
                "# Harness:   generic",
                "# PB:        22.0",
                f"# MCP:       {report.MCP_MARKER_SKIPPED}",
                "# Contents:",
                "#   .agents/skills/pb-review",
                "#   .agents/commands/pb-review.md",
            ]
        ),
        encoding="utf-8",
    )
    latest = update._release_from_payload(release_payload())
    assert latest is not None
    monkeypatch.setattr(
        update,
        "check",
        lambda version, refresh: update.CheckResult(version, latest, True, False),
    )
    calls: list[list[str]] = []
    monkeypatch.setattr(cli, "_windows_self_update", lambda: False)
    monkeypatch.setattr(update, "run", lambda command: calls.append(command) or 0)

    assert cli.main(["update", "--target", str(target), "--yes"]) == 0

    assert calls[0] == update.global_install_command(latest)
    assert calls[1] == update.project_install_command(
        latest,
        [
            "--target",
            str(target),
            "--harness",
            "generic",
            "--skills-dir",
            ".agents/skills",
            "--commands-dir",
            ".agents/commands",
            "--pb-version",
            "22.0",
            "--skip-mcp-config",
        ],
    )
    assert "Project bundle updated." in capsys.readouterr().out


def test_windows_update_is_scheduled_after_the_running_tool_exits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scheduled: list[list[str]] = []
    monkeypatch.setattr(update.os, "name", "nt")
    monkeypatch.setattr(update.subprocess, "Popen", lambda command: scheduled.append(command))

    update.schedule_after_exit(
        ["uv", "tool", "install", "--force", "git+https://example.invalid/repo@v0.11.3"],
        ["uvx", "--from", "git+https://example.invalid/repo@v0.11.3", "pb-ai-code", "install"],
    )

    assert scheduled[0][:3] == ["powershell", "-NoProfile", "-EncodedCommand"]
    script = base64.b64decode(scheduled[0][3]).decode("utf-16-le")
    assert "Wait-Process -Id" in script
    assert "Start-Sleep -Milliseconds 750" in script
    assert "& 'uv' @('tool', 'install', '--force'" in script
    assert "& 'uvx' @('--from', 'git+https://example.invalid/repo@v0.11.3'" in script


def test_project_update_command_can_read_a_marker_with_the_pb_version() -> None:
    fields = marker.parse("# PB:        22.0\n# Harness:   claude-code\n")
    assert fields.pb_version == "22.0"
