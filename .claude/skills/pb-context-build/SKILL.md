---
name: pb-context-build
description: Use this when you are about to read, review, or refactor PowerBuilder code in a monolithic legacy workspace and need to assemble a scoped context pack — a budgeted slice of entries (sources + dependency map) instead of dumping whole PBLs into the conversation. Orchestrates `pb-orca-mcp` primitives (`pb_target_info`, `pb_library_directory`, `pb_object_query_hierarchy`, `pb_object_query_reference`, `pb_library_entry_export`). Required pre-step for the `/pb-review` flow. v1.1 covers incoming references (callers) via ORCA and outgoing references (callees) via heuristic source parsing — dynamic calls are flagged but unresolved.
---

# Building a scoped context pack for review / refactoring

Use this skill any time you are about to **work on PowerBuilder code
in a real codebase** (not a fresh empty `.pbl`) and need to load
enough — but not too much — context into the agent.

PowerBuilder PBLs are physical containers, not logical modules. Real
legacy apps (Magware-class) hold thousands of entries spread across
dozens of PBLs. Reading them all at once is impossible; reading the
single target entry in isolation misses parents and callers. This
skill bridges the gap: it explores the dependency neighborhood of a
chosen target, respects a budget, and returns a structured
**context pack** the agent can use downstream.

## When to invoke this skill

- The user asks for code review, refactoring, bug-fix, or extension
  on an existing PowerBuilder workspace.
- The `/pb-review` slash command invokes you automatically as its
  context-building step.
- You are about to call `pb_library_entry_export` more than once and
  the choice of which entries to export is not obvious.
- You want to understand the blast-radius of a potential change
  (although for *that* specific question prefer
  [`pb-impact-analysis`](../pb-impact-analysis/SKILL.md) — it's a
  more focused report).

If the workspace is a brand-new `.pbl` you just created and you only
need to scaffold a fresh entry, this skill is overkill — go straight
to [`pb-scaffold`](../pb-scaffold/SKILL.md).

## The MCP primitives this skill orchestrates

All from the sibling [`pb-orca-mcp`](../../../../pb-orca-mcp/) server.
This skill never replaces a primitive; it just sequences them.

| Primitive | Purpose | Needs ORCA session? |
|---|---|---|
| `pb_target_info(path)` | Parse a `.pbt` (or `.pbw`) into liblist + app metadata | no |
| `pb_library_directory(lib_path, entry_type?)` | List entries in a PBL, optionally filter by type | no |
| `pb_object_query_hierarchy(lib_path, entry_name, entry_type)` | Inheritance chain (ancestors) of an entry | yes |
| `pb_object_query_reference(lib_path, entry_name, entry_type)` | **Incoming** references to an entry (callers). `ref_type` ∈ {`simple`, `open`} | yes |
| `pb_library_entry_information(lib_path, entry_name, entry_type)` | Metadata for an entry (timestamps, size, base class, comment) | yes |
| `pb_library_entry_export(lib_path, entry_name, entry_type)` | Full source of an entry as plain text | yes |

ORCA does not expose outgoing references natively. To populate the
`outgoing_refs` (callees) of each exported entry, this skill runs a
heuristic source-parsing pass over `pb_library_entry_export` output
(see "Callee discovery" below). Verification of each candidate uses
`pb_library_directory` against the configured liblist.

To use the session-bound primitives, the agent must first open a
session via `pb_session_open`, set the current application via
`pb_set_current_application`, and configure the library list via
`pb_set_library_list`. The [`pb-workflow`](../../../../pb-orca-mcp/.claude/skills/pb-workflow/SKILL.md)
skill in the sibling repo documents that bring-up sequence.

## Three scope flavors

The skill supports three starting points; pick the smallest one that
matches the user's request.

### Flavor A — entry-driven (default for "review this object")

Input: one entry triple `(lib_path, entry_name, entry_type)`.

Default flow:

