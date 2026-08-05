"""The MCP server can actually be constructed.

This exists because it once could not, and nothing noticed. `mcp` 2.0.0
removed `mcp.server.fastmcp`, the dependency had no upper bound, and every
other test kept passing because none of them imported this module — while
`__main__` imports it at module scope, so *every* subcommand died, including
the `update` that `docs/install.md` tells you to run first.

Building the server touches the import, the FastMCP construction and the four
tool registrations, which is the whole surface a client depends on before it
sends a single request. It needs no database: `build_server` only resolves a
path, and the tools open the connection when called.
"""

from __future__ import annotations

import asyncio

EXPECTED_TOOLS = {
    "appeon_search",
    "appeon_get",
    "appeon_list_topics",
    "appeon_list_versions",
}


def test_build_server_registers_every_tool(tmp_path) -> None:
    from pb_appeon_index.mcp_server import build_server

    server = build_server(tmp_path / "index.db")
    names = {t.name for t in asyncio.run(server.list_tools())}
    assert names == EXPECTED_TOOLS


def test_cli_module_imports() -> None:
    """`__main__` imports `mcp_server` at module scope, so a broken MCP layer
    takes the whole CLI down with it - `update` and `search` included."""
    from pb_appeon_index.__main__ import main

    assert callable(main)
