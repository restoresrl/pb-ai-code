# `pb-ai-code` — Agentic dev kit for PowerBuilder

## Context

PowerBuilder is a closed-world IDE: a coding agent can read and edit the
text sources PB exports (`.sra`/`.srf`/`.srw`/`.sru`/...), but it cannot
compile, validate, or build them, nor can it autonomously design, test,
or debug PowerBuilder code without external help.

The sibling project [`pb-orca-mcp`](https://github.com/restoresrl/pb-orca-mcp) closes the
infrastructure gap: it exposes PowerBuilder's ORCA API (`pborc.dll`) as
MCP tools so an agent can act on `.pbl` libraries — create, modify,
compile, build EXE/PBD, navigate inheritance hierarchies and
cross-references.

**`pb-ai-code` is the layer above it**: the knowledge, skills, and
orchestration needed to actually *do* agentic PB development — design,
write, test, and debug — using `pb-orca-mcp` as the foundation tool.

## Realignment 2026-07-29 — decoupling, and agent-agnostic for real

The sections below are dated design records; read them as history. This
section is what is true now. Three things changed, none of them a change
of direction.

**1. The `pb-orca-mcp` surface moved, and the skills followed.** The
server was reworked in June-July 2026: `pb_edit_and_import` — the
single-call write helper this kit was built around — no longer exists,
and the edit loop is now two calls on a file:

```text
pb_object_export_file(lib, entry, type)   -> ORCA writes the .sr*
edit the file with ordinary text tools
pb_object_import_file(path, lib)          -> compile + sync in one call
```

The consequences went beyond a rename. **The text projection is updated
in the same call that writes the `.pbl`**, so every "remember to
propagate to `ws_objects/`" step and every "commit both files" checklist
was deleted rather than rewritten — the skills got shorter. The caller
no longer chooses an encoding either: ORCA writes the file, byte
identical to the IDE's. Three new tools are now load-bearing:
`pb_workspace_info` (project shape, encoding, git, and
`outside_source_tree` — with no ORCA session and no PB install), which
is the first call of every flow; `pb_library_export_sources` (a whole
library to disk in one call), which turns "who calls this" from 1000
ORCA queries into a grep; and the `pb-orca-mcp check <target>` CLI as
the diagnostic prerequisite when bring-up fails.

Two beliefs baked into the old docs were also wrong and are now
corrected: `$PBExportHeader$` is **not** required on import (ORCA
ignores header lines; the `C0114` that suggested otherwise came from a
size argument counted in characters instead of bytes), and the binary
tail some `.sr*` files carry comes **only** from OLE/ActiveX controls,
not from DataWindow pictures.

**2. The formatter is a separate project.** The 2026-05-22 design put
the PowerScript normalizer inside `pb-orca-mcp`, reached through a
`format="auto"` parameter on the write tool, on a choke-point argument.
That lost to a stronger one: the ORCA bridge should contain no
PowerScript knowledge at all. The engine now lives in
[`pb-format`](https://github.com/restoresrl/pb-format) — a standalone
CLI and library, ORCA-independent, working on files on disk on any OS —
and it plugs into the edit loop as one optional step between the edit
and the import. It is genuinely optional: with no `.pb-format.toml` in
the tree, or no tool installed, the kit does not format and nothing else
changes.

**3. Agent-agnostic became structural, not aspirational.** "Agent
agnostic by design" was in the README from day one while every artefact
lived under `.claude/`, the MCP config pointed at a `.venv-x86` inside a
sibling checkout, and eleven files linked across repositories by
relative path. All three made the project unusable by anyone whose
directory layout differed from ours. Now:

- Canonical, committed: `skills/<name>/SKILL.md` (Agent Skills format),
  `commands/<name>.md` (thin wrappers that delegate to the skill of the
  same name), `harness/<harness>/` (per-assistant config).
- Generated and gitignored: `.claude/` and anything else an install
  produces. `scripts/install-skills.ps1` materializes the canonical
  files into whatever directory an assistant reads — including into this
  repository itself — with a marker file recording the source commit.
- `pb-orca-mcp` is consumed as any other user would consume it:
  `uvx --from git+https://github.com/restoresrl/pb-orca-mcp`. No
  editable install, no sibling-directory assumption.
- Cross-repository links are URLs. Interactive prompts inside skills are
  written in neutral English, with the standing instruction to speak the
  user's language.
- The `/pb-review` flow moved out of the command file into
  `skills/pb-review/SKILL.md`, so an assistant with no slash commands
  and no skill discovery can still be pointed at the file and follow it.
- [`docs/install.md`](docs/install.md) is new: the per-client setup, and
  what to do when a client has neither commands nor discovery.

**Still open after this pass**: end-to-end validation of `/pb-review`
against a real target (the point of the whole exercise, and the next
thing to do); `pb-impact-analysis`, never started; `pb-format` has no
remote and is not published, so the install instructions for it name a
repository that does not exist yet.

## Re-prioritization 2026-05-19 — refactoring-first

The original 2026-05-14 design framed `pb-ai-code` as a balanced
four-pillar dev kit: design, coding, testing, debugging. After a week
of dogfooding (Pillar 1 scaffolding closed, Pillar 2 testing
brainstorming) the primary use case has been sharpened:

> **`pb-ai-code` is, first and foremost, a code-review assistant for
> refactoring legacy PowerBuilder codebases.** Greenfield PB development
> is rare; the realistic audience is people maintaining decades-old
> monolithic PB applications — hundreds to thousands of objects across
> dozens of PBLs, ported forward since the 1990s — who
> need to read, understand, refactor, bug-fix, and extend existing
> code.

Implications for the four pillars:

| Pillar | Status under refactoring-first lens |
|---|---|
| 1. Design — *understand existing architecture* | **Primary**. Was secondary in the 2026-05-14 framing. Now the entry point of every workflow. |
| 1. Design — *scaffold new entries* | **Demoted to on-demand**. Refactoring rarely creates new top-level objects. The 6-entry-type MVP done 2026-05-19 is enough; the 3 residual types (`application`, `query`, `project`) are not blocking. |
| 1. Design — *idiomatic patterns* | **Promoted, but bottom-up**. The Layer 2 wiki grows from real review sessions, not as an upfront cookbook. |
| 2. Coding | **Foundation, unchanged**. Edit + propagate + compile-error loop is already covered by `pb-orca-mcp` (`pb-workflow` skill + ORCA primitives). |
| 3. Testing | **Deferred**. PB testing (both unit and UAT) is structurally hard. The pbunit22 architectural work (SPEC.md, 2026-05-19) remains valid as a future direction but is not driving immediate development. |
| 4. Debugging — *impact analysis* | **Promoted**. Refactoring without blast-radius analysis is unsafe; `pb_object_query_reference` orchestration becomes a Tier-1 skill. |
| 4. Debugging — *runtime trace logging* | **Deferred**. Useful for live debugging but not for the static-review primary loop. |

**Three-tier priority for the new direction**:

- **Tier 1** (active development): `pb-context-build` skill +
  `/pb-review` slash command (report-only v1) + `pb-impact-analysis`
  skill. These three orchestrate existing ORCA primitives into the
  refactoring loop.
- **Tier 2** (grows alongside Tier 1): Layer 2 wiki expansion on
  real findings; the **`pb-format` skill**, driving the standalone
  [`pb-format`](https://github.com/restoresrl/pb-format) tool, with
  config via `.pb-format.toml`. Optional `pb-style-guide` skill folded
  into `pb-format` and
  `docs/pb-source-format/style-conventions.md`.
- **Tier 3** (on-demand or deferred): scaffolding completion (3
  residual entry types); Pillar 2 testing; runtime trace logging;
  upfront pattern cookbook.

The sections below (Vision, Composition, Sequencing) keep the
original four-pillar conceptual framework as reference, but the
current direction is what this section spells out. Where the older
content lists work that is now Tier 3, the deferred status is called
out inline.

## Vision: the four pillars of agentic PB development

> **Note**: this section describes the *conceptual framework* of
> four pillars. The current sequencing and weight of each pillar is
> set by the [Re-prioritization 2026-05-19](#re-prioritization-2026-05-19--refactoring-first)
> section above. Read both together.

The goal is to let a coding agent — any client, any model; see the
[2026-07-29 realignment](#realignment-2026-07-29--decoupling-and-agent-agnostic-for-real)
for what that took — handle the full development loop on a PowerBuilder
project:

1. **Design** — read existing architecture, follow PB-idiomatic
   patterns, scaffold new objects (windows, userobjects, datawindows,
   functions, menus) from minimal templates.
2. **Coding** — write valid PowerScript that respects PB semantics,
   propagate edits to `.pbl` with proper encoding (the workspace
   `DefaultExportEncode` — UTF-8 BOM, UTF-16BOM, or ANSI — plus CRLF
   and `$PBExportHeader$` / `$PBExportComments$`), iterate on compile
   errors.
3. **Testing** — write tests, compile a test runner, execute it,
   capture and parse structured results, correlate failures back to
   source entries.
4. **Debugging** — read compile errors (already covered by the MCP),
   read failing tests (testing layer), parse runtime traces/logs (PB
   has no DAP, so debugging is post-mortem), do impact analysis before
   changing code (`pb_object_query_reference`).

### What pb-orca-mcp already covers vs what `pb-ai-code` must add

| Pillar | Covered by `pb-orca-mcp` | Must be built in `pb-ai-code` |
|---|---|---|
| **Design** — read existing architecture | `pb_object_query_hierarchy`, `pb_object_query_reference` | — |
| **Design** — know which PB patterns to use | — | Style/architecture-guide skill + Appeon docs context |
| **Design** — scaffold new entries (PBL, app, window, userobject, …) | `pb_library_create`, `pb_compile_entry_import` with minimal syntax (Application has a known catch-22) | Skill carrying the correct minimal template per `entry_type` |
| **Coding** — know PowerScript syntax + PB runtime API | — | **Appeon documentation ingested** (priority) |
| **Coding** — edit `.sr*` respecting encoding | Entirely covered: ORCA writes the file (`pb_object_export_file`) and reads it back (`pb_object_import_file`), keeping the text projection in step in the same call | Nothing: the caller never picks an encoding |
| **Coding** — propagate to `.pbl` and read errors | `pb_compile_entry_import{,_list}`, `pb_scc_refresh_target`, `pb_get_last_compile_errors` | — |
| **Testing** — decide/write tests | — | Skill that knows the chosen test framework(s) — agnostic with adapters |
| **Testing** — compile the test runner | `pb_executable_create` | — |
| **Testing** — execute runner + parse output | — | **New tool/skill**: launch compiled EXE, collect structured output, correlate test → entry |
| **Debugging** — compile-time errors | `pb_get_last_compile_errors` | — |
| **Debugging** — failing tests | — | Falls inside Testing |
| **Debugging** — runtime errors / crashes | — | **New**: structured logging pattern (PB has no DAP) + parser the agent can read |
| **Debugging** — impact analysis | `pb_object_query_reference` | Skill that orchestrates the pattern |

## Relationship with `pb-orca-mcp`

- **Required dependency**: `pb-ai-code` does not duplicate any ORCA
  primitive. Every action on a `.pbl` goes through `pb-orca-mcp` tools.
- **Consumption model**: `pb-orca-mcp` is consumed as an **MCP
  server, from its GitHub repository** (`uvx --from
  git+https://github.com/restoresrl/pb-orca-mcp`), exactly as any other
  user would. It is not a Python dependency of this project, and no
  longer an editable install of a local checkout — that coupling was
  removed 2026-07-29 because it made `pb-ai-code` unusable by anyone
  whose directory layout differed from ours.
- **Audience overlap, but distinct scope**: both repos target anyone
  who develops PB. `pb-orca-mcp` is the engine; `pb-ai-code` is the
  workflow + knowledge + orchestration. Either can be adopted
  independently — you can use the MCP alone with your own prompts, or
  use the dev kit if you want the ready-made experience.

## Composition

### Current focus under refactoring-first (2026-05-19)

Active components driving the next slices of work:

- **`pb-context-build` skill** (new, Tier 1) — orchestrates ORCA
  primitives (`pb_target_info`, `pb_library_directory`,
  `pb_object_query_hierarchy`, `pb_object_query_reference`,
  `pb_library_entry_export`) to assemble a scoped context pack from a
  monolithic PB workspace, respecting a token / depth budget. v1: only
  incoming references (callers); callees via source parsing deferred.
- **`/pb-review` slash command** (new, Tier 1) — two-phase
  refactoring loop. Phase A: invoke `pb-context-build`, run review,
  emit structured report (bug-risk, refactoring-opportunities,
  style-issues). Phase B: confirmed edits applied via `pb-workflow`
  (sibling) → `pb_compile_entry_import` → `pb_get_last_compile_errors`.
  v1 = Phase A only (report-only).
- **`pb-impact-analysis` skill** (new, Tier 1) — pre-flight
  blast-radius report for any non-trivial refactor, built on
  `pb_object_query_reference` with `ref_type` (`simple` vs `open`)
  interpretation.
- **`pb-scaffold` skill + Layer 2 wiki** (existing, kept) — invariant
  for now. The wiki grows on-encounter during real review sessions
  (Tier 2). The 3 residual scaffold entry types are Tier 3, on-demand.
- **`pb-format` skill + `/pb-format` slash command + Layer 2 wiki
  page `style-conventions.md`** (Tier 2). Defines the four style
  invariants (indent, line endings, keyword case, operator spacing),
  the `.pb-format.toml` config contract, and the boundaries with
  `pb-src-format` (structure vs style) and `pb-scaffold` (templates
  emit a neutral style; the formatter normalizes afterwards). The
  engine is the standalone
  [`pb-format`](https://github.com/restoresrl/pb-format) tool: a
  separate repository, optional, ORCA-independent.
- **`appeon-query` skill + `pb-appeon-index` MCP** (existing, kept) —
  the `/pb-review` flow calls into it for syntax / runtime API
  cross-reference.

### Historical full composition (as designed 2026-05-14)

The list below is the original full-scope composition. Items not in
the Current focus block above are either covered by what is now in
Tier 2/3 of the [re-prioritization](#re-prioritization-2026-05-19--refactoring-first)
section, or are deferred. Kept here as reference.

The repo contains a mix of artifacts:

1. **Skills** (`skills/<name>/SKILL.md`, Agent Skills format) — one
   skill per workflow that needs the agent to follow a specific
   pattern:
   - Scaffolding skills (new application / window / userobject / …)
   - Style and architecture guide for idiomatic PowerScript
   - Test orchestration skill (writing tests + invoking the runner)
   - Debugging skills (failing test loop, runtime trace parsing,
     impact analysis)

2. **Knowledge base, organized in three layers** (revised
   2026-05-15; supersedes the earlier "hybrid mirror + WebFetch"
   plan):

   - **Layer 1 — PowerScript language and runtime API (Appeon docs)**:
     a custom Python tool (`tools/pb-appeon-index/`) scrapes
     `docs.appeon.com` into a local SQLite FTS5 database and serves
     it via an MCP server exposing `appeon_search`, `appeon_get`,
     `appeon_list_topics`, `appeon_list_versions`. Multi-version
     by design — schema has a `version` column, a TOML config
     enumerates the PB versions to index, and the `update` command
     is idempotent and incremental (conditional `If-None-Match` /
     `If-Modified-Since` skips unchanged pages). The earlier
     attempt with `cli-printing-press` was abandoned 2026-05-15
     after the POC confirmed it's tuned for REST API docs, not
     language-reference doc-sites — see
     [the Appeon index README](docs/appeon-index/README.md)
     for the replacement design and the
     [`appeon-query`](skills/appeon-query/SKILL.md) skill
     for agent-side usage.

   - **Layer 2 — `.sr*` source-file format (reverse-engineered)**:
     a Karpathy-style ["LLM Wiki"](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
     under `docs/pb-source-format/` — Markdown pages, one per
     entry type (`.sra/.srw/.sru/.srf/.srd/.srm/.srs/.srq/.srj`)
     plus an `encoding.md` seed page and a `patterns/` folder for
     cross-cutting blocks. Pre-populated by a Python tool
     (`tools/pb-source-analyzer/`) that ingests a real `.sr*` tree
     privately, anonymizes project-specific identifiers, and emits
     statistics merged into a dedicated section of each page. The
     wiki then grows incrementally during real agent work: when
     the agent encounters a variant the wiki has not documented,
     it appends a new entry. Skill `pb-src-format` triggers this
     behavior.

   - **Layer 3 — codebase-specific patterns and conventions
     (project-private)**: deferred. The vendor-neutral repo cannot
     mirror a specific codebase. When this layer is added, it
     will live outside the public repo (per-workspace
     `.knowledge/`, gitignored) and use semantic RAG or LLM Wiki
     depending on requirements seen during dogfooding.

3. **Test orchestration — framework-agnostic with adapters**:
   - A common interface "run test suite, return structured results"
     (suite name → list of tests → outcome + error per test).
   - Adapters per framework: probably **pbunit first** (the one we
     have ground truth on), then others. The first
     adapter informs the abstraction; we do not freeze the interface
     until we have at least one working adapter.
   - The MCP only provides the build primitive (`pb_executable_create`);
     `pb-ai-code` carries the "how to invoke the produced EXE and
     interpret its output" knowledge.

4. **Structured logging pattern for runtime debugging**:
   - Since PB has no DAP, the only realistic "debug" path for runtime
     issues is post-mortem analysis of logs/traces. The dev kit
     proposes a structured logging convention (JSON-lines is the
     candidate; format TBD) and ships a parser the agent can call to
     correlate trace entries with source files.
   - A logging NVO from a private framework is the candidate reusable
     **pattern** (the pattern, never the object: this repo is public
     and vendor-neutral).

5. **Slash commands** (`commands/<name>.md`) — thin entry points that
   delegate to the skill of the same name. Candidates:
   - `/pb-new-userobject <name>` (scaffolding)
   - `/pb-run-tests` (test orchestration)
   - `/pb-trace <log-file>` (post-mortem)
   - `/pb-impact <object>` (cross-reference audit)

6. **Tooling code** (only if necessary) — small Python helpers for
   parsing trace logs, computing test-result diffs, etc. Whether
   `pb-ai-code` becomes a Python package or stays as a "skills + docs"
   repo with no executable surface is a residual decision (see below).

## Decisions taken in the review session 2026-05-14

| Aspect | Choice | Rationale |
|---|---|---|
| Repo location | Public, separate from `pb-orca-mcp` | International audience; no vendor-internal references; clean LICENSE story for Appeon docs mirror |
| Project name | **`pb-ai-code`** | Self-explanatory ("AI coding assistant for PB"); pairs naturally with `pb-orca-mcp` (engine + experience); agent-agnostic in name (no "claude" in the slug) |
| Appeon docs | Hybrid: core pages mirrored, rest via WebFetch | Balances offline friendliness, context cost, and freshness — **superseded 2026-05-15, see below** |
| Test framework | Agnostic via adapters; first adapter pbunit | The audience is broader than any one shop; the first adapter is the one we have ground truth on |
| Debugging scope | Four levels: compile-time (already MCP) + failing-test + runtime trace/log parsing + impact analysis | All four are realistic for PB given no DAP exists |
| Sequencing relative to `pb-orca-mcp` PyPI publish | **Internal dogfooding first** — both repos private; active dev on `pb-ai-code` can start whenever Carlo wants, using an editable install of the local sibling. PyPI versioning + public flip when dogfooding confirms stability - **the editable-install part superseded 2026-07-29, see the realignment section** | Decouples scope readiness from external release pressure |

### Knowledge architecture revision (2026-05-15)

The "Appeon docs ingested in hybrid mode" decision above is replaced
by a three-layer knowledge architecture, because a single layer
conflated three distinct needs:

| Layer | Knowledge | Tech | Public in repo? |
|---|---|---|---|
| 1 | PowerScript language + runtime API (docs Appeon) | custom Python: `tools/pb-appeon-index/` (scrape → SQLite FTS5 → MCP server) | yes (code + config + skill; DB rebuilt locally per dev) |
| 2 | `.sr*` source-file format (reverse-engineered) | Karpathy-style LLM Wiki in `docs/pb-source-format/`, pre-populated by `tools/pb-source-analyzer/` | yes |
| 3 | Codebase-specific patterns / style | LLM Wiki or semantic RAG (TBD) | no — per-workspace, gitignored |

Rationales: Layer 1 → FTS suffices for reference-style queries on
already-curated docs; cli-printing-press generates the MCP for free.
Layer 2 → no upstream documentation exists; the wiki has to be built
ex nihilo and grows incrementally. Layer 3 → vendor-neutral repo
constraint plus genuine project-specific knowledge, so it lives
outside.

## Residual decisions (to settle before active development starts)

1. ~~Which Appeon pages go into the static mirror~~ — **closed
   2026-05-15**: superseded by the layer-1 design. There is no
   Markdown mirror; `cli-printing-press` ingests the whole
   relevant subtree of `docs.appeon.com/pb2022` into a local
   SQLite+FTS DB and exposes search via an MCP server. The
   recipe (`docs/appeon-cli/recipe.json`) lists exactly which
   URLs are ingested — start with `powerscript_reference` and
   expand as gaps surface during dogfooding. The Appeon
   license / attribution check remains a blocker for
   *distributing* the generated DB, not for the design.
2. **Structured logging format for runtime trace** — JSON-lines is
   the leading candidate. The format must be (a) easy to emit from
   PowerScript (no JSON-stringify dependency), (b) easy to parse
   line-by-line in a Python tool, (c) self-describing enough for the
   agent to correlate events with source. A structured-logging NVO from
   a private framework is the candidate inspiration.
3. **First testing adapter** — **pbunit-first** is concrete and
   leverages knowledge we already have, but ties the abstraction to
   one framework. The alternative — design the abstraction agnostic
   from day one — produces upfront work without proof it's the right
   shape. Default: pbunit-first, extract the abstraction *from* it
   once it works.
4. **Distribution model for `pb-ai-code`** — **settled 2026-07-29**:
   git-clone plus `scripts/install-skills.ps1`, which materializes
   `skills/` + `commands/` + `harness/<harness>/` into whatever
   directory the assistant reads, in the target project or in this repo
   itself. PyPI would still make sense for the two Python tools
   (`pb-source-analyzer`, `pb-appeon-index`) but is not the delivery
   mechanism for the skills.
5. **Name availability verification** — check that
   `github.com/restoresrl/pb-ai-code` is free (very likely) and, if
   the distribution model ends up using PyPI, that `pb-ai-code` is
   free on PyPI too.

## Sequencing

**Current phase — internal dogfooding (both repos private)**: the
`pb-orca-mcp` foundation is usable straight from its GitHub repository
via `uvx`. The goal is to drive real work through this stack and
discover the gaps before any public release pressure.

**Next slice (2026-05-19, refactoring-first re-prioritization)**:

1. Write `pb-context-build` skill.
2. Write the `pb-review` flow, Phase A only — report-only.
3. Validate end-to-end on a small real target. Measure context-build
   cost, signal/noise of findings, scoping efficacy.
4. Iterate on `pb-context-build` heuristics based on real findings,
   *not* upfront on hypotheses.
5. Add `pb-impact-analysis` skill once `/pb-review` has shaped the
   surface area expectations.
6. Phase B of `/pb-review` (edit-loop) after v1 is stable on real
   targets.

Tier 2 work (Layer 2 wiki growth, style-guide skill) follows the
first slice on-encounter. Tier 3 (testing, runtime trace, scaffold
completion) remains deferred.

**Formatter slice (started 2026-05-22, Tier 2)**:

1. ✅ Wiki page `docs/pb-source-format/style-conventions.md` defining
   the four invariants.
2. ✅ Skill `skills/pb-format/` + command `commands/pb-format.md`.
3. ✅ Cross-links in `pb-src-format`, `pb-scaffold`, `pb-apply-plan`.
4. ✅ The engine, shipped as the standalone
   [`pb-format`](https://github.com/restoresrl/pb-format) project
   (token lexer + the four rules + `.pb-format.toml` + CLI
   `detect` / `format` / `check` / `write`) — **not** inside
   `pb-orca-mcp` as originally designed. The choke-point argument for
   putting it in the write tool lost to the argument for keeping
   PowerScript knowledge out of the ORCA bridge entirely.
5. ✅ Integration rewritten accordingly: the formatter is a step in the
   edit loop (`export_file` → edit → `pb-format format` →
   `import_file`), not a parameter of a write tool.
6. ⏳ End-to-end validation on a real workspace (compile invariance
   and idempotency).
7. ⏳ An AST-based layer stays deferred — trigger: a maintained
   PowerScript grammar cutting a real 1.0, or three concrete cases the
   token-based approach cannot resolve.

**Public release path (deferred, no deadline)** — when dogfooding has
confirmed stability:

1. Update the "Stato" line in `pb-orca-mcp/CLAUDE.md` (currently
   reflects dogfooding phase).
2. `gh repo edit restoresrl/pb-orca-mcp --visibility public --accept-visibility-change-consequences`.
3. `twine upload "dist/*"` for `pb-orca-mcp`.
4. Flip `restoresrl/pb-ai-code` to public once dogfooding on real
   targets confirms the skills hold up.
5. Publish `restoresrl/pb-format`, which today exists only as a local
   repository with no remote.

## Out of scope

- **Reimplementing ORCA primitives**: all `.pbl` actions flow through
  `pb-orca-mcp`. If something is missing in the MCP, fix it there, not
  here.
- **Production build pipelines**: `pb-ai-code` is a development tool,
  not a release-build runner. PowerGen / OrcaScript / custom batch
  scripts remain the way to produce tagged-release artifacts.
- **A new UI / dashboard**: this is a skills-and-docs repo (plus a
  couple of Python helpers). It has no UI of its own, and no runtime
  beyond what the assistant provides.
- **Generic MCP servers unrelated to PB development**: in-scope MCP
  servers are limited to the PB-dev stack (`pb-orca-mcp` for ORCA,
  `pb-appeon-index` for Appeon docs). New MCP servers are built only
  when they serve a clear PB-dev knowledge or workflow need, not as a
  general capability sprawl.
- **PowerBuilder Classic (pre-2019)**: not supported — same boundary
  as `pb-orca-mcp`.

## References

- Sibling project: [`pb-orca-mcp`](https://github.com/restoresrl/pb-orca-mcp)
  (currently private; will flip to public before its PyPI publish). Its
  `docs/integrating.md` is the contract this project is built against.
- Sibling project: [`pb-format`](https://github.com/restoresrl/pb-format)
  - the optional PowerScript formatter (local-only for now).
- Appeon PowerBuilder docs (the documentation source we'll ingest):
  https://docs.appeon.com/
- PowerScript Language Reference (the priority mirror candidate):
  https://docs.appeon.com/pb2022/powerscript_reference/
