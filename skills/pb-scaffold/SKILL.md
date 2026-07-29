---
name: pb-scaffold
description: Use this when you need to create a new PowerBuilder object from scratch — a window, userobject, function, datawindow, menu, or structure — and want a minimal body that the ORCA compiler accepts on the first try. Provides validated inline templates plus the rules for the one entry type the API cannot bootstrap (`application`). Pairs with pb-src-format (variants observed in real codebases) and pb-format (surface style).
metadata:
  version: "1.1.0"
---

# Scaffolding new PowerBuilder objects

Use this skill when you need to **create a new PB object**: emit the
minimal body for one of the supported entry types and feed it to
`pb_compile_entry_import`.

A new entry is the one case where there is nothing to export first, so
it is also the one case where the body has to come from somewhere
other than ORCA. Everything else — editing an object that already
exists — goes through the export/edit/import loop instead; see
[`pb-apply-plan`](../pb-apply-plan/SKILL.md).

## When to invoke this skill

- The user asks for a new window / userobject / function / datawindow /
  menu / structure (by name or by purpose).
- You are about to construct the `syntax` argument for
  `pb_compile_entry_import` from scratch.

If you are *editing* an existing object's body, you do not need this
skill — use [`pb-src-format`](../pb-src-format/SKILL.md) instead.

## What this skill covers

Six entry types, each with a template validated end-to-end against
ORCA on PB 22 (compile succeeds, entry lands in the `.pbl`, round-trip
export matches the input modulo whitespace):

