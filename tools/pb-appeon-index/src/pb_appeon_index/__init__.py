"""pb-appeon-index — searchable index of Appeon PowerBuilder docs.

Layer 1 of the pb-ai-code knowledge architecture. Replaces the
abandoned cli-printing-press attempt (which targets API REST docs,
not language-reference doc-sites).

Pipeline:

    scrape    -> fetch HTML pages from docs.appeon.com, cache locally
    parse     -> extract structured fields (name, syntax, args, return, examples)
    index     -> populate a SQLite FTS5 database
    serve-mcp -> expose appeon_search / appeon_get / appeon_list_topics
                 as MCP tools for any MCP-capable agent

Each step is a CLI subcommand exposed by ``python -m pb_appeon_index``
or the console script ``pb-appeon-index``.
"""

from __future__ import annotations

__version__ = "0.0.1"
