---
name: datawindow
status: stub
description: Layout of .srd files (PB DataWindow entry).
---

# DataWindow (`.srd`)

A query + presentation definition. Internally a heavy text format
with band layouts, columns, computed fields, and embedded SQL.
Probably the format most likely to contain edge cases.

## Canonical form

> Stub. Seed with the minimal `.srd` that PB Designer produces from
> "New DataWindow → grid → one table, two columns".

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
