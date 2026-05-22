---
name: pb-format
description: Use this when you need to apply, generate, or verify PowerScript style conventions (indent, keyword case, operator spacing, line endings) on a `.sr*` source — either at write-time through `pb_edit_and_import`, or after the fact via the `/pb-format` slash command. Owns the `.pb-format.toml` config contract and the boundary between style normalization (this skill) and structural format (`pb-src-format`).
---

# PowerScript style formatting

This skill is about **how PowerScript looks on disk** — indent
character, keyword case, spacing around operators — separately from
**where things go in the file**, which is the domain of
[`pb-src-format`](../pb-src-format/SKILL.md), and separately from
**what the code does at runtime**, which is the domain of
[`appeon-query`](../appeon-query/SKILL.md). Use this skill when style
is the question.

## When to invoke this skill

- Before writing a new `.sr*` body and the workspace ships a
  `.pb-format.toml` (= the user has opted into style normalization).
  In that case, the agent does **not** hand-format the body — it
  emits the natural style and lets `pb_edit_and_import` normalize on
  its way to the `.pbl`.
- After the fact, when re-formatting an existing entry without
  changing its semantics. The slash command
  [`/pb-format`](../../commands/pb-format.md) is the dedicated
  entry point for this.
- When the user asks "what's the style of this codebase?" or "set up
  a `.pb-format.toml` for me" — see [Detecting the dialect](#detecting-the-dialect).
- When a code-review fix from `/pb-review` would be a pure style
  change (e.g. uppercase → lowercase keyword sweep). Flag it as a
  candidate for `/pb-format` instead of a per-entry fix, because the
  formatter handles it in one pass.

## What this skill covers

Four normalization invariants, fully specified in the wiki page
[`style-conventions`](../../../docs/pb-source-format/style-conventions.md):

1. **Indent** — TAB or `N` spaces, configurable.
2. **Body line endings** — locked to CRLF.
3. **Keyword case** — lowercase / UPPERCASE / preserve.
4. **Spaces around binary operators** — on / off.

Configuration lives in `.pb-format.toml` at the workspace root, with
the same lookup rules Prettier / dprint use (walk up from the source
path until a config is found, otherwise fall back to defaults).

Out of scope, deliberately:

- Identifier renaming (Hungarian prefix enforcement). That is a
  semantic rewrite — touches every reference — and belongs in a
  future `pb-lint` skill, not here.
- Blank-line policy between methods / events. Cosmetic, deferred to
  a future invariant.
- Continuation alignment after a line-ending `&`. Deferred.
- `.srd` (DataWindow) body. The formatter recognizes the extension
  and skips with a log line.

## How styling reaches the disk

There are two entry points, both backed by the same Python normalizer
inside `pb-orca-mcp`:

### Entry point 1 — `pb_edit_and_import` with `format="auto"`

The default flow for at-write normalization. When the agent calls
`pb_edit_and_import` to land a new or modified entry, the tool's
`format` parameter governs whether the body is normalized before
import:

