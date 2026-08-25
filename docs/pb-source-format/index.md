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
accept. Errors here are not PowerScript syntax errors: they are
*file-format* errors: missing header, wrong block ordering, wrong
encoding, missing terminators. Compile-time error messages tend to be
unhelpful for this category. A wiki of canonical forms and observed
variants short-circuits the trial-and-error.

## How this wiki grows

It is not finished, and it is not meant to be: it documents what has been
observed. A project using this kit holds a **snapshot** of these pages, so
an agent that meets an undocumented construction cannot edit them where it
works: it writes a note into the review's plan file instead, and the note
is carried back. [`wiki-notes.md`](../wiki-notes.md) explains the shape of
a note, why the fields are what they are, and how to turn one into a
change here.

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

- [encoding](encoding.md): `DefaultExportEncode` + CRLF + `$PBExportHeader$` / `$PBExportComments$`. Read this first.
- [style-conventions](style-conventions.md): indent character, keyword case, operator spacing, line endings. The four invariants the optional [`pb-format`](https://github.com/restoresrl/pb-format) tool normalizes when a workspace opts in with a `.pb-format.toml`.
- [patterns/](patterns/): recurring blocks that appear in multiple entry types: `forward`, `type variables`, `event`, `on …` blocks, etc.

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

1. **Bootstrap**: the `pb-source-analyzer` tool
   (`tools/pb-source-analyzer/`) ingests a `.sr*` tree and emits
   aggregated pattern statistics. The output is anonymized (no
   project-specific names) and merged into these pages.

2. **Incremental**, when an agent is about to edit a `.sr*` and the
   relevant page is incomplete or the file shows a variant not yet
   documented, the agent appends a new entry under "Variants observed"
   (or opens an item under "Open questions"). This is the
   [Karpathy "LLM Wiki" pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f),
   the agent contributes to the knowledge base as a side-effect of
   doing the work.

The skill that triggers this behavior is
[`pb-src-format`](../../skills/pb-src-format/SKILL.md).

## What this wiki is not

- Not a PowerScript language reference. For that, use the indexed
  Appeon documentation via the
  [`appeon-query`](../../skills/appeon-query/SKILL.md) skill.
- Not a workflow guide for getting edits into a `.pbl`. That is
  [`pb-orca-mcp`](https://github.com/restoresrl/pb-orca-mcp)'s job: it
  exports the file, compiles it back, and keeps the text projection in
  step. The pages here describe what the text inside that file looks
  like.
- Not project-specific. Conventions, naming, and patterns specific to
  one codebase belong outside this wiki (layer 3: deferred).

## A `.pbl` holds two things, and only one of them is here

Every page in this wiki describes the **source** form of an entry: the
text an export produces and an import consumes. A `.pbl` also holds the
**compiled p-code**, and several behaviours that look mysterious from
the source side are explained by that second half:

- **Importing the same source twice produces different `.pbl` bytes.**
  The compiled form carries a compilation timestamp, so a re-import
  reproduces the code and re-stamps the time. Sizes match, bytes do
  not. Consequence: a `.pbl` hash is not an equality check, and
  `git status` will report a library as modified after a change that
  reverted itself. Only restoring the file from a copy gives byte
  identity back.
- **A failed import damages the two halves differently.** Measured on
  one entry: the source grew by the edited line (`source_size`
  3920 → 3962) while the compiled form **shrank by 1218 bytes**
  (`object_size` 6792 → 5574): the event that failed to compile lost
  its p-code. The entry is left with new text and a mutilated object,
  not with old code.
- **An export cannot show you any of this.** It returns the source
  half, so an entry whose p-code is damaged exports byte-identical
  text. Verifying a library by diffing exported sources is therefore
  blind to exactly the failure mode a bad import produces.

`pb_library_entry_information` reports the two sizes separately,
`source_size` (in UTF-16 code units, so halve it for the exported
bytes) and `object_size`, which is the only view of the compiled half
the tooling offers.

The write loop in
[`pb-apply-plan`](../../skills/pb-apply-plan/SKILL.md) is built around
these facts: it snapshots the `.pbl` file before every import and
restores that file on failure, because no re-import can undo what a
failed one did.

## Source of truth caveat

No authoritative spec exists. Everything here is observation. Treat
each page's content as a *best current understanding*, not a contract.
When in doubt, look at real files in a PB project and check the
"Variants observed" section first.
