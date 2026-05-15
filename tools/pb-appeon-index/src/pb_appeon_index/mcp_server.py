"""MCP server that exposes the Appeon doc index as tools.

Four tools:

- ``appeon_search(query, version?, limit?)`` — FTS5 keyword search;
  returns ranked hits with short description excerpts.
- ``appeon_get(name, version?)`` — full structured content for one
  page (name, syntax, args, return value, examples, see-also).
- ``appeon_list_topics(version?)`` — distinct (category, kind) buckets
  with counts; useful for the agent to discover what's indexed.
- ``appeon_list_versions()`` — versions present in the DB with counts.

The server is read-only on the SQLite DB. Build/update is handled by
the ``pb-appeon-index update`` CLI.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .index import (
    connect,
    get_by_name,
    list_topics,
    list_versions,
    search,
)

_DEFAULT_DB_ENV = "PB_APPEON_INDEX_DB"


def _resolve_db_path() -> Path:
    """Find the index DB. Env var wins; otherwise look in the conventional
    locations next to the user's config."""
    if env_path := os.environ.get(_DEFAULT_DB_ENV):
        return Path(env_path)
    # Convention: docs/appeon-index/index.db inside the project workspace.
    candidates = [
        Path.cwd() / "docs" / "appeon-index" / "index.db",
        Path.home() / ".pb-appeon-index" / "index.db",
    ]
    for c in candidates:
        if c.exists():
            return c
    # Fall back to the first candidate; the server will raise on first query
    # if the file is missing — better than failing at startup before the
    # user gets a chance to set the env var.
    return candidates[0]


def build_server(db_path: Path | None = None) -> FastMCP:
    """Construct a FastMCP server bound to ``db_path`` (or the resolved default)."""
    db_path = db_path or _resolve_db_path()
    server = FastMCP("pb-appeon-index")

    @server.tool()
    def appeon_search(
        query: str,
        version: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Keyword search across the Appeon doc index.

        ``query`` is an FTS5 match expression. Plain words are ANDed
        together; quote multi-word phrases. ``version`` filters to a
        single PB slug (e.g. ``pb2022r3``); omit to search all
        indexed versions. ``limit`` caps the result count.
        """
        conn = connect(db_path, read_only=True)
        try:
            return [hit.to_dict() for hit in search(conn, query, version, limit)]
        finally:
            conn.close()

    @server.tool()
    def appeon_get(name: str, version: str | None = None) -> dict[str, Any] | None:
        """Fetch a page by its exact name (case-insensitive).

        Returns the structured record (syntax, arguments, return value,
        examples, see-also). ``version`` pins to a specific slug;
        omit to take whichever record matches.
        """
        conn = connect(db_path, read_only=True)
        try:
            return get_by_name(conn, name, version)
        finally:
            conn.close()

    @server.tool()
    def appeon_list_topics(version: str | None = None) -> list[dict[str, Any]]:
        """Distinct ``(category, kind)`` buckets with page counts.

        Use this to discover what's been indexed. Filter by ``version``
        to scope to one PB slug.
        """
        conn = connect(db_path, read_only=True)
        try:
            return list_topics(conn, version)
        finally:
            conn.close()

    @server.tool()
    def appeon_list_versions() -> list[dict[str, Any]]:
        """Versions present in the index, with per-version page counts."""
        conn = connect(db_path, read_only=True)
        try:
            return list_versions(conn)
        finally:
            conn.close()

    return server


def run_stdio(db_path: Path | None = None) -> None:
    """Run the MCP server over stdio transport."""
    server = build_server(db_path)
    server.run()
