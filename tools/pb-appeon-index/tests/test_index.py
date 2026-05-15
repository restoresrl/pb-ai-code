"""Tests for the SQLite FTS5 indexer."""

from __future__ import annotations

from pathlib import Path

from pb_appeon_index.index import (
    connect,
    get_by_name,
    init_schema,
    list_topics,
    list_versions,
    search,
    upsert_page,
)
from pb_appeon_index.parse import Page


def _seed(conn) -> None:
    init_schema(conn)
    upsert_page(
        conn,
        Page(
            version="pb2022r3",
            url="https://docs.appeon.com/pb2022r3/powerscript_reference/left_func.html",
            category="powerscript_reference",
            kind="function",
            name="Left",
            description="Obtains a specified number of characters from the beginning of a string.",
            syntax="Left ( string, n )",
            arguments="string: source. n: long, count.",
            return_value="String. Leftmost n characters.",
            examples='Left("BABE RUTH", 4) returns "BABE".',
            see_also=["mid_func.html", "right_func.html"],
        ),
    )
    upsert_page(
        conn,
        Page(
            version="pb2022r3",
            url="https://docs.appeon.com/pb2022r3/powerscript_reference/mid_func.html",
            category="powerscript_reference",
            kind="function",
            name="Mid",
            description="Returns a substring from a string starting at a specified position.",
            syntax="Mid ( string, start [, length ] )",
            arguments="string: source. start: long. length: long.",
            return_value="String. The substring.",
            examples='Mid("BASEBALL", 5) returns "BALL".',
            see_also=["left_func.html"],
        ),
    )
    conn.commit()


def test_upsert_is_idempotent(tmp_path: Path) -> None:
    conn = connect(tmp_path / "x.db")
    try:
        _seed(conn)
        # Re-seed: counts should not change.
        _seed(conn)
        row = conn.execute("SELECT COUNT(*) AS n FROM pages").fetchone()
        assert row["n"] == 2
    finally:
        conn.close()


def test_search_finds_by_keyword(tmp_path: Path) -> None:
    conn = connect(tmp_path / "x.db")
    try:
        _seed(conn)
        hits = search(conn, "leftmost")
        assert len(hits) == 1
        assert hits[0].name == "Left"
    finally:
        conn.close()


def test_search_finds_by_function_name(tmp_path: Path) -> None:
    conn = connect(tmp_path / "x.db")
    try:
        _seed(conn)
        hits = search(conn, "Mid")
        names = {h.name for h in hits}
        assert "Mid" in names
    finally:
        conn.close()


def test_search_version_filter(tmp_path: Path) -> None:
    conn = connect(tmp_path / "x.db")
    try:
        _seed(conn)
        # Add a record under a different version.
        upsert_page(
            conn,
            Page(
                version="pb2025",
                url="https://docs.appeon.com/pb2025/powerscript_reference/left_func.html",
                category="powerscript_reference",
                kind="function",
                name="Left",
                description="(pb2025) Obtains a specified number of characters...",
            ),
        )
        conn.commit()
        hits_22 = search(conn, "Left", version="pb2022r3")
        hits_25 = search(conn, "Left", version="pb2025")
        assert {h.version for h in hits_22} == {"pb2022r3"}
        assert {h.version for h in hits_25} == {"pb2025"}
    finally:
        conn.close()


def test_get_by_name_returns_structured_record(tmp_path: Path) -> None:
    conn = connect(tmp_path / "x.db")
    try:
        _seed(conn)
        rec = get_by_name(conn, "left")
        assert rec is not None
        assert rec["name"] == "Left"
        assert rec["see_also"] == ["mid_func.html", "right_func.html"]
        assert "leftmost" in rec["return_value"].lower()
    finally:
        conn.close()


def test_list_topics_and_versions(tmp_path: Path) -> None:
    conn = connect(tmp_path / "x.db")
    try:
        _seed(conn)
        topics = list_topics(conn)
        assert any(t["category"] == "powerscript_reference" for t in topics)
        versions = list_versions(conn)
        assert any(v["version"] == "pb2022r3" for v in versions)
    finally:
        conn.close()
