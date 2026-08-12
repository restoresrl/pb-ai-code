---
name: pb-context-build
description: Use this when you are about to read, review, or refactor PowerBuilder code in a monolithic legacy workspace and need to assemble a scoped context pack — a budgeted slice of entries (sources + dependency map) instead of dumping whole PBLs into the conversation. Orchestrates pb-orca-mcp primitives (pb_workspace_info, pb_target_info, pb_library_directory, pb_object_query_hierarchy, pb_object_query_reference, pb_library_entry_export, pb_library_export_sources). Required pre-step for the pb-review flow. Covers outgoing references (callees, ancestors used, types declared) natively via ORCA. Incoming references (callers) are not native to ORCA — they require an opt-in brute-force inversion of the library index and are off by default.
metadata:
  version: "1.2.0"
---

# Building a scoped context pack for review / refactoring

Use this skill any time you are about to **work on PowerBuilder code
in a real codebase** (not a fresh empty `.pbl`) and need to load
enough — but not too much — context.

PowerBuilder PBLs are physical containers, not logical modules. Real
legacy apps hold thousands of entries spread across dozens of PBLs.
Reading them all at once is impossible; reading the single target
entry in isolation misses parents and callers. This skill bridges the
gap: it explores the dependency neighborhood of a chosen target,
respects a budget, and returns a structured **context pack** for the
work downstream.

## When to invoke this skill

- The user asks for code review, refactoring, bug-fix, or extension
  on an existing PowerBuilder workspace.
- The [`pb-review`](../pb-review/SKILL.md) flow invokes you as its
  context-building step.
- You are about to export more than one entry and the choice of which
  entries to export is not obvious.
- You want to understand the blast-radius of a potential change
  (although for *that* specific question prefer `pb-impact-analysis`
  — a more focused report — once it exists).

If the workspace is a brand-new `.pbl` you just created and you only
need to scaffold a fresh entry, this skill is overkill — go straight
to [`pb-scaffold`](../pb-scaffold/SKILL.md).

## The MCP primitives this skill orchestrates

