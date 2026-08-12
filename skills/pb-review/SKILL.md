---
name: pb-review
description: Use this to run a structured code review on a PowerBuilder target — an entry, a .pbl, a .pbt, or a free-form description of a block of code. Frames the work with the user, builds a scoped context pack, validates understanding before reviewing, then produces two persistent artefacts (a plan file with one YAML-tagged finding per fix, and a CHANGELOG entry) and hands off to pb-apply-plan for the edit loop. Never edits PowerBuilder sources; it does write three files — the plan, the CHANGELOG entry, and a one-line pointer into the project's own backlog if it has one.
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

## Running unattended

This flow is written for a conversation, and several steps say to wait
for the user. When there is no user — a subagent, `claude -p`, a
scheduled run — do not hang and do not silently ignore the
instruction. Switch to these defaults, and **state at the top of the
plan file that the run was unattended and which choices were made for
the user**:

| Step | Interactive | Unattended default |
| --- | --- | --- |
| Step 0 framing | confirm five things | derive them: scope category from the request's wording, context slug from the entry name, entry set = the target plus its ORCA-resolved neighbourhood, budget computed and reported, semver from the finding mix |
| Step 2a understanding gate | wait for acknowledgement | the `## Understanding` section *is* the gate — write it, and mark every assumption you could not confirm |
| Second sweep | offer | run at least two; keep going while a sweep adds a finding; stop at four |
| `.pb-review/` gitignore offer | ask | do not ask, and do not gitignore it. The plan file is work product, not harness state, and the promise that another agent can resume it later only holds if it reaches the repository. This flow does not commit it, so say so explicitly in the closing summary: the plan file is untracked and wants committing |
| Step 4 handoff | offer the apply loop | never **on your own initiative**. If the invoker explicitly asked for the apply loop, run it — restricted to `evidence: code-read` and `verified-in-docs` findings, under `pb-apply-plan`'s own unattended rules — and record the override in the plan file |

Everything else — the pre-flight, the gates that protect the workspace,
the refusal in `pb-apply-plan` — applies unchanged. Unattended means
*nobody to ask*, not *nobody to protect*.

## Pre-flight

0. **Find out what the project already knows about this code.** Cheap,
   and skipping it is the single most expensive mistake this flow can
   make: on a project with review history, most of what you are about to
   produce is already written down, and a report that re-derives it is
   worse than no report — the maintainer now has to diff two documents
   to find what is new.

   Read, in this order: `CHANGELOG.md`, `AGENTS.md` (or `CLAUDE.md`),
   `README`, and **any backlog, plan or review document they link to**.
   The pointer is often a single line — a real project had
   "voci con riferimento (`piano X.Y`) rimandano al piano fix" three
   lines into its `CHANGELOG.md`, pointing at a 15 KB prior review of
   the very object under review. Also look for `doc/`, `docs/`,
   `.pb-review/` and anything matching `*plan*`, `*review*`,
   `*backlog*`, `*todo*`.

   Carry the result into the review as a list of what is already
   recorded, with that document's own identifiers. Findings that match
   it do not go in the queue: they go in `## Already recorded elsewhere`
   (see Step 3), which tells the maintainer you looked and agreed. State
   in the report which documents you read; if there were none, say that
   too, because "no prior review exists" is itself worth knowing.

