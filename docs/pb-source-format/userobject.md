---
name: userobject
status: seeded
description: Layout of .sru files (PB User Object entry: visual or non-visual).
---

# Userobject (`.sru`)

A reusable building block: either visual (custom controls, response
windows of a kind) or non-visual (logic-only classes). The same
extension serves both flavors; the type is determined by the
`global type … from …` line.

## Canonical form

Minimal valid `.sru` for an NVO (non-visual object), validated
end-to-end against ORCA on PB 22 (compile + import + round-trip
export):

```
$PBExportHeader$u_basic.sru
forward
global type u_basic from nonvisualobject
end type
end forward

global type u_basic from nonvisualobject
end type
global u_basic u_basic

on u_basic.create
call super::create
TriggerEvent( this, "constructor" )
end on

on u_basic.destroy
TriggerEvent( this, "destructor" )
call super::destroy
end on
```

Anatomy:

- **`$PBExportHeader$<name>.sru`**: first text line. Required on
  disk; ignored by `pb_compile_entry_import`.
- **`forward … end forward`**: declares the userobject type up front.
- **`global type <name> from <parent>`**: the body. `<parent>`
  determines flavor:
  - `nonvisualobject`: NVO, pure logic, no UI surface.
  - `userobject` / `customvisual`: generic visual base.
  - `commandbutton`, `datawindow`, `dragobject`, …: specialized
    visual ancestors.
  - a custom `u_<base>` / `n_<base>`: typical in framework-heavy
    codebases (see parent-class corpus list below).
- **`global <name> <name>`**: global instance declaration. Present
  even though userobjects are normally instantiated by name, not used
  as a global.
- **`on <name>.create` / `on <name>.destroy`**: constructor /
  destructor. Both `call super::create` / `call super::destroy` *and*
  `TriggerEvent( this, "constructor" )` / `…, "destructor"` are
  required to fire the user-defined events of the same name. The
  `call super::…` must be **first** in create and **last** in destroy
  (mirror order so the parent's setup runs before the user's events
  and the user's destruction events run before the parent tears
  down).

A visual userobject adds geometry properties to the body block
(`integer width`, `integer height`, etc.) and may nest control
declarations. Member functions live in a `type <name>.functions`
block; instance variables in a `type variables` block.

## Variants observed

> Stub.

## Open questions

- How does the file structure differ among base types such as
  `nonvisualobject`, `userobject`, `customvisual`, `external` and
  `transaction`?
- In a multi-level userobject hierarchy, how are overrides and instance
  variables ordered in the file?

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

- [[index]]: wiki entry point.
- [[encoding]]: `DefaultExportEncode` + CRLF + `$PBExportHeader$` / `$PBExportComments$` rules.
- [[window]]: windows commonly inherit from visual userobjects.
- [[function]]: userobject functions are structurally similar to
  global functions but live inside the type block.
- [[patterns/forward]]: TBD.
- [[patterns/type-variables]]: TBD.
- [[patterns/event-syntax]]: TBD.
