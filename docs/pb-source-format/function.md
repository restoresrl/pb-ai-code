---
name: function
status: stub
description: Layout of .srf files (PB global function entry).
---

# Function (`.srf`)

A global function. The file name equals the function name (no `f_`
or other prefix is enforced by the format — that is a project-level
convention).

## Canonical form

> Stub. Seed with: one global function taking two typed parameters
> and returning a value.

## Variants observed

> Stub.

## Open questions

- Parameter modifier syntax (`ref`, `readonly`) — exact placement in
  the parameter list.
- Return type for functions returning a userobject or structure —
  declaration order vs the `forward` block.
- Functions with default parameter values — how PB serializes the
  defaults (or whether it does at all in older versions).

<!-- BEGIN auto-generated: pb-source-analyzer -->

## Auto-generated from corpus

Derived from `pb-source-analyzer` over a private corpus. Do not edit by hand; this section is replaced on each render.

- **File count:** 116
- **CRLF OK:** 100.0%
- **`$PBExportHeader$` present:** 100.0%

### Encoding distribution

- `utf-8-bom`: 116 (100.0%)

### Block-kind frequency (mean occurrences per file)

| Kind | Mean |
|---|---|
| `type_close` | 1.026 |
| `global_type` | 1.0 |
| `function_close` | 0.862 |
| `subroutine_close` | 0.164 |
| `function` | 0.043 |

### Most common top-level block sequences

- (89 files) `global_type` → `type_close` → `function_close`
- (18 files) `global_type` → `type_close` → `subroutine_close`
- (5 files) `global_type` → `type_close` → `function` → `function_close`
- (3 files) `type_close` → `global_type` → `type_close` → `function_close`
- (1 files) `global_type` → `type_close` → `function_close` → `subroutine_close`

### Parent classes observed (`global type ... from ...`)

- `anon_3995` (116)

<!-- END auto-generated: pb-source-analyzer -->

## Cross-references

- [[index]] — wiki entry point.
- [[encoding]] — UTF-16 LE BOM + CRLF + `$PBExportHeader$` rules.
- [[userobject]] — userobject member functions share the body syntax
  but live in a different file structure.
