---
description: Re-format an existing PowerBuilder entry (or a set of them) according to the workspace `.pb-format.toml` style conventions. Pure surface change — no semantics, no edits to logic. Backed by the same normalizer used at write-time by `pb_edit_and_import(format="auto")`.
argument-hint: <target> — entry triple `<lib>::<name>:<type>`, a `.pbl` path, or a `.pbt` path
---

# `/pb-format` — re-format an entry on disk

You are running a PowerScript style re-format on the target the user
specified. The argument is: **`$ARGUMENTS`**

This command applies the four style invariants documented in
[`docs/pb-source-format/style-conventions.md`](../../docs/pb-source-format/style-conventions.md)
to the source of each in-scope entry. It does **not** change
semantics — no rename, no logic edit, no statement rewrite. The diff
should be a surface-only sweep (keyword case, indent character,
operator spacing, line endings).

If you need to change behavior, use [`/pb-review`](pb-review.md)
instead and let `pb-apply-plan` land the change; the formatter then
runs implicitly on import.

## Status — stub during L2 implementation

The body normalizer engine lives in
[`pb-orca-mcp`](../../../pb-orca-mcp/) under
`src/pb_orca_mcp/format/` (planned). Until that ships, this command
is a stub: it explains the flow and points the user at the skill
[`pb-format`](../skills/pb-format/SKILL.md) for the contract. Once
the engine is live, this section is removed and the flow below
becomes executable.

To check status: look for `from pb_orca_mcp.format import format_powerscript`
in the sibling repo. If the import resolves, the engine is live.

## What `$ARGUMENTS` can be

Three accepted forms:

1. **Entry triple** — `<lib_path>::<entry_name>:<entry_type>`. Most
   focused scope: one entry.
2. **`.pbl` path** — `<path>.pbl`. Re-formats every entry in that
   library.
3. **`.pbt` path** — `<path>.pbt`. Re-formats every entry across
   every library on the target's library list.

If the argument is missing, ask the user to restate. Do not guess.

## Pre-flight

Before doing anything, verify:

1. **MCP session is up**. If `pb_session_open` has not been called
   yet in this conversation, open one now and bring up the target
   per the
   [`pb-workflow`](../../../pb-orca-mcp/.claude/skills/pb-workflow/SKILL.md)
   bring-up recipe.
2. **`.pb-format.toml` exists** for the workspace. Walk up from the
   target's location until you find one. If absent, surface to the
   user:

   > "Nessun `.pb-format.toml` trovato per il workspace. Posso
   > generarlo con `pb-format detect <workspace>` (verrà proposto un
   > set di default basato sul codice esistente, da rivedere prima
   > del commit). Procedo?"

   Do not invent a config silently — the user must opt in.
3. **Engine availability**. If the `pb_orca_mcp.format` module is
   not importable, stop and report "L2 engine non ancora disponibile
   in `pb-orca-mcp`. Vedi PLAN.md per lo stato di implementazione."

## Step 1 — Enumerate the entry set

Resolve `$ARGUMENTS` to a concrete list of entry triples:

- **Triple** → singleton list.
- **`.pbl`** → `pb_library_directory` over that PBL.
- **`.pbt`** → enumerate each PBL on the target's library list,
  union the entries.

Filter out `.srd` (DataWindow) entries — the formatter skips them
with a log line. Surface the count of skipped entries to the user.

Compute a budget estimate: total source lines that will be
re-emitted. If > 10000 lines, ask the user to confirm before
proceeding — the run is fast but the diff will be large.

## Step 2 — Confirm the run plan

Present the enumerated set and the config that will be applied:

> "Re-format di N entry secondo `.pb-format.toml`:
>
> - indent = tab
> - keyword_case = lower
> - spaces_around_operators = true
>
> Entry coinvolti:
> 1. lib_a.pbl :: n_widget : userobject
> 2. lib_a.pbl :: n_logger : userobject
> 3. ...
>
> Procedo? (verrà chiesta conferma su ogni entry con diff visibile)"

Wait for explicit OK. This is the gate before any write.

## Step 3 — The format loop

For each entry in the enumerated set:

