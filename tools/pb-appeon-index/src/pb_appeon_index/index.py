"""SQLite FTS5 index over parsed Appeon pages.

A single database holds every indexed version; the ``version`` column
distinguishes pages belonging to different PB versions. The FTS table
shadows the ``pages`` table over the four fields most useful for
keyword retrieval (``name``, ``description``, ``syntax``, ``examples``);
``version`` is carried as UNINDEXED so it can be referenced in match
queries without affecting the BM25 ranking.

Inserts are ``INSERT OR REPLACE`` on the ``(version, url)`` unique key,
which makes re-runs of ``build`` idempotent: a page that didn't
change re-imports identically; a page that did change gets the new
content; a page that was removed upstream stays in the DB until you
explicitly clear that version (acceptable for now — a future ``vacuum``
subcommand can prune orphans).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Config
from .parse import Page, parse_page

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL,
    url TEXT NOT NULL,
    category TEXT NOT NULL,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    syntax TEXT NOT NULL DEFAULT '',
    arguments TEXT NOT NULL DEFAULT '',
    return_value TEXT NOT NULL DEFAULT '',
    examples TEXT NOT NULL DEFAULT '',
    see_also TEXT NOT NULL DEFAULT '[]',
    scraped_at TEXT NOT NULL,
    UNIQUE(version, url)
);

CREATE INDEX IF NOT EXISTS idx_pages_version_name ON pages(version, name);
CREATE INDEX IF NOT EXISTS idx_pages_version_category ON pages(version, category);

CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
    name, description, syntax, arguments, return_value, examples,
    version UNINDEXED,
    content='pages',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS pages_ai AFTER INSERT ON pages BEGIN
    INSERT INTO pages_fts(rowid, name, description, syntax, arguments,
                        return_value, examples, version)
    VALUES (new.id, new.name, new.description, new.syntax,
            new.arguments, new.return_value, new.examples, new.version);
END;

CREATE TRIGGER IF NOT EXISTS pages_ad AFTER DELETE ON pages BEGIN
    INSERT INTO pages_fts(pages_fts, rowid, name, description, syntax, arguments,
                        return_value, examples, version)
    VALUES ('delete', old.id, old.name, old.description, old.syntax,
            old.arguments, old.return_value, old.examples, old.version);
END;

CREATE TRIGGER IF NOT EXISTS pages_au AFTER UPDATE ON pages BEGIN
    INSERT INTO pages_fts(pages_fts, rowid, name, description, syntax, arguments,
                        return_value, examples, version)
    VALUES ('delete', old.id, old.name, old.description, old.syntax,
            old.arguments, old.return_value, old.examples, old.version);
    INSERT INTO pages_fts(rowid, name, description, syntax, arguments,
                        return_value, examples, version)
    VALUES (new.id, new.name, new.description, new.syntax,
            new.arguments, new.return_value, new.examples, new.version);
END;
"""


@dataclass
class SearchHit:
    version: str
    name: str
    kind: str
    category: str
    url: str
    description: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "name": self.name,
            "kind": self.kind,
            "category": self.category,
            "url": self.url,
            "description": self.description,
            "score": self.score,
        }


def connect(db_path: Path, read_only: bool = False) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if read_only:
        # SQLite needs a URI for ro flag.
        uri = f"file:{db_path.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    conn.commit()


def upsert_page(conn: sqlite3.Connection, page: Page) -> None:
    """Insert or replace a page. Idempotent by (version, url)."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO pages
            (version, url, category, kind, name, description, syntax,
             arguments, return_value, examples, see_also, scraped_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(version, url) DO UPDATE SET
            category = excluded.category,
            kind = excluded.kind,
            name = excluded.name,
            description = excluded.description,
            syntax = excluded.syntax,
            arguments = excluded.arguments,
            return_value = excluded.return_value,
            examples = excluded.examples,
            see_also = excluded.see_also,
            scraped_at = excluded.scraped_at
        """,
        (
            page.version,
            page.url,
            page.category,
            page.kind,
            page.name,
            page.description,
            page.syntax,
            page.arguments,
            page.return_value,
            page.examples,
            json.dumps(page.see_also),
            now,
        ),
    )


