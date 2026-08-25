"""PB Search setup selects exact documentation releases from the machine."""

from __future__ import annotations

from pathlib import Path

import pytest

from pb_ai_code import __main__ as cli
from pb_ai_code import pbversion


def test_search_status_reports_exact_detected_release(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    release = pbversion.parse("pb2022r3")
    monkeypatch.setattr(cli, "_search_installed_releases", lambda: (release,))
    monkeypatch.setattr(cli, "_search_indexed_versions", lambda db: {release.value})

    assert cli.main(["search", "status", "--db", str(tmp_path / "index.db")]) == 0

    output = capsys.readouterr().out
    assert "PowerBuilder 2022 R3" in output
    assert "pb2022r3" in output
    assert "indexed" in output


def test_search_setup_updates_only_missing_detected_releases(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    release_2019 = pbversion.parse("pb2019r3")
    release_2022 = pbversion.parse("pb2022r3")
    monkeypatch.setattr(
        cli,
        "_search_installed_releases",
        lambda: (release_2019, release_2022),
    )
    monkeypatch.setattr(cli, "_search_indexed_versions", lambda db: {release_2019.value})
    calls: list[list[str]] = []
    from pb_appeon_index import __main__ as index_cli

    monkeypatch.setattr(index_cli, "main", lambda args: calls.append(args) or 0)

    assert cli.main(["search", "setup", "--yes", "--db", str(tmp_path / "index.db")]) == 0

    assert calls == [["update", "--version", "pb2022r3", "--db", str(tmp_path / "index.db")]]


def test_build_flag_maps_to_an_exact_slug() -> None:
    release = pbversion.from_build_flag("2022 R3")
    assert release is not None
    assert release.value == "pb2022r3"
    assert release.orca_version == "22.0"
