---
description: Run a structured code review on a PowerBuilder target. Frames the work, builds a scoped context pack, validates understanding, produces a persistent plan file + CHANGELOG entry, then hands off to `pb-apply-plan` for the edit loop.
argument-hint: <target> — entry triple, .pbt path, .pbl path, or free-form intent (e.g. "the n_logger chain")
---

# `/pb-review` — PowerBuilder code-review and plan generation

You are running a structured code-review on a PowerBuilder workspace.
The argument the user gave you is: **`$ARGUMENTS`**

This command does NOT apply edits directly to PB sources. It produces
two persistent artifacts (a plan file and a CHANGELOG entry) and
then hands off to the `pb-apply-plan` skill, which orchestrates the
edit loop voce-by-voce via `pb-workflow` (sibling
[`pb-orca-mcp`](../../../pb-orca-mcp/.claude/skills/pb-workflow/SKILL.md)).

## What `$ARGUMENTS` can be

The argument is **intent-bearing**, not a rigid type identifier.
Four accepted forms:

1. **Entry triple** — `<lib_path>::<entry_name>:<entry_type>`. Most
   focused scope. Example: `C:\proj\src\mw_core.pbl::n_widget_helper:userobject`.
2. **`.pbt` path** — `<path>.pbt`. Target-level entry point.
3. **`.pbl` path** — `<path>.pbl`. PBL-level scope.
4. **Free-form intent** — natural language describing what to review
   (e.g. "the `n_logger` chain", "the data migration flow",
   "error handling in `mw_aclw.pbl`"). The command resolves the
   referenced entries during Step 0.

If the argument is missing or unintelligible, ask the user to
restate. Do not guess.

## Pre-flight

Before invoking `pb-context-build`, verify the MCP session is up:

- If you haven't called `pb_session_open` yet in this conversation,
  open one now.
- Configure the current application and library list per the
  workspace's `.pbt`. The
  [`pb-workflow`](../../../pb-orca-mcp/.claude/skills/pb-workflow/SKILL.md)
  skill in the sibling repo documents the bring-up sequence.

If session bring-up fails (DLL not found, x86 mismatch, etc.), stop
and report the diagnostic. Do not paper over it.

## Step 0 — Frame the work (always interactive)

**Always run this step**, even if `$ARGUMENTS` is a precise entry
triple. The point is not to disambiguate input syntax but to
**make the intent explicit and confirm scope before any expensive
work**.

The agent must determine and **explicitly confirm with the user**
four things:

### (a) Scope category — purpose of the review

One of `review`, `refactoring`, `audit`, `bug-hunt`, or a free
slug. This becomes the leading component of the plan-file name and
informs the report orientation (a `bug-hunt` weights bug-risk
findings, an `audit` weights compliance/security, a `refactoring`
weights structural opportunities).

Propose a default based on the wording of `$ARGUMENTS` ("refactor"
→ `refactoring`, "review" → `review`, ambiguous → ask). User
confirms or replaces.

### (b) Context slug — semantic identifier for the block

A short kebab-case slug describing the block of code under review
(e.g. `n_logger_chain`, `data_migration_flow`, `mw_aclw_error_handling`).
This becomes the second component of the plan-file name and the
title of the report. Propose, confirm.

### (c) Candidate entry set

Resolve `$ARGUMENTS` into a concrete set of entry triples:

- **From a triple**: start with it, then walk the inheritance chain
  upward and look for siblings by naming pattern (e.g. for
  `n_logger`, sweep entries matching `n_log*` in the same PBL and
  in PBLs marked as candidates by the user). Propose the candidate
  set, ask: "ho trovato N entry candidate: [list]. Includo tutte,
  solo una sotto-selezione, o aggiungo qualcosa?".
- **From a `.pbt`**: defer scope resolution to Flavor B of
  `pb-context-build` (fast-path: present PBL list, ask for
  refinement, then propose entry set).
- **From a `.pbl`**: defer to Flavor C of `pb-context-build`
  (enumerate, filter, propose).
- **From free-form intent**: use `pb_library_directory` +
  naming-pattern guess to locate candidates, then walk hierarchy.
  Same propose-confirm loop.

### (d) Honest budget estimate

Before the user confirms the scope, compute a budget estimate:
**how many entries** would be exported, **roughly how many KB** of
source. If the estimate exceeds `pb-context-build`'s default cap
(20 entries / ~150 KB), say so loudly and propose narrowing.
**Never proceed silently into a budget-violating scope**.

### (e) Semver bump proposal

Propose an initial semver bump level (`patch` / `minor` / `major`)
based on the expected category of findings (bug-hunt → likely
`patch`; refactoring with API shape changes → likely `minor` or
`major`; audit-only → likely `patch`). This is a **proposal**; the
actual bump is finalized when the entry is promoted from
`[Unreleased]` to `[X.Y.Z]` after `pb-apply-plan` completes.

**Local versioning skill hook**: before proposing, scan the
consumer's `.claude/skills/` for a skill matching the convention
`pb-review-versioning` or `pb-version-local`. If found, invoke it
to get the next version number according to the project's
convention (Restore `.version` file, `package.json`, etc.). If
absent, fall back to plain semver.

