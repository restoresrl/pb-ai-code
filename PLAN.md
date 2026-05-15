# `pb-ai-code` — Agentic dev kit for PowerBuilder

## Context

PowerBuilder is a closed-world IDE: a coding agent can read and edit the
text sources PB exports (`.sra`/`.srf`/`.srw`/`.sru`/...), but it cannot
compile, validate, or build them, nor can it autonomously design, test,
or debug PowerBuilder code without external help.

The sibling project [`pb-orca-mcp`](../pb-orca-mcp/) closes the
infrastructure gap: it exposes PowerBuilder's ORCA API (`pborc.dll`) as
MCP tools so an agent can act on `.pbl` libraries — create, modify,
compile, build EXE/PBD, navigate inheritance hierarchies and
cross-references.

**`pb-ai-code` is the layer above it**: the knowledge, skills, and
orchestration needed to actually *do* agentic PB development — design,
write, test, and debug — using `pb-orca-mcp` as the foundation tool.

## Vision: the four pillars of agentic PB development

The goal is to let a coding agent (Claude Code in first instance, but
agent-agnostic by design) handle the full development loop on a
PowerBuilder project:

1. **Design** — read existing architecture, follow PB-idiomatic
   patterns, scaffold new objects (windows, userobjects, datawindows,
   functions, menus) from minimal templates.
2. **Coding** — write valid PowerScript that respects PB semantics,
   propagate edits to `.pbl` with proper encoding (UTF-16 LE BOM + CRLF
   + `$PBExportHeader$`), iterate on compile errors.
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
| **Coding** — edit `.sr*` respecting encoding | `pb-workflow` skill in the MCP repo (UTF-16 LE BOM + CRLF + `$PBExportHeader$`) | Already covered |
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
- **Versioning**: during the current **internal dogfooding phase**
  (both repos private), `pb-ai-code` depends on an **editable install**
  of the local sibling — `pip install -e ../pb-orca-mcp`. When both
  repos flip to public and `pb-orca-mcp` ships on PyPI, this switches
  to versioned `pb-orca-mcp>=0.1.0` to avoid drift between releases.
  The editable mode is acceptable now because both projects are
  Carlo-only or restore-team-only.
- **Audience overlap, but distinct scope**: both repos target anyone
  who develops PB. `pb-orca-mcp` is the engine; `pb-ai-code` is the
  workflow + knowledge + orchestration. Either can be adopted
  independently — you can use the MCP alone with your own prompts, or
  use the dev kit if you want the ready-made experience.

## Composition (as designed in the review session 2026-05-14)

The repo contains a mix of artifacts:

1. **Skills** (`.claude/skills/<name>/SKILL.md` format) — one skill per
   workflow that needs the agent to follow a specific pattern:
   - Scaffolding skills (new application / window / userobject / …)
   - Style and architecture guide for idiomatic PowerScript
   - Test orchestration skill (writing tests + invoking the runner)
   - Debugging skills (failing test loop, runtime trace parsing,
     impact analysis)

