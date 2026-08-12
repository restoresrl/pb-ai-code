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
server is not in this project's MCP configuration, and there is exactly
one reason for that: **the index has never been built on this machine.**
The installer adds the server by itself wherever it finds one — it runs
from the `pb-ai-code` checkout, so it knows the absolute paths — and
where it does not find one it says so, in its output and in the marker
file it leaves in the target. So this is a state with a cause and a
two-command cure, not a configuration anybody chose.

**The tools are listed but `appeon_search` errors** with something like
"database not found" — the server is wired up but the index has never
been populated on this machine.

In both cases: **tell the user, and never answer from memory.** A
PowerScript semantic you did not verify is a guess, and a guess inside
a finding is worse than an absent finding — it looks the same as a
right one and arrives with a suggested edit attached.

But "no MCP server" is not the same as "no index", and the difference
is worth two minutes. Work down this ladder and stop at the first rung
that answers:

1. **The database itself, if a `pb-ai-code` checkout is on this
   machine.** The MCP server is a thin wrapper over a SQLite file at
   `docs/appeon-index/index.db`, and the file is useful without the
   server. It is gitignored — every user builds their own — so it
   exists only where somebody has run `update`, but where it exists it
   is exact, offline, and costs nothing:

   ```python
   import sqlite3
   db = sqlite3.connect(r"C:\path\to\pb-ai-code\docs\appeon-index\index.db")
   c = db.cursor()
   c.execute("select version, name, url, syntax, return_value "
             "from pages where name = ?", ("Pos",))
   print(c.fetchall())
   ```

   Columns: `id`, `version`, `url`, `category`, `kind`, `name`,
   `description`, `syntax`, `arguments`, `return_value`, `examples`,
   `see_also`, `scraped_at`. For a name you are unsure of, search
   `pages_fts` and join back on `pages.id = pages_fts.rowid` — mind
   that both tables have a `name` column, so qualify it.

   A lookup answered this way is `verified-in-docs` exactly as if the
   server had answered, and cite the `url` column, which is the real
   Appeon page.

2. **A budgeted live fetch**, when there is no checkout and a finding
   genuinely turns on the semantic. Two or three pages, on the
   behaviours your findings depend on — not background reading. The
   objection to the web is **volume**, thousands of tokens per page,
   not principle. Be warned that guessing the URL wastes the budget:
   the page names are not derivable (`Pos` is `pos_func.html`), so
   search rather than construct.

3. **Neither** — then say so in the finding. `evidence:
   unverified-semantics` with an `experiment:` naming the concrete test
   that would settle it. That is an honest finding. Asserting it is not.

**There is one thing to do, and it is not editing an MCP config.** The
installer wires this server up by itself whenever the machine can host
it — it runs from the `pb-ai-code` checkout, so it knows the absolute
paths that a committed, shared config could never carry, and the
`.mcp.json` it writes is generated and gitignored, which makes it the
right place for them.

So the server is absent for exactly one reason: **the index has never
been built on this machine.** In the `pb-ai-code` checkout:

```pwsh
uv venv                                 # an environment with the tools
uv pip install -e ".[dev]"
.venv\Scripts\pb-appeon-index update    # scrape and index (idempotent)
```

Then re-run `scripts\install-skills.ps1` for the project, and the four
`appeon_*` tools appear. The permission file already pre-approves them.

**The database is referenced, never copied.** Every project points at the
one file in the checkout, so rebuilding the index — to add a PB release,
say, `pb-appeon-index update --version pb2025` after adding it to
`config.toml` — updates every configured project at once, with no
re-install. One file, many consumers; a new session picks up the new
content. Re-running the installer is for changed *skills*, not for a
changed index.

Full detail: `docs/appeon-index/README.md` and `docs/install.md` §3 in
that repository.