All from [`pb-orca-mcp`](https://github.com/restoresrl/pb-orca-mcp).
This skill never replaces a primitive; it sequences them.

| Primitive | Purpose | Session | Current app |
|---|---|---|---|
| `pb_workspace_info(lib_path)` | Project shape, projection directory, source encoding, git root, `outside_source_tree`, `source_protection` | no — and no PB install either | no |
| `pb_target_info(path)` | Parse a `.pbt` (or `.pbw`) into liblist + app metadata | no | no |
| `pb_library_directory(lib_path, entry_type?)` | List entries in a PBL, optionally filter by type | **yes** | no |
| `pb_object_query_hierarchy(lib_path, entry_name, entry_type)` | Inheritance chain (ancestors) of an entry | yes | **yes** |
| `pb_object_query_reference(lib_path, entry_name, entry_type)` | **Outgoing** refs of an entry (callees, ancestors used, types declared, windows opened). `ref_type` ∈ {`simple`, `open`} | yes | **yes** |
| `pb_library_entry_information(lib_path, entry_name, entry_type)` | Metadata for an entry (timestamps, size, base class, comment) | yes | no |
| `pb_library_entry_export(lib_path, entry_name, entry_type)` | Source **body** of one entry, as a string in the response | yes | no |
| `pb_library_export_sources(lib_path)` | Every entry in the library written out as `.sr*` files, in one call | yes | no |

**Two prerequisites, not one.** The last column exists because ORCA
distinguishes them and reports them separately: a session that is open
with a library list but no current application answers
`PBORCA_LIBLISTNOTSET (-12)` or `PBORCA_CURRAPPLNOTSET (-13)`, not
"entry not found". The two query primitives are the ones that need the
full bring-up; everything else works as soon as the session is up. If a
`pb_object_query_*` call comes back with `-13`, nothing is wrong with
your arguments — `pb_set_current_application` has not run yet.

**Direction note.** ORCA's `PBORCA_ObjectQueryReference` returns
**outgoing** refs of the queried object — what it calls and uses, not
what uses it. The opposite direction (incoming refs, "who calls
this") is **not exposed natively** by ORCA. Reconstructing it means
inverting the index: iterate every candidate caller in the library
list, query each, and keep those whose result set contains the
target. Costly (O(N) on liblist size), so it is offered only as an
opt-in pass — see [Caller discovery](#caller-discovery--opt-in-inversion-off-by-default).

Only the first two work before `pb_session_open`. Everything else,
`pb_library_directory` included, fails with a state guard until the
session is up.

**"Nothing to report" arrives in two different shapes, and one of them
looks like a failure.** Both query tools can answer "empty" with an
`error` envelope instead of an empty list:

| Response | Means |
| --- | --- |
| `{references: [], count: 0}` | no outgoing refs |
| `PBORCA_OBJHASNOREFS (-15)` | no outgoing refs — same thing |
| `PBORCA_OBJHASNOANCS (-14)` | no ancestors |

Which shape you get is not predictable from the entry type: in one
library a window with no refs returned the empty list while a datawindow
with no refs returned `-15`. And `-14` is the **normal** answer for any
object deriving straight from a built-in class (`window`,
`nonvisualobject`, …), which in most codebases is a large fraction of
them.

So treat `-14` and `-15` as **empty, not broken**. Record "no ancestors"
or "no outgoing refs" in the pack and move on. Do not report them to the
user as errors, do not retry them, and do not let them abort the walk.

**Which read primitive to use.** `pb_library_entry_export` puts the
body straight into your context and is the right default for the
handful of entries in a pack. `pb_library_export_sources` writes a
whole library to disk in one call — reach for it when you want to
**grep** across a library rather than read it (every caller of a
name, every `Dynamic Call`, every use of a literal), and when the
library is large enough that per-entry calls would dominate. Bear in
mind it materializes files: on a `pbl_only` project it *creates* a
source projection that did not exist, which changes the shape of the
repository. Say so before running it there.

## Step 0 — Ask the workspace what it is

Before any session bring-up, call `pb_workspace_info(lib_path)` on
one library of the target. One call, no ORCA session, no PB install
required. Four fields change how the rest of the work proceeds:

**Then look for libraries nobody told you about.** One call answers for
one library, so a flow that calls it once can only confirm what you
already knew — and a vendored dependency is by definition the thing you
did not know was there. After the first call, glob the project root for
`*.pbl` that are **not** under the `ws_objects_dir` the call just handed
you, and call `pb_workspace_info` on each hit. Sessionless and cheap: a
handful of calls on any real project. List what comes back flagged, in
the pack, even when the answer is none — "I looked and there are none"
and "nobody looked" are different statements and only one of them is
worth writing down.

A library sitting in `dep/`, `vendor/`, `lib/` or beside the `.pbl`s
without a projection is the shape to expect. Note that it may not be in
any target's `LibList`, so enumerating the liblist is not a substitute.

- **`mode`** — `ws_objects` (this library keeps `.sr*` text sources
  next to the `.pbl`, and those are the source of truth) or
  `pbl_only` (the `.pbl` is everything). It decides what a fix will
  touch and what the user commits at the end. **Per library, not per
  project**: a vendored `.pbl` inside a project that plainly keeps text
  sources answers `pbl_only`, and that is a fact about the library. Do
  not carry one library's answer to another — and do not read it as
  licence to run `pb_library_export_sources` on a library whose missing
  projection is the very thing that marks it as vendored.
- **`source_protection`** — `protected`, `unprotected` or `no_git`.
  **`unprotected` is a stop-and-say-so, not a footnote.** No
  `.gitattributes` rule exempts the `.sr*` files from git's
  line-ending translation, so git stores them with LF and hands them
  back as CRLF: the index and the working tree differ by exactly the
  bytes ORCA writes. A change lands in the `.pbl` and its projection
  while `git status` stays clean, and nobody sees the drift until a
  fresh checkout. Measure how far it has already gone with
  `git ls-files --eol <projection dir>` — count the files reported
  `i/lf w/crlf` — and report the number. Do not fix it silently as
  part of other work: the fix is `*.sr* -text` (and `*.pbl`, `*.pbd` as `binary`) plus
  `git add --renormalize -- '*.sr*' '*.pbl' '*.pbd'`, which rewrites every source in the index
  and belongs in its own commit with its own explanation.
  Use `-text`, not `binary`: both stop the translation, but `binary` implies `-diff`, so git answers "Binary files differ" and the change cannot be read — which is what the projection is for.
- **`export_encode`** — the workspace's `DefaultExportEncode`. You never
  have to act on it (ORCA writes the files), but it belongs in the
  pack: it is what makes a hand-edited file look out-of-sync to the
  IDE.
  There is no field called `encoding`: the tool returns `export_encode`,
  `orca_encoding`, `observed_encoding` and `encoding_source`. Record all
  four. `observed_encoding: null` means there was nothing to sample —
  a library with no projection — and is **not** a mismatch; skip the
  check rather than raising a finding about files that do not exist.
  Otherwise, `export_encode` disagreeing with `observed_encoding` means the
  workspace is already inconsistent and the IDE will rewrite those files
  on its next export, which is a finding, not a footnote.
- **`outside_source_tree`** — a **boolean about the library you asked
  about**, not a list. True for a library that sits inside the project
  but outside its source tree. **This one is load-bearing for a
  review.** A library flagged this way is a vendored dependency
  snapshot or a third-party component: it gets replaced wholesale by
  whatever produced it, so a refactoring proposed inside it will be
  overwritten at the next update of that dependency. Either exclude
  it from scope, or tell the user plainly that the finding belongs
  upstream, in the project that owns that library.

  **What the pack does with one**, since a warning is not a rule: include
  its entries as **read-only context** when the dependency graph reaches
  them — an ancestor three levels up often lives in one — and mark them
  in the `## Sources` heading as `— vendored, read-only`. They do not
  count against the entry cap, because they are context and not scope.
  Never propose a fix inside one, and never generate a projection for
  one. An unmarked vendored ancestor reads as ordinary project code, and
  the reviewer files a finding that will be overwritten by the next
  dependency update.

- **`work_dir`** — where working files go for a library with no
  projection, i.e. exactly the vendored case: `<root>/.pb-orca`. Worth
  reading because the first export against such a library creates that
  directory, and it is often not in the project's `.gitignore`. Say so
  rather than leaving an untracked directory for someone to find.


Record all four at the top of the context pack.

## Session bring-up

The session-bound primitives need, in order: `pb_session_open`
(`pb_version` or `install_path` is **required** — there is no
auto-pick, because `.pbt`/`.pbw` files do not record a PB release;
list the options with `pb_discover_pb_install` and say which you
chose), then `pb_set_library_list`, then
`pb_set_current_application`.

Two things to keep in mind:

- `pb_set_current_application` **may rewrite the `.pbw`** as a side
  effect. If the session ends with the user looking at `git status`,
  advise reverting that file unless a target was really added or
  removed.
- Sessions are not cheap to churn. Open one per unit of work, not one
  per object.

When bring-up fails, `pb-orca-mcp check <.pbw|.pbt|.pbl>` is a CLI
that validates the whole stack against the real project with no MCP
in the way. Use it as the diagnostic prerequisite instead of
guessing.

## Three scope flavors

Pick the smallest one that matches the user's request.

### Flavor A — entry-driven (default for "review this object")

Input: one entry triple `(lib_path, entry_name, entry_type)`.

1. Export the target entry's source (`pb_library_entry_export`).
2. Get the **inheritance chain** via `pb_object_query_hierarchy`.
   Export every ancestor up to the budget depth (default 3 levels;
   the topmost framework class — `window`, `nonvisualobject`, … — is
   the natural stop).
3. Get the **outgoing refs** (callees, used types, opened windows)
   via `pb_object_query_reference`. For each, read its metadata via
   `pb_library_entry_information` to decide whether to expand it. By
   default expand only `ref_type=open` (windows the entry opens —
   they are the integration boundary downstream); list
   `ref_type=simple` (functions called, types declared) without
   expanding unless budget allows.
4. If budget allows and the user asked for transitive outgoing refs
   (depth 2+), repeat step 3 on the depth-1 set — but prune
   aggressively: cap each level's expansion at ~5 entries.
5. **(Opt-in)** If the user asked for callers, run the inversion
   pass. Off by default because it is O(N) on liblist size.

### Flavor B — target-driven (default for "review this `.pbt`")

Input: a `.pbt` (or `.pbw`) path.

1. `pb_target_info(path)` → `lib_list` and `app_name`. Cheap, no
   enumeration.
2. **Immediately** show the PBL list to the user, marking any library
   that `pb_workspace_info` reported as `outside_source_tree`, then
   ask which PBL or entry-name pattern to focus on.
3. Only after the user has chosen a sub-scope (a single PBL → Flavor
   C; a single entry → Flavor A; a name pattern → filtered Flavor C)
   run `pb_library_directory` on that scope.

**Why not sweep first?** On real legacy targets (~6-12 PBLs × 100+
entries each) enumerating every PBL costs many round-trips and almost
always ends in "too big, refine". Skipping the sweep reaches the same
refinement turn one step earlier.

**Opt-in full sweep**: if the user explicitly asks for a complete
overview ("give me a count by entry type for the whole target"),
enumerate all PBLs, aggregate, and return a summary ("1834 entries
total: 1240 functions, 312 userobjects, …; largest PBLs by entry
count: …"). Then ask for refinement before any export.

This flavor's job is **orientation**, not export. Exporting at target
level is almost always a budget violation.

### Flavor C — PBL-driven (default for "review this PBL")

Input: one `lib_path`.

1. `pb_library_directory(lib_path, "any")` → list of entries.
2. Small count (≤ ~20 entries): export all of them in order. This is
   "review the whole PBL".
3. Moderate count (~20-100): filter by `entry_type` if the user named
   one ("review the userobjects in `core.pbl`"), then apply step 2 to
   the filtered set.
4. Large count (> ~100): refuse to export en masse. Return a summary
   and ask for refinement (single entry, or a pattern on entry name).
   If what the user actually wants is a *search* across the library
   rather than a read of it, that is the case for
   `pb_library_export_sources` plus grep.

## Outgoing refs from ORCA (default)

For each exported entry, call `pb_object_query_reference` to get the
`outgoing_refs` list — what the entry calls, opens, declares as a
type, or otherwise references. This is the **native, exact**
direction ORCA exposes and it is essentially free (one call per entry
already in the pack).

Each item comes back with `library`, `entry_name`, `entry_type` and
`ref_type` (`simple` for declarative refs, `open` for runtime window
opens). Record them `confidence: high` — they come from ORCA's index,
not from parsing.

What ORCA **cannot** see:

- `Dynamic Call`, `Dynamic Function`, `Dynamic Event` invocations.
- DataWindow expression strings (`SetItem(row, "col", value)` where
  `"col"` could be anything at runtime).
- Function names built at runtime by concatenation:
  `f_call(name + "_handler")`.

For those, see the heuristic fallback below.

## Caller discovery — opt-in inversion (off by default)

ORCA has no native primitive for "who calls this entry". To compute
incoming refs the skill must invert the index: iterate the library
list, query each candidate caller, keep those whose result set
contains the target.

This is **O(N) on liblist size** — on a monolith (~6-12 PBLs × 100+
entries each) it can mean 1000+ ORCA calls per target entry. Hence
**off by default**.

Activate it only when the user explicitly asks ("who calls
`n_logger.flush`?", "find all callers of `f_legacy_thing`") or when a
downstream skill needs the caller set. When activated:

1. Iterate every entry in the configured liblist via
   `pb_library_directory(lib, "any")`, skipping entries already known
   to be in the call-graph closure.
2. For each candidate call `pb_object_query_reference(candidate)` and
   check whether the target appears in its outgoing refs.
3. Cap the work: stop after N candidates probed (default 500) or N
   matches found (default 20), whichever comes first. Report honestly
   ("scanned 500/2400 entries, found 12 callers; widening would take
   roughly 5× longer").
4. Mark each caller `confidence: high` (it is ORCA — exact) with the
   `ref_type` from the query.

**The cheaper alternative worth offering first.** If the question is
"who mentions this name", `pb_library_export_sources` on the
candidate libraries plus a grep over the resulting files answers it
in a couple of calls instead of a thousand. Being textual, it also
catches the dynamic invocations ORCA cannot see — and it will produce
false positives (comments, similarly-named identifiers). Offer it as
the fast pass; reserve the inversion for when exactness matters.

For very-base userobjects with hundreds of callers, do not chase the
full set: give a count and the top-N by liblist proximity.

## Heuristic fallback for dynamic patterns (optional)

Some dependencies are invisible to ORCA's index because they resolve
at runtime. If you suspect a refactor crosses such a boundary, run a
regex pass over the exported source for the patterns above, flag the
candidates `confidence: low, kind: dynamic`, and present them as
"ORCA cannot confirm these edges; review by hand". Never treat them
as hard topological constraints downstream.

This pass is intentionally narrow: it covers only what ORCA cannot
see. The bulk of the call-graph already comes from
`pb_object_query_reference` with `confidence: high`.

## Editability contract

The `outgoing_refs` from ORCA are facts; the heuristic
dynamic-pattern fallback produces **proposals**. The downstream
plan-file format lets the user edit the `depends_on` field by hand.
User-added edges are marked `confidence: user-augmented` and override
anything the heuristic pass suggested. ORCA-sourced edges marked
`confidence: high` should not be edited away without good reason.

## Budget mechanics

Judgment-based, not a strict counter. Defaults that work as starting
points on monolithic codebases:

- **Cap on exported entries**: the size budget is the rule; 20 entries is a rule of thumb for typical sizes, not a limit to prune to. If the natural
  flow would exceed it, prune (depth, then breadth) until under cap.

  **The size cap is the binding one; the count is advisory.** Twenty is
  twenty entries *of typical size*. A library of global functions is
  mostly 300-600 byte wrappers, and pruning six of them to satisfy an
  arithmetic limit removes the callers that give the object under review
  its contract, while freeing well under 1% of the budget. Entries below
  ~2 KB do not count against the twenty. If the pack is under the size
  cap, do not prune to meet the count — say what you included and why.
- **Soft cap on cumulative source size**: ~150 KB of plain text
  (~50 K tokens). Track as you go; if you cross it before reaching
  the outgoing-refs expansion, stop and report what you have. The
  target entry and its inheritance chain take precedence.

  **Neither size field ORCA reports is the size of the export.** There
  are two, they are different numbers, and both mislead:

  | field | where | relation to the exported bytes |
  |---|---|---|
  | `source_size` | `pb_library_entry_information` | ≈ **2×**, always — it counts UTF-16 code units |
  | `object_size` | `pb_library_entry_information`, and the `size` in every `pb_library_directory` row | **unrelated**, and wrong in *both* directions depending on entry type |

  `source_size` is the safe one: halve it. Measured on a real library,
  `source_size: 41076` for an entry `pb_object_export_file` wrote as
  20 577 bytes, and `source_size: 122652` for one it wrote as 61 375.
  The factor held on every entry checked. Not halving it makes the pack
  look 2× more expensive than it is, which prunes scope that did not
  need pruning — conservative, but a real distortion at the moment you
  decide what to leave out.

  `object_size` is the compiled object, and it is the trap, because it
  is **the only size in a `pb_library_directory` listing** — which is
  exactly what Flavor C has to budget from, before anything is
  exported. Measured across one 10-entry library:

  | entry type | `object_size` ÷ exported bytes |
  |---|---|
  | userobject | 2.7× – 7.9× (over) |
  | menu | 3.7× – 4.0× (over) |
  | window | 3.5× – 4.6× (over) |
  | **datawindow** | **0.58× – 0.67× (under)** |

  Compiled PowerScript is bulkier than its source; a DataWindow's
  source is bulkier than its compiled form. So on a library of mixed
  types the errors do not even cancel — they point opposite ways, and
  the type that under-reports is the one whose sources are largest. In
  that library the directory listing totalled 216 KB against 158 KB of
  actual source, while the four DataWindows alone — 77% of the real
  bytes — looked like a third of the total.

  **So do not budget a library scope from the directory listing.** Use
  it to enumerate and filter, then get `source_size` for the shortlist
  and halve it. One extra call per candidate entry, and it is the
  difference between a budget and a guess.
- **Default expansion depth**: ancestors = 3, outgoing refs = 1. Both
  configurable per invocation.
- **Caller discovery (opt-in) caps**: max 500 ORCA queries on the
  liblist, max 20 callers reported, whichever comes first. Always
  honest about partial scans.
- **Pruning order** when over budget: (a) drop `simple`-typed
  outgoing refs first (declarative refs are usually less load-bearing
  than `open`-typed ones); (a′) **when every ref is `simple`, rank them
  instead** — see below; (b) drop ancestors beyond depth 2; (c)
  drop framework-level ancestors (`nonvisualobject`, `window`,
  `userobject`) since the language reference covers them — see
  [`appeon-query`](../appeon-query/SKILL.md); (d) skip the
  caller-discovery pass entirely.

  **(a′) matters more often than (a).** Step (a) assumes the refs are a
  mix of `simple` and `open`, and on a `nonvisualobject` they never are:
  `open` is a window-opening reference, so a non-visual class has none
  and step (a) degenerates to drop-everything-or-nothing. Measured on a
  real persistence base class: 37 outgoing refs, **all `simple`, zero
  `open`**, with a depth-1 expansion at 159% of the size cap. The type
  told you nothing about what to cut.

  Rank by these two, in order, and say in the pack which ones you kept
  and why:

  1. **Is the entry in the target's own inheritance or delegation
     chain?** An ancestor, an interface the target owns, the datastore
     it drives — these are the code the target's behaviour is *made of*,
     and a review without them is guessing. Keep them.
  2. **Size**, descending, among everything left. Two 20 KB peers cost
     as much as the target itself and usually buy one finding between
     them; ten 500-byte helpers cost nothing and often carry a contract.

  What that produced on the case above: the target plus its two
  interface classes plus its datastore — 4 entries, 95 KB, 62% of the
  cap — with the eighteen referenced peers (21 KB, 17 KB, 15 KB, 14 KB
  and so on) left out and **listed by name in `## Skipped`, with the
  questions their absence leaves open**. That last part is the
  obligation: a pruned pack is honest only if the reader can see the
  shape of the hole.

These caps are starting points, not law. Adjust if the user signals
they want a deeper or shallower view.

## Output: the context pack shape

Return a structured summary to whoever called you (usually
[`pb-review`](../pb-review/SKILL.md), but a direct user invocation is
fine). Recommended shape — flexible markdown, not a rigid schema:

```
## Context pack: <target description>

**Workspace** (from `pb_workspace_info`): mode=<ws_objects|pbl_only>,
encoding=<export_encode> (orca=<…>, observed=<…>, from=<…>), git=<yes|no>,
outside_source_tree=<the flagged libraries found by the sweep above, or 'none found'>, source_protection=<…>

**Target**: `lib_path` :: `entry_name` (`entry_type`)

**Inheritance chain** (depth: N exported, M skipped):
- ancestor_1 (lib) — exported
- ancestor_2 (lib) — exported
- nonvisualobject — framework, not exported (see appeon-query)

**Outgoing refs** — via `pb_object_query_reference` (callees,
ancestors used, types declared, windows opened), depth 1, N total,
M exported:
- ref_1 (lib, kind=function,   ref_type=simple, confidence=high) — exported
- ref_2 (lib, kind=window,     ref_type=open,   confidence=high) — exported
- ref_3 (lib, kind=userobject, confidence=low,  kind=dynamic)    — Dynamic Call, heuristic

**Incoming refs (callers)** — OPT-IN, off by default; populated only
when the user asks. Via inversion of `pb_object_query_reference`
over the liblist:
- caller_1 (lib, ref_type=open, confidence=high)
- ... (scanned N/M liblist entries; capped at 20 unless overridden)

**Budget**: N entries exported, ~K tokens of source loaded.
Pruned: <what was dropped and why>.

## Sources

### `lib_path` :: `entry_name` (target)

<full source>

### `lib_path` :: `ancestor_1`

<full source>
```

The pack is informational, not executable. ORCA-sourced edges are
`confidence: high`; heuristic dynamic-pattern edges are
`confidence: low` and belong in the output as warnings, not facts.

## Limitations (explicit non-goals)

- **Caller discovery is opt-in and capped.** Inverting ORCA's index
  is O(N) on liblist size. The skill is always honest about partial
  scans.
- **Dynamic patterns are flagged, not resolved.** `Dynamic Call`,
  `Dynamic Function`, DW expression strings and runtime-built names
  are invisible to ORCA's index. The optional heuristic pass marks
  them `confidence: low`; never treat them as hard edges.
- **No cross-target review.** If the workspace has multiple `.pbt`
  files and the refactor would span them, this skill does one target
  at a time.
- **No caching of context packs between sessions.** Every invocation
  rebuilds from scratch. Caching is a future optimization if review
  latency becomes painful.
- **No automatic bulk sweep.** Manual-assist by design: the user
  picks the target, the skill helps understand it.

## Failure modes to handle gracefully

Every tool returns one of exactly two shapes: a success payload, or a
single `error` envelope (`{"error": {"code", "name", "message"}}`).
Branch on `"error" in response` first. Read success payloads
defensively — index by key, do not assume a fixed field set.

- **Session not open**: the session-bound primitives fail with a
  state-guard error. Bring the session up rather than retrying.
- **Entry not found**: `pb_object_query_*` errors when the entry is
  not in the library list. Verify via `pb_library_directory` first,
  then guide the user to the right spelling or PBL. Do not confuse this
  with `-14` / `-15`, which mean the entry was found and has nothing to
  report.
- **PBL not in library list**: even when the file exists on disk,
  `pb_object_query_*` only sees entries in the configured liblist.
  Check that `pb_set_library_list` covered every relevant PBL.
- **Wrong architecture / DLL not found**: the server's Python must
  match `pborc.dll` (x86 through PB 2025). `pb-orca-mcp doctor`
  reports the whole picture; do not work around it.
- **Huge incoming-ref set** during opt-in caller discovery (a base
  userobject used everywhere): truncate aggressively and report the
  count honestly.

## Boundaries with sibling skills

- `pb-impact-analysis` (planned): when the question is specifically
  "what breaks if I touch X", that skill will produce a tighter,
  blast-radius-focused report. This one is broader: it loads context
  for *any* downstream task.
- [`pb-scaffold`](../pb-scaffold/SKILL.md): unrelated — that one
  *creates* new entries; this one helps *understand* existing ones.
- [`appeon-query`](../appeon-query/SKILL.md): for questions about
  PowerScript syntax or runtime API, not project-specific code.
  Complementary: this skill loads the project context, that one loads
  the language context.
- [`pb-src-format`](../pb-src-format/SKILL.md): once you have the
  exported source, its wiki pages explain the file format if you need
  to edit it.
- [`pb-review`](../pb-review/SKILL.md) is the primary consumer:
  context-build → review → plan file → apply loop.
