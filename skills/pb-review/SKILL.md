---
name: pb-review
description: Use this to run a structured code review on a PowerBuilder target — an entry, a .pbl, a .pbt, or a free-form description of a block of code. Frames the work with the user, builds a scoped context pack, validates understanding before reviewing, then produces two persistent artefacts (a plan file with one YAML-tagged finding per fix, and a CHANGELOG entry) and hands off to pb-apply-plan for the edit loop. Report-only by itself — it never edits PowerBuilder sources.
metadata:
  version: "1.2.0"
---

# Structured code review on a PowerBuilder target

This is the entry point of the refactoring loop. It does **not** apply
edits: it produces two artefacts on disk — a plan file and a CHANGELOG
entry — and then hands off to
[`pb-apply-plan`](../pb-apply-plan/SKILL.md), which walks the queue
one fix at a time with confirmation on each.

The split exists because a review is worth persisting. The plan file
survives the session, can be edited by hand, and can be resumed by a
different agent days later.

**On language**: the prompts quoted below are in English for
legibility. Speak whatever language the user is speaking.

## What the target can be

The target is **intent-bearing**, not a rigid type identifier. Four
accepted forms:

1. **Entry triple** — `<lib_path>::<entry_name>:<entry_type>`. The most
   focused scope. Example:
   `C:\proj\src\core.pbl::n_widget_helper:userobject`.
2. **`.pbt` path** — target-level entry point.
3. **`.pbl` path** — library-level scope.
4. **Free-form intent** — natural language describing what to review
   ("the `n_logger` chain", "the data migration flow", "error handling
   in `aclw.pbl`"). Resolved during Step 0.

If the target is missing or unintelligible, ask the user to restate. Do
not guess.

## Pre-flight

1. **`pb_workspace_info(lib_path)`** — one call, no ORCA session, no PB
   install needed. It gives the project shape (`ws_objects` vs
   `pbl_only`), the source encoding, whether git is watching, and
   `outside_source_tree`. Note any library flagged
   `outside_source_tree`: it is a vendored dependency snapshot or a
   third-party component, so a refactoring proposed inside it will be
   overwritten at the next update of that dependency. Either keep it
   out of scope or say plainly that the finding belongs upstream.

   **Also read `source_protection`.** `unprotected` means git rewrites
   the `.sr*` line endings, so the index and the working tree differ by
   exactly the bytes ORCA writes — an applied fix can leave
   `git status` clean and surface as drift on someone else's checkout.
   A review is read-only and safe either way, but it ends by handing
   off to `pb-apply-plan`, which is not. Measure it now, while it costs
   one command: `git ls-files --eol <projection dir>`, count the files
   reported `i/lf w/crlf`, and put the number in the report. Say it
   has to be fixed — `*.sr* binary` plus `git add --renormalize`, its
   own commit — **before** the apply loop runs, not after.
2. **Bring up the ORCA session**: `pb_session_open` (`pb_version` or
   `install_path` is required — there is no auto-pick; enumerate with
   `pb_discover_pb_install` and say which you chose),
   `pb_set_library_list`, `pb_set_current_application`. The last one
   may rewrite the `.pbw` as a side effect; mention it if the session
   ends with the user looking at `git status`.

3. **Note which reference tools you have.** If the `appeon_*` tools are
   absent, the Appeon doc index is not configured on this machine (the
   normal state — see the `appeon-query` skill for why and how to turn
   it on). You can still review: most findings rest on reading the code,
   not on the language reference. But a finding whose truth depends on
   a PowerScript semantic you could not verify must say so in its body
   and name the experiment that would settle it. **Do not assert
   language behaviour from memory inside a finding** — a wrong one costs
   the user more than a missing one, because it looks the same as a
   right one and arrives with a suggested edit attached.

If bring-up fails, stop and report the diagnostic —
`pb-orca-mcp doctor` and `pb-orca-mcp check <target>` are CLI commands
that say why, with no MCP in the way. Do not paper over it.

## Step 0 — Frame the work (always interactive)

**Always run this step**, even when the target is already a precise
entry triple. The point is not to disambiguate syntax but to **make
the intent explicit and confirm scope before any expensive work**.

Determine and **explicitly confirm with the user** five things.

### (a) Scope category — the purpose of the review

One of `review`, `refactoring`, `audit`, `bug-hunt`, or a free slug.
This becomes the leading component of the plan-file name and orients
the report: a `bug-hunt` weights bug-risk findings, an `audit` weights
compliance and security, a `refactoring` weights structural
opportunities.

Propose a default from the wording of the request ("refactor" →
`refactoring`, "review" → `review`, ambiguous → ask). The user
confirms or replaces it.

### (b) Context slug — a semantic identifier for the block

A short kebab-case slug describing the block under review
(`n_logger_chain`, `data_migration_flow`, `aclw_error_handling`). It
becomes the second component of the plan-file name and the title of
the report. Propose, confirm.

### (c) Candidate entry set

Resolve the target into a concrete set of entry triples:

- **From a triple**: start there, walk the inheritance chain upward,
  and look for siblings by naming pattern (for `n_logger`, sweep
  entries matching `n_log*` in the same PBL and in PBLs the user marks
  as candidates). Propose the candidate set: "I found N candidate
  entries: [list]. All of them, a subset, or should I add something?"
- **From a `.pbt`**: defer to Flavor B of
  [`pb-context-build`](../pb-context-build/SKILL.md) — present the PBL
  list, ask for refinement, then propose the entry set.
- **From a `.pbl`**: defer to Flavor C (enumerate, filter, propose).
- **From free-form intent**: use `pb_library_directory` plus a
  naming-pattern guess to locate candidates, then walk the hierarchy.
  Same propose-confirm loop.

### (d) An honest budget estimate

Before the user confirms the scope, compute one: **how many entries**
would be exported, **roughly how many KB** of source. If it exceeds
`pb-context-build`'s default cap (20 entries / ~150 KB), say so loudly
and propose narrowing. **Never proceed silently into a budget-violating
scope.**

### (e) Semver bump proposal

Propose an initial bump level (`patch` / `minor` / `major`) from the
expected category of findings: bug-hunt → likely `patch`; refactoring
with API-shape changes → likely `minor` or `major`; audit-only →
likely `patch`. This is a **proposal**; the actual bump is finalized
when `[Unreleased]` is promoted, after `pb-apply-plan` completes.

**Project-local versioning hook**: before proposing, look for a
project-local skill named `pb-review-versioning` or
`pb-version-local`. If one exists, ask it for the next version number
according to the project's own convention (a `.version` file,
`package.json`, whatever it uses). If not, fall back to plain semver.

