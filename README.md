# pb-ai-code

Agentic dev kit for PowerBuilder — sibling project to
[`pb-orca-mcp`](https://github.com/restoresrl/pb-orca-mcp).

Where `pb-orca-mcp` exposes PowerBuilder's ORCA API to a coding agent
as MCP tools (the engine), `pb-ai-code` is the layer above: skills,
ingested Appeon documentation, test orchestration, debugging patterns
and slash commands that let a coding agent — Claude Code in first
instance, agent-agnostic by design — do full agentic PB development:
design, code, test, debug.

## Status

**WIP — design phase.** No scaffolding yet. The vision, decisions, and
open questions are in [`PLAN.md`](PLAN.md).

Active development on this repo starts **after** `pb-orca-mcp` is
published to PyPI as a stable, versioned dependency (currently
`v0.1.0`; target `pb-orca-mcp>=0.1.0`).

## What it will contain

- **Skills** — workflow patterns (scaffolding, idiomatic PowerScript,
  test orchestration, debugging) that the agent follows.
- **Layer 1 — Appeon doc index (`tools/pb-appeon-index/`)** —
  a Python tool that scrapes `docs.appeon.com` once into a local
  SQLite FTS5 database and exposes it as an MCP server with four
  tools (`appeon_search`, `appeon_get`, `appeon_list_topics`,
  `appeon_list_versions`). Multi-version by design — a TOML config
  lists the PB versions to index, and `pb-appeon-index update` is
  idempotent and incremental. A typical lookup costs ~400 tokens vs
  ~3000-10000 for a live `WebFetch`. See
  [`docs/appeon-index/README.md`](docs/appeon-index/README.md) for
  setup.
- **Layer 2 — `.sr*` source-file format wiki** — a Karpathy-style
  ["LLM Wiki"](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
  under `docs/pb-source-format/` documenting the textual layout of
  each PB entry type (`.sra`/`.srw`/`.sru`/`.srf`/`.srd`/`.srm`/
  `.srs`/`.srq`/`.srj`). Pre-populated by `pb-source-analyzer`
  (Python tool in `tools/`) from a real `.sr*` corpus, then grows
  incrementally during agent work — when the agent meets an
  undocumented variant, it appends an entry.
- **Test orchestration, framework-agnostic via adapters** — first
  adapter likely pbunit, abstraction extracted from there.
- **Structured logging pattern for runtime debugging** — PB has no DAP,
  so debugging is post-mortem; a structured-log convention plus a
  parser the agent can call.
- **Slash commands** — named flows that compose skills + MCP tools
  (e.g. `/pb-new-userobject`, `/pb-run-tests`, `/pb-trace`,
  `/pb-impact`).

See [`PLAN.md`](PLAN.md) for the full design.

## Dependencies

- [`pb-orca-mcp`](https://github.com/restoresrl/pb-orca-mcp) (required) —
  every action on `.pbl` libraries goes through its MCP tools. No ORCA
  primitive is reimplemented here.
- Claude Code (or another MCP-capable coding agent) to consume the
  skills and slash commands.

## License

MIT — see [`LICENSE`](LICENSE).

## Author

Carlo Torrese — Restore srl — `carlo.torrese@re-store.it`
