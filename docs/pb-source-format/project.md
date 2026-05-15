---
name: project
status: stub
description: Layout of .srj files (PB Project entry — build target definition).
---

# Project (`.srj`)

A project entry defines a build target — executable, deployment, or
component packaging. Usually one or two per application target.

## Canonical form

> Stub. Seed with a minimal executable-project definition.

## Variants observed

> Stub.

## Open questions

- Differences between EXE projects, DLL/PBD projects, and
  deployment projects in file structure.
- How resource manifests, version info, and icon references are
  embedded.
- Conditional build options — are they stored in the `.srj` or
  externally?

<!-- BEGIN auto-generated: pb-source-analyzer -->

## Auto-generated from corpus

Derived from `pb-source-analyzer` over a private corpus. Do not edit by hand; this section is replaced on each render.

- **File count:** 1
- **CRLF OK:** 100.0%
- **`$PBExportHeader$` present:** 100.0%

### Encoding distribution

- `utf-8-bom`: 1 (100.0%)

### Most common top-level block sequences

- (1 files) 

<!-- END auto-generated: pb-source-analyzer -->

## Cross-references

- [[index]] — wiki entry point.
- [[encoding]] — UTF-16 LE BOM + CRLF + `$PBExportHeader$` rules.
- [[application]] — projects target one application object.
