"""Tests for the config loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from pb_appeon_index.config import load_config


def _write_toml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.toml"
    p.write_text(content, encoding="utf-8")
    return p


def test_load_config_single_version(tmp_path: Path) -> None:
    cfg_path = _write_toml(
        tmp_path,
        """
[[versions]]
slug = "pb2022r3"
base_url = "https://docs.appeon.com/pb2022r3"
sections = ["powerscript_reference"]
priority = 1
""",
    )
    cfg = load_config(cfg_path)
    assert len(cfg.versions) == 1
    v = cfg.versions[0]
    assert v.slug == "pb2022r3"
    assert v.base_url.endswith("/")
    assert v.sections == ("powerscript_reference",)
    assert v.priority == 1


def test_load_config_multiple_versions_default_is_lowest_priority(tmp_path: Path) -> None:
    cfg_path = _write_toml(
        tmp_path,
        """
[[versions]]
slug = "pb2022r3"
base_url = "https://docs.appeon.com/pb2022r3/"
sections = ["powerscript_reference"]
priority = 1

[[versions]]
slug = "pb2025"
base_url = "https://docs.appeon.com/pb2025/"
sections = ["powerscript_reference"]
priority = 2
""",
    )
    cfg = load_config(cfg_path)
    assert cfg.default_version().slug == "pb2022r3"
    assert cfg.find_version("pb2025") is not None
    assert cfg.find_version("nope") is None


def test_load_config_requires_versions(tmp_path: Path) -> None:
    cfg_path = _write_toml(tmp_path, "")
    with pytest.raises(ValueError):
        load_config(cfg_path)


def test_load_config_scraper_defaults(tmp_path: Path) -> None:
    cfg_path = _write_toml(
        tmp_path,
        """
[[versions]]
slug = "pb2022r3"
base_url = "https://docs.appeon.com/pb2022r3/"
sections = []
""",
    )
    cfg = load_config(cfg_path)
    assert cfg.scraper.request_delay_ms == 200
    assert cfg.scraper.max_pages_per_run == 5000
    assert cfg.scraper.user_agent.startswith("pb-appeon-index/")