1. **`pb_workspace_info(lib_path)`** — one call, no ORCA session, no PB
   install needed. It gives the project shape (`ws_objects` vs
   `pbl_only`), the source encoding, whether git is watching, and
   `outside_source_tree` — **a boolean about the library you asked
   about, not a list**, so speaking about several means one call each;
   `pb-context-build` Step 0 sweeps for the ones nobody named. Note any
   library flagged `outside_source_tree`: it is a vendored dependency snapshot or a
   third-party component, so a refactoring proposed inside it will be
   overwritten at the next update of that dependency. Either keep it
   out of scope or say plainly that the finding belongs upstream.

   **When the *target itself* is vendored, the whole review is an
   upstream review, and that changes where its output goes.** This is a
   legitimate thing to ask for — reviewing a shared framework from the
   project that consumes it is often the only place anybody reads it —
   but the flow's two artefacts assume the findings can land here, and
   they cannot: every one of them carries `outside_source_tree: true`,
   `pb-apply-plan` refuses all of them, and the next dependency update
   would overwrite anything applied anyway. So:

   - **Write the plan file as usual.** It is the deliverable, and it is
     what somebody carries to the other repository. Name the scope for
     what it is (`upstream-<libname>` rather than `review-<libname>`)
     and put the owning project in the header's `target` line.
   - **Do not write a `CHANGELOG.md` entry in the consuming project.**
     That file is the record of *this* project's changes; an
     `[Unreleased]` section listing fixes that will never be made here
     is a lie that outlives the review. Say in the summary that the
     entry was deliberately not written, and why.
   - **Do not offer the apply-loop handoff.** There is nothing here it
     is allowed to touch.
   - **Say that Pre-flight 0 could not run properly.** The prior
     reviews, backlog and changelog that would tell you what is already
     known belong to the upstream repository, and they are not in this
     checkout. Record that as a limitation rather than reporting "no
     prior review exists", which is a claim you have no way to make.

   A mixed scope — some entries local, some vendored — is the normal
   case and needs none of this: keep the CHANGELOG entry, and list only
   the local findings in it.

   **A `.pbd` in the library list is a third case, and it looks like a
   bug when you meet it.** Compiled libraries enumerate but carry no
   source: `pb_library_directory` lists their entries happily, and
   every `pb_library_entry_export` or `pb_library_entry_information`
   on those same names answers `PBORCA_OBJNOTFOUND (-3)`, *"was not
   found"*. The name is right and the library is right — the source
   simply is not there. See
   [`pb-context-build`](../pb-context-build/SKILL.md) for the detail.
   In the report, list such references under `## Skipped` as
   unreadable-by-construction rather than silently dropping them: an
   outgoing ref into a `.pbd` is a real dependency, and the fact that
   this review could not read it is exactly the kind of gap
   `## Skipped` exists to make visible.

   **Also read `source_protection`.** `unprotected` means git rewrites
   the `.sr*` line endings, so the index and the working tree differ by
   exactly the bytes ORCA writes — an applied fix can leave
   `git status` clean and surface as drift on someone else's checkout.
   A review is read-only and safe either way, but it ends by handing
   off to `pb-apply-plan`, which is not.

   **Measure the disagreement that actually matters**, which is between
   what ORCA holds and what is on disk — not between git's index and the
   working tree. Export one entry of the target to a scratch directory
   and compare:

   ```python
   # <a> = the scratch export, <b> = the projection file
   a = open(r"<a>", "rb").read()
   b = open(r"<b>", "rb").read()
   print("identical:", a == b)
   print("bytes", len(a), len(b), " CR", a.count(13), b.count(13))
   print("same once CR stripped:",
         a.replace(b"\r", b"") == b.replace(b"\r", b""))
   ```

   "Same once CR stripped" with different CR counts is the signature:
   the content agrees and every line ending will flip the moment the
   apply loop writes the file back. Report the number of line endings
   involved — it is the size of the invisible change. Measured on a real
   library: ORCA held 663 of 704 line breaks as bare LF while the
   working tree had all 704 as CRLF, so an apply loop would have
   rewritten 663 of them with `git status` clean throughout.

   `git ls-files --eol <projection dir>` is a useful **secondary**
   reading — how far the normalization has already spread across the
   tree — but it is a fact about git, not about ORCA, and on its own it
   does not establish the danger.

   Either way, say it has to be fixed — `*.sr* -text` (and `*.pbl`,
   `*.pbd` as `binary`) plus `git add --renormalize -- '*.sr*' '*.pbl' '*.pbd'`, its own commit —
   **before** the apply loop runs, not after. Use `-text`, not `binary`:
   both stop the translation, but `binary` implies `-diff`, so git
   answers "Binary files differ" and the change cannot be read, which is
   what the projection is for.
