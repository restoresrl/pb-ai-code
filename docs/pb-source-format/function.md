---
name: function
status: seeded
description: Layout of .srf files (PB global function entry).
---

# Function (`.srf`)

A global function. The file name equals the function name (no `f_`
or other prefix is enforced by the format — that is a project-level
convention).

## Canonical form

Minimal valid `.srf`, validated end-to-end against ORCA on PB 22
(compile + import + round-trip export):

```
$PBExportHeader$gf_hello.srf
global type gf_hello from function_object
end type

forward prototypes
global function string gf_hello ()
end prototypes

global function string gf_hello ();return "hello"
end function
```

Anatomy:

- **`$PBExportHeader$<name>.srf`** — first text line. Required on disk
  so PB IDE can identify the entry on import; ignored when passing the
  body to `pb_compile_entry_import` (entry name/type are arguments).
- **`global type <name> from function_object` … `end type`** —
  declares the global function object. The parent is always
  `function_object` for a free-standing global function.
- **`forward prototypes` … `end prototypes`** — declares the function
  signature. Required even with zero arguments.
- **`global function <return> <name> (<args>);<body>` … `end function`** —
  the body. The opening `;` lives on the same line as the signature;
  `<body>` may continue on subsequent lines. `end function` is on
  its own line.

Member functions of a userobject / window use the same body syntax but
live inside a `type <name>.functions` block in the owning object's
file — they are not `.srf` entries.

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
- [[encoding]] — `DefaultExportEncode` + CRLF + `$PBExportHeader$` / `$PBExportComments$` rules.
- [[userobject]] — userobject member functions share the body syntax
  but live in a different file structure.