### Output of Step 0

Once the user has confirmed (a)-(e), record them. They drive
everything downstream:

- Plan filename:
  `.pb-review/<scope_category>-<context_slug>-<YYYY-MM-DD-HHMM>.md`
- The plan header block
- The CHANGELOG entry section
- The candidate entry set passed to `pb-context-build`

## Step 1 — Build the context pack

Invoke [`pb-context-build`](../pb-context-build/SKILL.md) with the
confirmed entry set. It returns, per entry:

- The exported source.
- The inheritance chain (via `pb_object_query_hierarchy`).
- Outgoing refs — callees, ancestors used, types declared, windows
  opened — via `pb_object_query_reference`. Exact, `confidence: high`.
  Optionally enriched by a heuristic pass for dynamic patterns
  (`Dynamic Call`, DW expression strings) flagged `confidence: low`.
- Incoming refs (callers) — **opt-in, off by default**. Only present if
  the user asked for callers.
- A budget summary: what was loaded, what was pruned.

Watch the budget summary. If too much was pruned to make the review
fair, say so immediately and loop back to Step 0 (d).

## Step 1a — Pack-driven clarifications

After reading the pack, ask only the **specific questions the pack
itself raised** — ambiguities that could not be foreseen at Step 0:

- "There are two entries named `n_log_target`, one in `core.pbl` and
  one in `legacy.pbl`. The hierarchy walk picked the first. Is that the
  one you meant?"
