---
description: Run a structured code review on a PowerBuilder target (entry, .pbt, or PBL). v1 = report-only (no edits applied).
argument-hint: <target> — entry triple (lib:name:type), .pbt path, or .pbl path
---

# `/pb-review` — PowerBuilder code-review (Phase A: report-only)

You are running a structured code-review on a PowerBuilder workspace.
The target the user gave you is: **`$ARGUMENTS`**

## What `$ARGUMENTS` means

Parse it before doing anything else. Three accepted forms:

1. **Entry triple** — `<lib_path>::<entry_name>:<entry_type>`. Example:
   `C:\proj\src\mw_core.pbl::n_widget_helper:userobject`. This is the
   most focused scope. Pass it as-is to `pb-context-build` in Flavor A.
2. **`.pbt` path** — `<path>.pbt` (e.g.
   `C:\proj\src\mw_aclw.pbt`). Use Flavor B in `pb-context-build`:
   orientation first, then ask the user to refine to a Flavor A or
   Flavor C scope. **Do not try to review an entire target in one
   shot** — the budget cannot absorb thousands of entries.
3. **`.pbl` path** — `<path>.pbl`. Use Flavor C: list entries, decide
   based on count whether to review wholesale or ask for refinement.

If the argument doesn't match any form, ask the user to restate it.
Do not guess.

## Pre-flight

Before invoking `pb-context-build`, verify the MCP session is up:

- If you haven't called `pb_session_open` yet in this conversation,
  open one now.
- If you don't know which target is current, call
  `pb_set_current_application` and `pb_set_library_list` per the
  workspace's `.pbt`. The
  [`pb-workflow`](../../../pb-orca-mcp/.claude/skills/pb-workflow/SKILL.md)
  skill in the sibling repo documents the bring-up sequence.

If session bring-up fails (DLL not found, x86 mismatch, etc.), stop
and report the diagnostic. Do not paper over it.

## Step 1 — build the context pack

Invoke the [`pb-context-build`](../skills/pb-context-build/SKILL.md)
skill with the parsed target. The skill returns a context pack
containing:

- The target entry (or set of entries).
- Inheritance chain.
- Callers (incoming references).
- Source for each exported entry.
- A budget summary (what was loaded, what was pruned).

Keep an eye on the budget summary. If too much was pruned to do a
fair review, surface that immediately and ask whether to widen the
budget or narrow the target.

## Step 2 — run the review

Read every exported source in the context pack. For each, look for
issues in the following categories. Cross-reference
[`appeon-query`](../skills/appeon-query/SKILL.md) when you need to
verify PowerScript or runtime API semantics — do not guess language
behavior.

### Bug-risk findings (highest priority)

- Uninitialized variables before read; null reads without `IsNull()`
  guard; type coercion that silently drops precision.
- Dynamic SQL strings concatenated from user input (SQL injection).
- `Open()` without paired `Close()`; `CREATE` without `DESTROY` for
  NVOs allocated on the fly.
- Empty `catch` blocks, or `catch` blocks that swallow without
  logging.
- Cursor logic without `CLOSE` on every code path.
- Hard-coded environment-specific paths or credentials.
- Numeric loop counters declared `integer` when the upper bound
  could exceed 32767 (use `long`).
- `MessageBox` left in production code paths (debug residue).
- Off-by-one in array bounds (PB arrays are 1-based by default).

### Refactoring opportunities (medium priority)

- Duplication: identical or near-identical blocks across multiple
  events / functions that could become a shared NVO method.
- Functions whose body is dominated by deeply nested `if`/`choose
  case` — candidates for guard clauses or strategy pattern.
- DataWindow logic embedded inline in window events when an NVO
  would isolate it.
- Direct SQL against `sqlca` from window code (skip-the-DAL
  pattern). If the codebase has a DAL convention, flag the
  bypass.
- Magic numbers and string literals that recur — extract to
  constants.
- Inherited overrides that re-implement the parent's behavior
  identically (dead override).
- Long parameter lists (>5) that could be replaced by a structure
  or NVO state.

### Style / idiomatic findings (lowest priority, optional)

- Naming that violates the codebase's convention (check the
  inheritance chain in the context pack to infer the convention
  before flagging).
- Comments in non-English where the rest of the codebase is
  English (or vice-versa).
- Inconsistent indentation that survives the encoding (tabs vs
  4-space).
- `forward prototypes` order that doesn't match function definition
  order (cosmetic but readable).

If you encounter a pattern that recurs across the context pack and
isn't documented in the
[`pb-src-format`](../skills/pb-src-format/SKILL.md) wiki under
`docs/pb-source-format/`, note it for the user — that's a candidate
for Layer 2 wiki growth (Tier 2 work).

## Step 3 — emit the report

Output a single markdown report with this structure. Lead with the
highest-priority issues. Cite each finding with the entry it lives
in and a line range if you can identify one.

```
# Code review: <target>

**Scope**: <what was actually reviewed — entry count, total source
lines, budget summary from pb-context-build>.

**Skipped**: <anything pruned that you think the user should know
about>.

## Bug-risk findings

### 1. <short title>
- **Where**: `lib_path` :: `entry_name` (`entry_type`), lines N-M
- **What**: <one-paragraph description>
- **Why it matters**: <impact>
- **Suggested fix**: <concrete change, or "needs investigation —
  cannot tell from context pack alone">

### 2. ...

## Refactoring opportunities

(same shape)

## Style / idiomatic findings

(same shape — bullet list is fine if findings are minor)

## Notes for the wiki

<patterns observed that should be added to docs/pb-source-format/
if they recur — Tier 2 work, not for this PR>

## Next steps

- For each bug-risk finding, do you want me to draft a fix? (Phase
  B is not yet implemented — for now I can produce a diff
  proposal as text, but applying it requires the
  pb-workflow + pb_compile_entry_import loop and is out of scope
  for v1.)
- For refactor opportunities marked "non-trivial", call
  `pb-impact-analysis` (planned skill) first to see the blast
  radius before deciding.
```

## Hard limits for v1

- **No edits**. v1 is report-only. If the user asks you to apply a
  fix, explain that Phase B (edit-loop via `pb-workflow` +
  `pb_compile_entry_import`) is the next slice and offer to draft
  the patch as text for them to apply manually in the IDE.
- **No bulk sweep**. v1 reviews one target (entry / `.pbt` / `.pbl`)
  at a time. If the user wants to review three PBLs, ask them to
  pick one and queue the others.
- **No automated test execution**. PB testing is out of scope per
  the refactoring-first re-priorization (2026-05-19). If a fix
  conceptually needs a test, suggest it as a follow-up, do not
  generate a test runner.
- **Honest about cost**. If the budget was hit early and the
  review is partial, say so loudly at the top of the report.
  Partial reviews are still valuable; pretending to be exhaustive
  is not.

## Cross-references

- [`pb-context-build`](../skills/pb-context-build/SKILL.md) — the
  context-building primitive this command depends on.
- [`appeon-query`](../skills/appeon-query/SKILL.md) — for language
  / runtime API lookups while reviewing.
- [`pb-src-format`](../skills/pb-src-format/SKILL.md) — for
  questions about the on-disk source format.
- `pb-impact-analysis` (planned, Tier 1) — invoke when a finding
  proposes a non-trivial refactor.
- [`pb-workflow`](../../../pb-orca-mcp/.claude/skills/pb-workflow/SKILL.md)
  (sibling) — for session bring-up and the edit-encoding loop that
  Phase B will use.