2. **Resolve which target owns the library**, before opening anything.
   An entry triple does not name a library list, and the workspace's
   default target is frequently the wrong one: in a real project the
   default's `LibList` did not contain the library under review at all,
   so a session opened against it would have failed every
   `pb_object_query_*` call with "entry not found" — a symptom that
   looks like a misspelled entry name and sends you hunting in the wrong
   place. Read the `.pbw`, call `pb_target_info` on each target, and
   pick the one whose `LibList` contains your library; use its `applib`
   and `appname`. Say which you picked and why. If no target contains
   it, stop and say so: the entry is not reachable from any build.

   **Get the target list from the `.pbw`, never from a glob.**
   `pb_target_info` on the workspace file returns the targets it
   actually declares — one call, no session — and a filesystem glob
   disagrees with it in **both** directions. In one real workspace,
   `src/*.pbt` matched 16 files while the `.pbw` declared 14: the glob
   missed two targets that live in subdirectories (`src\test\…`,
   `src\tools\…`) and picked up two orphaned `.pbt` files that no
   longer belong to any workspace. Reviewing against an orphan means
   resolving a library list nobody builds; missing a subdirectory
   target means concluding a library is unreachable when it is not.

   **Then shortlist.** "Call `pb_target_info` on each target" is fine
   for three and wasteful for fourteen, and a `.pbt` is a text file
   whose `LibList` is in it verbatim — so grep the library's basename
   across **the paths the `.pbw` returned** to narrow the field, then
   call `pb_target_info` on the survivors, because that is what parses
   the liblist properly and resolves the relative paths. The grep
   decides which targets to ask about; the tool still decides the
   answer.

   When several targets qualify — eleven of fourteen did, in one real
   workspace — the choice is yours to justify, not to make silently.
   Prefer the one whose application is the primary consumer of the code
   under review, and say so; the library list you pick is recorded in
   the plan header precisely because a different target would have given
   a different set of callers.

3. **Bring up the ORCA session**: `pb_session_open` (`pb_version` or
   `install_path` is required — there is no auto-pick; enumerate with
   `pb_discover_pb_install` and say which you chose),
   `pb_set_library_list`, `pb_set_current_application`. The last one
   may rewrite the `.pbw` as a side effect — **which is not worth
   mentioning.** That file also changes when somebody opens the
   workspace in the IDE and picks a different target, so a dirty `.pbw`
   is noise. Report it only if the `@targets` block gained or lost an
   entry; see
   [`pb-context-build`](../pb-context-build/SKILL.md) under *Session
   bring-up* for the one-line check.

   **On a `ws_objects` project you may skip the session and read the
   projection instead** — it is cheaper and a review writes nothing.
   Two conditions, and they are not optional:

   - Say you are doing it, and say what it costs. Without a session
     there is no `pb_object_query_hierarchy` and no
     `pb_object_query_reference`, so ancestors and callers come from
     reading text. That is workable inside one library and unreliable
     across a whole workspace; state which you did.
   - **Never claim the projection matches the `.pbl` because git is
     clean.** It does not follow, and least of all here: an unprotected
     workspace is one where `git status` stays clean *by construction*.
     Git compares the working tree to the index, and the `.pbl` is
     opaque to it. Only an ORCA export compared against the file settles
     it — the procedure is below. If that matters to a finding and you
     do not run it, write down that you assumed it.

   **This measurement needs an ORCA session**, so it happens after
   step 2 even though it belongs to this one. Do the reading here, bring
   the session up, then come back and measure before any other work.

   **Export to a scratch directory, never in place.**
   `pb_object_export_file` writes into the projection directory when you
   omit `dest_dir` — it refreshes the source of truth — so calling it to
   "check" the projection overwrites the file you were about to compare
   and then reports a match. Pass a `dest_dir` outside the project.

   **For this measurement, `pb_library_entry_export` is not a
   substitute**, even though it writes nothing. It returns the object
   *body*: no `$PBExportHeader$`, no `$PBExportComments$`, and — the
   part that surprises — **no binary section**. An entry hosting an OLE
   or ActiveX control serializes that control's state into a binary tail
   after the PowerScript, and on one measured `olecustomcontrol` that
   tail was 8 196 bytes, **40% of the file**. Compare the in-memory
   string against the projection and you get a mismatch of exactly that
   size, which is not drift and has nothing to do with line endings.

   The file-based export does include it: measured on an OLE-bearing
   window, `pb_object_export_file` produced a file **byte-identical** to
   the projection, binary tail and all, despite `export_include_binary`
   defaulting to `false` at the session level — the file-based tools set
   that option themselves. So the apply loop is safe on these entries;
   it is only the comparison shortcut that is not.

   Use `pb_library_entry_export` for **reading** an entry into the pack,
   where dropping an opaque blob of serialized ActiveX state is exactly
   what you want. Use `pb_object_export_file` with a scratch `dest_dir`
   for **comparing**.