1. Export the target entry's source (`pb_library_entry_export`).
2. Get the **inheritance chain** via `pb_object_query_hierarchy`.
   Export every ancestor's source up to the budget depth (default 3
   levels; the topmost framework class — `window`,
   `nonvisualobject`, etc. — is the natural stop).
3. Get the **callers** via `pb_object_query_reference` (depth 1 by
   default). For each caller, get its metadata via
   `pb_library_entry_information` to assess whether to expand it. By
   default, expand only `ref_type=open` callers (those that
   `Open()` the target) since they're the integration points;
   `ref_type=simple` callers (typed references) you list but don't
   expand unless budget allows.
4. If budget allows and the user asked for transitive callers
   (depth 2+), repeat step 3 on the depth-1 callers — but be
   aggressive about pruning: cap each level's expansion at ~5
   entries.

### Flavor B — target-driven (default for "review this `.pbt`")

Input: a `.pbt` (or `.pbw`) path.

Default flow (fast-path, v1.1):

1. `pb_target_info(path)` → extract `lib_list` and `app_name`. Cheap,
   no enumeration.
2. **Immediately** show the PBL list to the user:
   - "Target `foo.pbt`: app `app_foo`, 12 libraries: `mw_core.pbl`,
     `mw_aclw.pbl`, `mw_ppc.pbl`, …"
   - Ask: "Which PBL or entry name pattern do you want to focus on?"
3. Only after the user has chosen a sub-scope (a single PBL → Flavor
   C; a single entry → Flavor A; a name pattern → filtered Flavor
   C), run `pb_library_directory` on the chosen scope.

**Why fast-path?** On real legacy targets (~6-12 PBLs × 100+ entries
each), the v1 sweep — running `pb_library_directory` on every PBL —
costs many round-trips and almost always concludes with "too big,
refine". Skipping the sweep saves the round-trips and gets the user
to the same refinement turn one step earlier.

**Opt-in full sweep** (fallback): if the user explicitly asks for a
complete overview ("give me a count by entry type for the whole
target"), run the legacy v1 flow: enumerate all PBLs, aggregate
counts, return a summary like "1834 entries total (1240 functions,
312 userobjects, …); largest PBLs by entry count: `mw_core.pbl`
(412), …". Then ask for refinement before any export.

This flavor's job is **orientation**, not export. Exporting at the
target level is almost always a budget violation.

### Flavor C — PBL-driven (default for "review this PBL")

Input: one `lib_path`.

Default flow:

1. `pb_library_directory(lib_path, "any")` → list of entries.
2. If the count is small (≤ ~20 entries), proceed to export all of
   them in order; this is "review the whole PBL".
3. If the count is moderate (~20-100), filter by `entry_type` if the
   user named one ("review the userobjects in `mw_core.pbl`"). Then
   apply step 2 to the filtered set.
4. If the count is large (> ~100), refuse to export en masse. Return
   a summary and ask for refinement (single entry, or a sub-pattern
   match on entry name).

## Callee discovery (v1.1)

After exporting each entry's source, run a heuristic parsing pass to
populate the entry's `outgoing_refs` (callees). The MCP does not
expose outgoing references natively, so this is a best-effort step
verified against ORCA.

### Patterns the parser recognizes

Run regex passes on the exported source, in this order:

1. **Global function call**: `\bf_[a-z0-9_]+\s*\(` — PB convention,
   global functions are commonly prefixed `f_`. Refine to the
   project's actual convention if `pb_library_directory` reveals
   a different prefix.
2. **Method call on object reference**: `\b[a-z][a-z0-9_]*\.[a-z_]+\s*\(` —
   captures `iuo_logger.write(...)`, `lnv_target.flush(...)`, etc.
   Resolution of the receiver type requires reading declarations
   (DECLARE/instance variables) higher up in the same source.
3. **Ancestor / scoped call**: `\bCall\s+\w+::\w+`, `\bSuper::\w+`,
   `\b\w+::\w+\s*\(` — explicit scoped invocation.
4. **Event triggers**: `\b(Post|Trigger|Send)Event\b`,
   `\bPostEvent\s*\(`, `\bTriggerEvent\s*\(` — event names follow
   the open-paren or a comma after the target.
