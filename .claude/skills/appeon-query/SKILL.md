---
name: appeon-query
description: Use this whenever you need to look up PowerScript language syntax, runtime API, events, or DataWindow reference material. Drives the four MCP tools exposed by the local pb-appeon-index server (appeon_search / appeon_get / appeon_list_topics / appeon_list_versions). Replaces ad-hoc WebFetch against docs.appeon.com — those calls cost thousands of tokens per page; this skill keeps a typical lookup under ~400.
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
  ~400-800 tokens vs ~3000-10000 tokens for a `WebFetch` of the
  same content. Use the index first; reserve `WebFetch` for cases
  where the index returns nothing and you need to confirm a guess.

## Boundary with `pb-src-format`

This skill answers questions about *PowerScript behavior at runtime*
(what the function does, what arguments it takes, what events fire
when). It does **not** answer questions about how a `.sru`/`.srw`/...
file is laid out on disk — that's `pb-src-format`'s job. If you find
yourself reaching for `appeon_search` to find file-format details,
switch skills.

## What to do when the index isn't built

If `appeon_search` returns an error like "database not found" or the
MCP server isn't connected, the local index hasn't been built yet
on this machine. Tell the user; do not silently fall back to
`WebFetch`. The user can run `pb-appeon-index update` to populate
the index — instructions live in `docs/appeon-index/README.md`.
