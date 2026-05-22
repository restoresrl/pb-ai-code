# PB source-file format reference

A reverse-engineered reference for the **textual form** of PowerBuilder
objects: how an `.sra` / `.srw` / `.sru` / `.srf` / `.srd` / `.srm` /
`.srs` / `.srq` / `.srj` file is laid out on disk.

Appeon documents the *PowerScript language* (what you write inside
events and functions). It does **not** document how the IDE serializes
an object to a text file. That format is what this wiki covers.

## Why this wiki exists

An agent that edits PB source files has to produce text that the PB
IDE (or the `pb_compile_entry_import` MCP tool on top of ORCA) will
accept. Errors here are not PowerScript syntax errors — they are
*file-format* errors: missing header, wrong block ordering, wrong
encoding, missing terminators. Compile-time error messages tend to be
unhelpful for this category. A wiki of canonical forms and observed
variants short-circuits the trial-and-error.

## How this wiki is organized

One page per entry type:

| Page | Extension | PB entry type |
|---|---|---|
| [application](application.md) | `.sra` | `application` |
| [window](window.md) | `.srw` | `window` |
| [userobject](userobject.md) | `.sru` | `userobject` |
| [function](function.md) | `.srf` | `function` |
| [datawindow](datawindow.md) | `.srd` | `datawindow` |
| [menu](menu.md) | `.srm` | `menu` |
| [structure](structure.md) | `.srs` | `structure` |
| [query](query.md) | `.srq` | `query` |
| [project](project.md) | `.srj` | `project` |

Plus cross-cutting concerns:

- [encoding](encoding.md) — `DefaultExportEncode` + CRLF + `$PBExportHeader$` / `$PBExportComments$`. Read this first.
- [style-conventions](style-conventions.md) — indent character, keyword case, operator spacing, line endings. The four invariants the planned formatter normalizes via `.pb-format.toml`.
- [patterns/](patterns/) — recurring blocks that appear in multiple entry types: `forward`, `type variables`, `event`, `on …` blocks, etc.

## Page conventions

Each entry-type page follows the same structure:

```
---
name: <entry-type>
status: stub | seeded | populated
description: <one-line summary>
---

# <Entry type> (`.srX`)

## Canonical form
The minimal valid example that compiles, annotated.

## Variants observed
Concrete deviations seen in real codebases (with frequency notes),
each with a minimal repro snippet. Append-only; do not delete past
variants without checking they are no longer present.

## Open questions
Things we have not yet figured out. Each question should be specific
enough that an agent encountering an answer can come back and close it.

## Cross-references
Pages and skills this page depends on or relates to: `[[name]]`-style
links.
```

The `status` field tracks maturity: `stub` (no real content yet),
`seeded` (canonical form written), `populated` (canonical form +
variants from real observation).

## How the wiki grows

Two channels:

1. **Bootstrap** — the `pb-source-analyzer` tool
   (`tools/pb-source-analyzer/`) ingests a `.sr*` tree and emits
   aggregated pattern statistics. The output is anonymized (no
   project-specific names) and merged into these pages.

2. **Incremental** — when an agent is about to edit a `.sr*` and the
   relevant page is incomplete or the file shows a variant not yet
   documented, the agent appends a new entry under "Variants observed"
   (or opens an item under "Open questions"). This is the
   [Karpathy "LLM Wiki" pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) —
   the agent contributes to the knowledge base as a side-effect of
   doing the work.

The skill that triggers this behavior is
[`pb-src-format`](../../.claude/skills/pb-src-format/SKILL.md).

## What this wiki is not

- Not a PowerScript language reference. For that, use the docs Appeon
  publishes (consumed via the layer-1 mechanism — see the project
  `PLAN.md`).
- Not a workflow guide for propagating edits into a `.pbl`. That's the
  job of the sibling skill `pb-workflow` in `pb-orca-mcp`.
- Not project-specific. Conventions, naming, and patterns specific to
  one codebase belong outside this wiki (layer 3 — deferred).

## Source of truth caveat

No authoritative spec exists. Everything here is observation. Treat
each page's content as a *best current understanding*, not a contract.
When in doubt, look at real files in a PB project and check the
"Variants observed" section first.