| Type | Extension | Template section |
|---|---|---|
| function | `.srf` | [function](#function-srf) |
| structure | `.srs` | [structure](#structure-srs) |
| menu | `.srm` | [menu](#menu-srm) |
| window | `.srw` | [window](#window-srw) |
| userobject | `.sru` | [userobject](#userobject-sru) |
| datawindow | `.srd` | [datawindow](#datawindow-srd) |

Not covered:

- **`application`** — see [the application catch-22](#the-application-catch-22) below.
- **`query`** / **`project`** — out of MVP scope. If you need one, fall
  through to [`pb-src-format`](../pb-src-format/SKILL.md) for the
  on-disk format and write the file directly; ORCA can compile it from
  the same `pb_compile_entry_import` path once you have the body.

## How to use a template

1. Pick the template for the entry type you need.
2. Replace placeholders (the `<…>` tokens — entry name, parent class,
   custom fields).
3. Pass the resulting string as the `syntax` argument to
   `pb_compile_entry_import`. Required arguments:
   - `lib_path`: absolute path to the target `.pbl`.
   - `entry_name`: the object name (lowercase, no extension).
   - `entry_type`: the type string (`"function"`, `"window"`, …).
   - `syntax`: the template body.
4. Read the response. Branch on `"error" in response` first — that is a
   tool or state failure (session not configured, library not in the
   list). Otherwise check `success`: `false` with a populated `errors`
   array is **compile diagnostics, not a tool failure**, and each item
   carries `message_number`, `message_text`, `line` and `column`. Fix
   the body and re-import the whole thing.

## A note on the template surface style

The templates below use 4-space indent and lowercase PowerScript
keywords. That choice is **cosmetic to the skill**, not normative for
any codebase: it keeps the templates readable inline in this Markdown
file. **Do not hand-tune a template's surface to match a target
style.** If the workspace opted into a house style (it ships a
`.pb-format.toml`), run the formatter over the file once it is on
disk — see [`pb-format`](../pb-format/SKILL.md). Where it did not, the
template's own style is what lands, and that is fine.

## On `$PBExportHeader$`

The first line `$PBExportHeader$<name>.<ext>` is **not required by the
import**: ORCA ignores header lines in the syntax it is given, and the
entry name and type travel as separate parameters. It is required in a
`.sr*` **file** on disk, because that is how the IDE locates the
entry — but you should not be writing those files by hand anyway (see
below).

Including the header in the template costs nothing and keeps the body
valid on both paths, so the templates keep it.

Two related facts, since they used to be believed otherwise: ORCA is
encoding-agnostic at the C ABI (strings cross as wide chars), so pass
a plain `str` with no BOM to `pb_compile_entry_import`; and a compile
error on first import is almost never about the header. For the
on-disk encoding rules see
[`docs/pb-source-format/encoding.md`](../../docs/pb-source-format/encoding.md).

## Templates

### function (`.srf`)

```
$PBExportHeader$<name>.srf
global type <name> from function_object
end type

forward prototypes
global function <return_type> <name> (<args>)
end prototypes

global function <return_type> <name> (<args>);<body>
end function
```

Smallest concrete example (validated):

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

Notes:

- The `forward prototypes` block is required even with zero arguments.
- `<body>` lives on the same line as the function header after `;`.
  Multi-line bodies put each statement on its own line; the closing
  `end function` is a separate line.

### structure (`.srs`)

```
$PBExportHeader$<name>.srs
global type <name> from structure
    <type> <field_name>
    <type> <field_name>
end type
```

Smallest concrete example (validated):

```
$PBExportHeader$s_point.srs
global type s_point from structure
    long x
    long y
end type
```

Notes:

- Indent is 4 spaces (ORCA preserves it verbatim).
- A structure may also descend from another structure (`from <parent>`)
  instead of the built-in `structure`.

### menu (`.srm`)

```
$PBExportHeader$<name>.srm
forward
global type <name> from menu
end type
end forward

global type <name> from menu
end type
global <name> <name>

on <name>.create
call super::create
end on

on <name>.destroy
call super::destroy
end on
```

Smallest concrete example (validated):

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

Notes:

- A menu without items is structurally valid but useless. Add `m_item`
  entries inside the `global type` block once you have a working
  template.
- `call super::create` / `call super::destroy` are required when the
  menu has no custom create/destroy code (without them, the parent
  chain is broken).

### window (`.srw`)

```
$PBExportHeader$<name>.srw
forward
global type <name> from <parent>
end type
end forward

global type <name> from <parent>
integer width = <w>
integer height = <h>
boolean titlebar = true
string title = "<title>"
end type
global <name> <name>

on <name>.create
end on

on <name>.destroy
end on
```

Smallest concrete example (validated):

```
$PBExportHeader$w_blank.srw
forward
global type w_blank from window
end type
end forward

global type w_blank from window
integer width = 2400
integer height = 1500
boolean titlebar = true
string title = "Blank"
end type
global w_blank w_blank

on w_blank.create
end on

on w_blank.destroy
end on
```

Notes:

- `<parent>` is `window` for a fresh top-level window, or a custom
  ancestor name (`w_base`, `w_modal_base`, etc.) in a typical app.
- `width` and `height` are in **PBUnits** (~1/256 of an inch). The
  example uses 2400x1500 which is roughly 600x375 pixels at standard
  DPI. Override for your case.
- Controls (buttons, datawindows, etc.) go inside the `global type`
  block, after the property assignments and before `end type`. See
  [`docs/pb-source-format/window.md`](../../docs/pb-source-format/window.md)
  for the control-block format.

### userobject (`.sru`)

```
$PBExportHeader$<name>.sru
forward
global type <name> from <parent>
end type
end forward

global type <name> from <parent>
end type
global <name> <name>

on <name>.create
call super::create
TriggerEvent( this, "constructor" )
end on

on <name>.destroy
TriggerEvent( this, "destructor" )
call super::destroy
end on
```

Smallest concrete example (validated, NVO):

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

Notes:

- `<parent>` choices: `nonvisualobject` (NVO — pure logic, no UI),
  `userobject` (visual, generic), `datawindow` (visual DW user object),
  `dragobject`, `windowobject`, or a custom userobject class.
- The `TriggerEvent` calls in create/destroy are the convention that
  makes user-defined `constructor` / `destructor` events fire. They
  are required even for NVOs that do not define those events yet
  (descendants may).

### datawindow (`.srd`)

DataWindow source is a DSL of its own (not PowerScript). The minimum
valid body declares the layout bands, a `table` block with at least
one column, a `column` control for that column, and an `htmltable`
block. Without all four, ORCA rejects the entry.

```
$PBExportHeader$<name>.srd
release <pb_major>;
datawindow(units=0 timer_interval=0 color=1073741824 processing=<p> )
header(height=0 color="536870912" )
summary(height=0 color="536870912" )
footer(height=0 color="536870912" )
detail(height=<detail_h> color="536870912" )
table(column=(type=<col_type> update=yes updatewhereclause=yes name=<col_name> dbname="<col_dbname>" ) )
column(band=detail id=1 alignment="0" tabsequence=10 border="0" color="0" x="5" y="4" height="<col_h>" width="<col_w>" format="[general]" name=<col_name> visible="1" edit.limit=<col_limit> edit.case=any edit.autoselect=yes edit.autohscroll=yes font.face="Arial" font.height="-10" font.weight="400" font.family="2" font.pitch="2" font.charset="0" background.mode="1" background.color="536870912" )
htmltable(border="1" cellpadding="0" cellspacing="0" generatecss="no" nowrap="yes" )
```

Smallest concrete example (validated, external single-column):

```
$PBExportHeader$d_minimal.srd
release 22;
datawindow(units=0 timer_interval=0 color=1073741824 processing=0 )
header(height=0 color="536870912" )
summary(height=0 color="536870912" )
footer(height=0 color="536870912" )
detail(height=80 color="536870912" )
table(column=(type=char(10) update=yes updatewhereclause=yes name=col1 dbname="col1" ) )
column(band=detail id=1 alignment="0" tabsequence=10 border="0" color="0" x="5" y="4" height="76" width="200" format="[general]" name=col1 visible="1" edit.limit=10 edit.case=any edit.autoselect=yes edit.autohscroll=yes font.face="Arial" font.height="-10" font.weight="400" font.family="2" font.pitch="2" font.charset="0" background.mode="1" background.color="536870912" )
htmltable(border="1" cellpadding="0" cellspacing="0" generatecss="no" nowrap="yes" )
```

Notes:

- `release N;` must match the **major** PB version of the target
  install (use `pb_target_info` if uncertain). The template above is
  for PB 22.
- `processing=N` selects the presentation style: `0` = Grid, `1` =
  Group, `4` = TreeView, etc. `processing=0` with a single column is
  the simplest viable form.
- The `table` block's `column=(…)` defines the **data column**;
  the standalone `column(…)` defines the **visual control** that
  shows it. Both refer to each other by `name` (here, `col1`).
- For a DataWindow with a DB-backed source instead of external, add
  `retrieve="<sql>"` to the `table(…)` block. See
  [`docs/pb-source-format/datawindow.md`](../../docs/pb-source-format/datawindow.md)
  for retrieve syntax and other presentation modes.

## The application catch-22

ORCA cannot create the **first** application object in an empty `.pbl`:

- `pb_compile_entry_import` requires `set_current_application` to have
  been called first.
- `set_current_application(lib, name)` requires `name` to already exist
  as an application entry in `lib`.

The only ways out of this knot:

- **Use the PowerBuilder IDE.** New Workspace → New Target →
  Application — PB writes the initial application object directly to
  the `.pbl` (it does not use the ORCA path). After that, this skill
  can scaffold everything else.
- **Copy a pre-existing application from another `.pbl`.** If you have
  any `.pbl` with an application object, you can export its `.sra` and
  import it into the target with `pb_compile_entry_import` — but only
  after `set_current_application` has been pointed at *that* existing
  app. [`pb-orca-mcp`](https://github.com/restoresrl/pb-orca-mcp) ships
  a test fixture with an empty application object for exactly this
  purpose.

For a fresh project, the IDE path is the only practical workflow.
This skill does not attempt to script it.

## After the import succeeds

`pb_compile_entry_import` writes the compiled object into the `.pbl`
**and**, when the project keeps a `ws_objects/` text projection, writes
the matching `.sr*` file in the same call. The response says what it
touched: `sync: "ok"` with `synced_files`, or `sync:
"not_applicable"` when the project keeps no projection. So there is no
propagation step to remember, and no second file to keep aligned by
hand.

Two things are still yours:

- **Check `sync`.** `sync: "failed"` (with `sync_error`) means the
  `.pbl` has the new object but the text file was not written. Surface
  it; the two forms now disagree.
- **Decide the commit.** The server never stages and never commits, and
  whether the `.pbl` is tracked varies by project. `git status` shows
  what the repository actually does.

One thing worth checking on a new object: some workspaces keep a
`.pbg` file listing which object belongs to which library. ORCA does
not manage it. If the project has one, adding an entry may mean
updating it.

If the workspace has no projection yet and you want one,
`pb_library_export_sources(lib_path)` writes every entry in the library
out as text in a single call — that is the bootstrap from a
binary-only project to a reviewable one.

## Boundary with `pb-src-format`

The templates here are **canonical forms** — the minimum body that
ORCA accepts. Real codebases diverge from them in countless ways
(inherited base classes, instance variables, embedded controls,
non-default property values, …). When you need to *read* or *edit*
a real-world object, [`pb-src-format`](../pb-src-format/SKILL.md)
documents observed variants and points at the per-type wiki pages
under `docs/pb-source-format/`.

## Boundary with `pb-format`

`pb-scaffold` produces the **structural body** of a new entry. The
surface style (indent character, keyword case, operator spacing) is
[`pb-format`](../pb-format/SKILL.md)'s responsibility. Do not
pre-format the scaffold output to match a workspace style: import the
template as it is, and when the workspace opted into a house style
(it ships a `.pb-format.toml`), run `pb-format format` over the
resulting `.sr*` and re-import. The formatter is a separate, optional
tool; without it nothing here changes.

## Boundary with `appeon-query`

This skill answers "*how do I lay out a new object on disk so the
compiler accepts it*". For questions about the **PowerScript language
itself** — what `MessageBox()` takes as arguments, how
`DataWindow.Retrieve()` behaves, what events fire in what order —
use [`appeon-query`](../appeon-query/SKILL.md) to consult the Appeon
docs. Do not paste language reference into scaffolded bodies; keep
them empty and let the user fill in real logic.
