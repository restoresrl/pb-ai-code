---
name: encoding
status: populated
description: PB source files on disk are encoded per the workspace .pbw DefaultExportEncode directive (UTF-8 BOM / UTF-16BOM / ANSI), always CRLF, always starting with $PBExportHeader$. PB 2022 default is UTF-8 BOM. PB itself detects via BOM on read but writes with the configured value, so a mismatch triggers a Refresh cascade.
---

# Encoding and file header

Every PB source file (`.sra`, `.srw`, `.sru`, `.srf`, `.srd`, `.srm`,
`.srs`, `.srq`, `.srj`) is bound by three rules. Violating any of them
produces a file that PB silently rejects, imports as garbage, or
re-exports on the next Refresh (a "phantom" diff).

## Rule 1 — Encoding follows the workspace `DefaultExportEncode`

PB IDE picks the encoding of `ws_objects/<lib>.pbl.src/<name>.<ext>`
files from the `DefaultExportEncode` directive in the workspace
`.pbw`. The same value is what the IDE writes when you "Export
Source", "Refresh", or have SCC-driven regenerate enabled. PB 2022
accepts three values:

| `DefaultExportEncode` | First bytes | Typical use |
|---|---|---|
| `"UTF-8"` | `EF BB BF` | PB 2022 default; observed across every Restore workspace surveyed |
| `"UTF-16BOM"` | `FF FE` | PB legacy default (pre-2019) |
| `"ANSI"` | (no BOM) | Older Windows workspaces, system codepage |

On **read** (Import, Refresh), PB detects the encoding via BOM
inspection and accepts any of the three regardless of the workspace
setting. The setting only governs what PB **writes** on its own.

Verification (Windows PowerShell):

```pwsh
# Check the workspace setting
Select-String -Path '<workspace>\<name>.pbw' -Pattern 'DefaultExportEncode'

# Inspect the BOM of a .sr* file
$b = [System.IO.File]::ReadAllBytes('path\to\file.sru')
'{0:X2} {1:X2} {2:X2}' -f $b[0], $b[1], $b[2]
# Expect: EF BB BF (UTF-8 BOM)  |  FF FE __ (UTF-16 LE BOM)  |  any non-BOM byte (ANSI)
```

A file whose encoding does **not** match the `.pbw` setting will be
read OK by PB on Refresh, but the IDE then re-exports it in the
configured encoding — producing a phantom diff against whatever the
agent wrote, and triggering an import + compile + regenerate cascade
on other entries in the same library.

## Rule 2 — CRLF line endings

Every line is terminated with `0D 0A` (CRLF), regardless of which of
the three encodings is in use. LF-only files are not accepted.

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

The header is **not** a comment — it is a magic marker the IDE and
ORCA use to locate the entry. The name + extension in the header must
match the file basename and entry type.

When the PBL entry has a non-empty comment metadata, PB IDE emits a
**second** header line right after the first:

```
$PBExportHeader$<entry_name>.<ext>
$PBExportComments$<comment text with PowerScript escapes>
```

The comment uses PowerScript escape sequences for control characters:
`~r` for CR, `~n` for LF (so a CRLF-bearing comment becomes
`…~r~n…`), `~t` for TAB, and `~~` for `~` itself. PB IDE on Windows
expects the underlying metadata to be CRLF — the Library Painter
Properties dialog uses a multi-line Windows edit control that renders
bare LF without a visible line break.

A file with the correct encoding but a missing or wrong
`$PBExportComments$` line will be ingested correctly (the metadata
comes from the PBL), but PB IDE will see it as out-of-sync on the
next Refresh and trigger a regenerate cascade.

## Why standard text-editing tools can still break PB files

The breakage path that originally motivated this page: an existing
file is saved by a tool that rewrites it as **UTF-8 without BOM**, or
strips the original BOM, or flips line endings to LF only. PB then
rejects the file silently.

A subtler trap when the workspace setting is `UTF-16BOM`: most
editors default to UTF-8, so on save they replace the original
`FF FE` header with `EF BB BF` and the file body halves in size (the
content is now UTF-8, not UTF-16). The file opens in any editor but
PB rejects it.

When the workspace setting is `UTF-8` (the PB 2022 default), the
trap is narrower — many tools preserve UTF-8 BOM round-trip — but
you can still corrupt the file by stripping the BOM, converting to
UTF-8 no BOM, or changing CRLF to LF.

Symptoms either way: PB IDE refuses to open the object, or ORCA's
`pb_compile_entry_import` returns a vague compile error. The diff
often looks "fine" in the editor — the breakage is in the byte-level
header, invisible without a hex check.

## Preferred workflow — let the MCP tool handle encoding

The MCP tool `pb_edit_and_import` (sibling `pb-orca-mcp`) accepts a
`source_encoding` parameter that takes the same three values as
`DefaultExportEncode` (default `"UTF-8"`). It writes the file with
the matching BOM + codec, rebuilds the canonical
`$PBExportHeader$` / `$PBExportComments$` header block, normalizes
comment newlines to CRLF, and imports atomically — no host-tool
round-trip, no encoding pitfall:

```jsonc
pb_edit_and_import {
  "lib_path":         "...",
  "entry_name":       "...",
  "entry_type":       "...",
  "syntax":           "<body, no $PBExportHeader$ needed>",
  "source_path":      "<workspace>/ws_objects/<lib>.pbl.src/<name>.<ext>",
  "comments":         "...",
  "source_encoding":  "UTF-8"   // read from .pbw DefaultExportEncode
}
```

The caller should read `DefaultExportEncode` from the workspace `.pbw`
and pass the matching value. Passing the wrong one silently triggers
the Refresh cascade described in Rule 1.

## Restoring encoding after a host-tool edit (legacy fallback)

If you must edit a `.sr*` with a host tool that doesn't preserve the
PB encoding, re-encode in PowerShell. Pick the snippet that matches
the workspace `DefaultExportEncode`:

```pwsh
# UTF-8 BOM (PB 2022 default, all Restore workspaces)
$content = Get-Content -Raw -Encoding UTF8 path\to\file.sru
[System.IO.File]::WriteAllText('path\to\file.sru', $content, [System.Text.UTF8Encoding]::new($true))
```

```pwsh
# UTF-16 LE BOM
$content = Get-Content -Raw -Encoding UTF8 path\to\file.sru
[System.IO.File]::WriteAllText('path\to\file.sru', $content, [System.Text.Encoding]::Unicode)
```

```pwsh
# ANSI (no BOM, system codepage)
$content = Get-Content -Raw -Encoding UTF8 path\to\file.sru
[System.IO.File]::WriteAllText('path\to\file.sru', $content, [System.Text.Encoding]::Default)
```

After the write, the first few bytes should match the BOM of the
target encoding (`EF BB BF` for UTF-8 BOM, `FF FE` for UTF-16 LE
BOM, no BOM for ANSI).

The sibling skill [`pb-workflow`](../../../pb-orca-mcp/.claude/skills/pb-workflow/SKILL.md)
in `pb-orca-mcp` documents this re-encoding step as part of the
edit/propagate workflow. This page is the *what and why*; that skill
is the *how, in context*.

## Export/import asymmetry

When ORCA exports an entry (`pb_library_entry_export`), it returns
the body **without** the `$PBExportHeader$` line and **without** the
`$PBExportComments$` line — those are an on-disk export convention,
not part of the source-as-syntax. When importing back
(`pb_compile_entry_import`), the `syntax` field must include the
`$PBExportHeader$` line as its first line; the entry comment metadata
travels separately via the `comments` parameter. Round-tripping
requires manually re-prepending the header (or letting
`pb_edit_and_import` do it).

ORCA itself is encoding-agnostic — strings cross the C ABI as wide
chars — so the `source_encoding` choice only affects the on-disk
representation, never the in-memory call.

## Variants observed

- **UTF-8 BOM dominates on git-managed projects** — corpus scan
  (2421 files across 8 entry types) found 100% of `.sra`/`.srw`/
  `.sru`/`.srf`/`.srd`/`.srm`/`.srs`/`.srj` files in a real
  `ws_objects/` mirror to be UTF-8 BOM + CRLF, not UTF-16 LE BOM.
  This is the consequence of `DefaultExportEncode "UTF-8"` in the
  `.pbw` — the PB 2022 default. Survey of 24 `.pbw` files across the
  Restore stack (rstpb22, pbgettext22, pbunit22, mw21r2 and all 11
  Magware customizations) returned `"UTF-8"` in every case.

  Practical consequence for agents: when editing a file under
  `ws_objects/`, *preserve the BOM you find*, and pass the matching
  `source_encoding` to `pb_edit_and_import`. Re-encoding a UTF-8 BOM
  file to UTF-16 LE BOM (or vice versa) is unnecessary and triggers
  the IDE refresh cascade on the next open.

## Open questions

- Are `.srd` files truly text end-to-end, or do they embed binary
  segments (image data, raw control bytes) that require a
  different handling path?
- Are there PB-version differences in the `$PBExportHeader$` syntax
  (e.g. older versions producing `$PBExportHeader$` without the
  filename suffix)?
- What does PB do with files that have valid content but no BOM
  and `DefaultExportEncode "UTF-8"` / `"UTF-16BOM"` (i.e. the
  workspace expects a BOM but the file is BOM-less)? Reject
  outright, or fall back to ANSI detection?

## Cross-references

- [[index]] — wiki entry point.
- `[[pb-workflow]]` in sibling `pb-orca-mcp` — operational
  edit/import workflow + `source_encoding` parameter usage.
- [[application]], [[window]], [[userobject]], [[function]],
  [[datawindow]], [[menu]], [[structure]], [[query]], [[project]] —
  every entry type inherits the encoding rules from this page.
