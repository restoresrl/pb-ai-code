---
name: datawindow
status: seeded
description: Layout of .srd files (PB DataWindow entry).
---

# DataWindow (`.srd`)

A query + presentation definition. Internally a heavy text format
with band layouts, columns, computed fields, and embedded SQL.
Probably the format most likely to contain edge cases.

Unlike the other entry types, `.srd` is **not PowerScript** — it is
a DSL of its own (the same syntax that `DataWindow.Describe(…)` /
`DataWindow.Modify(…)` return and accept at runtime).

## Canonical form

Minimal valid `.srd` — an external single-column grid, validated
end-to-end against ORCA on PB 22 (compile + import + round-trip
export):

```
$PBExportHeader$d_minimal.srd
release 22;
datawindow(units=0 timer_interval=0 color=1073741824 processing=0 )
header(height=0 color="536870912" )
summary(height=0 color="536870912" )
footer(height=0 color="536870912" )
detail(height=80 color="536870912" )
table(column=(type=char(10) update=yes updatewhereclause=yes name=col1 dbname="col1" ) )
column(band=detail id=1 alignment="0" tabsequence=10 border="0" color="0" x="5" y="4" height="76" width="200" format="[general]" name=col1 visible="1" edit.limit=10 edit.case=any edit.autoselect=yes edit.autohscroll=yes font.face="Arial" font.height="-10" font.weight="400" font.family="2" font.pitch="2" font.charset="0" background.mode="1" background.color="536870912" )
htmltable(border="1" cellpadding="0" cellspacing="0" generatecss="no" nowrap="yes" )
```

Anatomy (top-level blocks, in the order they must appear):

- **`$PBExportHeader$<name>.srd`** — first text line. Required on
  disk; ignored by `pb_compile_entry_import`.
- **`release N;`** — major PB version the source targets. Must match
  the runtime that will load the DW (use `pb_target_info` if
  unsure). The example targets PB 22.
- **`datawindow(...)`** — top-level DW properties. `processing=N`
  selects the presentation style:
  - `0` = Grid
  - `1` = Group
  - `2` = Composite
  - `3` = Crosstab
  - `4` = TreeView
  - `5` = OLE / RichText / Graph (further sub-typed)
- **`header(...)` / `summary(...)` / `footer(...)` / `detail(...)`** —
  band declarations. `detail` is the only one that *must* have
  non-zero height for the DW to render anything; the others can be
  `height=0` (invisible).
- **`table(...)`** — data source. The nested `column=(…)` defines a
  **data column** (type + name + dbname). `processing=0` + an
  external `table` (no `retrieve=`) makes the DW external — no DB
  connection required. For a DB-backed DW, add `retrieve="<sql>"`
  to the `table` block.
- **`column(...)`** — a **visual control** that displays one data
  column. Refers to the data column by `name=`. The verbose property
  list (`edit.limit`, `font.face`, `background.color`, …) is what
  PB IDE writes by default; ORCA preserves it verbatim.
- **`htmltable(...)`** — HTML rendering hints. Required even for
  non-HTML DWs (ORCA rejects the entry without it).

Multi-column DWs add one `column=(…)` inside the `table(…)` block
*and* one top-level `column(…)` per visible column. Other top-level
blocks may appear (`text`, `compute`, `line`, `rectangle`, `bitmap`,
`group`, …) — one per visual element. See "Open questions" below
for what is not yet documented.

## Variants observed

> Stub.

## Open questions

- Does the `.srd` ever contain non-UTF-16 binary segments (embedded
  bitmaps, custom drawing data), or is it purely text?
- DataWindow style sheets / external descriptor references —
  inline or by URL/path?
- Computed fields, retrieval arguments, and report-style band
  ordering — how are these serialized? Inline expressions vs
  referenced expression strings?
- How is `dw_syntax` mirrored in `.srd` vs what
  `DataWindow.Describe('DataWindow.Syntax')` returns at runtime?

<!-- BEGIN auto-generated: pb-source-analyzer -->

## Auto-generated from corpus

Derived from `pb-source-analyzer` over a private corpus. Do not edit by hand; this section is replaced on each render.

- **File count:** 900
- **CRLF OK:** 100.0%
- **`$PBExportHeader$` present:** 100.0%

### Encoding distribution

- `utf-8-bom`: 900 (100.0%)

### Most common top-level block sequences

- (900 files) 

<!-- END auto-generated: pb-source-analyzer -->

## Cross-references

- [[index]] — wiki entry point.
- [[encoding]] — UTF-16 LE BOM + CRLF + `$PBExportHeader$` rules.
- [[window]] — windows can embed DataWindow controls.