4. **Note which reference tools you have.** If the `appeon_*` tools are
   absent, the Appeon doc index has not been built on this machine — see
   the `appeon-query` skill for the two commands that build it and the
   re-install that wires it up. You can still review: most findings rest
   on reading the code, not on the language reference. But a finding whose truth depends on
   a PowerScript semantic you could not verify must say so in its body
   and name the experiment that would settle it. **Do not assert
   language behaviour from memory inside a finding** — a wrong one costs
   the user more than a missing one, because it looks the same as a
   right one and arrives with a suggested edit attached.

   That leaves a real gap, so name what fills it. **The absence of the
   `appeon_*` tools does not mean the index is absent** — it is a
   SQLite file, and the server is a wrapper over it. If a `pb-ai-code`
   checkout is on this machine, query
   `docs/appeon-index/index.db` directly and you get the same answer,
   citable, for nothing; only if there is no checkout do you spend
   **two or three** web lookups on the semantics a finding actually
   turns on. The ladder and the SQL are in
   [`appeon-query`](../appeon-query/SKILL.md) under *What to do when the
   index isn't available* — follow it there rather than improvising,
   and budget the web tier: the handful of behaviours your findings
   depend on, not background reading.

   What you look up becomes `evidence: verified-in-docs` with the
   citation. What you cannot check becomes `evidence:
   unverified-semantics` with an `experiment:`. Both are honest; only
   the third option, asserting it, is not.

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
- **From free-form intent**: defer to Flavor D of
  [`pb-context-build`](../pb-context-build/SKILL.md) — search the
  projection's **content**, group the hits by library, propose. Do not
  guess a naming pattern and enumerate libraries: the domain is spelled
  in the codebase's language, not the user's, and that method returns a
  plausible near-miss instead of nothing, which is worse.

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

When you spot a recurring pattern the catalog does not have yet, write
it into the plan file's **`## Notes for the wiki`** section, in the shape
given under Step 3 — `page: pb-antipatterns/<slug>.md`, `section: new
page`. That is a candidate for a new catalog entry, and the note is how
it gets back to the repository that holds the catalog; see
[`docs/wiki-notes.md`](../../docs/wiki-notes.md).

### DataWindows are not PowerScript, and the list above does not apply

Everything above assumes the entry is PowerScript. A `.srd` is not: it
is the DataWindow DSL, the same syntax `Describe()` and `Modify()`
speak. None of the generic patterns match it, and a review that walks
that list over a DataWindow will correctly find nothing and incorrectly
conclude there was nothing to find.

This is not an edge case. Measured on one real 10-entry library:
**four DataWindows carried 77% of the source bytes** while the six
PowerScript entries carried 23%. Any `.pbl`-scope review runs into
this immediately, and a `.pbt`-scope one runs into it at scale.

What is worth reading in a `.srd`, in rough order of payoff:

- **`update=yes` on a key column.** In `table(column=(… name=id
  dbname="spedizione.id" update=yes updatewhereclause=yes ))` the
  primary key is marked updatable. That is almost never intended, and
  it silently widens what an `Update()` can rewrite.
- **The `updatewhereclause` strategy**, and whether the application
  agrees with it. `0` = key only, `1` = key and updatable columns,
  `2` = key and modified columns; they are three different concurrency
  contracts. Check it against what the framework does at runtime — one
  codebase's persistence base class issued
  `Modify("DataWindow.Table.UpdateWhere='1'")` on every store, which
  means the value saved in the `.srd` is decoration for those objects
  and load-bearing for every other DataWindow in the library.
