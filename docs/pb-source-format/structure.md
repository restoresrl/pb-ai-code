---
name: structure
status: seeded
description: Layout of .srs files (PB Structure entry).
---

# Structure (`.srs`)

A typed record (named, fixed set of fields). Lighter than a
userobject, no methods. Used as a value type.

## Canonical form

Minimal valid `.srs`, validated end-to-end against ORCA on PB 22
(compile + import + round-trip export):

```
$PBExportHeader$s_point.srs
global type s_point from structure
    long x
    long y
end type
```

Anatomy:

- **`$PBExportHeader$<name>.srs`**: first text line. Required on
  disk; ignored by `pb_compile_entry_import`.
- **`global type <name> from structure` … `end type`**: declares
  the structure. The parent is `structure` for a flat record (all
  corpus observations to date use this); a structure may instead
  extend another structure to inherit its fields.
- **Field lines**: `<type> <name>`, one per line, **indented by
  4 spaces** (ORCA preserves the indent verbatim on round-trip).
  Supported field types include all PB scalars (`long`, `string`,
  `decimal`, `date`, …) plus arrays and other structures.

A zero-field structure (just `global type … end type` with no fields
in between) compiles but is degenerate; the minimal *useful* form
has at least one field.

## Variants observed

> Stub.

## Open questions

- Are nested structures supported (a structure field whose type is
  another structure), and how are they serialized?
- How do fixed-size and dynamic array fields differ in their declarations?

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

- [[index]]: wiki entry point.
- [[encoding]]: `DefaultExportEncode` + CRLF + `$PBExportHeader$` / `$PBExportComments$` rules.
