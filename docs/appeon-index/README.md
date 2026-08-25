# Appeon doc index: Layer 1 of the pb-ai-code knowledge architecture

A searchable, token-efficient index of Appeon's PowerBuilder
documentation, exposed to any MCP-capable coding assistant as four
tools:

- `appeon_search(query, version?, limit?)`: FTS5 keyword search.
- `appeon_get(name, version?)`: full structured page record.
- `appeon_list_topics(version?)`: category / kind buckets.
- `appeon_list_versions()`: versions present in the DB.

The agent-side flow is driven by the
[`appeon-query`](../../skills/appeon-query/SKILL.md) skill.

## What it replaces

This is the Layer 1 substitute for the originally-planned
`cli-printing-press` integration, which turned out to be the wrong
tool for the job (it targets REST API docs, not language-reference
sites: see `PLAN.md` for the full story). The replacement is
written in Python, lives in `tools/pb-appeon-index/`, and reuses
the same stack as `tools/pb-source-analyzer/`.

## Why an index and not WebFetch

A `WebFetch` against `docs.appeon.com/pb2022r3/.../left_func.html`
pulls the entire page (sidebar + nav + body + footer) and converts
it to Markdown: typically 3000-10000 tokens per call. Multiply by
"every PowerScript lookup in a coding session" and the cost dominates.

The index, after a one-time scrape into a local SQLite FTS5 DB,
answers a typical query in ~400 tokens: about 10x cheaper. It is
also offline-resilient: once built, queries don't touch the network.

## What's in the index

The DB contains one row per indexed doc page, with these fields
(see `tools/pb-appeon-index/src/pb_appeon_index/parse.py` for the
extraction):

| Field | Source |
|---|---|
| `version` | PB version slug (e.g. `pb2022r3`) |
| `url` | the canonical docs.appeon.com URL |
| `category` | top section under the version (e.g. `powerscript_reference`) |
| `kind` | inferred from the URL suffix: `function` (`*_func.html`), `event` (`*_event.html`), `object` (`*_obj.html`), `statement` (`*_stmt.html`), … |
| `name` | from `<meta name="Section-title">` |
| `description`, `syntax`, `arguments`, `return_value`, `examples`, `see_also` | extracted from the function-page template |

FTS5 indexes `name`, `description`, `syntax`, `arguments`,
`return_value`, `examples`. The `name` field is weighted 10× via
`bm25()` so a search for `Left` ranks the `Left` page first
ahead of related pages like `SetLeftMargin`.

## Multi-version

A single SQLite DB holds every indexed release; rows are distinguished by the
`version` slug. The packaged catalog contains the Appeon releases supported by
the kit. Normal setup does not require a TOML edit: `pb-ai-code search setup`
detects installed products and indexes their matching slugs.

A project records one exact slug, for example `pb2022r3`. That same slug filters
every documentation query. ORCA's `22.0` is derived from the slug and is not a
documentation version: it cannot distinguish PB 2022, 2022 R2, and 2022 R3.

The full list of slugs Appeon currently publishes (verified
2026-05-15): `pb2017`, `pb2017r2`, `pb2017r3`, `pb2019`, `pb2019r2`,
`pb2019r3`, `pb2021`, `pb2022`, `pb2022r2`, `pb2022r3`, `pb2025`,
`pb2025r2` (Beta).

## How to build the index

For a normal installation, install the kit as a persistent tool:

```pwsh
uv tool install git+https://github.com/restoresrl/pb-ai-code@v0.12.1
```

Then set up the shared machine-local database:

```pwsh
# Detect installed releases, show their slugs, and ask before downloading.
pb-ai-code search setup

# Inspect detected releases and indexed documentation.
pb-ai-code search status

# Refresh documentation for releases installed on this machine.
pb-ai-code search update
```

For diagnostics or a deliberate override, the lower-level command remains:

```pwsh
pb-appeon-index update --version pb2022r3
```

These commands use the default shared database at
`%USERPROFILE%\.pb-appeon-index\index.db`.

When developing this repository itself, an editable environment also works:
`uv venv` followed by `uv pip install -e ".[dev]"`.

