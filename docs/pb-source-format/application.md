---
name: application
status: stub
description: Layout of .sra files (PB Application entry).
---

# Application (`.sra`)

The application object. One per target. Catch-22 noted in
`pb-orca-mcp`: creating a brand-new application via
`pb_compile_entry_import` has unusual requirements compared to other
entry types — see [[create-application-catch-22]] (TBD) once observed.

## Canonical form

> Stub. To be filled in from `pb-source-analyzer` bootstrap or a
> hand-curated minimal example.

## Variants observed

> Stub.

## Open questions

- What is the minimal `.sra` that compiles via
  `pb_compile_entry_import` from a cold session? (Tied to the
  catch-22 above.)
- Which fields appear in `appname`, `themepath`, and other
  application-level metadata blocks across PB versions?

<!-- BEGIN auto-generated: pb-source-analyzer -->

## Auto-generated from corpus

Derived from `pb-source-analyzer` over a private corpus. Do not edit by hand; this section is replaced on each render.

- **File count:** 18
- **CRLF OK:** 83.3%
- **`$PBExportHeader$` present:** 100.0%

### Encoding distribution

- `utf-8-bom`: 18 (100.0%)

### Block-kind frequency (mean occurrences per file)

| Kind | Mean |
|---|---|
| `event` | 2.444 |
| `event_close` | 2.444 |
| `on_block` | 2.0 |
| `on_close` | 2.0 |
| `global_type` | 1.889 |
| `type_close` | 1.778 |
| `type_variables_close` | 1.222 |
| `forward_open` | 1.0 |
| `forward_close` | 1.0 |
| `type_variables_open` | 0.389 |
| `function` | 0.056 |

### Most common top-level block sequences

- (6 files) `forward_open` → `global_type` → `type_close` → `forward_close` → `type_variables_close` → `global_type` → `type_close` → `on_block` → `on_close` → `on_block` → `on_close` → `event` → `event_close` → `event` → `event_close` → `event` → `event_close`
- (5 files) `forward_open` → `global_type` → `type_close` → `forward_close` → `type_variables_close` → `global_type` → `type_close` → `type_variables_open` → `type_variables_close` → `event` → `event_close` → `event` → `event_close` → `on_block` → `on_close` → `on_block` → `on_close` → `event` → `event_close`
- (2 files) `forward_open` → `global_type` → `type_close` → `forward_close` → `type_variables_close` → `global_type` → `type_close` → `on_block` → `on_close` → `on_block` → `on_close` → `event` → `event_close`
- (1 files) `forward_open` → `global_type` → `type_close` → `forward_close` → `type_variables_close` → `global_type` → `type_close` → `type_variables_open` → `type_variables_close` → `event` → `event_close` → `on_block` → `on_close` → `on_block` → `on_close` → `event` → `event_close`
- (1 files) `forward_open` → `forward_close` → `type_variables_close` → `global_type` → `function` → `on_block` → `on_close` → `on_block` → `on_close` → `event` → `event_close` → `event` → `event_close` → `event` → `event_close`

### Parent classes observed (`global type ... from ...`)

- `application` (34)

<!-- END auto-generated: pb-source-analyzer -->

## Cross-references

- [[index]] — wiki entry point.
- [[encoding]] — `DefaultExportEncode` + CRLF + `$PBExportHeader$` / `$PBExportComments$` rules.
- [[patterns/forward]] — TBD.
- [[patterns/type-variables]] — TBD.
