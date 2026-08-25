---
name: appeon-query
description: Use this whenever you need to look up PowerScript language syntax, runtime API, events, or DataWindow reference material. Drives the four MCP tools exposed by the local pb-appeon-index server (appeon_search / appeon_get / appeon_list_topics / appeon_list_versions). Replaces ad-hoc WebFetch against docs.appeon.com — those calls cost thousands of tokens per page; this skill keeps a typical lookup under ~400.
metadata:
  version: "1.1.0"
---

# Querying the Appeon doc index

Use this skill any time you need authoritative answers about
PowerScript itself — function signatures, runtime API, events on
visual controls, system objects, DataWindow methods, etc. The
content comes from `docs.appeon.com`, ingested once into a local
SQLite FTS5 index and exposed via four MCP tools.

This is the **Layer 1** companion to the `pb-src-format` skill
(Layer 2 — file-format wiki). They answer different questions:

- *"What does `Mid()` do? What are its arguments? What does it
  return?"* → **this skill** (the language).
- *"Where in a `.sru` file does the `forward` block go? What
  encoding does the file use?"* → `pb-src-format` (the file format).

If you can't decide which one applies, default to this skill for
anything about runtime behavior, and to `pb-src-format` for
anything about file layout on disk.

## The four MCP tools

| Tool | When to use |
|---|---|
| `appeon_search(query, version?, limit?)` | Keyword/concept lookup — you don't know the exact name. FTS5 ranks by relevance with the `name` field heavily weighted, so a query for `Left` ranks the `Left` page first ahead of related pages like `SetLeftMargin`. |
| `appeon_get(name, version?)` | Pull the full structured record for a page whose name you already know (or just learned from `appeon_search`). Returns `{name, description, syntax, arguments, return_value, examples, see_also, ...}`. |
| `appeon_list_topics(version?)` | Discover what categories and entry kinds are indexed (e.g. `powerscript_reference / function`, `powerscript_reference / event`). Useful when a `appeon_search` returns nothing. |
| `appeon_list_versions()` | List the PB versions present in the index with page counts. Useful at the start of a session to know what's covered. |

## Default flow

1. Start with `appeon_search(query)`. If the top hit's `name` matches
   what you were looking for and the `description` excerpt confirms,
   call `appeon_get(name)` for the full structured content.
2. If the top hit looks off (wrong topic, low relevance to the query),
   inspect the next 2-3 hits before falling back. Often the right
   page is at rank 2-3 because of how the underlying docs phrase
   things.
3. If `appeon_search` returns empty, try a less specific query (the
   index favors keyword match, so multi-word semantic queries
   sometimes miss). As last resort, `appeon_list_topics()` to confirm
   the topic area is even indexed.

## Versioning

The index can hold multiple PB versions simultaneously. The default
(`pb2022r3`) is the lowest-priority slug in `config.toml`. If you
need to compare versions or pin to a specific one, pass the
`version` argument. To find out what's available, call
`appeon_list_versions()`.

## Cost expectations

- `appeon_search` returns ~10 short hits, ~30-60 tokens each:
  total ~300-600 tokens.
- `appeon_get` returns one full record, typically ~300-500 tokens.
- A typical "I need to know how `Foo()` works" exchange costs
  ~400-800 tokens vs ~3000-10000 tokens for a live web fetch of the
  same content. Use the index first; reserve a live web fetch for cases
  where the index returns nothing and you need to confirm a guess.

## Boundary with `pb-src-format`

This skill answers questions about *PowerScript behavior at runtime*
(what the function does, what arguments it takes, what events fire
when). It does **not** answer questions about how a `.sru`/`.srw`/...
file is laid out on disk — that's `pb-src-format`'s job. If you find
yourself reaching for `appeon_search` to find file-format details,
switch skills.

## What to do when the index isn't available

Two different situations, and they need different things said.

**The `appeon_*` tools are not listed at all.** The `pb-appeon-index`
server is not in this project's MCP configuration. The usual reason is that
the index has not been built for this Windows user. The installer adds the
server when it finds the shared database. Otherwise it reports the missing
database in its output and marker file. This is a setup gap, not a project
configuration decision.

**The tools are listed but `appeon_search` errors** with something like
"database not found" — the server is wired up but the index has never
been populated on this machine.

In both cases: **tell the user, and never answer from memory.** A
PowerScript semantic you did not verify is a guess, and a guess inside
a finding is worse than an absent finding — it looks the same as a
right one and arrives with a suggested edit attached.

But "no MCP server" is not the same as "no index". Work down this ladder
and stop at the first rung that answers:

1. **The shared database itself.** Its normal location is
   `%USERPROFILE%\.pb-appeon-index\index.db`. It is useful without the MCP
   server and is exact, offline, and free to query:

   ```python
   import sqlite3
   db = sqlite3.connect(r"C:\Users\me\.pb-appeon-index\index.db")
   c = db.cursor()
   c.execute("select version, name, url, syntax, return_value "
             "from pages where name = ?", ("Pos",))
   print(c.fetchall())
   ```

   Columns: `id`, `version`, `url`, `category`, `kind`, `name`,
   `description`, `syntax`, `arguments`, `return_value`, `examples`,
   `see_also`, `scraped_at`. For a name you are unsure of, search
   `pages_fts` and join back on `pages.id = pages_fts.rowid`. Both tables
   have a `name` column, so qualify it.

   A lookup answered this way is `verified-in-docs` exactly as if the server
   had answered. Cite the `url` column, which is the real Appeon page.

2. **A budgeted live fetch**, when the database is absent and a finding
   depends on the semantic. Read two or three pages about the required
   behavior, not background material. Search for the page instead of guessing
   its URL; `Pos`, for example, is `pos_func.html`.

3. **Neither**. Record `evidence: unverified-semantics` with an `experiment:`
   that names the concrete test that would settle it. Do not present an
   unverified semantic as fact.

**Do not edit an MCP config by hand to add this server.** The project installer
adds it when it finds a database. If the index is absent, ask the user whether
they want to download and build it once for their Windows user:

```pwsh
pb-appeon-index update --all
```

If the command is not installed persistently, the user can run:

```pwsh
uvx --from git+https://github.com/restoresrl/pb-ai-code@v0.11.1 `
  pb-appeon-index update --all
```

Then rerun `pb-ai-code install` for the project and restart the assistant so
the four `appeon_*` tools appear.

**The database is referenced, never copied.** Every project points at the one
machine-local file, so rebuilding it updates every configured project without
a reinstall. Reinstall projects for changed skills, not for a database refresh.

For setup details, direct the user to the installation guide for
`pb-ai-code`.
