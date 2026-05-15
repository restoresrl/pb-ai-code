---
name: menu
status: stub
description: Layout of .srm files (PB Menu entry).
---

# Menu (`.srm`)

A menu definition (menu bar + items + sub-items + per-item events).
Typically attached to a window.

## Canonical form

> Stub. Seed with a two-level menu (one top item, two children, one
> event handler).

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
- [[encoding]] — UTF-16 LE BOM + CRLF + `$PBExportHeader$` rules.
- [[window]] — menus are typically attached to windows.
- [[patterns/event-syntax]] — TBD.
