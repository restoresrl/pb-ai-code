---
name: pb-src-format
description: Use this whenever you are about to write or edit the content of a PowerBuilder source file (.sra/.srw/.sru/.srf/.srd/.srm/.srs/.srq/.srj). Tells you where to find the canonical layout for each entry type, how to spot variants the wiki has not documented yet, and how to grow the wiki as you meet new cases. The file itself is produced by ORCA through pb-orca-mcp — this skill is about writing correct content inside it, not about assembling the file.
metadata:
  version: "1.1.0"
---

# Editing PB source content with the format wiki

Use this skill whenever you are about to **write** or **edit** the
textual content of a PowerBuilder source file. It answers "what does
correct text look like here"; getting that text into the `.pbl` is the
job of [`pb-orca-mcp`](https://github.com/restoresrl/pb-orca-mcp), and
the loop is described in
[`pb-apply-plan`](../pb-apply-plan/SKILL.md).

## The division of labour, stated once

**Never hand-assemble a `.sr*` file.** ORCA writes it, byte-identical
to what the IDE produces:

```
pb_object_export_file(lib, entry, type)   -> ORCA writes <entry>.<ext>
   ... you edit that file with ordinary text tools ...
pb_object_import_file(path, lib)          -> compiles, reports errors,
                                             and updates the text
                                             projection in the same call
```

So the envelope — the `$PBExportHeader$` line, the `$PBExportComments$`
line, the BOM, the CRLF line endings — is not yours to build. What is
yours is the **content between them**, and that is what the wiki
documents.

Three rules when you edit the exported file:

- Leave the `$PBExport*` header lines alone. They carry the entry's
  identity and its comment metadata.
- **Do not translate newlines.** The file is CRLF. An editor that
  normalizes to LF turns a one-line fix into a whole-file diff and puts
  LF inside the `.pbl`.
- **Do not re-encode.** Preserve the BOM you found.

The only case where content has to come from somewhere other than an
export is a **brand-new entry**, because there is nothing to export
yet — see [`pb-scaffold`](../pb-scaffold/SKILL.md).

## When to invoke this skill

- Before editing the body of an exported `.sr*`.
- Before producing the `syntax` argument of a `pb_compile_entry_import`
  call.
- When reading an unfamiliar entry type and you need to know which
  blocks mean what.

## The wiki

The format wiki lives at `docs/pb-source-format/` in this repo. Start
at [`index.md`](../../docs/pb-source-format/index.md). One page per
entry type:

| Extension | Page |
|---|---|
| `.sra` | [application](../../docs/pb-source-format/application.md) |
| `.srw` | [window](../../docs/pb-source-format/window.md) |
| `.sru` | [userobject](../../docs/pb-source-format/userobject.md) |
| `.srf` | [function](../../docs/pb-source-format/function.md) |
| `.srd` | [datawindow](../../docs/pb-source-format/datawindow.md) |
| `.srm` | [menu](../../docs/pb-source-format/menu.md) |
| `.srs` | [structure](../../docs/pb-source-format/structure.md) |
| `.srq` | [query](../../docs/pb-source-format/query.md) |
| `.srj` | [project](../../docs/pb-source-format/project.md) |

Two cross-cutting pages apply to every entry type:

- [`encoding.md`](../../docs/pb-source-format/encoding.md) — the
  `DefaultExportEncode`-driven encoding, CRLF, and the
  `$PBExportHeader$` / `$PBExportComments$` header block. Read it to
  understand *why* the rules above exist and what breaks when they are
  violated. You do not have to implement any of it.
- [`style-conventions.md`](../../docs/pb-source-format/style-conventions.md) —
  indent character, keyword case, operator spacing. **Out of scope for
  this skill**: they belong to [`pb-format`](../pb-format/SKILL.md), an
  optional external tool. Produce a body whose *structure* is canonical
  per the entry-type page and do not hand-tune its surface.

## The flow (read - consult - write - grow)

1. **Identify the entry type** by extension (`.sru` → userobject,
   `.srw` → window, …).

2. **Read the corresponding wiki page.** Pay attention to "Canonical
   form" (always present in `seeded` / `populated` pages) and to
   "Variants observed" if your case is non-trivial.

3. **If the page is `stub`** (the frontmatter `status` field), you have
   two options:
   - Write the content using your best understanding, verify it
     compiles, then *upgrade the page* (step 5).
   - If you cannot proceed confidently, say so to the user before
     guessing.

4. **Write the content** following the canonical form, into the file
   ORCA exported. Then import it and read the result: `success: false`
   with an `errors` array is compile diagnostics, each with a line and
   column — the normal outcome of an edit loop, not a failure of the
   tooling.

5. **Grow the wiki as a side-effect.** Once you have content that
   compiles (`success: true`), if your case revealed something the wiki
   did not document:

   - **New variant** of an existing entry type → append under
     "Variants observed" on that page, with a minimal repro snippet and
     a one-line note on why it differs.
   - **Open question answered** → move it from "Open questions" into
     "Variants observed" or "Canonical form", with the resolved
     content.
   - **New cross-cutting pattern** worth extracting → create a page
     under `docs/pb-source-format/patterns/` and cross-link it from the
     entry-type pages that use it.

   Use the `[[name]]` convention for cross-references. A link to a page
   that does not exist yet is a *signal*, not an error: it marks
   something worth writing.

   **Where to write it matters.** If these pages arrived as
   `pb-ai-code-docs/` beside the skills, you are looking at a vendored
   **snapshot**: the next install overwrites it, so an addition made there
   is lost.

   - **Working in the `pb-ai-code` repository itself** — edit the page
     directly. You are at the source.
   - **Working in a consumer project**, which is the usual case — write a
     note into the review's plan file, under `## Notes for the wiki`. The
     fields and an example are in
     [`pb-review`](../pb-review/SKILL.md) under Step 3; the short version
     is *page, section, observed-against, evidence, repro, why*. Say in
     your summary that you wrote one, because a note nobody reads is the
     same as no note.

   What happens to it afterwards — who collects it, how it becomes a
   change to the wiki — is [`docs/wiki-notes.md`](../../docs/wiki-notes.md).
   Read it once; it is short, and it explains why the fields are what
   they are.

6. **Update the page `status`** in the frontmatter when it changes:
   `stub` → `seeded` (canonical form filled in), `seeded` →
   `populated` (variants documented from real cases).

## Boundary with `pb-format`

This skill answers "*where do blocks go in the file*" (structure).
[`pb-format`](../pb-format/SKILL.md) answers "*how do tokens look*"
(style: tab vs spaces, `if` vs `IF`, `a = b` vs `a=b`). They are split
so the writing flow has one place to look for each question.

Write structurally correct content per the entry-type page; if the
workspace opted into a house style, run the formatter over the file
before importing.

## Boundary with the language reference

The wiki documents the **file format**, not the language. "What is the
syntax of `MessageBox()`", "what arguments does `DataWindow.Retrieve()`
take", "what events fire in what order" are PowerScript questions,
answered by [`appeon-query`](../appeon-query/SKILL.md) against the
indexed Appeon documentation. Do not pollute the format wiki with
language reference.

## When in doubt

If the question is about *where things go in the file*, it is format.
If it is about *what the code does at runtime*, it is language.