def _iter_cached_pages(cfg: Config, cache_root: Path) -> Iterator[Page]:
    for version in cfg.versions:
        slug_dir = cache_root / version.slug
        if not slug_dir.is_dir():
            continue
        for section in version.sections:
            section_dir = slug_dir / section
            if not section_dir.is_dir():
                continue
            for html_file in section_dir.rglob("*.html"):
                rel = html_file.relative_to(slug_dir).as_posix()
                url = version.base_url + rel
                try:
                    yield parse_page(html_file, version.slug, section, url)
                except (OSError, ValueError):
                    continue


def build_index(cfg: Config, cache_root: Path, db_path: Path) -> int:
    """Build the index from the cache. Returns count of pages indexed."""
    conn = connect(db_path)
    try:
        init_schema(conn)
        count = 0
        for page in _iter_cached_pages(cfg, cache_root):
            upsert_page(conn, page)
            count += 1
        conn.commit()
        return count
    finally:
        conn.close()


def search(
    conn: sqlite3.Connection,
    query: str,
    version: str | None = None,
    limit: int = 10,
) -> list[SearchHit]:
    """FTS5 keyword search. ``version`` filters to a single PB version."""
    # bm25 column weights, in declaration order:
    #   name, description, syntax, arguments, return_value, examples.
    # The name carries the strongest signal (it's the identifier the
    # user is most likely searching for); we crank it up so a query
    # for "Left" beats pages that merely mention "Left" in their body.
    sql = """
        SELECT p.version, p.name, p.kind, p.category, p.url,
               substr(p.description, 1, 240) AS description_excerpt,
               bm25(pages_fts, 10.0, 1.0, 2.0, 1.0, 1.0, 1.0) AS score
        FROM pages_fts
        JOIN pages p ON p.id = pages_fts.rowid
        WHERE pages_fts MATCH ?
    """
    params: list[Any] = [query]
    if version:
        sql += " AND p.version = ?"
        params.append(version)
    sql += " ORDER BY score LIMIT ?"
    params.append(limit)
    return [
        SearchHit(
            version=row["version"],
            name=row["name"],
            kind=row["kind"],
            category=row["category"],
            url=row["url"],
            description=row["description_excerpt"],
            score=row["score"],
        )
        for row in conn.execute(sql, params)
    ]


def get_by_name(
    conn: sqlite3.Connection,
    name: str,
    version: str | None = None,
) -> dict[str, Any] | None:
    """Exact-name lookup (case-insensitive). With ``version=None``, picks
    the lowest-priority slug — currently lexicographically smallest, which
    happens to favor older slugs; callers that care should pass version."""
    sql = """
        SELECT version, url, category, kind, name, description, syntax,
               arguments, return_value, examples, see_also, scraped_at
        FROM pages
        WHERE LOWER(name) = LOWER(?)
    """
    params: list[Any] = [name]
    if version:
        sql += " AND version = ?"
        params.append(version)
    sql += " LIMIT 1"
    row = conn.execute(sql, params).fetchone()
    if row is None:
        return None
    out = dict(row)
    try:
        out["see_also"] = json.loads(out["see_also"])
    except (json.JSONDecodeError, TypeError):
        out["see_also"] = []
    return out


def list_topics(
    conn: sqlite3.Connection,
    version: str | None = None,
) -> list[dict[str, Any]]:
    """Distinct (category, kind) buckets with page counts."""
    sql = """
        SELECT version, category, kind, COUNT(*) AS n
        FROM pages
    """
    params: list[Any] = []
    if version:
        sql += " WHERE version = ?"
        params.append(version)
    sql += " GROUP BY version, category, kind ORDER BY version, category, kind"
    return [dict(row) for row in conn.execute(sql, params)]


def list_versions(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Versions present in the index, with page counts."""
    return [
        dict(row)
        for row in conn.execute(
            "SELECT version, COUNT(*) AS n FROM pages GROUP BY version ORDER BY version"
        )
    ]