5. **Type declarations**: `\b[a-z]+_\w+\s+\w+\s*$` — captures
   `n_logger inv_log` or `u_dw_grid idw_main` declarations in
   instance variable blocks. The type name is a callee dependency.
6. **`Open()` / `OpenWithParm()` of windows**: captures the
   first arg literal if present.

### Filter step

Discard candidates that are PowerScript keywords (`if`, `then`,
`return`, `string`, …) or runtime built-ins. Use the
[`appeon-query`](../appeon-query/SKILL.md) skill to check if an
identifier matches a documented PowerScript function before treating
it as a user-defined callee.

### Verification step

For each surviving candidate identifier:

- Try `pb_library_directory` with each plausible `entry_type`
  (`function`, `userobject`, `window`, `datawindow`, `menu`,
  `structure`) against each PBL in the configured liblist. If found
  → add to `outgoing_refs` with `confidence: high` and `kind`
  resolved.
- If matched in multiple PBLs (homonyms), record all matches with
  `confidence: medium` — the agent or user will need to disambiguate.
- If no match: drop the candidate silently (likely a local variable,
  a builtin we missed, or a typo in the source).

### Unresolvable patterns (flagged, not resolved)

Mark these explicitly in the output as `confidence: low, kind:
dynamic`:

- `Dynamic Call`, `Dynamic Function`, `Dynamic Event` invocations.
- DataWindow expression strings (`SetItem(row, "col", value)` where
  `"col"` could be anything at runtime).
- Function name constructed at runtime via string concat:
  `f_call(name + "_handler")`.

The downstream consumer (`/pb-review`, `pb-apply-plan`) treats
`confidence: low` edges as warnings to surface to the user during
topo-sort or impact-check, not as hard dependencies.

### Editability contract

The `outgoing_refs` produced by this pass are **proposals**, not
truth. The downstream plan-file format (`.pb-review/<...>.md`,
opzione 2+ YAML front-matter) allows the user to edit the
`depends_on` field by hand. The user-augmented edges are marked
`confidence: user-augmented` and override anything the parser
suggested.

## Budget mechanics

The skill is judgment-based, not a strict counter. Defaults that
work as starting points on Magware-class codebases:

- **Hard cap on exported entries**: 20 per invocation. If the
  natural flow would exceed it, prune (depth, then breadth) until
  under cap.
- **Soft cap on cumulative source size**: ~150 KB of plain text
  (~50 K tokens). Track as you go; if you cross it before reaching
  step 3 (callers), stop and report what you have. The target
  entry and its inheritance chain take precedence over callers.
- **Default expansion depth**: ancestors = 3, callers = 1. Both
  configurable per invocation.
- **Pruning order** when over budget: (a) drop `simple`-typed
  callers first; (b) drop ancestors beyond depth 2; (c) drop
  framework-level ancestors (`nonvisualobject`, `window`,
  `userobject`) since the agent knows them from
  [`appeon-query`](../appeon-query/SKILL.md); (d) drop the lowest-
  priority callers last.

