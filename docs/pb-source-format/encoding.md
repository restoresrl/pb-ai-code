---
name: encoding
status: populated
description: PB source files use either UTF-16 LE BOM or UTF-8 BOM (the latter on ws_objects/ SCC mirrors), always CRLF, always starting with $PBExportHeader$. Standard text-editing tools that re-encode to UTF-8 without BOM break the file.
---

# Encoding and file header

Every PB source file (`.sra`, `.srw`, `.sru`, `.srf`, `.srd`, `.srm`,
`.srs`, `.srq`, `.srj`) is bound by three encoding rules. Violating
any of them produces a file that PB silently rejects or — worse —
imports as garbage.

## Rule 1 — UTF-16 LE BOM **or** UTF-8 BOM

Two BOM-marked encodings are accepted in practice:

| Encoding | First bytes | Where you see it |
|---|---|---|
| UTF-16 LE BOM | `FF FE` | PB IDE "Export to file"; `.sr*` extracted from a `.pbl` via ORCA |
| UTF-8 BOM | `EF BB BF` | The `ws_objects/` Source Code Control mirror on git-managed projects |

UTF-8 *without* BOM is not accepted. Other encodings (UTF-16 BE,
Windows-1252, …) are not accepted either.

Verification (UTF-16 LE BOM):

```pwsh
Get-Content -Encoding Byte -TotalCount 2 path\to\file.sru
# Expected: 255 254
```

Verification (UTF-8 BOM):

```pwsh
Get-Content -Encoding Byte -TotalCount 3 path\to\file.sru
# Expected: 239 187 191
```

## Rule 2 — CRLF line endings

Every line is terminated with `0D 0A` (CRLF). LF-only files are not
accepted.

## Rule 3 — `$PBExportHeader$` as the first line

The first text line of the file is:

```
$PBExportHeader$<entry_name>.<ext>
```

Examples:

```
$PBExportHeader$n_userobject_1.sru
$PBExportHeader$w_main.srw
$PBExportHeader$f_helper.srf
```

The header is **not** a comment. It is a magic marker the IDE and
ORCA use to locate the entry. The name + extension in the header must
match the file basename and entry type.

## Why standard text-editing tools can still break PB files

The breakage path that originally motivated this page: an existing
file is saved by a tool that rewrites it as **UTF-8 without BOM**, or
strips the original BOM, or flips line endings to LF only. PB then
rejects the file silently.

A subtler trap on **UTF-16 LE BOM** files: most editors default to
UTF-8, so on save they replace the original `FF FE` header with
`EF BB BF` and double the file size halves (the body is now UTF-8,
not UTF-16). The file *opens* in any editor but PB rejects it.

On **UTF-8 BOM** files (the `ws_objects/` flavor) the trap is
narrower — many tools preserve UTF-8 BOM round-trip — but you can
still corrupt the file by stripping the BOM, converting to UTF-8 no
BOM, or changing CRLF to LF.

Symptoms either way: PB IDE refuses to open the object, or ORCA's
`pb_compile_entry_import` returns a vague compile error. The diff
often looks "fine" in the editor — the breakage is in the byte-level
header, invisible without a hex check.

## Restoring encoding after a host-tool edit

After editing a `.sr*` with any tool that does not preserve UTF-16 LE,
re-encode in PowerShell:

```pwsh
$content = Get-Content -Raw -Encoding UTF8 path\to\file.sru
[System.IO.File]::WriteAllText('path\to\file.sru', $content, [System.Text.Encoding]::Unicode)
```

The .NET name `Unicode` denotes UTF-16 LE (with BOM). After the
write, the first two bytes should again be `FF FE`.

The sibling skill [`pb-workflow`](../../../pb-orca-mcp/.claude/skills/pb-workflow/SKILL.md)
in `pb-orca-mcp` documents this re-encoding step as part of the
edit/propagate workflow. This page is the *what and why*; that skill
is the *how, in context*.

## Export/import asymmetry

When ORCA exports an entry (`pb_library_entry_export`), it returns the
body **without** the `$PBExportHeader$` line. When importing back
(`pb_compile_entry_import`), the `syntax` field **must** include the
header as its first line. Round-tripping requires manually re-prepending
the header.

This is a known property of the ORCA API, documented in the sibling
`pb-orca-mcp` (see its `docs/workflow.md`).

## Variants observed

- **UTF-8 BOM dominates on git-managed projects** — corpus scan
  (2421 files across 8 entry types) found 100% of `.sra`/`.srw`/
  `.sru`/`.srf`/`.srd`/`.srm`/`.srs`/`.srj` files in a real
  `ws_objects/` mirror to be UTF-8 BOM + CRLF, not UTF-16 LE BOM.
  This means the original "PB source files are UTF-16 LE BOM"
  rule is *one of two* valid forms, not the only one. Both are
  accepted by PB IDE and ORCA's `pb_compile_entry_import`.

  Practical consequence for agents: when editing a file under
  `ws_objects/`, *preserve the BOM you find*. Re-encoding a
  UTF-8 BOM file to UTF-16 LE BOM (or vice versa) is unnecessary
  and risks breaking other tooling in the project that expects
  the original flavor.

## Open questions

- Are `.srd` files truly text end-to-end, or do they embed binary
  segments (image data, raw control bytes) that require a
  different handling path?
- Are there PB-version differences in the `$PBExportHeader$` syntax
  (e.g. older versions producing `$PBExportHeader$` without the
  filename suffix)?
- What does PB do with files that have valid content but no BOM?
  Reject outright, or attempt to load?
- Does the IDE pick UTF-16 LE BOM vs UTF-8 BOM based on PB version,
  project settings, or workspace flavor (`ws_objects/` mirror vs
  standalone)? Initial evidence: the SCC mirror format is UTF-8 BOM
  on PB 2022 R2; direct IDE export may still produce UTF-16 LE BOM.

## Cross-references

- [[index]] — wiki entry point.
- `[[pb-workflow]]` in sibling `pb-orca-mcp` — operational
  re-encoding procedure.
- [[application]], [[window]], [[userobject]], [[function]],
  [[datawindow]], [[menu]], [[structure]], [[query]], [[project]] —
  every entry type inherits the encoding rules from this page.