- "The refs include a `Dynamic Call` to a runtime-built name in
  `n_logger.write`. Should the dynamic target be in scope, or skipped?"

This step is **conditionally interactive**: if the pack reveals no
ambiguity, skip it silently. Do not invent questions to fill a turn.

## Step 2a — Understanding gate

Before producing any findings, write a short semantic summary of the
block: what it does, what its responsibilities seem to be, what
assumptions you are making about its role. Present it as a gate:

> "Here is my understanding of the block under review:
>
> - Purpose: …
> - Responsibilities: …
> - Assumptions I am making: …
>
> Have I got it right, or is there something to correct before I
> review?"

**Say what the confirmation authorizes.** "Have I got it right?" on its
own invites the reasonable reply "proceed to do what?". Name the three
things that follow, concretely: the findings get written (Step 2b), two
files are created in the reviewed project — the plan file and a
CHANGELOG entry (Step 3) — and then you offer the apply loop, which is
the only part that modifies a `.pbl` (Step 4). If the review is likely to
yield one or two findings, say that too: it changes whether the user
wants the full flow or a shortcut.

Wait for explicit confirmation. **Do not run the review until the user
has acknowledged the understanding.** If they correct it, regenerate
and ask again.

This gate costs one turn and prevents an entire review built on a
misreading.

## Step 2b — Run the review

Read every exported source in the pack. Consult
[`appeon-query`](../appeon-query/SKILL.md) whenever you need to verify
PowerScript or runtime API semantics — do not guess language behaviour.

### Bug-risk findings (highest priority)

Before the generic list, work through the
[PowerScript antipattern catalog](../../docs/pb-antipatterns/index.md).
It records concrete PB-specific hazards that recur across legacy
codebases, with code samples and idiomatic fixes. Match the sources
against every entry in the catalog before concluding the code is clean
— these are the bugs that compile fine and bite in production.

Generic patterns to also check:

- Uninitialized variables read before assignment; null reads without an
  `IsNull()` guard; type coercion that silently drops precision. (See
  [`isnull-on-numeric`](../../docs/pb-antipatterns/isnull-on-numeric.md)
  for the PB-specific trap.)
- Dynamic SQL concatenated from user input (SQL injection).
- `Open()` without a paired `Close()`; `CREATE` without `DESTROY` for
  NVOs allocated on the fly. (See
  [`destroy-on-auto-instance`](../../docs/pb-antipatterns/destroy-on-auto-instance.md)
  and
  [`exitprocess-in-destruction`](../../docs/pb-antipatterns/exitprocess-in-destruction.md).)
- Empty `catch` blocks, or `catch` blocks that swallow without logging.
  (See
  [`throw-factory-loses-subtype`](../../docs/pb-antipatterns/throw-factory-loses-subtype.md).)
- Cursor logic without `CLOSE` on every code path.
- Hard-coded environment-specific paths or credentials.
- Loop counters declared `integer` where the upper bound could exceed
  32767 (use `long`).
- `MessageBox` left in a production code path (debug residue).
- Off-by-one on array bounds (PB arrays are 1-based by default).
- IO calls without checking the sentinel return. (See
  [`fileopen-unchecked`](../../docs/pb-antipatterns/fileopen-unchecked.md)
  and
  [`space-before-init`](../../docs/pb-antipatterns/space-before-init.md).)

When you spot a recurring pattern the catalog does not have yet, note
it under "Notes for the wiki" in the report — that is a candidate for a
new page under `docs/pb-antipatterns/`.

### Refactoring opportunities (medium priority)

- Duplication: identical or near-identical blocks across events or
  functions that could become a shared NVO method.
- Functions dominated by deeply nested `if` / `choose case` —
  candidates for guard clauses or a strategy split.
- DataWindow logic embedded inline in window events where an NVO would
  isolate it.
- Direct SQL against the transaction object from window code. If the
  codebase has a data-access convention, flag the bypass.
- Magic numbers and repeated string literals — extract to constants.
- Inherited overrides that re-implement the parent's behaviour
  identically (dead override).
- Long parameter lists (>5) that a structure or NVO state would
  replace.

