---
name: pb-impact-analysis
description: Use this before a non-trivial PowerBuilder refactor when you need to know what can break if an entry, method, event, DataWindow contract, or inherited API changes. Produces a read-only blast-radius report from the target's library list. Uses ORCA for outgoing references and exact caller confirmation, source search for candidate callers and dynamic uses, and hierarchy inversion for descendants. Reports partial coverage instead of treating an incomplete scan as proof that an object is unused.
metadata:
  version: "1.1.0"
---

# PowerBuilder impact analysis before a refactor

Use this skill to answer a specific question: what code can be affected by
this proposed change?

The proposed change matters as much as the target. Replacing an internal
algorithm has a different blast radius from renaming a public function, even
when both touch the same entry. Resolve both before querying the workspace.

This flow reads the project and reports its evidence. It does not edit source
files, regenerate objects, or write a report to disk unless the user asks for
a saved copy.

Prompts in this file are written in English. Speak the user's language.

## Inputs

Collect these before starting:

1. The PowerBuilder target or workspace that supplies the library list.
2. The affected entry, preferably as
   `<lib_path>::<entry_name>:<entry_type>`.
3. The member, event, control, DataWindow column, or other sub-entry symbol,
   if the change is narrower than the entry.
4. A concrete description of the proposed change.
5. The exact PowerBuilder release slug recorded in the project's instructions,
   such as `pb2022r3`. Use its derived ORCA token (`22.0` for this example)
   when opening a session. Do not infer the release from `appruntimeversion` in
   an export.

If the request names an object but not the change, ask what will change. If it
names a method but not its owning entry, resolve the owner before continuing.
Do not substitute a similarly named entry when more than one library contains
the name.

Impact analysis covers one target at a time. If several `.pbt` files consume
the library, list them and ask which one to analyse first. Other targets remain
an explicit coverage gap.

## Choose the analysis mode

Use the smallest mode that can answer the question.

| Proposed change | Default mode | Why |
| --- | --- | --- |
| Internal implementation with the same observable contract | fast | Direct consumers and dependencies usually provide enough context |
| Changed result, side effect, error handling, or timing | fast, then widen selected callers | The effect may pass through callers that expose it |
| Rename, delete, move, signature, return type, or visibility change | exhaustive | A missed caller can become a compile or runtime failure |
| Change to an ancestor, inherited contract, or overridable event | exhaustive hierarchy and callers | Descendants may break without naming the changed member directly |
| Method, event, control, DataWindow column, or string-addressed API | source-led | ORCA reports entry-level edges, not a complete member-level graph |

The fast mode finds candidates from source and asks ORCA to confirm the entry
edges. It is the practical default on a large workspace, but it is not an
exhaustive caller search.

The exhaustive mode inverts ORCA's index across every eligible entry in the
resolved library list. Count the candidates first and show the estimate:

> "This target contains 2,430 entries. An exhaustive caller pass can require
> one ORCA query per entry. Run the full pass, set a limit, or start with the
> fast pass?"

For destructive contract changes, recommend the full pass. If the user chooses
a limit, the result is partial and the report must say so.

## Tool contract

