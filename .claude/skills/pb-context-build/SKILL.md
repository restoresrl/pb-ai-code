---
name: pb-context-build
description: Use this when you are about to read, review, or refactor PowerBuilder code in a monolithic legacy workspace and need to assemble a scoped context pack — a budgeted slice of entries (sources + dependency map) instead of dumping whole PBLs into the conversation. Orchestrates `pb-orca-mcp` primitives (`pb_target_info`, `pb_library_directory`, `pb_object_query_hierarchy`, `pb_object_query_reference`, `pb_library_entry_export`). Required pre-step for the `/pb-review` flow. v1.1 covers outgoing references (callees, ancestors used, types declared) natively via ORCA. Incoming references (callers) are not native to ORCA — they require an opt-in brute-force inversion of the library index and are off by default.
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
| `pb_object_query_reference(lib_path, entry_name, entry_type)` | **Outgoing** refs of an entry (callees, ancestors used, types declared, windows opened). `ref_type` ∈ {`simple`, `open`} | yes |
| `pb_library_entry_information(lib_path, entry_name, entry_type)` | Metadata for an entry (timestamps, size, base class, comment) | yes |
| `pb_library_entry_export(lib_path, entry_name, entry_type)` | Full source of an entry as plain text | yes |

**Direction note**. ORCA's `PBORCA_ObjectQueryReference` returns
**outgoing** refs of the queried object — what it calls/uses, not
what uses it. The opposite direction (incoming refs, "who calls
this") is **not exposed natively** by ORCA. Reconstructing it
requires inverting the index: iterate every candidate caller in
the library list, call `pb_object_query_reference` on each, and
collect those whose result set contains the target entry. Costly
(O(N) on liblist size), so it is offered only as an opt-in pass
when the user explicitly asks for it (see "Caller discovery"
below).

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
3. Get the **outgoing refs** (callees, used types, opened windows)
   via `pb_object_query_reference`. For each ref, get its metadata
   via `pb_library_entry_information` to assess whether to expand
   it. By default, expand only `ref_type=open` (windows the entry
   opens — they're the integration boundary downstream);
   `ref_type=simple` (functions called, types declared) you list
   but don't expand unless budget allows.
4. If budget allows and the user asked for transitive outgoing
   refs (depth 2+), repeat step 3 on the depth-1 outgoing — but be
   aggressive about pruning: cap each level's expansion at ~5
   entries.
5. **(Opt-in)** If the user asked for callers ("who calls this?"),
   run the inversion pass — see "Caller discovery" below. Off by
   default because it is O(N) on liblist size.

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

## Outgoing refs from ORCA (default, v1.1)

For each exported entry, call `pb_object_query_reference` to get
the `outgoing_refs` list — what the entry calls, opens, declares
as a type, or otherwise references. This is the **native, exact**
direction ORCA exposes and it is essentially free (one ORCA call
per entry already in the pack).

Each item comes back with `library`, `entry_name`, `entry_type`,
and `ref_type` (`simple` for declarative refs, `open` for runtime
window opens). Record them in the context pack with
`confidence: high` — these come from ORCA's index, not from
parsing.

What ORCA **cannot** see:

- `Dynamic Call`, `Dynamic Function`, `Dynamic Event` invocations.
- DataWindow expression strings (`SetItem(row, "col", value)` where
  `"col"` could be anything at runtime).
- Function names constructed at runtime via string concat:
  `f_call(name + "_handler")`.

For those, see the heuristic fallback pass below.

## Caller discovery — opt-in inversion (off by default)

ORCA has no native primitive for "who calls this entry". To compute
incoming refs, the skill must invert the index: iterate the library
list, and for each candidate caller call `pb_object_query_reference`,
keeping those whose result set contains the target.

This is **O(N) on liblist size** — for a Magware-class workspace
(~6-12 PBLs × 100+ entries each) it can mean 1000+ ORCA calls per
target entry. So it is **off by default**.

Activate it only when the user explicitly asks ("who calls
`n_logger.flush`?", "find all callers of `f_legacy_thing`") or when
a downstream skill needs the caller set (e.g. `pb-impact-analysis`
when scoped for blast-radius). When activated:

1. Iterate every entry in the configured liblist via
   `pb_library_directory(lib, "any")`. Skip entries already known to
   be in the call-graph closure (avoid redundant queries).
2. For each candidate, call `pb_object_query_reference(candidate)`
   and check whether the target entry appears in its outgoing refs.
3. Cap the work: stop after N candidates probed (default 500) or N
   matches found (default 20), whichever first. Report honestly
   ("scanned 500/2400 entries, found 12 callers; widening would
   take ~5× longer").
4. Mark each caller with `confidence: high` (it's ORCA — exact)
   and the `ref_type` from the query.

For very-base userobjects with hundreds of callers, do not chase
the full set: list a count and the top-N by liblist proximity, and
defer the full blast-radius to `pb-impact-analysis` (planned).

## Heuristic fallback for dynamic patterns (optional)

Some dependencies are invisible to ORCA's index because they are
resolved at runtime (`Dynamic Call`, DW expressions, name concat).
If the agent suspects a refactor crosses such a boundary, optionally
run a regex pass on the exported source for the patterns above,
flag the candidates as `confidence: low, kind: dynamic`, and present
them to the user as "ORCA cannot confirm these edges; review by
hand". Never treat them as hard topological constraints in
`pb-apply-plan`.

This pass is intentionally narrow: it covers only what ORCA cannot
see. The bulk of the call-graph already comes from
`pb_object_query_reference` above with `confidence: high`.

## Editability contract

The `outgoing_refs` from ORCA are facts; the heuristic dynamic-pattern
fallback produces **proposals**. The downstream plan-file format
(`.pb-review/<...>.md`, opzione 2+ YAML front-matter) allows the
user to edit the `depends_on` field by hand. The user-augmented
edges are marked `confidence: user-augmented` and override anything
the heuristic pass suggested. ORCA-sourced edges marked
`confidence: high` should not be edited away without good reason.

## Budget mechanics

The skill is judgment-based, not a strict counter. Defaults that
work as starting points on Magware-class codebases:

- **Hard cap on exported entries**: 20 per invocation. If the
  natural flow would exceed it, prune (depth, then breadth) until
  under cap.
- **Soft cap on cumulative source size**: ~150 KB of plain text
  (~50 K tokens). Track as you go; if you cross it before reaching
  the outgoing-refs expansion, stop and report what you have. The
  target entry and its inheritance chain take precedence.
- **Default expansion depth**: ancestors = 3, outgoing refs = 1.
  Both configurable per invocation.
- **Caller discovery (opt-in) caps**: max 500 ORCA queries on the
  liblist, max 20 callers reported, whichever comes first. Always
  honest about partial scans ("scanned 500/2400, found 12").
- **Pruning order** when over budget: (a) drop `simple`-typed
  outgoing refs first (declarative refs are usually less load-bearing
  than `open`-typed ones); (b) drop ancestors beyond depth 2; (c)
  drop framework-level ancestors (`nonvisualobject`, `window`,
  `userobject`) since the agent knows them from
  [`appeon-query`](../appeon-query/SKILL.md); (d) skip the caller-
  discovery opt-in pass entirely.

These caps are starting points, not law. Adjust if the user signals
they want a deeper or shallower view ("just the entry, no
ancestors", "give me the full outgoing tree two levels deep",
"include the caller set even if it's big").

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

**Outgoing refs** — via `pb_object_query_reference` (callees,
ancestors used, types declared, windows opened), depth 1, N total,
M exported:
- ref_1 (lib, kind=function, ref_type=simple, confidence=high) — exported
- ref_2 (lib, kind=window,   ref_type=open,   confidence=high) — exported
- ref_3 (lib, kind=userobject, confidence=low, kind=dynamic) — Dynamic Call, flagged via heuristic fallback
- ...

**Incoming refs (callers)** — OPT-IN only, off by default; populated
when the user asks. Via inversion of `pb_object_query_reference` on
the liblist:
- caller_1 (lib, ref_type=open, confidence=high)
- caller_2 (lib, ref_type=simple, confidence=high)
- ... (scanned N/M liblist entries; capped at 20 unless overridden)

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
informational, not executable. ORCA-sourced edges are
`confidence: high`; heuristic dynamic-pattern fallback edges are
`confidence: low` and should be presented as warnings, not facts.

## v1.1 limitations (explicit non-goals)

- **Caller discovery is opt-in and capped**. Inverting ORCA's index
  is O(N) on liblist size; default scan limits are 500 ORCA queries
  / 20 callers reported. The skill is always honest about partial
  scans. Activate only when the user explicitly requests callers.
- **Dynamic patterns are flagged, not resolved**. `Dynamic Call`,
  `Dynamic Function`, DW expression strings, and function names
  constructed at runtime are invisible to ORCA's index. The optional
  heuristic fallback marks them `confidence: low` for the user to
  review; the agent never treats them as hard topological edges.
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
- **Huge incoming-ref set** during opt-in caller discovery (a base userobject used everywhere): truncate
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
