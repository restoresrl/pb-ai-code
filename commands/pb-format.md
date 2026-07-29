---
description: Re-format PowerBuilder entries to the workspace .pb-format.toml style conventions and land the result in the .pbl. Pure surface change — no semantics, no logic edits. Requires the optional pb-format tool.
argument-hint: <target> — entry triple `<lib>::<name>:<type>`, a `.pbl` path, or a `.pbt` path
---

# `/pb-format` — re-format PowerScript entries to the workspace style

Run a PowerScript style re-format over: **`$ARGUMENTS`**

The rules, the config contract and the boundaries are in the
`pb-format` skill — read
[`../skills/pb-format/SKILL.md`](../skills/pb-format/SKILL.md) now.
The engine is [`pb-format`](https://github.com/restoresrl/pb-format), a
separate optional CLI.

This flow changes **only** indent, keyword case, operator spacing and
line endings. No rename, no logic edit, no statement rewrite. If
behaviour needs to change, that is `/pb-review` instead.

## Pre-flight — three checks, in this order

1. **The tool.** Run `pb-format --version`. If it does not resolve,
   stop and say so: `uv tool install pb-format` (or
   `pipx install pb-format`). Do not attempt to hand-format anything as
   a substitute.
2. **The opt-in.** Walk up from the target's location looking for
   `.pb-format.toml`. If there is none, the user has not opted into a
   house style. Offer to generate one:

   > "No `.pb-format.toml` for this workspace. I can generate a starter
   > from the existing code with `pb-format detect <workspace>` — it
   > samples the sources and proposes the dominant style, for you to
   > review before committing. Shall I?"

   Never invent a config silently.
3. **The library.** `pb_workspace_info(lib_path)`. If the library is
   flagged `outside_source_tree` it is a vendored snapshot or a
   third-party component: a style sweep there will be overwritten at the
   next dependency update, and it turns that update into a merge
   conflict. Say so and stop unless the user insists.

Then bring up the ORCA session (`pb_session_open` with an explicit PB
version, `pb_set_library_list`, `pb_set_current_application`).

## The loop

1. **Resolve the scope.** An entry triple → that one entry. A `.pbl` →
   `pb_library_directory` over it. A `.pbt` → every library on the
   target's list. Drop `.srd` (DataWindow) entries — the formatter skips
   them by design — and report how many you dropped.
2. **Get the sources on disk.** `pb_object_export_file` per entry, or
   `pb_library_export_sources(lib_path)` for a whole library in one
   call. On a `pbl_only` project the bulk form *creates* a source
   projection that did not exist; say so before running it.
3. **Size the change honestly.** `pb-format check <paths>` reports which
   files would change without writing, and exits non-zero if any would.
   Present the count and the config that will be applied:

   > "`pb-format check` says 34 of 51 entries would change, under:
   > indent = tab, keyword_case = lower, spaces_around_operators = true.
   > The diff will be large. Proceed? I will confirm each entry with you
   > before importing it."

   Wait for an explicit yes. This is the gate before any write.
4. **Format.** `pb-format format <paths>`. It preserves the
   `$PBExportHeader$` / `$PBExportComments$` lines and round-trips the
   file's encoding, so nothing about the envelope changes.
5. **Land each changed entry.** For each file the formatter rewrote:
   show the diff, ask, and on yes `pb_object_import_file(file_path,
   lib_path)`. Read the response: `"error" in response` is a tool or
   state failure; `success: false` with an `errors` array is compile
   diagnostics. **A formatter that produces a compile error is a bug in
   the formatter** — stop the sweep, report it, and do not keep going
   through the queue. On success the text projection is updated in the
   same call (`sync` / `synced_files`).
6. **Summarize**: formatted N, skipped M (by user choice / by error),
   `.srd` skipped by design L, and the total line delta.

Formatting the text files without importing them would leave the `.pbl`
stale — a commit that reviews clean and builds old. Step 5 is not
optional.

## What this flow never does

- **Never changes semantics.** If the diff contains anything beyond
  indent / keyword case / operator spacing / line endings, that is a
  formatter bug: surface it, do not paper over it.
- **Never rewrites identifiers.** Variable, function and type names are
  preserved verbatim.
- **Never touches `.srd`** bodies.
- **Never touches the entry's comment metadata.** It rides in the
  `$PBExportComments$` line, which the formatter preserves.
- **Never commits.** A re-format can produce a very large diff; the user
  reviews and commits.
- **Never re-formats part of an entry.** The unit of work is the entry.

If `$ARGUMENTS` is missing, ask the user to restate. Do not guess.