These caps are starting points, not law. Adjust if the user signals
they want a deeper or shallower view ("just the entry, no
ancestors", "give me the full caller tree two levels deep").

## Output: the context pack shape

Return a structured summary to whoever called you (usually
`/pb-review`, but could be a direct user invocation). Recommended
shape — flexible markdown, not a rigid schema:

```
## Context pack: <target description>

**Target**: `lib_path` :: `entry_name` (`entry_type`)

**Inheritance chain** (depth: N exported, M skipped):
- ancestor_1 (lib) — exported
- ancestor_2 (lib) — exported
- ...
- nonvisualobject — framework, not exported (see appeon-query)

**Incoming refs (callers)** — via `pb_object_query_reference`,
depth 1, N total, M exported:
- caller_1 (lib, ref_type=open) — exported
- caller_2 (lib, ref_type=simple) — listed, not exported (budget)
- ...

**Outgoing refs (callees)** — via heuristic source parsing,
verified against liblist, N total:
- callee_1 (lib, kind=function, confidence=high)
- callee_2 (lib, kind=userobject, confidence=high)
- callee_3 (?, confidence=medium) — homonym in 2 PBLs, disambiguate
- callee_4 (?, confidence=low, kind=dynamic) — Dynamic Call, flagged
- ...

**Budget**: N entries exported, ~K tokens of source loaded.
Pruned: <what was dropped and why>.

## Sources

### `lib_path` :: `entry_name` (target)

<full source>

### `lib_path` :: `ancestor_1`

<full source>

...
```

The agent that receives the pack is then responsible for the
downstream work (review, refactor, impact analysis). The pack is
informational, not executable. The `outgoing_refs` confidence levels
should be surfaced honestly — they are proposals, not facts.

## v1.1 limitations (explicit non-goals)

- **Callee discovery is heuristic, not exhaustive**. The parser
  catches static call patterns (function calls, method calls,
  ancestor scoped calls, event triggers, type declarations) and
  verifies each candidate against the liblist via
  `pb_library_directory`. Dynamic patterns (`Dynamic Call`, DW
  expressions, runtime-constructed function names) are flagged with
  `confidence: low` but not resolved. The downstream user can
  augment `depends_on` manually in the plan-file YAML.
- **No cross-target review**. If the workspace has multiple `.pbt`
  files (Magware: 13 targets) and the refactor would span them, v1.1
  does one target at a time. Cross-target is a future extension.
- **No caching of context packs between sessions**. Every invocation
  rebuilds from scratch. Caching is a future optimization if review
  latency becomes painful.
- **No automatic bulk sweep**. v1.1 is manual-assist: the user picks
  the target; the skill helps the agent understand it. Bulk
  refactoring across many targets is out of scope.

## Failure modes to handle gracefully

- **Session not open**: if `pb_session_open` hasn't been called, the
  session-bound primitives will fail. Detect early and ask the agent
  to bring up the session (or refer to `pb-workflow` for the
  bring-up recipe).
- **Entry not found**: `pb_object_query_*` errors when the entry
  doesn't exist in the library list. Verify the entry exists via
  `pb_library_directory` first, then guide the user to the correct
  spelling or PBL.
- **PBL not in library list**: even if the file exists on disk,
  `pb_object_query_*` only sees entries in the configured liblist.
  Check `pb_set_library_list` was called with all relevant PBLs of
  the target.
- **Huge caller set** (a base userobject used everywhere): truncate
  aggressively. Report the count honestly ("`u_base` has 487
  callers; showing the top 5 by recency, see
  [`pb-impact-analysis`](../pb-impact-analysis/SKILL.md) for the
  full blast-radius report").

## Boundaries with sibling skills

- [`pb-impact-analysis`](../pb-impact-analysis/SKILL.md) (planned):
  if the user's question is specifically "what breaks if I touch
  X", call that skill directly. It produces a tighter, blast-
  radius-focused report. This skill is broader: it loads context
  for *any* downstream task, not just impact assessment.
- [`pb-scaffold`](../pb-scaffold/SKILL.md): unrelated — that one is
  for *creating new* entries from minimal templates. This one is
  for *understanding existing* entries.
- [`appeon-query`](../appeon-query/SKILL.md): use it for questions
  about PowerScript syntax or runtime API, *not* for project-
  specific code. The two are complementary: this skill loads the
  project context; `appeon-query` loads the language context.
- [`pb-src-format`](../pb-src-format/SKILL.md): once you have the
  exported `.sr*` source in the context pack, that skill's wiki
  pages explain the file format if you need to edit them. The
  edit-encoding loop itself is in `pb-workflow` (sibling).

## Cross-reference: `/pb-review`

The slash command [`/pb-review`](../../commands/pb-review.md) is the
primary consumer of this skill. It invokes context-build → runs the
actual review → emits a structured report. Phase B (apply edits) is
deferred to a later iteration; v1 of `/pb-review` is report-only.