- `"auto"` (default) — walk up from `source_path` looking for
  `.pb-format.toml`. If found → normalize. If absent → pass the body
  through (= today's behavior). **Zero breaking change** for
  workspaces that don't opt in.
- `True` — force normalization, use hard-coded defaults when no
  config is found.
- `False` — skip normalization entirely.

The agent does not need to call any extra tool; the choke-point is
`pb_edit_and_import` itself. Treat the body you produce as
*semantically* correct PowerScript; the normalizer makes it
*stylistically* correct on the way to the `.pbl`.

### Entry point 2 — `/pb-format` slash command

For re-formatting an entry **already on disk** without an import
cycle. The command exports the current source from the `.pbl` (or
reads it from `ws_objects/` if mirrored), runs the same normalizer
in-place, and writes the result back through `pb_edit_and_import`.
See [`/pb-format`](../../commands/pb-format.md) for the user-facing
flow.

Note: while the L2 normalizer engine is being implemented in
`pb-orca-mcp`, the `/pb-format` command is a stub that explains the
contract and points back here. Once the engine ships, the stub gets
replaced with the live flow without changing this skill's wording.

## Detecting the dialect

When a workspace has no `.pb-format.toml`, generate one with:

```
pb-format detect <workspace>
```

This Python CLI (entry point in `pb-orca-mcp`) samples N `.sr*` files
under the workspace, computes the frequency of each dimension
(indent character, keyword case, operator spacing) and writes a
`.pb-format.toml` with the winning choice for each. The output
includes explanatory comments so the user can review and adjust
before committing.

Heuristics applied:

- A ≥ 70% majority on a dimension → that's the choice.
- A 30-70% split → emit the majority but flag in a `# warning:`
  comment ("60% of files use uppercase; consider `preserve` if mixed
  is intentional").
- Mixed indent (tab + spaces in the same file) → flag, propose the
  more common one, do not silently rewrite.

After running `detect`, the next `pb_edit_and_import(format="auto")`
on the workspace picks up the new config and starts normalizing.

## Boundary with `pb-src-format`

These two skills are intentionally separate:

| Question | Skill |
|---|---|
| Where does the `forward prototypes` block go? | [`pb-src-format`](../pb-src-format/SKILL.md) |
| What does `$PBExportHeader$` look like? | [`pb-src-format`](../pb-src-format/SKILL.md) (encoding page) |
| Does `if` go before or inside the `function` declaration? | [`pb-src-format`](../pb-src-format/SKILL.md) (entry-type page) |
| `IF` or `if`? | this skill |
| Tab or spaces? | this skill |
| `a = b` or `a=b`? | this skill |

If you find yourself unsure, the rule is: **structural** (positions
of blocks, headers, terminators) → `pb-src-format`; **stylistic**
(how individual tokens render) → here.

When [`pb-src-format`](../pb-src-format/SKILL.md) ships a new
canonical-form template (Tier 1 work), this skill ensures the
template's surface style matches the formatter's defaults — so a
freshly scaffolded entry that runs through `pb_edit_and_import`
produces zero-diff output (idempotent).

## Boundary with `pb-scaffold`

[`pb-scaffold`](../pb-scaffold/SKILL.md) provides minimal templates
for new entries. Historically those templates baked in a specific
style (4-space indent, lowercase keywords) because no formatter
existed. With the formatter in place, the templates can now emit a
neutral baseline (4-space indent for readability in the skill text
itself) and rely on `pb_edit_and_import` to re-style on import per
the workspace's `.pb-format.toml`.

Practically: when scaffolding into a workspace with a
`.pb-format.toml`, the template's surface style does not matter — it
gets normalized. When scaffolding into a workspace without one,
nothing changes (formatter is no-op).

## Boundary with `pb-apply-plan`

[`pb-apply-plan`](../pb-apply-plan/SKILL.md) walks a code-review plan
voce-by-voce, calling `pb_edit_and_import` to land each fix. Because
`format="auto"` is the default, each landed fix is style-normalized
on the way in. The apply-plan skill itself does not need to know
about style — it lands semantic content, and the formatter ensures
the surface is consistent.

One operational consequence: when a `/pb-review` produces a fix
whose entire delta is a style change (e.g. lowercasing a single
keyword), the right move is usually to **skip that fix** in
`pb-apply-plan` and run `/pb-format` once over the affected entry
instead. Surface this to the user.

## When the formatter is the wrong tool

- **Pure semantic refactor** (rename, extract function, change
  signature). Style is a side effect; do the refactor via
  `/pb-review` + `pb-apply-plan` and let the formatter clean up the
  surface.
- **Mixed-style codebase** where the goal is to *preserve* per-file
  variance (rare but legitimate during a migration). Use
  `keyword_case = "preserve"` and accept that the formatter only
  normalizes the other three dimensions.
- **`.srd` (DataWindow) edits**. The formatter skips them; rely on
  [`pb-src-format`](../pb-src-format/SKILL.md) and the per-entry
  wiki pages.

## Cross-references

- [`docs/pb-source-format/style-conventions.md`](../../../docs/pb-source-format/style-conventions.md) —
  the rule spec the formatter implements.
- [`/pb-format`](../../commands/pb-format.md) — the slash command for
  re-formatting an entry on disk.
- [`pb-src-format`](../pb-src-format/SKILL.md) — structural format
  rules (where things go) — the sibling layer of this skill.
- [`pb-scaffold`](../pb-scaffold/SKILL.md) — emits minimal entry
  bodies; relies on this skill's normalizer at import time.
- [`pb-apply-plan`](../pb-apply-plan/SKILL.md) — calls
  `pb_edit_and_import` per fix; receives style normalization
  transparently.
- [`pb-workflow`](../../../../pb-orca-mcp/.claude/skills/pb-workflow/SKILL.md)
  (sibling) — documents `pb_edit_and_import` itself, including the
  `format` parameter.