### Style / idiomatic findings (lowest priority, optional)

- Naming that violates the codebase's own convention — check the
  inheritance chain in the pack to infer the convention before flagging
  anything.
- Comments in a language the rest of the codebase does not use.
- Inconsistent indentation, keyword casing, or operator spacing. **Do
  not file these one entry at a time**: they are a single sweep for
  [`pb-format`](../pb-format/SKILL.md). One finding saying so is worth
  more than twenty saying the same thing.
- `forward prototypes` order that does not match definition order
  (cosmetic, but affects readability).

If a pattern recurs across the pack and is not documented in the
[`pb-src-format`](../pb-src-format/SKILL.md) wiki under
`docs/pb-source-format/`, note it — that is a candidate for wiki
growth.

## Step 3 — Emit the plan file and the CHANGELOG entry

Two artefacts on disk, one user-facing summary.

### Plan file

Path:
`.pb-review/<scope_category>-<context_slug>-<YYYY-MM-DD-HHMM>.md`
(values from Step 0). Create `.pb-review/` if it does not exist. On
first creation, mention it: "I created `.pb-review/` in the working
directory. Want a `.gitignore` suggestion for it?"

The format is YAML front-matter per finding, **plus** a generated
summary table at the top.

#### Header block

```markdown
# <scope_category>: <context_slug>

- **scope**: <scope_category>
- **context**: <context_slug>
- **target**: <entry triples / .pbt / .pbl reviewed>
- **workspace**: mode=<ws_objects|pbl_only>, encoding=<…>, outside_source_tree=<…>, source_protection=<…>
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

| id     | entry                              | kind     | depends_on | confidence | status  |
|--------|------------------------------------|----------|------------|------------|---------|
| fix-01 | core.pbl :: n_logger : userobject  | bug-risk | —          | parsed     | pending |
| fix-02 | core.pbl :: n_log_target : uobj    | refactor | fix-01     | parsed     | pending |
```

The table is **derived** from the YAML blocks below;
`pb-apply-plan` regenerates it whenever a `status` changes. It is not
the source of truth — the YAML is.

#### Findings (one section per finding)

````markdown
### fix-01 — Null deref in `n_logger::flush()` on empty buffer

```yaml
id: fix-01
entry: core.pbl::n_logger:userobject
function: flush
lines: [42, 58]
kind: bug-risk
priority: high
depends_on: []
confidence: parsed
status: pending
```

**Where**: `core.pbl` :: `n_logger` (`userobject`), function `flush`,
lines 42-58.

**Why it matters**: crashes when the internal buffer is empty.

**Suggested fix**:

```pb
if IsNull(buf) or Len(buf) = 0 then return
```

**Notes**: the caller `n_log_target.write` already guards against
empty input; this is defense-in-depth.
````

Required YAML fields: `id`, `entry`, `kind` (bug-risk | refactor |
style | …), `priority` (high | medium | low), `depends_on` (list of
`id`), `confidence` (parsed | user-augmented | manual), `status`
(pending | applied | skipped).

Optional YAML fields:

- `function`, `lines` — narrow down the location.
- `effort_estimate` — `small` | `medium` | `large`. Signals to
  `pb-apply-plan` whether to expect a long apply step.
- `tag` — free-form labels for grouping or filtering.
- `also_in: [entry_triple, …]` — when the same fix concept applies to
  several entries (the same pattern repeated across similar NVOs), list
  the secondary ones here. `pb-apply-plan` applies the primary `entry`
  first, then iterates `also_in` in topological order. One body of text
  covers the group; the YAML records the spread.
- `requires_discussion: true` — the fix is not a single pre-decided
  patch but a **choice between alternatives** the user must make first.
  Use with `decision_options`. `pb-apply-plan` pauses on it and asks
  instead of presenting a diff.
- `decision_options: [{label, summary}, …]` — the alternatives: a short
  label plus a one-line summary each. The finding body can expand them.
  The user's pick is recorded back as `chosen_option: <label>`.

Confidence semantics:

- `parsed` — dependencies came from `pb-context-build`'s ORCA-sourced
  outgoing refs.