The primitives come from
[`pb-orca-mcp`](https://github.com/restoresrl/pb-orca-mcp). This skill only
sequences them.

| Primitive | Use |
| --- | --- |
| `pb_workspace_info(lib_path)` | Read project shape, projection path, encoding, git state, and vendor boundary without a session |
| `pb_target_info(path)` | Resolve a `.pbt` or `.pbw` into its target and library list |
| `pb_library_directory(lib_path, entry_type?)` | Enumerate caller and descendant candidates after session bring-up |
| `pb_object_query_reference(lib_path, entry_name, entry_type)` | Read an entry's outgoing references |
| `pb_object_query_hierarchy(lib_path, entry_name, entry_type)` | Read an entry's ancestors, closest first |
| `pb_library_entry_export(lib_path, entry_name, entry_type)` | Read a small number of candidate sources |
| `pb_library_export_sources(lib_path, dest_dir)` | Put a whole library in a scratch directory for source search |

`pb_object_query_reference` returns outgoing references: what the queried
entry uses. It does not return callers. Caller discovery queries candidate
callers and keeps the ones whose outgoing list contains the target.

The query tools require an open session, a library list, and a current
application. `pb_library_directory` also requires the session. Treat a
`PBORCA_CURRAPPLNOTSET (-13)` response as incomplete bring-up, not a missing
entry.

Every tool has one of two top-level response shapes: a success payload or an
`error` envelope. Branch on `"error" in response` first. Read successful
payloads by key because the server may add fields.

Two query errors mean an empty result:

- `PBORCA_OBJHASNOANCS (-14)`: no reported ancestors.
- `PBORCA_OBJHASNOREFS (-15)`: no reported outgoing references.

Do not retry or report these as tool failures. The reference case needs the
stale-index check described below before it can be called a true empty result.

## Step 0: map the workspace

Call `pb_workspace_info` on the target library before opening ORCA. Then call
it on every library in the resolved target and on project-local `.pbl` files
that sit outside the source tree.

Record, per library:

- `mode`, either `ws_objects` or `pbl_only`;
- `outside_source_tree`;
- `source_protection`;
- `work_dir`;
- whether the file is a `.pbl` or `.pbd`.

A library with `outside_source_tree: true` is read-only context. Report impacts
inside it as work for the owning project. Do not propose editing its local
snapshot.

A `.pbd` can appear in the library list even though its source is unavailable.
Keep its entries in the external or unreadable section. Do not turn an export
failure into "no impact".

For a `.pbt` or `.pbw`, use `pb_target_info` and keep the exact library order.
For a bare entry triple, ask which target supplies the library list when that
cannot be established from project instructions. Do not build a synthetic list
from every `.pbl` found on disk. It may include unrelated applications with
colliding entry names.

## Step 1: bring up one ORCA session

Use this order:

1. `pb_session_open` with an explicit PB version or install path.
2. `pb_set_library_list` with the resolved target list.
3. `pb_set_current_application` for that target.

A library list can be set only once in a session. If the server returns
`PBORCA_DUPOPERATION (-2)`, close the session and start again. Continuing would
query the previous target and produce plausible results for the wrong
application.

If bring-up fails, use `pb-orca-mcp check <target>` as the diagnostic step.
Do not replace missing ORCA evidence with guesses.

## Step 2: establish the changed surface

Export and read the target entry. State what part of its contract can change:

- name or location;
- parameters, return value, visibility, or exceptions;
- observable state and side effects;
- inherited or overridden behaviour;
- string-addressed names, such as DataWindow columns or dynamic calls;
- internal implementation only.

This is a classification, not a code edit. If the user described an internal
refactor but the source shows that it changes a public side effect, say so and
ask which contract is intended.

ORCA's granularity is the library entry. A confirmed edge to a window proves
that the caller uses the window, not that it invokes one particular event. For
a method or event change, read the matching source locations before calling a
candidate a consumer of that member.

## Step 3: read outgoing constraints

Call `pb_object_query_reference` on the target and record its outgoing
references. These are not the blast radius, but they constrain the change. A
replacement must still satisfy any contracts that the target relies on unless
the proposed work includes those dependencies.

Also call `pb_object_query_hierarchy` on the target. Export the nearest relevant
ancestors when the change touches inherited behaviour. Use
[`pb-context-build`](../pb-context-build/SKILL.md) if understanding those
sources would exceed a small, focused read.

Mark ORCA edges `confidence: high`. Mark runtime-built names found only in
source `confidence: low` until a person or test confirms them.

## Step 4: find direct consumers

### Fast mode

Search only the source trees that belong to the resolved library list.

- On a `ws_objects` library, search its existing PowerBuilder-managed
  projection. It is a candidate surface, not authority over the `.pbl`.
- On a `pbl_only` library, offer `pb_library_export_sources` with a
  `dest_dir` outside the project. This creates scratch files but does not
  change the `.pbl` or create a project projection.
- Never bulk-export a vendored library into the project source tree, and
  never create `ws_objects/` on behalf of the IDE.

Use a case-insensitive, word-boundary search for the entry or member name.
PowerBuilder identifiers ignore case, and its naming conventions make
substring matches common. Keep searches scoped to the target library list
because unrelated targets often reuse the same application and userobject
names.

For each candidate entry:

1. Read the source location that matched.
2. Call `pb_object_query_reference` on the candidate.
3. If its outgoing references contain the exact target entry triple, record an
   ORCA-confirmed consumer with `confidence: high`.
4. If the source visibly uses a changed member but ORCA only confirms the owner
   entry, record both facts. The member evidence comes from code reading.
5. If the text appears only in a comment, unrelated identifier, or inert
   string, reject it and keep the reason out of the consumer count.
6. If it can be a dynamic invocation, retain it as a possible runtime consumer
   with `confidence: low`.

The fast pass is candidate-bounded. Say that in the report even when every
candidate was checked.

### Exhaustive mode

Enumerate every eligible entry in each `.pbl` from the resolved library list.
For every candidate, query its outgoing references and compare each result with
the target's library, entry name, and entry type. Normalize Windows library
paths and compare PowerBuilder identifiers without case sensitivity. Preserve
the spelling returned by ORCA in the report. Matching only the name is not
enough.

Report progress at useful intervals and finish with `scanned N/M`. Do not call
a capped or interrupted pass exhaustive. A complete ORCA inversion proves the
static entry-level caller set only. Dynamic dispatch and consumers in another
target remain outside that proof.

Do not skip candidates already found by source search. They still count toward
the complete scan, and querying them catches cycles and confirms the final
total.

## Step 5: find inheritance impact

Changing an ancestor or overridable contract requires the reverse of a
hierarchy query. ORCA returns ancestors, not descendants.

In fast mode, search source for the target type name, then call
`pb_object_query_hierarchy` on each plausible descendant. Keep a candidate only
when the returned chain contains the exact target entry.

In exhaustive mode, query every compatible object candidate in the library
list and invert the hierarchy results. Record:

- direct descendants;
- deeper descendants and their distance from the target;
- overrides or same-named members visible in their sources;
- descendants in vendored or unreadable libraries.

For a contract change, direct callers of affected descendants may also matter.
Run caller discovery on a descendant only when reading it shows that the
changed contract is exposed or relied on. Do not expand every branch without a
reason. Record which branches were not expanded.

## Step 6: check dynamic and string-addressed uses

ORCA cannot fully resolve:

- Dynamic Call, Dynamic Function, and Dynamic Event targets;
- names assembled at runtime;
- DataWindow column and expression strings;
- external code that loads entries by name;
- callers in another PowerBuilder target or repository.

Search the scoped sources for the exact symbol and inspect the surrounding
code. Classify each remaining hit as a confirmed source use, a possible runtime
use, or a rejected text match. Do not turn text hits into hard graph edges.

For a rename or delete, include comments and documentation in a separate
cleanup list. They are not runtime consumers, but leaving the old name there
can mislead the next maintainer.

## Step 7: decide whether to widen

Depth 1, the direct consumers, is the default. Widen to another caller layer
when a direct consumer:

- exposes the changed value or exception through its own public contract;
- translates the changed side effect into state used elsewhere;
- is a shared wrapper or service boundary;
- contains no local guard against the changed behaviour.

Explain why each branch was widened. Stop branches that absorb the change and
name the evidence, such as a conversion, fallback, or stable wrapper contract.

Do not report the unexpanded remainder as unaffected. Put it in the coverage
section.

## Stale or absent ORCA reference data

ORCA reads reference information written when an entry was compiled. An entry
that has never been regenerated can return `-15` even when its source plainly
calls another object.

Use both checks:

- Per entry, compare an empty ORCA result with the source already read.
- Per library, treat a run of empty results across entries that visibly call
  one another as evidence that the index is unavailable.

When the index is unavailable, label ORCA coverage `unavailable`, fall back to
source evidence, and stop calling the result exact.

`pb_object_regenerate` repairs the index by writing the `.pbl`. This skill does
not run it. Offer the repair as a separate, explicit operation, explain that it
changes the library, and rerun the analysis afterwards if the user accepts.

## Report shape

Return the report in the conversation. Use this structure:

```markdown
# Impact analysis: <target and proposed change>

## Changed surface
- Target: <library>::<entry>:<type>
- Member: <member or whole entry>
- Proposed change: <specific description>
- Mode: <fast|exhaustive|source-led>

## Confirmed direct consumers
- <caller> (orca-confirmed, confidence=high): <how it uses the target>

## Inheritance impact
- <descendant> (distance N, confidence=high): <override or inherited use>

## Possible runtime consumers
- <entry> (source-only, confidence=low): <dynamic or string-addressed use>

## Outgoing constraints
- <dependency>: <contract the target still relies on>

## External or unreadable
- <library or target>: <why it could not be checked>

## Coverage
- Libraries in target: N
- Entries scanned: N/M
- ORCA reference index: <available|partly available|unavailable>
- Source search: <projection|scratch export|not run>
- Not expanded: <branches, targets, or libraries>

## Recommendation
<proceed with named checks | widen first | blocked by missing evidence>

## Verification checklist
- <specific compile, rebuild, test, or manual exercise>
```

Use counts as evidence, not as a risk score. Ten small wrappers are not
necessarily riskier than one application boundary.

Never write "unused" or "no impact" from a fast pass. Prefer precise wording:

> "No ORCA-confirmed callers were found among 84 source candidates in the
> configured target. The pass did not inspect other targets, and dynamic uses
> remain possible."

If the scan is partial, put that in the first paragraph of the report, not only
in `## Coverage`.

## Verification checklist rules

Derive checks from the affected surface:

- Compile the changed entry and every source entry that must change with it.
- Regenerate descendants when an inherited contract changed.
- Rebuild the target for a rename, delete, signature change, or shared
  ancestor change.
- Exercise dynamic and DataWindow uses manually when no automated test covers
  them.
- Check each external consumer in its owning target or repository.

These are recommendations for the later edit flow. This skill does not execute
them and does not claim that a successful compile proves runtime compatibility.

## Failure modes

- **Target entry not found**: verify the exact library and type with
  `pb_library_directory`; do not search a different library silently.
- **Current application missing**: complete session bring-up before retrying
  query tools.
- **Duplicate library-list operation**: close and reopen the session.
- **Reference index unavailable**: report source-only evidence and offer a
  separate regeneration step.
- **Scratch export refused**: continue with directory metadata and ORCA if
  possible, then state that dynamic and member-level search was not run.
- **`.pbd` consumer**: list it as unreadable; source absence is not proof of no
  dependency.
- **Candidate limit reached**: report `scanned N/M`, keep the result partial,
  and offer to resume.
- **IDE lock or DLL failure**: stop and use `pb-orca-mcp doctor` or `check`.
- **Several targets consume the library**: finish one target, then repeat. Do
  not merge their library lists into a synthetic application.

## Boundaries with sibling skills

- [`pb-context-build`](../pb-context-build/SKILL.md) loads a budgeted source
  neighborhood for general review. This skill asks a narrower blast-radius
  question and enables caller discovery by design.
- [`pb-review`](../pb-review/SKILL.md) uses this skill for findings that change
  a public contract, inherited behaviour, or a string-addressed name.
- [`pb-apply-plan`](../pb-apply-plan/SKILL.md) applies approved fixes. Its skip
  impact check concerns dependencies between plan findings, not source-level
  consumers.
- [`appeon-query`](../appeon-query/SKILL.md) checks PowerScript language and
  runtime semantics. It cannot answer which project entries use a symbol.
- [`pb-orca-mcp`](https://github.com/restoresrl/pb-orca-mcp) owns every ORCA
  primitive. Missing graph operations belong there, not in a parser added to
  this repository.