- **Raw SQL versus `PBSELECT(...)`.** `retrieve="PBSELECT( VERSION(400)
  TABLE(NAME=…" is the graphical form, round-trippable in the painter.
  `retrieve="  SELECT spedizione.id, …"` is hand-written SQL that the
  painter can no longer edit graphically. Both are legitimate; a
  library containing both is worth a note, because the two are
  maintained by different people in different tools.
- **Retrieval arguments**: declared in `arguments=((name, type), …)`
  and referenced as `:name`. Look for arguments declared and never
  used, used and never declared, and — the one that matters —
  string arguments concatenated into the `retrieve=` text rather than
  passed as `:name`, which is the DataWindow spelling of SQL
  injection.
- **`release N;`** against the PB version the target actually builds
  with (`pb_target_info`). A DataWindow saved by a newer painter than
  the runtime loading it is a deployment failure that looks like a
  data problem.
- **Column count versus the select list**, and columns present in the
  table definition but on no band — leftovers that still get fetched.

Two practical notes. `.srd` sources are **large and repetitive**:
per-column font, colour and position attributes dominate, and none of
it is reviewable. Grep for the structural bits — `table(`, `retrieve=`,
`arguments=`, `update=`, `key=` — rather than reading top to bottom,
and say in `## Scope` that you did. And the size trap in
[`pb-context-build`](../pb-context-build/SKILL.md) bites hardest here:
a DataWindow's `object_size` is *smaller* than its source, so a budget
built from a directory listing under-counts exactly the entries that
cost the most.

Menus (`.srm`) are PowerScript and the generic list does apply, with
one addition: check that a menu item's `visible`/`enabled` state is
driven from one place. Structures (`.srs`) and queries (`.srq`) carry
no behaviour; note them in `## Scope` and move on.

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

### A second sweep, when it is worth it

Because one pass misses things, offer another before handing off — not
a re-run, a **sweep for what the first pass did not see**:

> "That is N findings. A single pass typically misses a third of what
> is there. Want a second sweep? I re-read the same code with these N
> already known, hunting only for what they do not cover. It costs
> roughly what the first pass cost."

Unattended, do not ask — run the sweeps (see *Running unattended*).

If the user accepts, list the existing findings as known, review again,
and **append** the new ones to the same plan file with fresh ids —
never renumber, the CHANGELOG already links to the old anchors. Repeat
until a sweep adds nothing, and record in `## Scope` how many sweeps ran
and what each added. A sweep that finds nothing is the only evidence of
coverage this flow can honestly produce.

### Consumers you cannot see

Caller discovery, even when enabled, inverts the **configured library
list** — it cannot see a project that consumes this one. For a library
with a public surface (global functions wrapping an object, a `.pbd`
other products link, an API the project's own docs describe as shared)
that is most of the risk, and it is invisible from here.

So: if the target has such a surface, or `AGENTS.md` / `CLAUDE.md` /
the README names external consumers, open a **`## Consumers outside
this workspace`** section listing what you could not check. And **do
not assign a priority above `medium` to a public-contract change on
that basis alone** — the priority would be a guess dressed as a
judgement. Say what would settle it: usually one question to a human
who knows who links this library.

## Step 3 — Emit the plan file and the CHANGELOG entry

Two artefacts on disk, one user-facing summary.

### Plan file

Path:
`.pb-review/<scope_category>-<context_slug>-<YYYY-MM-DD-HHMM>.md`
(values from Step 0). Create `.pb-review/` if it does not exist. On
first creation, mention it: "I created `.pb-review/` in the working
directory. Want a `.gitignore` suggestion for it?"

**Always here, even when the project already keeps its own plan or
backlog document.** Many do, with their own numbering. Do not ask, and
do not merge into it: `pb-apply-plan` parses *this* file — the YAML
front-matter, the `depends_on` graph, the `status:` fields it rewrites
as it goes — and findings folded into a hand-maintained document have
none of that, so the handoff cannot run. The two are different
artefacts: this one is a machine-readable snapshot of one review, that
one is a curated backlog.

Connect them instead of merging them. Add **one line** pointing at this
file, and after the apply loop promote what actually landed into the
project's own numbering. Not before: a curated backlog should not fill
up with findings that may yet be rejected.

#### Never link the plan file into the installed bundle

**Cite the catalog by slug and public URL, never by relative path.**

```markdown
See the antipattern catalog entry `pb-antipatterns/isnull-on-numeric`
(<https://github.com/restoresrl/pb-ai-code/blob/main/docs/pb-antipatterns/isnull-on-numeric.md>).
```

What you must **not** write is a Markdown link that points at the
installed knowledge base — `../<bundle-dir>/pb-ai-code-docs/pb-antipatterns/<slug>.md`,
where `<bundle-dir>` is whatever this harness uses: `.claude/`,
`.agent/`, or whatever `-SkillsDir` was given. That is where the file
genuinely sits on your machine, and it is exactly the trap. The rule is
about the *installed bundle*, not about any one assistant, so do not
read it as applying only to the directory name you happen to see.

The reason is that two correct decisions collide here. The plan file is
work product: it goes into the reviewed project's repository, because
the promise that another agent can resume it later only holds if it
reaches the repository. The installed bundle is *not* work product: it
is harness state, reinstalled from `pb-ai-code` whenever it changes, and
a PB project is meant to commit nothing agentic at all.

So a relative link from `.pb-review/` into the bundle resolves on the
machine that wrote it and is dead for everybody else — the colleague who
pulls the branch, the reviewer reading it on the web, the agent that
picks the plan up on another checkout. It fails in the worst way, too:
silently, and only for the reader who was not there. And it fails
whether or not the bundle directory happens to be gitignored: if it is,
the target is absent; if it is not, the target is a snapshot of a
knowledge base that has since moved on.

The same rule covers `docs/wiki-notes.md` and the `pb-source-format`
pages. Inside a skill file, relative links are right and the installer
rewrites them. Inside the plan file, they are not: write the slug so a
human can find it, and the URL so a machine can.

Which document, and where: the backlog or plan document found in
Pre-flight 0 — not `CHANGELOG.md`, which already gets its own entry.
Put it under a references or index heading if one exists, otherwise at
the end. If Pre-flight 0 found no such document, there is nothing to
link and you write only the two artefacts.

The format is YAML front-matter per finding, **plus** a generated
summary table at the top.

#### Header block

```markdown
# <scope_category>: <context_slug>

- **scope**: <scope_category>
- **context**: <context_slug>
- **target**: <entry triples / .pbt / .pbl reviewed>
- **workspace**: mode=<ws_objects|pbl_only>, encoding=<export_encode> (orca=<orca_encoding>, observed=<observed_encoding>, from=<encoding_source>), outside_source_tree=<true|false, for the library queried>, source_protection=<…>, sources_diffable=<…>
- **library**: <absolute path of the .pbl holding the target>
- **resolved target**: <the .pbt whose LibList contains it> — applib=<…>, liblist=<…>
- **generated**: <YYYY-MM-DD HH:MM>
- **source skill**: pb-review @ <pb-ai-code version — see below>
- **version bump proposed**: <in the project's own scheme — see Step 3>

## Understanding

<the semantic summary from Step 2a, verbatim>

## Scope

<entries reviewed, total source lines, budget summary from
pb-context-build>

## Skipped

<anything pruned that the user should know about>

## Already recorded elsewhere

<findings that Pre-flight 0 showed are already in the project's own
plan, backlog or changelog — each with that document's identifier, not
a new fix id. "I looked at these and agree they are known" is one of
the most useful things this report says.>

## Consumers outside this workspace

<omit unless the target has a public surface. See "Consumers you cannot see".>

## Notes for the wiki

<omit when empty. Anything this review learned that the knowledge base
does not document — a `.sr*` layout the format wiki has not seen, a
recurring hazard the antipattern catalog lacks. One entry per note, in
the shape below; see docs/wiki-notes.md for what happens to them.>
```

### The shape of a wiki note

The knowledge base lives in the `pb-ai-code` repository, and what you
have in front of you is a **snapshot** — the next install overwrites it,
so an edit made there is lost. A note in the plan file is how a
discovery survives the trip back. It is collected from here, so the
fields are not decoration: they are what makes it collectable.

```markdown
### note-01 — <one line: entry type, and what is different>

- **page**: `pb-source-format/userobject.md` | `pb-antipatterns/<slug>.md`
- **section**: `Variants observed` | `Canonical form` | `Open questions`
  | `new page`
- **observed-against**: `pb-ai-code @ <version>` — from the installer's
  marker file, `_installed-from-pb-ai-code.txt`, inside whatever
  directory this harness installed into (`.claude/`, `.agent/`, …), the
  `# Version:` line
- **evidence**: `compiled clean` (and how — the tool call and its
  result) | `observed only`
- **repro**: the smallest snippet that shows it
- **why it differs**: one line

<optional prose, if a line is not enough>
```

Two fields carry the weight. **`observed-against`** says which version of
the wiki this was new *against*, so whoever collects it can tell a
discovery from something already documented since. A marker written by
the old PowerShell installer carries no `# Version:` line; there, the
token after `pb-ai-code @` on the `# Source:` line is a short commit sha,
and that is the answer. **`evidence`** is the gate: `compiled clean`
means the entry went through `pb_object_import_file` with `errors: []`,
so the claim is a fact about PowerBuilder rather than an impression. A
note marked `observed only` is still worth writing — it just does not get
applied without someone reproducing it.

If the discovery arrives during the apply loop rather than the review —
which is usual, since that is where things compile — write it into the
same plan file. That is what the section is for.

`pb_workspace_info` returns **no** field called `encoding`: it returns
`export_encode`, `orca_encoding`, `observed_encoding` and
`encoding_source`, and the interesting case is when the first and third
disagree — the workspace is already inconsistent and the IDE will
rewrite those files on its next export. Record all four, and raise a
finding on a mismatch.

`outside_source_tree` is a **boolean about the one library you asked
about**, not a list. To speak about several libraries, call the tool
once per library.

The **library** and **resolved target** lines exist because an entry
triple does not identify a file: two libraries in one workspace can
share a basename, and `pbgettext.pbl` under `src/` and under `test/`
is a realistic collision. `pb-apply-plan` needs the absolute path, and
it needs to know which target's library list this review assumed.

The **source skill** line is the reproducibility record: which version of
the kit produced this plan. Read the version from the marker the
installer leaves next to the skills — `_installed-from-pb-ai-code.txt`,
the `# Version:` line; the `# Source:` line beside it adds the origin and
the commit, and on a marker too old to have a `# Version:` line it is
where the version lives, as the token after `pb-ai-code @`. Do not write
"n/d" because the skills are not tracked in the consumer's git: they are
not supposed to be, and the marker exists precisely so the version
survives that. If the marker is genuinely missing, say so and name the
directory you looked in.

#### Summary table

```markdown
## Queue

| id     | entry                              | kind     | depends_on | evidence | status  |
|--------|------------------------------------|----------|------------|------------|---------|
| fix-01 | core.pbl::n_logger:userobject      | bug-risk | —          | code-read | pending |
| fix-02 | core.pbl::n_log_target:userobject  | refactor | fix-01     | code-read | pending |

The `entry` column is the **same string** as the finding's `entry:`
field — `lib::name:type`, no spaces, type spelled in full. One spelling
so the table can be regenerated from the YAML and compared to it.
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
depends_on_confidence: parsed
evidence: code-read
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

**Applied**: *(written by `pb-apply-plan`, absent until then. What
actually landed, when it differs from **Suggested fix** — which stays
as written, because the difference between what was proposed and what
was needed is worth keeping.)*
````

Required YAML fields: `id`, `entry`, `kind` (bug-risk | refactor |
style | …), `priority` (high | medium | low — **severity if it happens, not
likelihood**: an infinite loop reachable only from an unusual input is
`high`, and the rarity belongs in the body. Two people ranking the same
finding must land on the same value, which they cannot do while the axis
is left to taste), `depends_on` (list of
`id`), `depends_on_confidence` (parsed | user-augmented | manual),
`evidence` (code-read | verified-in-docs | unverified-semantics),
`status` (pending | applied | skipped | partial — a review always writes
`pending`; the rest are written by `pb-apply-plan` as it runs).

**`depends_on_confidence` is about the dependency graph, not about the
finding.** It says where `depends_on` came from, and in a review that
ran normally with no hand edits it is `parsed` on every single finding,
which is why it must not be mistaken for a judgement about the finding
itself. (It was called `confidence` and was read that way.)

**`evidence` is the judgement about the finding**, and it is the field
`pb-apply-plan` gates on:

- `code-read` — established by reading the code in front of you.
- `verified-in-docs` — rests on a documented PowerScript behaviour that
  you looked up and can cite.
- `unverified-semantics` — rests on a language behaviour you could not
  check. **Requires an `experiment:` field**: one or two sentences
  naming the concrete test that would settle it. `pb-apply-plan` will
  not apply one of these without the user saying so explicitly.

A finding whose premise was never checked and whose check was never
named does not belong in the queue at all.

Optional YAML fields:

- `library_path` — the absolute path of the `.pbl`, **required whenever
  the queue spans more than one library**. `entry:` carries a bare
  basename and two libraries in one workspace can share one, so without
  this `pb-apply-plan` cannot tell which file a finding means.
- `outside_source_tree: true` — set it when the finding lands in a
  vendored library. The header's boolean answers for one library; the
  decision to skip is per finding, and `pb-apply-plan` gates on it.
- `experiment` — **required when `evidence: unverified-semantics`**. The
  test that would settle the premise, concretely enough to run.
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

Three conventions, because these bullets join a file somebody else
writes in:

- **Language.** An artefact appended to an existing document follows
  *that document's* language, not the conversation's. The plan file is
  new, so it follows the conversation. A project whose `CHANGELOG.md`
  is in Italian gets Italian bullets even when the review was conducted
  in English.
- **Bullet style.** The `- [ ]` checkbox is **structural, not
  cosmetic**: `pb-apply-plan` ticks those boxes as fixes land, so a
  bullet without one is a bullet nothing can update. Keep it even when
  the section's existing entries are prose. Match the house style in
  *wording, length and reference markers* — that is what "match the
  file you are writing into" means here.
- **Placeholders.** An empty subsection often holds a placeholder
  ("*(no entries yet)*"). Remove it from the section you write into.
  The append-only rule protects released versions and entries a
  previous run wrote; a placeholder is neither.

Look for the project's own scheme **before** falling back to semver, in
this order: a project-local versioning skill; a version file
(`*.version`, `.version`, `package.json`, `*.pbg`); a statement in
`AGENTS.md` / `CLAUDE.md` about how versions are decided. A real PB
project kept `src/<app>.version` with `major`/`minor`/`patch`/`build`
and a `major` that tracks the **PowerBuilder release**, not API
compatibility — under which "major bump" has no semver meaning and
proposing one is simply wrong. If the scheme is not semver, say which
component you are proposing to move and why, and do not translate it
into semver words.



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
  per-fix confirmation. Three writes are review output rather than
  source modification, and they are the only ones: the plan file, the
  `CHANGELOG.md` entry, and — when the project keeps its own plan or
  backlog — the single pointer line into it described in Step 3. Say
  in the summary that you touched that third file; it is the one the
  user did not ask for.
- **No automated test execution.** If a fix conceptually needs a test,
  suggest it as a follow-up note in the finding; do not generate a test
  runner.
- **Honest about cost.** If the budget was hit early and the review is
  partial, say so loudly at the top of the plan file, in `## Scope`.
  Partial reviews are valuable; pretending to be exhaustive is not.
- **Never call a review complete.** Not "review completa", not
  "exhaustive", not "all findings". One pass does not find everything,
  and this is measured, not cautious: two passes over the same object,
  same scope, same model produced 23 distinct findings between them and
  neither pass saw more than 83% of the union — while both called
  themselves complete. Say what you examined and how, and leave the
  reader to judge coverage. `## Scope` describes work done, not ground
  covered.

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