- `user-augmented` — from ORCA **plus** edits the user made by hand.
- `manual` — entirely from the user's edits (ORCA found none, or the
  user overrode it).

### CHANGELOG entry

Append to (or create) `CHANGELOG.md` in the reviewed project's root,
following [Keep a Changelog](https://keepachangelog.com/). Add or
extend `## [Unreleased]` with one sub-section per category (`### Fixed`,
`### Changed`, `### Added`, `### Removed`, `### Deprecated`,
`### Security`) and one `- [ ]` bullet per finding:

```markdown
## [Unreleased]

### Fixed

- [ ] **fix-01** — Null deref in `n_logger::flush()` on empty buffer
  ([plan](.pb-review/refactoring-n_logger_chain-2026-07-29-1130.md#fix-01))

### Changed

- [ ] **fix-02** — Extract `n_log_target` base class from `n_logger`
  ([plan](.pb-review/refactoring-n_logger_chain-2026-07-29-1130.md#fix-02))
```

**Append-only**: never edit or remove pre-existing sections (older
`[X.Y.Z]` releases, or items a previous run wrote). Add to
`[Unreleased]` only.

If `CHANGELOG.md` does not exist, create one with the Keep a Changelog
header and the `[Unreleased]` section.

### User-facing summary

After writing both artefacts, summarize in the conversation:

- The plan file path.
- N findings, grouped by kind and priority.
- Semver bump proposed: `patch|minor|major` → `X.Y.Z`.
- `CHANGELOG.md`: updated, or created from scratch.
- "I can load `pb-apply-plan` to apply the N queued fixes in
  topological order (ancestors first, callees first). Shall I?"

## Step 4 — Handoff to `pb-apply-plan`

On the user's OK, hand off to
[`pb-apply-plan`](../pb-apply-plan/SKILL.md) with the plan-file path.
That skill knows how to:

- Parse the YAML findings and the queue table.
- Topo-sort the DAG on `depends_on`, respecting inheritance (ancestor
  before descendant) and the call graph (callee before caller).
- Walk the queue one finding at a time: export the entry to a file,
  show the diff, ask for confirmation, edit the file, import it, and
  read the compile result. On refusal: skip with an impact check.
- Update `status:` in the YAML and regenerate the summary table.
- Tick the `- [ ]` boxes in `CHANGELOG.md`.
- When every finding reaches a terminal state, propose promoting
  `[Unreleased]` → `[X.Y.Z] - YYYY-MM-DD`.

If the user declines the handoff, stop gracefully. The plan file and
the CHANGELOG entry persist; the work can resume later by invoking
`pb-apply-plan` with the plan-file path.

## Hard limits

- **No bulk sweep across targets.** One scope at a time. Multi-target
  refactors are out of scope.
- **No edits during the review itself.** This flow produces artefacts;
  edits to PB sources happen only in the `pb-apply-plan` handoff, with
  per-fix confirmation. Writing the plan file and the CHANGELOG entry
  is review output, not a source modification.
- **No automated test execution.** If a fix conceptually needs a test,
  suggest it as a follow-up note in the finding; do not generate a test
  runner.
- **Honest about cost.** If the budget was hit early and the review is
  partial, say so loudly at the top of the plan file, in `## Scope`.
  Partial reviews are valuable; pretending to be exhaustive is not.

## Cross-references

- [`pb-context-build`](../pb-context-build/SKILL.md) — the
  context-building step Step 1 depends on.
- [`pb-apply-plan`](../pb-apply-plan/SKILL.md) — Phase B: topo-sort,
  impact check, and the edit loop.
- [`appeon-query`](../appeon-query/SKILL.md) — language and runtime API
  lookups while reviewing.
- [`pb-src-format`](../pb-src-format/SKILL.md) — the on-disk source
  format.
- [`pb-format`](../pb-format/SKILL.md) — where pure-style findings
  belong.
- [`pb-orca-mcp`](https://github.com/restoresrl/pb-orca-mcp) — the ORCA
  bridge every `.pbl` operation goes through.
