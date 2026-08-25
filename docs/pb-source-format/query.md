---
name: query
status: stub
description: Layout of .srq files (PB Query entry: saved SQL).
---

# Query (`.srq`)

A saved SQL query, reusable across DataWindows. Lower-traffic entry
type; often a thin wrapper around a `SELECT` statement.

## Canonical form

> Stub. Seed with a basic `SELECT` against a single table.

## Variants observed

> Stub.

## Open questions

- Does parameter binding inside an `.srq` use placeholders or named markers?
- Are DBMS-specific constructs, such as SQL Server T-SQL or Oracle PL/SQL,
  stored verbatim?

## Cross-references

- [[index]]: wiki entry point.
- [[encoding]]: `DefaultExportEncode` + CRLF + `$PBExportHeader$` / `$PBExportComments$` rules.
- [[datawindow]]: DataWindows can reference a stored query.
