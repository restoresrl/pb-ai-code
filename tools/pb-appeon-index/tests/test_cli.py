"""CLI defaults keep generated index data out of a caller's project."""

from __future__ import annotations

from pathlib import Path

from pb_appeon_index import __main__ as cli


def test_default_cache_is_beside_the_shared_user_database(monkeypatch, tmp_path: Path) -> None:
    """A global command must not create ``.appeon-cache`` in its working directory."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    assert cli._default_cache() == tmp_path / ".pb-appeon-index" / "cache"
