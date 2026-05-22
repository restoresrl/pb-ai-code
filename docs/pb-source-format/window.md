---
name: window
status: seeded
description: Layout of .srw files (PB Window entry).
---

# Window (`.srw`)

A visual container with controls, events, and instance variables. One
of the highest-complexity entry types: visual layout, control tree,
events, functions, and instance state all coexist in the same file.

## Canonical form

Minimal valid `.srw` — a control-less, event-less window, validated
end-to-end against ORCA on PB 22 (compile + import + round-trip
export):

```
$PBExportHeader$w_blank.srw
forward
global type w_blank from window
end type
end forward

global type w_blank from window
integer width = 2400
integer height = 1500
boolean titlebar = true
string title = "Blank"
end type
global w_blank w_blank

on w_blank.create
end on

on w_blank.destroy
end on
```

Anatomy:

- **`$PBExportHeader$<name>.srw`** — first text line. Required on
  disk; ignored by `pb_compile_entry_import`.
- **`forward … end forward`** — declares the window type up front so
  the body can reference its own symbol.
- **`global type <name> from <parent>`** — the body. `<parent>` is
  `window` for a top-level window, or a custom ancestor (`w_base`,
  `w_modal_base`, …) in typical apps — see the corpus parent-class
  list below.
- **Property assignments** inside the body — `integer width`,
  `integer height`, `boolean titlebar`, `string title`, etc. PB IDE
  writes these on save; values are in PBUnits (~1/256 of an inch) for
  geometry, native types for booleans/strings.
- **`global <name> <name>`** — global instance declaration.
- **`on <name>.create` / `on <name>.destroy`** — constructor /
  destructor. May be left empty (the `call super::…` form is also
  valid and is what userobjects/menus use, but windows do not need
  it).

Controls (buttons, datawindow controls, etc.) are declared as
**nested `type` blocks** inside the body, before `end type`. Events
are `event <name>; … end event` blocks at the body level. Instance
variables go into a `type variables` block. The corpus auto-stats
below give the typical block ordering.

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
- [[encoding]] — `DefaultExportEncode` + CRLF + `$PBExportHeader$` / `$PBExportComments$` rules.
- [[userobject]] — windows often inherit from custom userobjects;
  shared structural blocks.
- [[datawindow]] — embedded DataWindow controls.
- [[patterns/forward]] — TBD.
- [[patterns/type-variables]] — TBD.
- [[patterns/event-syntax]] — TBD.
