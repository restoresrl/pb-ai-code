---
name: userobject
status: stub
description: Layout of .sru files (PB User Object entry — visual or non-visual).
---

# Userobject (`.sru`)

A reusable building block — either visual (custom controls, response
windows of a kind) or non-visual (logic-only classes). The same
extension serves both flavors; the type is determined by the
`global type … from …` line.

## Canonical form

> Stub. Two minimal forms to seed:
> 1. Non-visual class extending `nonvisualobject`, with one function.
> 2. Visual userobject extending one of the visual base types.

## Variants observed

> Stub.

## Open questions

- The full taxonomy of base types (`nonvisualobject`,
  `userobject`, `customvisual`, `external`, `transaction`, etc.) —
  which is which, and how does the file structure differ between
  them?
- Userobjects that inherit from another userobject (multi-level
  hierarchy) — ordering of overrides and instance variables in the
  file.

<!-- BEGIN auto-generated: pb-source-analyzer -->

## Auto-generated from corpus

Derived from `pb-source-analyzer` over a private corpus. Do not edit by hand; this section is replaced on each render.

- **File count:** 746
- **CRLF OK:** 100.0%
- **`$PBExportHeader$` present:** 100.0%

### Encoding distribution

- `utf-8-bom`: 746 (100.0%)

### Block-kind frequency (mean occurrences per file)

| Kind | Mean |
|---|---|
| `function` | 9.205 |
| `function_close` | 4.489 |
| `event` | 2.609 |
| `event_close` | 2.332 |
| `type_close` | 2.189 |
| `global_type` | 2.0 |
| `on_block` | 1.552 |
| `on_close` | 1.552 |
| `subroutine` | 1.48 |
| `forward_open` | 1.0 |
| `forward_close` | 1.0 |
| `subroutine_close` | 0.69 |
| `type_variables_close` | 0.61 |
| `type_variables_open` | 0.56 |

### Most common top-level block sequences

- (43 files) `forward_open` → `global_type` → `type_close` → `forward_close` → `global_type` → `type_close` → `on_block` → `on_close` → `on_block` → `on_close`
- (42 files) `forward_open` → `global_type` → `type_close` → `forward_close` → `global_type` → `type_close` → `type_variables_open` → `type_variables_close` → `event` → `event_close` → `event` → `event_close`
- (40 files) `forward_open` → `global_type` → `type_close` → `forward_close` → `global_type` → `type_close` → `on_block` → `on_close` → `on_block` → `on_close` → `event` → `event_close`
- (34 files) `forward_open` → `global_type` → `type_close` → `forward_close` → `global_type` → `type_close` → `on_block` → `on_close` → `on_block` → `on_close` → `event` → `event_close` → `event` → `event_close`
- (29 files) `forward_open` → `global_type` → `type_close` → `forward_close` → `global_type` → `type_close` → `event` → `event_close` → `event` → `event_close`

### Parent classes observed (`global type ... from ...`)

- `u_userobject_1` (298)
- `u_userobject_5` (252)
- `nonvisualobject` (124)
- `u_userobject_4` (108)
- `n_userobject_136` (74)
- `n_userobject_19` (42)
- `commandbutton` (36)
- `u_userobject_48` (28)
- `u_userobject_3` (26)
- `n_userobject_18` (24)

<!-- END auto-generated: pb-source-analyzer -->

## Cross-references

- [[index]] — wiki entry point.
- [[encoding]] — UTF-16 LE BOM + CRLF + `$PBExportHeader$` rules.
- [[window]] — windows commonly inherit from visual userobjects.
- [[function]] — userobject functions are structurally similar to
  global functions but live inside the type block.
- [[patterns/forward]] — TBD.
- [[patterns/type-variables]] — TBD.
- [[patterns/event-syntax]] — TBD.
