---
name: menu
status: seeded
description: Layout of .srm files (PB Menu entry).
---

# Menu (`.srm`)

A menu definition (menu bar + items + sub-items + per-item events).
Typically attached to a window.

## Canonical form

Minimal valid `.srm` — a menu with no items, validated end-to-end
against ORCA on PB 22 (compile + import + round-trip export):

```
$PBExportHeader$m_basic.srm
forward
global type m_basic from menu
end type
end forward

global type m_basic from menu
end type
global m_basic m_basic

on m_basic.create
call super::create
end on

on m_basic.destroy
call super::destroy
end on
```

Anatomy:

- **`$PBExportHeader$<name>.srm`** — first text line. Required on
  disk; ignored by `pb_compile_entry_import`.
- **`forward … end forward`** — declares the menu type before the
  body. PB needs this even for a flat single-type file because the
  body references the type symbol.
- **`global type <name> from menu` … `end type`** — the body. Item
  definitions (sub-menu types) go inside this block.
- **`global <name> <name>`** — the global instance declaration.
- **`on <name>.create` / `on <name>.destroy`** — constructor /
  destructor with `call super::create` / `call super::destroy`. They
  are required even when empty; without them the parent chain breaks.

A menu without items is structurally valid but useless at runtime.
In real-world menus, item definitions are nested `global type m_<item>
from menu` blocks inside the body, each with its own
`event clicked` handler. The corpus auto-stats below give a sense of
how many items / events typical menus carry.

## Variants observed

> Stub.

## Open questions

- Menu inheritance — how does an inherited menu serialize overrides
  vs the parent definition?
- Toolbar-attached menus — extra fields?
- Right-to-left / localization metadata in the file?

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
| `on_block` | 23.103 |
| `on_close` | 23.103 |
| `type_close` | 18.31 |
| `event` | 5.509 |
| `event_close` | 5.509 |
| `global_type` | 2.457 |
| `forward_open` | 1.0 |
| `forward_close` | 1.0 |
| `type_variables_open` | 0.181 |
| `type_variables_close` | 0.181 |
| `function` | 0.095 |
| `function_close` | 0.043 |
| `subroutine` | 0.034 |
| `subroutine_close` | 0.017 |

### Most common top-level block sequences

- (7 files) `forward_open` → `global_type` → `type_close` → `forward_close` → `global_type` → `type_close` → `on_block` → `on_close` → `on_block` → `on_close` → `on_block` → `on_close` → `on_block` → `on_close` → `on_block` → `on_close`
- (6 files) `forward_open` → `global_type` → `type_close` → `forward_close` → `global_type` → `type_close` → `on_block` → `on_close` → `on_block` → `on_close` → `on_block` → `on_close` → `on_block` → `on_close`
- (4 files) `forward_open` → `global_type` → `type_close` → `forward_close` → `global_type` → `type_close` → `on_block` → `on_close` → `on_block` → `on_close` → `on_block` → `on_close` → `on_block` → `on_close` → `on_block` → `on_close` → `on_block` → `on_close`
- (3 files) `forward_open` → `global_type` → `type_close` → `forward_close` → `global_type` → `type_close` → `on_block` → `on_close` → `on_block` → `on_close`
- (3 files) `forward_open` → `global_type` → `type_close` → `forward_close` → `global_type` → `type_close` → `on_block` → `on_close` → `on_block` → `on_close` → `on_block` → `on_close` → `on_block` → `on_close` → `on_block` → `on_close` → `on_block` → `on_close` → `on_block` → `on_close` → `on_block` → `on_close` → `on_block` → `on_close` → `on_block` → `on_close` → `on_block` → `on_close`

### Parent classes observed (`global type ... from ...`)

- `m_menu_2` (89)
- `m_menu_11` (44)
- `menu` (38)
- `m_menu_15` (25)
- `m_menu_96` (20)
- `m_menu_49` (15)
- `m_menu_45` (12)
- `m_menu_66` (9)
- `m_menu_47` (8)
- `m_menu_83` (8)

<!-- END auto-generated: pb-source-analyzer -->

## Cross-references

- [[index]] — wiki entry point.
- [[encoding]] — `DefaultExportEncode` + CRLF + `$PBExportHeader$` / `$PBExportComments$` rules.
- [[window]] — menus are typically attached to windows.
- [[patterns/event-syntax]] — TBD.
