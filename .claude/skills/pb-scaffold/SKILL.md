---
name: pb-scaffold
description: Use this when you need to create a new PowerBuilder object from scratch — a window, userobject, function, datawindow, menu, or structure — and want a minimal body that the ORCA compiler accepts on the first try. Provides validated inline templates plus the rules for the one entry type the API cannot bootstrap (`application`). Pairs with `pb-workflow` (propagation into a `.pbl`) and `pb-src-format` (variants observed in real codebases).
---

# Scaffolding new PowerBuilder objects

Use this skill when you need to **create a new PB object**: emit the
minimal body for one of the supported entry types and feed it to
`pb_compile_entry_import` (or write it to a `.sr*` on disk).

## When to invoke this skill

- The user asks for a new window / userobject / function / datawindow /
  menu / structure (by name or by purpose).
- You are about to construct the `syntax` argument for
  `pb_compile_entry_import` from scratch.
- You are about to write a new `.sr*` file under `ws_objects/`.

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
4. Check the returned `success` flag. On failure, inspect the `errors`
   list — diagnostics include line + column.

## A note on the template surface style

The templates below use 4-space indent and lowercase PowerScript
keywords. That choice is **cosmetic to the skill**, not normative
for the codebase: it keeps the templates readable inline in this
Markdown file. When you scaffold into a workspace that ships a
`.pb-format.toml`, the body is automatically re-styled by the
formatter at the next `pb_edit_and_import` call (indent character,
keyword case, operator spacing) — see [`pb-format`](../pb-format/SKILL.md).
When the workspace does not ship a config, the template's surface
style is what lands on disk (same as today).

In either case, **do not hand-tune the template's surface to match
a target style** — emit the natural template and let the formatter
do its job.

The first line `$PBExportHeader$<name>.<ext>` is **optional** for the
ORCA API (entry name and type are passed as separate parameters) but
**required** if you write the body to a `.sr*` file on disk. Include
it by default: it costs nothing and keeps the body valid for both
code paths.

For the encoding rules that apply when writing to disk (the file
encoding follows the workspace `DefaultExportEncode` — UTF-8 BOM,
UTF-16BOM, or ANSI — always with CRLF), see
[`docs/pb-source-format/encoding.md`](../../../docs/pb-source-format/encoding.md).
When calling `pb_compile_entry_import`, pass a plain Python `str`
without BOM — ORCA is encoding-agnostic at the C ABI (strings cross as
wide chars). When you need the file *also* persisted on disk, prefer
`pb_edit_and_import` with the matching `source_encoding` parameter.

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
  [`docs/pb-source-format/window.md`](../../../docs/pb-source-format/window.md)
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
  [`docs/pb-source-format/datawindow.md`](../../../docs/pb-source-format/datawindow.md)
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
  app. The `pb-orca-mcp` test fixture `tests/fixtures/tiny_app/genapp.pbl`
  ships an empty application named `genapp` for exactly this purpose.

For a fresh project, the IDE path is the only practical workflow.
This skill does not attempt to script it.

## After the import succeeds

`pb_compile_entry_import` only writes the compiled object into the
`.pbl` binary. On git-tracked projects that mirror the `.pbl` into
`ws_objects/`, you also need to update the corresponding `.sr*` source
file so the next checkout sees the new object. That propagation is the
job of the [`pb-workflow`](../../../../pb-orca-mcp/.claude/skills/pb-workflow/SKILL.md)
skill in the sibling `pb-orca-mcp` repo. Hand off to it once the entry
exists in the `.pbl`.

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
[`pb-format`](../pb-format/SKILL.md)'s responsibility, applied at
import time by `pb_edit_and_import` when the workspace has a
`.pb-format.toml`. Do not pre-format the scaffold output to match
the workspace style — emit the template, let the formatter
normalize it on its way to the `.pbl`.

## Boundary with `appeon-query`

This skill answers "*how do I lay out a new object on disk so the
compiler accepts it*". For questions about the **PowerScript language
itself** — what `MessageBox()` takes as arguments, how
`DataWindow.Retrieve()` behaves, what events fire in what order —
use [`appeon-query`](../appeon-query/SKILL.md) to consult the Appeon
docs. Do not paste language reference into scaffolded bodies; keep
them empty and let the user fill in real logic.