2. **Knowledge base, organized in three layers** (revised
   2026-05-15; supersedes the earlier "hybrid mirror + WebFetch"
   plan):

   - **Layer 1 — PowerScript language and runtime API (Appeon docs)**:
     ingested with [`cli-printing-press`](https://github.com/mvanhorn/cli-printing-press),
     which scrapes `docs.appeon.com/pb2022` once into a local
     SQLite+FTS database and emits an MCP server the agent queries
     via tools like `appeon_search` / `appeon_get_page`. Replaces
     both the Markdown mirror and the on-demand `WebFetch` of the
     original design: one-time ingest, token-efficient query, no
     per-call live download. Recipe and skill live in the repo;
     the SQLite DB is generated locally (and possibly distributed
     as a release artifact pending Appeon's license terms).

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
   - Adapters per framework: probably **pbunit first** (knowledge
     readily available in the Restore stack), then others. The first
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
   - Restore's `n_logger` in `rstpb22` is a candidate reusable
     **pattern** (not the object itself — the dev kit is public and
     vendor-neutral).

5. **Slash commands** (`.claude/commands/<name>.md`) — entry points that
   compose multiple skills + MCP tools into named flows. Candidates:
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
| Repo location | Public, separate from `pb-orca-mcp` | International audience; no Restore-internal references; clean LICENSE story for Appeon docs mirror |
| Project name | **`pb-ai-code`** | Self-explanatory ("AI coding assistant for PB"); pairs naturally with `pb-orca-mcp` (engine + experience); agent-agnostic in name (no "claude" in the slug) |
| Appeon docs | Hybrid: core pages mirrored, rest via WebFetch | Balances offline friendliness, context cost, and freshness — **superseded 2026-05-15, see below** |
| Test framework | Agnostic via adapters; first adapter pbunit | Audience is broader than Restore; first adapter is the one we have ground truth on |
| Debugging scope | Four levels: compile-time (already MCP) + failing-test + runtime trace/log parsing + impact analysis | All four are realistic for PB given no DAP exists |
| Sequencing relative to `pb-orca-mcp` PyPI publish | **Internal dogfooding first** — both repos private; active dev on `pb-ai-code` can start whenever Carlo wants, using editable install of the local sibling. PyPI versioning + public flip when dogfooding confirms stability | Decouples scope readiness from external release pressure |

### Knowledge architecture revision (2026-05-15)

The "Appeon docs ingested in hybrid mode" decision above is replaced
by a three-layer knowledge architecture, because a single layer
conflated three distinct needs:

| Layer | Knowledge | Tech | Public in repo? |
|---|---|---|---|
| 1 | PowerScript language + runtime API (docs Appeon) | `cli-printing-press` → SQLite+FTS + MCP server | yes (recipe + skill; DB pending license check) |
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
   agent to correlate events with source. Restore's `n_logger` pattern
   in `rstpb22` is a candidate inspiration.
3. **First testing adapter** — **pbunit-first** is concrete and
   leverages existing Restore knowledge, but ties the abstraction to
   one framework. The alternative — design the abstraction agnostic
   from day one — produces upfront work without proof it's the right
   shape. Default: pbunit-first, extract the abstraction *from* it
   once it works.
4. **Distribution model for `pb-ai-code`** — **partially settled
   2026-05-15**: the repo carries Python (`tools/pb-source-analyzer/`,
   exposed as console script `pb-source-analyzer`), Markdown wiki
   (`docs/pb-source-format/`), skills (`.claude/skills/`), and a
   cli-printing-press recipe (`docs/appeon-cli/`). Distribution
   model still TBD: PyPI is now justified by the Python component
   but git-clone-into-workspace remains viable for the
   skill/wiki side. Final call deferred to public-flip time.
5. **Name availability verification** — check that
   `github.com/restoresrl/pb-ai-code` is free (very likely) and, if
   the distribution model ends up using PyPI, that `pb-ai-code` is
   free on PyPI too.

## Sequencing

**Current phase — internal dogfooding (both repos private)**:
`pb-ai-code` development can start whenever Carlo wants. The
`pb-orca-mcp` foundation (v0.1.0, 107 pytest green, compile loop
validated via Claude Code) is already usable via editable install. The
goal is to drive real Restore Magware work through this stack and
discover the gaps before any public release pressure.

**`pb-orca-mcp` pre-flight already done** (commit `876c34d`, 2026-05-14):
PyPI name verified free, recipe export/import asymmetry documented,
tool count aligned 23→29 with SCC group, Restore-internal references
scrubbed from public-facing docs, wheel + sdist built locally in
`dist/`.

**Public release path (deferred, no deadline)** — when dogfooding has
confirmed stability:

1. Update the "Stato" line in `pb-orca-mcp/CLAUDE.md` (currently
   reflects dogfooding phase).
2. `gh repo edit restoresrl/pb-orca-mcp --visibility public --accept-visibility-change-consequences`.
3. `twine upload "dist/*"` for `pb-orca-mcp`.
4. Switch `pb-ai-code` dependency from editable install to versioned
   PyPI: `pip install pb-orca-mcp>=0.1.0`.
5. Flip `restoresrl/pb-ai-code` to public when its design phase
   matures into something with usable skills / docs.

## Out of scope

- **Reimplementing ORCA primitives**: all `.pbl` actions flow through
  `pb-orca-mcp`. If something is missing in the MCP, fix it there, not
  here.
- **Production build pipelines**: `pb-ai-code` is a development tool,
  not a release-build runner. PowerGen / OrcaScript / custom batch
  scripts remain the way to produce tagged-release artifacts.
- **A new UI / dashboard**: this is a Claude-Code-shaped repo (skills,
  slash commands, docs, occasional Python helpers). It has no UI of
  its own.
- **A new MCP server**: the only MCP server in play is `pb-orca-mcp`.
  `pb-ai-code` consumes it.
- **PowerBuilder Classic (pre-2019)**: not supported — same boundary
  as `pb-orca-mcp`.

## References

- Sibling project: [`pb-orca-mcp`](https://github.com/restoresrl/pb-orca-mcp)
  (currently private; will flip to public before its PyPI publish).
- Appeon PowerBuilder docs (the documentation source we'll ingest):
  https://docs.appeon.com/
- PowerScript Language Reference (the priority mirror candidate):
  https://docs.appeon.com/pb2022/powerscript_reference/