### Output of Step 0

Once the user has confirmed (a)-(e), record them. They drive
everything downstream:

- Plan filename: `.pb-review/<scope_category>-<context_slug>-<YYYY-MM-DD-HHMM>.md`
- Plan header block
- CHANGELOG entry section
- Topology of the candidate entry set passed to `pb-context-build`

## Step 1 — Build the context pack

Invoke [`pb-context-build`](../skills/pb-context-build/SKILL.md)
(v1.1) with the confirmed entry set. The skill returns a context
pack containing per entry:

- The exported source.
- Inheritance chain.
- Incoming refs (callers, via `pb_object_query_reference`).
- Outgoing refs (callees, via heuristic source parsing — confidence
  levels: high / medium / low).
- A budget summary (what was loaded, what was pruned).

Keep an eye on the budget summary. If too much was pruned to do a
fair review, surface that immediately and loop back to Step 0 (d).

## Step 1a — Pack-driven clarifications

After reading the context pack, ask the user only the **specific
questions that the pack itself raised** — ambiguities that could
not be foreseen at Step 0:

- "I found two entries named `n_log_target`, one in `core.pbl` and
  one in `legacy.pbl`. The hierarchy walk picked the first. Is
  that what you meant?"
- "`outgoing_refs` flagged `Dynamic Call` to a runtime-built name
  in `n_logger.write`. Should I treat the dynamic target as
  in-scope, or skip it?"

This step is **conditionally interactive**: if the pack reveals no
ambiguity, **skip silently**. Do not invent questions to fill the
turn.

## Step 2a — Understanding gate

Before producing any findings, write a short semantic summary of
the block: what it does, what its responsibilities seem to be,
what assumptions you are making about its role. Present it to the
user as a gate:

> "Ecco la mia comprensione del blocco sotto review:
>
> - Purpose: ...
> - Responsibilities: ...
> - Assumptions I'm making: ...
>
> Ho capito giusto, o c'è qualcosa da correggere prima che proceda
> con la review?"

Wait for explicit confirmation. **Do not run the review until the
user has acknowledged the Understanding**. If they correct your
understanding, regenerate it and ask again.

This gate costs one turn but prevents emitting an entire review
based on a misread of the code.

## Step 2b — Run the review

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

## Step 3 — Emit plan file + CHANGELOG entry

Produce two artifacts on disk and one user-facing summary.

### Plan file

Path: `.pb-review/<scope_category>-<context_slug>-<YYYY-MM-DD-HHMM>.md`
(values from Step 0). Create the `.pb-review/` directory if it
does not exist. On first creation, surface a friendly note: "ho
creato `.pb-review/` nel cwd. Vuoi che ti suggerisca un pattern
per `.gitignore`?".

The file format is **opzione 2+**: YAML front-matter per voce
**plus a generated summary table** at the top.

#### Header block

```markdown
# <scope_category>: <context_slug>

- **scope**: <scope_category>
- **context**: <context_slug>
- **target**: <entry triples / .pbt / .pbl reviewed>
- **generated**: <YYYY-MM-DD HH:MM>
- **source skill**: pb-review @ <pb-ai-code git sha>
- **semver bump proposed**: <patch|minor|major> → <X.Y.Z>

## Understanding

<the semantic summary from Step 2a, verbatim>

## Scope

<entries reviewed, total source lines, budget summary from
pb-context-build>

## Skipped

<anything pruned that the user should know about>
```

#### Summary table

```markdown
## Queue

| id     | entry                                    | kind     | depends_on   | confidence       | status   |
|--------|------------------------------------------|----------|--------------|------------------|----------|
| fix-01 | rstpb_core.pbl :: n_logger : userobject | bug-risk | —            | parsed           | pending  |
| fix-02 | rstpb_core.pbl :: n_log_target : uobj   | refactor | fix-01       | parsed           | pending  |
| fix-03 | ...                                      | ...      | ...          | ...              | ...      |
```

The table is **derived** from the YAML front-matter of each
finding below; `pb-apply-plan` regenerates it whenever a `status`
changes. It is not source of truth — the YAML is.

#### Findings (one section per finding)

For each finding, emit a section with a YAML front-matter block in
fenced `yaml` and a markdown body:

````markdown
### fix-01 — Null deref in `n_logger::flush()` on empty buffer

```yaml
id: fix-01
entry: rstpb_core.pbl::n_logger:userobject
function: flush
lines: [42, 58]
kind: bug-risk
priority: high
depends_on: []
confidence: parsed
status: pending
```

**Where**: `rstpb_core.pbl` :: `n_logger` (`userobject`), function
`flush`, lines 42-58.

**Why it matters**: crashes when the internal buffer is empty.

**Suggested fix**:

```pb
if IsNull(buf) or Len(buf) = 0 then return
```

**Notes**: caller `n_log_target.write` already guards against
empty input; this is defense-in-depth.
````

