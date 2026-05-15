---
name: window
status: stub
description: Layout of .srw files (PB Window entry).
---

# Window (`.srw`)

A visual container with controls, events, and instance variables. One
of the highest-complexity entry types: visual layout, control tree,
events, functions, and instance state all coexist in the same file.

## Canonical form

> Stub. To be filled in from `pb-source-analyzer` bootstrap or a
> hand-curated minimal example (single window, one button, one event).

## Variants observed

> Stub.

## Open questions

- Section ordering when the window descends from a custom base
  class (does the inheritance chain appear in the header, in
  `forward`, or only in `global type … from …`?).
- How are nested controls (controls inside DataWindows inside the
  window) serialized — flat list with parent reference, or nested
  blocks?
- DataWindow controls embedded in a window — does the `.srw` contain
  the DataWindow source inline, or only a reference?

<!-- BEGIN auto-generated: pb-source-analyzer -->

## Auto-generated from corpus

Derived from `pb-source-analyzer` over a private corpus. Do not edit by hand; this section is replaced on each render.

- **File count:** 504
- **CRLF OK:** 100.0%
- **`$PBExportHeader$` present:** 100.0%

### Encoding distribution

- `utf-8-bom`: 504 (100.0%)

### Block-kind frequency (mean occurrences per file)

| Kind | Mean |
|---|---|
| `type_close` | 16.317 |
| `event` | 7.683 |
| `event_close` | 5.948 |
| `on_block` | 3.286 |
| `on_close` | 3.286 |
| `global_type` | 2.0 |
| `forward_open` | 1.0 |
| `forward_close` | 1.0 |
| `type_variables_close` | 0.629 |
| `type_variables_open` | 0.627 |
| `function` | 0.427 |
| `subroutine` | 0.379 |
| `subroutine_close` | 0.188 |
| `function_close` | 0.171 |

### Most common top-level block sequences

- (82 files) `forward_open` → `global_type` → `type_close` → `forward_close` → `global_type` → `type_close` → `on_block` → `on_close` → `on_block` → `on_close` → `type_close`
- (11 files) `forward_open` → `global_type` → `type_close` → `forward_close` → `global_type` → `type_close` → `on_block` → `on_close` → `on_block` → `on_close` → `event` → `event_close` → `type_close`
- (9 files) `forward_open` → `global_type` → `type_close` → `forward_close` → `global_type` → `type_close` → `type_variables_open` → `type_variables_close` → `on_block` → `on_close` → `on_block` → `on_close` → `type_close`
- (9 files) `forward_open` → `global_type` → `type_close` → `forward_close` → `global_type` → `type_close` → `on_block` → `on_close` → `on_block` → `on_close` → `type_close` → `on_block` → `on_close` → `on_block` → `on_close` → `type_close`
- (8 files) `forward_open` → `global_type` → `type_close` → `forward_close` → `global_type` → `type_close` → `on_block` → `on_close` → `on_block` → `on_close` → `event` → `event_close` → `type_close` → `on_block` → `on_close` → `on_block` → `on_close` → `type_close`

### Parent classes observed (`global type ... from ...`)

- `window` (144)
- `w_window_24` (128)
- `w_window_118` (94)
- `w_window_120` (90)
- `w_window_116` (74)
- `Window` (56)
- `w_window_209` (20)
- `w_window_150` (18)
- `w_window_219` (16)
- `w_window_222` (16)

<!-- END auto-generated: pb-source-analyzer -->

## Cross-references

- [[index]] — wiki entry point.
- [[encoding]] — UTF-16 LE BOM + CRLF + `$PBExportHeader$` rules.
- [[userobject]] — windows often inherit from custom userobjects;
  shared structural blocks.
- [[datawindow]] — embedded DataWindow controls.
- [[patterns/forward]] — TBD.
- [[patterns/type-variables]] — TBD.
- [[patterns/event-syntax]] — TBD.
