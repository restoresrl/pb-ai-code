# Appeon doc index — Layer 1 of the pb-ai-code knowledge architecture

A searchable, token-efficient index of Appeon's PowerBuilder
documentation, exposed to any MCP-capable coding assistant as four
tools:

- `appeon_search(query, version?, limit?)` — FTS5 keyword search.
- `appeon_get(name, version?)` — full structured page record.
- `appeon_list_topics(version?)` — category / kind buckets.
- `appeon_list_versions()` — versions present in the DB.

The agent-side flow is driven by the
[`appeon-query`](../../skills/appeon-query/SKILL.md) skill.

## What it replaces

This is the Layer 1 substitute for the originally-planned
`cli-printing-press` integration, which turned out to be the wrong
tool for the job (it targets REST API docs, not language-reference
sites — see `PLAN.md` for the full story). The replacement is
written in Python, lives in `tools/pb-appeon-index/`, and reuses
the same stack as `tools/pb-source-analyzer/`.

## Why an index and not WebFetch

A `WebFetch` against `docs.appeon.com/pb2022r3/.../left_func.html`
pulls the entire page (sidebar + nav + body + footer) and converts
it to Markdown — typically 3000-10000 tokens per call. Multiply by
"every PowerScript lookup in a coding session" and the cost dominates.

The index, after a one-time scrape into a local SQLite FTS5 DB,
answers a typical query in ~400 tokens — about 10x cheaper. It is
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

A single SQLite DB holds every indexed version; rows are
distinguished by the `version` column. Adding a new version is a
TOML edit (no code change):

```toml
# tools/pb-appeon-index/config.toml
[[versions]]
slug = "pb2025"
base_url = "https://docs.appeon.com/pb2025/"
sections = ["powerscript_reference"]
priority = 2
```

…then `pb-appeon-index update --version pb2025`.

The full list of slugs Appeon currently publishes (verified
2026-05-15): `pb2017`, `pb2017r2`, `pb2017r3`, `pb2019`, `pb2019r2`,
`pb2019r3`, `pb2021`, `pb2022`, `pb2022r2`, `pb2022r3`, `pb2025`,
`pb2025r2` (Beta).

## How to build the index

Prereq: this repo's Python env (editable install of `pb-ai-code` in
a venv): `pip install -e ".[dev]"`.

```pwsh
# One-shot: scrape + parse + index for the default version
pb-appeon-index update

# Rebuild a specific version (idempotent — safe to re-run)
pb-appeon-index update --version pb2022r3

# Re-index every configured version
pb-appeon-index update --all
```

The first run scrapes from `docs.appeon.com` with a polite 200ms
delay between requests (configurable in `[scraper]`). Subsequent
runs use conditional `If-None-Match` / `If-Modified-Since` headers
to skip pages whose content hasn't changed — so updating to pick up
new doc edits is fast.

Inputs and outputs:

| Path | Contents | Gitignored? |
|---|---|---|
| `tools/pb-appeon-index/config.toml` | version list + scraper settings | no — committed |
| `.appeon-cache/<slug>/...html` | raw HTML mirror, one file per page | **yes** |
| `.appeon-cache/<slug>/.etag.json` | per-URL ETag/Last-Modified cache | **yes** |
| `docs/appeon-index/index.db` | SQLite FTS5 database | **yes** |
| `docs/appeon-index/README.md` | this file | no — committed |

## Wiring up the MCP server

The repo ships a project-level `.mcp.json` at the root. Claude Code
reads that file directly; for another client, copy the block into
whatever MCP config it uses (see [`docs/install.md`](../install.md)).
It points at the venv-resident Python so no PATH activation is needed:

```jsonc
{
  "mcpServers": {
    "pb-appeon-index": {
      "command": ".venv/Scripts/python.exe",
      "args": ["-m", "pb_appeon_index", "serve-mcp"]
    }
  }
}
```

Prereq for this form: a Python virtualenv at `.venv/` with
`pb_appeon_index` installed (`pip install -e ".[dev]"`).

The relative paths in that block assume the client launches the server
with the project root as its working directory, which is the usual
behaviour; the server falls back to `./docs/appeon-index/index.db` on
the same assumption. If either does not hold for your client, use
absolute paths for `command` and set `PB_APPEON_INDEX_DB` to the DB's
absolute path.

A user-level config works too if you would rather not commit the
server entry — the JSON shape is the same.

Once the server is connected, the agent calls `appeon_search` /
`appeon_get` / `appeon_list_topics` / `appeon_list_versions` as
ordinary MCP tools.

## Re-running for a new PB release

Steps the day a new PB release lands on `docs.appeon.com`:

1. Add a `[[versions]]` entry in `config.toml` with the new slug.
2. `pb-appeon-index update --version <new-slug>` — fetches only the
   new pages, leaves existing versions untouched.
3. Commit the updated `config.toml`. The `index.db` is gitignored;
   each developer rebuilds locally.

To refresh an existing version (e.g. Appeon edited a function page),
re-run the same `update --version <slug>`; conditional GETs make it
fast, and `INSERT OR REPLACE` handles the changed rows.

## What the index does *not* cover

- The textual format of `.sr*` source files. That's Layer 2 — see
  the [`pb-source-format` wiki](../pb-source-format/index.md) and
  the [`pb-src-format`](../../skills/pb-src-format/SKILL.md) skill.
- Project-specific codebase patterns (naming conventions, internal
  libraries, idiomatic flow for a given product). That's Layer 3 — deferred.
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