Required YAML fields: `id`, `entry`, `kind` (bug-risk | refactor |
style | ...), `priority` (high | medium | low), `depends_on` (list
of `id`), `confidence` (parsed | user-augmented | manual), `status`
(pending | applied | skipped).

Optional YAML fields: `function`, `lines`, `effort_estimate`,
`tag`, ...

Confidence semantics:

- `parsed`: dependencies came from `pb-context-build`'s heuristic
  callee parser (Step 1).
- `user-augmented`: dependencies came from the parser **plus**
  edits the user made by hand.
- `manual`: dependencies came entirely from the user's edits
  (parser found none).

### CHANGELOG.md entry

Append (or create) `CHANGELOG.md` in the consumer's repository
root. Follow the [Keep a Changelog](https://keepachangelog.com/)
convention. Add (or extend) the `## [Unreleased]` section with one
sub-section per category (`### Fixed`, `### Changed`, `### Added`,
`### Removed`, `### Deprecated`, `### Security`) and one `- [ ]`
bullet per finding:

```markdown
## [Unreleased]

### Fixed

- [ ] **fix-01** — Null deref in `n_logger::flush()` on empty buffer
  ([plan](.pb-review/refactoring-n_logger_chain-2026-05-20-1130.md#fix-01))

### Changed

- [ ] **fix-02** — Extract `n_log_target` base class from `n_logger`
  ([plan](.pb-review/refactoring-n_logger_chain-2026-05-20-1130.md#fix-02))
```

**Append-only** rule: never edit or remove pre-existing CHANGELOG
sections (older `[X.Y.Z]` releases, or `### Added` items the user
or a previous run already wrote). Add to `[Unreleased]` only.

If `CHANGELOG.md` does not exist in the consumer, create a fresh
one with the Keep a Changelog header:

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- [ ] **fix-01** — ...
```

### User-facing summary

After writing both artifacts, summarize to the user in chat:

- Plan file path.
- N findings written, grouped by kind and priority.
- Semver bump proposed: `patch|minor|major` → `X.Y.Z`.
- CHANGELOG.md updated: yes / created from scratch.
- "Carico `pb-apply-plan` per applicare gli N fix in coda secondo
  l'ordine topologico (prima ancestor, prima callee). Procedo?"

## Step 4 — Handoff to `pb-apply-plan`

On the user's OK, hand off to the
[`pb-apply-plan`](../skills/pb-apply-plan/SKILL.md) skill. Pass it
the plan-file path; that skill knows how to:

- Parse the YAML voices and the queue table.
- Topo-sort the DAG on `depends_on` (also respecting inheritance:
  ancestor before descendant, callee before caller).
- Walk the queue voce-by-voce. For each: show the diff, ask
  confirmation, on OK invoke `pb-workflow` (sibling) for the
  actual edit + `pb_compile_entry_import`. On rejection:
  skip-with-impact-check.
- Update `status:` in the YAML and regenerate the summary table.
- Tick the `- [ ]` boxes in `CHANGELOG.md`.
- When all voices reach a terminal state, propose promoting
  `[Unreleased] → [X.Y.Z] - YYYY-MM-DD` in the CHANGELOG.

If the user declines the handoff (says "no, mi fermo qui"), stop
gracefully. The plan file and CHANGELOG entry persist; the user
can resume later by invoking `pb-apply-plan` directly with the
plan-file path.

## Hard limits for v1.x

- **No bulk sweep across targets**. v1 reviews one scope at a time.
  Multi-target refactors are out of scope.
- **No edits during `/pb-review` itself**. The command produces
  artifacts (plan file, CHANGELOG entry) but the actual edits to PB
  sources happen only in the `pb-apply-plan` handoff, with per-fix
  confirmation. `/pb-review` writing the plan file and updating
  `CHANGELOG.md` is not "edits" in this sense — those are review
  output, not source modifications.
- **No automated test execution**. PB testing is out of scope per
  the refactoring-first re-priorization (2026-05-19). If a fix
  conceptually needs a test, suggest it as a follow-up note in the
  finding, do not generate a test runner.
- **Honest about cost**. If the budget was hit early and the
  review is partial, say so loudly at the top of the plan file
  (in the `## Scope` section). Partial reviews are still
  valuable; pretending to be exhaustive is not.

## Cross-references

- [`pb-context-build`](../skills/pb-context-build/SKILL.md) (v1.1) —
  the context-building primitive Step 1 depends on. Provides both
  incoming and outgoing refs.
- [`pb-apply-plan`](../skills/pb-apply-plan/SKILL.md) — the
  orchestrator Step 4 hands off to. Owns topo-sort, impact-check,
  and the edit loop.
- [`appeon-query`](../skills/appeon-query/SKILL.md) — for language
  / runtime API lookups while reviewing.
- [`pb-src-format`](../skills/pb-src-format/SKILL.md) — for
  questions about the on-disk source format.
- [`pb-workflow`](../../../pb-orca-mcp/.claude/skills/pb-workflow/SKILL.md)
  (sibling) — low-level edit-encoding + `pb_compile_entry_import`
  loop, invoked by `pb-apply-plan` per fix.