The first run scrapes from `docs.appeon.com` with a polite 200ms
delay between requests (configurable in `[scraper]`). Subsequent
runs use conditional `If-None-Match` / `If-Modified-Since` headers
to skip pages whose content hasn't changed, so updating to pick up
new doc edits is fast.

Inputs and outputs:

| Path | Contents | Gitignored? |
|---|---|---|
| `tools/pb-appeon-index/config.toml` | version list + scraper settings | no: committed |
| `~/.pb-appeon-index/cache/<slug>/...html` | raw HTML mirror, one file per page | outside the repository |
| `~/.pb-appeon-index/cache/<slug>/.etag.json` | per-URL ETag/Last-Modified cache | outside the repository |
| `~/.pb-appeon-index/index.db` | SQLite FTS5 database | outside the repository |
| `docs/appeon-index/README.md` | this file | no: committed |

## Wiring up the MCP server

> **On redistributing the index.** Each developer builds their own, and the
> database is never shipped. That is deliberate: the PowerBuilder manuals
> reserve reproduction rights, so a built index attached to a release would
> need Appeon's written permission. A drafted request for exactly that is in
> [`redistribution request`](../internal/appeon-index-redistribution-request.md):
> unsent, and nothing changes until it is answered.

**The installer configures this server for you** once the index exists.
It resolves the machine-local database to an absolute path and writes it into
the target's `.mcp.json`: a generated, gitignored, per-machine file.
The committed `harness/mcp-servers.json` cannot carry those paths, which
is why the entry is not in it and why this was once a manual step.

So the sequence is: build the index (above), then re-run the installer.
It prints `Appeon index      <db path>` and records the decision in the
marker as `# Appeon:    pb-appeon-index configured -> <db path>`, or names
what is missing if you have not built it yet.

The block uses `uvx` to start the same release that installed the project,
and it records the absolute path of the shared database:

```jsonc
{
  "mcpServers": {
    "pb-appeon-index": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/restoresrl/pb-ai-code@v0.12.1",
        "pb-appeon-index",
        "serve-mcp"
      ],
      "env": {
        "PB_APPEON_INDEX_DB": "C:\\Users\\me\\.pb-appeon-index\\index.db"
      }
    }
  }
}
```

The project does not need a checkout or a Python virtual environment. Absolute
paths keep the server independent of the MCP client's working directory.

Where the block goes depends on the client:
[`docs/install.md`](../install.md) has the table.

Once the server is connected, the agent calls `appeon_search` /
`appeon_get` / `appeon_list_topics` / `appeon_list_versions` as
ordinary MCP tools.

## Re-running for a new PB release

Steps the day a new PB release lands on `docs.appeon.com`:

1. Add the new slug and its ORCA mapping to the bundled release catalog when
   contributing to this repository.
2. `pb-appeon-index update --version <new-slug>` fetches only the new pages
   and leaves existing versions untouched.
3. Each developer runs `pb-ai-code search update` to rebuild documentation for
   releases installed on their machine. The database is not committed or
   redistributed.

To refresh an existing version (e.g. Appeon edited a function page),
re-run the same `update --version <slug>`; conditional GETs make it
fast, and `INSERT OR REPLACE` handles the changed rows.

## What the index does *not* cover

- The textual format of `.sr*` source files. That's Layer 2, see
  the [`pb-source-format` wiki](../pb-source-format/index.md) and
  the [`pb-src-format`](../../skills/pb-src-format/SKILL.md) skill.
- Project-specific codebase patterns (naming conventions, internal
  libraries, idiomatic flow for a given product). That's Layer 3, deferred.
- License-restricted content. Each developer rebuilds the index
  locally from the live `docs.appeon.com` site; the DB is not
  redistributed.

## Limitations and known gaps

- The parser is tuned to the function-page template (`*_func.html`).
  Pages of other kinds (object, event, statement) parse with the
  same code paths but may have weaker `description` / `arguments` /
  `return_value` extraction. Fix: extend `parse.py` per kind as
  gaps surface in real use.
- See-also links are kept as relative URLs; the agent has to
  combine them with the base URL if it wants to chase one (or just
  pass the resolved name to `appeon_get`).
- The scraper's link-follower stays inside the section base URL,
  which means inter-section cross-references (e.g.
  `powerscript_reference` → `datawindow_reference`) are not crawled
  unless both sections are listed in `config.toml`.
