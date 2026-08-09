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
| `"UTF-8"` | `EF BB BF` | PB 2022 default; the only value seen in the survey below |
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

## Rule 4 — reading the file must not translate newlines

The rules above describe bytes going *out*. There is a matching rule
for bytes coming *in*: read a `.sr*` **without newline translation**.

A reader that helpfully converts CRLF to LF — the default in a lot of
languages and editors — hands you a body whose every line differs from
what is in the library. Import that and the `.pbl` now holds LF, which
means the next export differs from the last commit on every single
line: a whole-file phantom diff produced by a one-line fix. The
breakage is silent, because the text looks identical on screen.

The same goes for writing: preserve the BOM and the CRLF you found.

**And do not measure line endings with a text-mode tool.** Anything that
opens these files as text may translate newlines on the way in, so it
reports what it produced rather than what is on disk — `grep -c $'\r$'`
under Git Bash counts a CR on lines that carry a bare LF, which is how a
file that is 100% LF gets misread as 100% CRLF. Count bytes in binary
mode: `open(path, 'rb')`, then compare occurrences of `\r\n` against
occurrences of `\n`. The difference is your bare-LF count.

The same caution applies to git. With `core.autocrlf = true` and no
`.gitattributes`, git normalizes these files on the way into the index and
converts back on checkout, so **a line-ending change produces no diff and
`git status` stays clean**. `git ls-files --eol` shows the truth
(`i/lf w/crlf` means the index and the working tree disagree by
normalization), and `git add --renormalize <dir>` brings the index onto
the real bytes. A `.gitattributes` rule stops the normalization for good,
which is what makes drift visible in the first place.

Use **`*.sr* -text`**, not `*.sr* binary`. Both stop the translation, but
`binary` is a macro for `-diff -merge -text`, so git then answers
`Binary files differ` for every change to a PowerBuilder object — trading a
silent-drift problem for an unreadable-diff one, and discarding the reason a
project keeps a text projection at all. Keep `binary` for `*.pbl` and `*.pbd`,
which really are opaque:

```gitattributes
*.sr* -text
*.pbl binary
*.pbd binary
```

## Who writes these files — and why it should not be you

**ORCA writes them.** `pb-orca-mcp` exposes the export in
write-to-file mode (`PBORCA_ConfigureSession` +
`PBORCA_LibraryEntryExportEx`), so the bytes come from the same engine
the IDE uses: correct BOM for the workspace encoding, CRLF throughout,
canonical `$PBExportHeader$` / `$PBExportComments$` block. The edit loop
is therefore:

```text
pb_object_export_file(lib, entry, type)   -> ORCA writes the file
   ... edit the file with ordinary text tools ...
pb_object_import_file(path, lib)          -> compiles and, when the
                                             project keeps a text
                                             projection, updates it in
                                             the same call
```

Nothing in that loop asks you for an encoding, and nothing asks you to
build a header block. Every rule on this page is a rule about what
would break *if* you hand-assembled the file — which is exactly why the
recommendation is not to.

Two consequences worth knowing:

- **ORCA's export is byte-stable.** Exporting an object that did not
  change reproduces the same bytes, so "export everything, then diff"
  is a valid way to detect drift, and a sync of an unchanged object
  does not dirty the working tree.
- **The import ignores header lines.** You can leave the
  `$PBExportHeader$` block in the syntax you pass to
  `pb_compile_entry_import`, or omit it; entry name and type travel as
  separate parameters either way. It is *not* a required prefix. (The
  belief that it was came from a `C0114` that turned out to be a size
  argument counted in characters instead of bytes.)

## Restoring encoding after a host-tool edit (last-resort fallback)

You should not need this. It is here for the case where a `.sr*` has
already been mangled by a tool that stripped the BOM or flipped the
line endings, and you want to repair the file rather than re-export it.
Re-exporting is almost always the better answer.

Pick the snippet that matches the workspace `DefaultExportEncode`:

```pwsh
# UTF-8 BOM (the PB 2022 default)
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

This page is the *what and why*.
[`pb-orca-mcp`](https://github.com/restoresrl/pb-orca-mcp) is the
*how*: its `docs/how-it-works.md` covers the two-forms model and the
one silent way to get it wrong, and its `docs/recipes.md` has the exact
call sequences.

## The string API, and its (lack of) asymmetry

Besides the file API there is a string API:
`pb_library_entry_export` returns the entry's **body** — without the
`$PBExportHeader$` and `$PBExportComments$` lines, which are an on-disk
convention rather than part of the source-as-syntax — and
`pb_compile_entry_import` takes a `syntax` string.

The import **ignores header lines if they are present**, so the two
sides compose without any manual re-prepending: export a body, transform
it, import it back. Entry comment metadata travels separately, via the
`comments` parameter.

ORCA itself is encoding-agnostic — strings cross the C ABI as wide
chars — so encoding is purely a property of the on-disk representation,
never of the in-memory call. Pass a plain string, no BOM.

Use the string API when the object is small or the transform is
mechanical; use the file API by default, so the source never travels
through a conversation as a tool argument.

## Variants observed

- **UTF-8 BOM dominates on git-managed projects** — corpus scan
  (2421 files across 8 entry types) found 100% of `.sra`/`.srw`/
  `.sru`/`.srf`/`.srd`/`.srm`/`.srs`/`.srj` files in a real
  `ws_objects/` mirror to be UTF-8 BOM + CRLF, not UTF-16 LE BOM.
  This is the consequence of `DefaultExportEncode "UTF-8"` in the
  `.pbw` — the PB 2022 default. A survey of 24 `.pbw` files across one
  organisation's PB stack — three shared framework libraries, one
  enterprise product and its eleven customer variants — returned
  `"UTF-8"` in every case.

  Practical consequence for agents: when editing a file under
  `ws_objects/`, *preserve the BOM you find*. Re-encoding a UTF-8 BOM
  file to UTF-16 LE BOM, or the other way round, is never necessary and
  triggers the IDE refresh cascade on the next open.

## Answered questions

- **Do `.sr*` files embed binary segments?** Yes, but narrowly: the
  binary tail is produced **only by OLE / ActiveX controls**, which
  serialize their state into the export. DataWindow pictures do *not*
  produce one — that was the assumption, and it is wrong. Practical
  consequence: a `.srd` is text end-to-end, and a `.srw` is too unless
  it hosts an OLE control. When one does, the file is not safely
  editable as text past that point, which is another reason to let ORCA
  produce it.

## Open questions

- Are there PB-version differences in the `$PBExportHeader$` syntax
  (e.g. older versions producing `$PBExportHeader$` without the
  filename suffix)?
- What does PB do with files that have valid content but no BOM
  and `DefaultExportEncode "UTF-8"` / `"UTF-16BOM"` (i.e. the
  workspace expects a BOM but the file is BOM-less)? Reject
  outright, or fall back to ANSI detection?

## Cross-references

- [[index]] — wiki entry point.
- [[style-conventions]] — indent, keyword case, operator spacing: what
  the body looks like inside this envelope.
- [`pb-orca-mcp`](https://github.com/restoresrl/pb-orca-mcp) — the
  export/import loop that produces these files, and the `pb-workflow`
  skill it ships describing what to commit afterwards.
- [[application]], [[window]], [[userobject]], [[function]],
  [[datawindow]], [[menu]], [[structure]], [[query]], [[project]] —
  every entry type inherits the encoding rules from this page.
