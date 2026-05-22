---
name: pb-src-format
description: Use this whenever you are about to write or edit a PowerBuilder source file (.sra/.srw/.sru/.srf/.srd/.srm/.srs/.srq/.srj). Tells you where to find the canonical layout for each entry type, how to spot variants that the wiki has not yet documented, and how to grow the wiki as you encounter new cases. Pairs with the sibling `pb-workflow` skill in `pb-orca-mcp` (which handles propagation to the .pbl after the file is written).
---

# Editing PB source files with the format wiki

Use this skill whenever you are about to **write** or **edit** the
textual content of a PowerBuilder source file. It is the companion
to `pb-workflow` in the sibling `pb-orca-mcp` repository: that one
covers *propagating* edits into the `.pbl`; this one covers writing
*correct text* in the first place.

## When to invoke this skill

- Before producing the body of a `pb_compile_entry_import` call.
- Before editing a `.sr*` file under `ws_objects/`.
- Before scaffolding a new entry (window, userobject, function, …).

## The wiki

The format wiki lives at `docs/pb-source-format/` in this repo. Start
at [`index.md`](../../../docs/pb-source-format/index.md). One page per
entry type:

| Extension | Page |
|---|---|
| `.sra` | [application](../../../docs/pb-source-format/application.md) |
| `.srw` | [window](../../../docs/pb-source-format/window.md) |
| `.sru` | [userobject](../../../docs/pb-source-format/userobject.md) |
| `.srf` | [function](../../../docs/pb-source-format/function.md) |
| `.srd` | [datawindow](../../../docs/pb-source-format/datawindow.md) |
| `.srm` | [menu](../../../docs/pb-source-format/menu.md) |
| `.srs` | [structure](../../../docs/pb-source-format/structure.md) |
| `.srq` | [query](../../../docs/pb-source-format/query.md) |
| `.srj` | [project](../../../docs/pb-source-format/project.md) |

Read [`encoding.md`](../../../docs/pb-source-format/encoding.md)
first if you are not yet familiar with the `DefaultExportEncode`-
driven encoding (UTF-8 BOM / UTF-16BOM / ANSI) + CRLF +
`$PBExportHeader$` / `$PBExportComments$` rules — they apply to every
entry type.

The second cross-cutting page is
[`style-conventions.md`](../../../docs/pb-source-format/style-conventions.md):
indent character, keyword case, operator spacing inside the body.
Those concerns are **out of scope for this skill** — they are
normalized at-import by the formatter (see
[`pb-format`](../pb-format/SKILL.md)) when the workspace ships a
`.pb-format.toml`. Produce a body whose **structure** is canonical
per the entry-type page; the formatter handles the surface style.

## The flow (read-consult-write-grow)

1. **Identify the entry type** by extension (`.sru` → userobject,
   `.srw` → window, etc.).

2. **Read the corresponding wiki page.** Pay attention to
   "Canonical form" (always present in `seeded`/`populated` pages)
   and "Variants observed" if your case is non-trivial.

3. **If the page is `stub`** (the frontmatter status field), you
   have two options:
   - Write the file using your best understanding from the available
     skill instructions and the encoding rules, then *upgrade the
     page* afterwards (see step 5).
   - If you cannot proceed confidently, surface this to the user
     before guessing.

4. **Write the file** following the canonical form. Respect the
   encoding rules from [encoding](../../../docs/pb-source-format/encoding.md):
   match the workspace `DefaultExportEncode` (UTF-8 BOM with `EF BB
   BF`, UTF-16 LE BOM with `FF FE`, or ANSI with no BOM), CRLF line
   endings, `$PBExportHeader$<name>.<ext>` on line 1, and (if the
   entry has a non-empty comment) `$PBExportComments$<escaped>` on
   line 2. Easier path: hand off to `pb_edit_and_import` in
   `pb-workflow`, which rebuilds the canonical header block and
   honors `source_encoding` for you.

5. **Grow the wiki as a side-effect.** After you have produced a
   file that compiles successfully (verified via
   `pb_compile_entry_import` returning `success: true`), if your
   case revealed something the wiki did not yet document:

   - **New variant** of an existing entry type → append under
     "Variants observed" on that page. Include a minimal repro
     snippet and a one-line note on why it differs.
   - **Open question answered** → move it from "Open questions" into
     "Variants observed" or "Canonical form", with the resolved
     content.
   - **New cross-cutting pattern** worth extracting → create a page
     under `docs/pb-source-format/patterns/` and cross-link from the
     entry-type pages that use it.

   Use the `[[name]]`-link convention for cross-references. If a
   link points to a page that does not exist yet, that is a
   *signal*, not an error — it marks something worth writing.

6. **Update the page `status`** in the frontmatter when relevant:
   `stub` → `seeded` (canonical form filled in), `seeded` →
   `populated` (variants documented from real cases).

## Boundary with `pb-workflow`

This skill stops once the file content is correct. Propagating that
content into a `.pbl` (via `pb_compile_entry_import` and, on git
projects, keeping `ws_objects/` and the `.pbl` in sync) is the job
of `pb-workflow` in `pb-orca-mcp`. Hand off to that skill once you
have the right bytes on disk.

## Boundary with `pb-format`

This skill answers "*where do blocks go in the file*" (structure).
[`pb-format`](../pb-format/SKILL.md) answers "*how do tokens look*"
(style: tab vs spaces, `if` vs `IF`, `a = b` vs `a=b`). They are
deliberately split so the writing flow has one place to look for
each question.

When you write a `.sr*` body, produce structurally correct text per
the entry-type wiki page; do **not** hand-tune the surface style.
`pb_edit_and_import` runs the formatter on its way to the `.pbl`
when the workspace ships a `.pb-format.toml`. If the workspace does
not opt in, the body passes through unchanged — same as today.

## Boundary with the Appeon docs

The wiki documents the **file format**, not the language. Questions
like "what is the syntax of `MessageBox()`" or "what arguments does
`DataWindow.Retrieve()` take" are PowerScript-language questions and
are answered by the layer-1 mechanism (cli-printing-press against
docs.appeon.com — see `docs/appeon-cli/README.md` once that layer is
in place). Do not pollute the format wiki with language reference.

## When in doubt

When you are uncertain whether you are looking at a format variant
(this skill's domain) or a language usage question (Appeon docs'
domain): if the question is about *where things go in the file*,
it's format; if it's about *what code does at runtime*, it's
language.