### (a) Read current source

Export via `pb_library_entry_export`. The exported body does **not**
include `$PBExportHeader$` / `$PBExportComments$` — those are an
on-disk export convention. Keep that in mind when computing the
diff: the diff is over the body, not the header block.

### (b) Format

Call `pb_orca_mcp.format.format_powerscript(source, config)` (when
the engine is live). The function returns the normalized body.

If `format_powerscript` raises on the input, surface the diagnostic
and skip the entry — never blindly re-import an entry the formatter
choked on.

### (c) Present the diff and confirm

Compute a unified diff between current and formatted bodies. Show
the user:

```
n_widget : userobject in lib_a.pbl
N lines, M lines changed

--- current
+++ formatted
@@ -42,3 +42,3 @@
-    IF ll_x = 0 THEN
+    if ll_x = 0 then
        return false
-    END IF
+    end if
```

Ask: "Applico il re-format a questa entry?".

### (d) On user OK

Call `pb_edit_and_import` with `format=False` (the body is already
formatted; we don't want the normalizer to re-run inside the tool):

```jsonc
pb_edit_and_import {
  "lib_path":         "<from entry triple>",
  "entry_name":       "<from entry triple>",
  "entry_type":       "<from entry triple>",
  "syntax":           "<formatted body>",
  "source_path":      "<workspace>/ws_objects/<lib>.pbl.src/<name>.<ext>",
  "comments":         "<preserved from the original entry metadata, do not invent>",
  "source_encoding":  "<from workspace .pbw DefaultExportEncode>",
  "format":           false
}
```

The original entry's comment metadata must be preserved verbatim;
this command is a surface re-format, not a metadata edit.

On `success: true` → mark the entry as formatted, continue to the
next.

On compile error → present errors, ask whether to revert (re-import
the original body) or skip and continue. Never silently accept a
broken state.

### (e) On user refusal (skip)

Skip this entry. Continue with the next. No CHANGELOG entry, no
plan-file update — `/pb-format` does not produce review artifacts.
The user can always re-run later.

## Step 4 — Summary

When the loop ends:

> "Re-format completato:
>
> - Formattati: N
> - Saltati: M (di cui K per scelta utente, K' per errore)
> - `.srd` skip-by-design: L
>
> Diff totale: <added>/<removed> linee su <total> linee."

## What this command never does

- **Never edits semantics.** If the formatter would change anything
  other than indent / keyword case / operator spacing / line
  endings, the implementation has a bug — surface it, do not paper
  over it.
- **Never rewrites identifiers.** Variable / function / type names
  are preserved verbatim.
- **Never edits `.srd` (DataWindow)** bodies. Skipped with a log
  line.
- **Never edits the entry's `comments` metadata.** That field is
  read from the existing entry and passed back unchanged.
- **Never modifies `$PBExportHeader$` / `$PBExportComments$`** lines
  directly — those are regenerated canonically by
  `pb_edit_and_import` from the entry name + comment metadata.
- **Never commits.** Re-formatting may produce large diffs; the
  user reviews and commits manually.

## Hard limits for v1.x

- **One workspace at a time**. The command operates on the single
  workspace `$ARGUMENTS` lives in. Cross-workspace sweeps are out
  of scope.
- **No partial entries**. The unit of work is the entry; the
  formatter does not re-format a single function inside an entry.
  (If that becomes a real need, it goes through `/pb-review` as a
  refactor finding instead.)
- **No automated test execution post-format**. The expectation is
  zero-semantic-change; if the workspace has tests, the user runs
  them.

## Cross-references

- [`pb-format`](../skills/pb-format/SKILL.md) — the skill that
  documents the formatter's contract and entry points.
- [`docs/pb-source-format/style-conventions.md`](../../docs/pb-source-format/style-conventions.md) —
  the rule spec.
- [`/pb-review`](pb-review.md) — for non-style changes that need a
  review-and-apply flow.
- [`pb-workflow`](../../../pb-orca-mcp/.claude/skills/pb-workflow/SKILL.md)
  (sibling) — documents `pb_edit_and_import` including the `format`
  parameter.
