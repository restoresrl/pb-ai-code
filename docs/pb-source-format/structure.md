---
name: structure
status: stub
description: Layout of .srs files (PB Structure entry).
---

# Structure (`.srs`)

A typed record (named, fixed set of fields). Lighter than a
userobject, no methods. Used as a value type.

## Canonical form

> Stub. Seed with a flat structure of three fields of different
> primitive types.

## Variants observed

> Stub.

## Open questions

- Are nested structures supported (a structure field whose type is
  another structure), and how are they serialized?
- Array-typed fields — fixed-size vs dynamic, declaration syntax.

<!-- BEGIN auto-generated: pb-source-analyzer -->

## Auto-generated from corpus

Derived from `pb-source-analyzer` over a private corpus. Do not edit by hand; this section is replaced on each render.

- **File count:** 20
- **CRLF OK:** 100.0%
- **`$PBExportHeader$` present:** 100.0%

### Encoding distribution

- `utf-8-bom`: 20 (100.0%)

### Block-kind frequency (mean occurrences per file)

| Kind | Mean |
|---|---|
| `global_type` | 1.0 |
| `type_close` | 1.0 |

### Most common top-level block sequences

- (20 files) `global_type` → `type_close`

### Parent classes observed (`global type ... from ...`)

- `structure` (20)

<!-- END auto-generated: pb-source-analyzer -->

## Cross-references

- [[index]] — wiki entry point.
- [[encoding]] — UTF-16 LE BOM + CRLF + `$PBExportHeader$` rules.
