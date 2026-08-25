---
name: pb-format
description: Use this when you need to apply, generate, or verify PowerScript style conventions (indent, keyword case, operator spacing, line endings) on a .sr* source — either as a step in the edit loop before importing, or after the fact over a whole library. Owns the .pb-format.toml config contract and the boundary between style normalization (this skill) and structural format (pb-src-format). The engine is pb-format, a separate, optional CLI: everything here degrades to a no-op when it is not installed.
metadata:
  version: "2.1.0"
---

# PowerScript style formatting

This skill is about **how PowerScript looks on disk** — indent
character, keyword case, spacing around operators, line endings —
separately from **where things go in the file**, which belongs to
[`pb-src-format`](../pb-src-format/SKILL.md), and separately from
**what the code does at runtime**, which belongs to
[`appeon-query`](../appeon-query/SKILL.md).

## The tool

The engine is [`pb-format`](https://github.com/restoresrl/pb-format):
a standalone, token-based formatter for PowerScript, shipped as a CLI
and an importable library. It is **independent of PowerBuilder and
ORCA** — it works purely on source files on disk, on any OS.

That independence is the design: nothing in this dev kit and nothing
in `pb-orca-mcp` parses PowerScript, and the formatter does not talk
to a `.pbl`. They meet on a file.

```pwsh
uv tool install git+https://github.com/restoresrl/pb-format@v0.1.0
```

Not on PyPI yet, hence the repository URL.

**It is optional, and its absence is not an error.** If
`pb-format --version` does not resolve, say so once and carry on
without it: an unformatted body compiles exactly as well as a
formatted one. Never make a fix conditional on the formatter being
present, and never hand-format a body to compensate — see
[When to leave style alone](#when-to-leave-style-alone).

## When to invoke this skill

- **In the edit loop**, after editing an exported `.sr*` and before
  importing it, when the workspace ships a `.pb-format.toml` (which is
  how a user opts in). One command, then the import proceeds normally.
- **After the fact**, to re-format existing entries without changing
  their semantics. `pb-format format <dir>` handles a whole tree; the
  `/pb-format` flow adds the confirm-and-reimport loop that makes the
  change reach the `.pbl`.
- When the user asks "what is the style of this codebase?" or "set up
  a `.pb-format.toml` for me" — see
  [Detecting the dialect](#detecting-the-dialect).
- When a review finding would be a **pure style change** (an
  uppercase → lowercase keyword sweep, say). Flag it as a candidate
  for the formatter instead of a per-entry fix: it handles the whole
  sweep in one pass and produces a reviewable diff.

## What it normalizes

Four invariants, applied to the **body** of an entry. The
`$PBExportHeader$` / `$PBExportComments$` lines are preserved
verbatim. Full specification:
[`docs/pb-source-format/style-conventions.md`](../../docs/pb-source-format/style-conventions.md).

| # | Invariant | Config key | Values | Default |
|---|---|---|---|---|
| 1 | Indent unit | `indent` | `"tab"`, `"spaces:N"` (1 ≤ N ≤ 16) | `"tab"` |
| 2 | Line endings | `line_endings` | `"crlf"`, `"lf"` | `"crlf"` |
| 3 | Keyword case | `keyword_case` | `"lower"`, `"upper"`, `"preserve"` | `"lower"` |
| 4 | Operator spacing | `spaces_around_operators` | `true`, `false` | `true` |
|   | Input tab width | `tab_width` | positive int | `4` |

Two properties worth relying on:

- **Indent is a 1:1 substitution, not a re-indent.** It converts
  between TAB and N-space forms; it does not infer logical nesting
  (that needs an AST). Sub-unit residue is preserved.
- **It is idempotent**: `format(format(x)) == format(x)` for every
  input and configuration. That is what makes it safe to run on every
  write.

Keep `line_endings = "crlf"` for PB IDE parity. LF exists because the
tool is general-purpose, not because PB wants it — LF inside a `.pbl`
produces a phantom diff over the whole file.

Out of scope, deliberately: no re-indentation, no blank-line policy,
no continuation-line alignment, no identifier renaming (that is a
semantic rewrite touching every reference), and no `.srd` DataWindow
source (a tabular DSL, not PowerScript).

## Configuration: `.pb-format.toml`

Drop it at, or above, the source directory. Discovery walks upward
from each file — the same rule Prettier and dprint use. With no config
anywhere, the tool uses its built-in defaults; **this skill treats
"no config" as "the user has not opted in" and skips formatting
entirely.**

```toml
[style]
indent = "tab"                 # "tab" | "spaces:N"  (1 <= N <= 16)
keyword_case = "lower"         # "lower" | "upper" | "preserve"
line_endings = "crlf"          # "crlf" | "lf" — keep crlf for PB
spaces_around_operators = true # true | false
tab_width = 4                  # input tab width when converting spaces -> tab
```

Unknown keys under `[style]` are ignored, so a newer config stays
readable by an older tool. An empty file is valid and means "the
defaults, deliberately".

## Entry point 1 — in the edit loop

The edit loop is
`pb_object_export_file` → edit the file → `pb_object_import_file`
(see [`pb-apply-plan`](../pb-apply-plan/SKILL.md)). The formatter
slots in as one step between the edit and the import:

```pwsh
pb-format format <path-to-the-exported-.sr*>
```

Then import as usual. Notes:

- The tool splits the export header from the body, normalizes only the
  body, and round-trips the file's BOM-detected encoding (UTF-8 or
  UTF-16 LE, with or without BOM) and its line endings. It will not
  break what ORCA wrote.
- Add `--dry-run` to see what would change without writing.
- Treat the body you produce as *semantically* correct PowerScript and
  let the formatter make it *stylistically* consistent. Do not do both
  jobs by hand.
- Formatting before the import is what makes it stick: ORCA stores the
  source text as given, and re-exports it byte-stably, so the
  normalized form is what lands in both the `.pbl` and the text
  projection.

## Entry point 2 — after the fact, over a set of entries

For re-formatting entries **already in a library**, the sweep has to
go through ORCA to reach the `.pbl`; formatting the text files alone
would leave the binary stale. The flow, which the `/pb-format` command
wraps:

1. `pb_library_export_sources(lib_path, dest_dir=<scratch>)` writes every
   entry to a directory outside the project. It must not create or replace
   `ws_objects/`; the PowerBuilder IDE owns that projection.
2. `pb-format check <scratch>` reports which files would change and exits
   non-zero if any would. This is the budget estimate before committing to a
   sweep.
3. `pb-format format <scratch>` rewrites only the exported scratch files.
4. For each changed file, use `pb_object_import_file` to land it in the
   `.pbl`, check the compile result, and require PowerBuilder's projection
   sync to succeed.

A read-only `pb-format check` can run in a pre-commit hook or CI and exits 1
on drift. Do not run `format` directly over `ws_objects/`; that would modify
the projection without changing the `.pbl` through ORCA.

## Entry point 3 — writing a file with no PB in the loop

`pb-format write` builds a well-formed `.sr*` from a body: canonical
`$PBExportHeader$` block, CRLF, and the BOM for the workspace
encoding.

```pwsh
pb-format write out\n_cst_order.sru --entry-name n_cst_order --ext sru `
    --encoding UTF-8 --comments "order NVO" --body-file body.txt
```

`--encoding` takes the three values PB accepts in the `.pbw`
`DefaultExportEncode` setting (`UTF-8`, `UTF-16BOM`, `ANSI`); the body
comes from `--body-file` or stdin.

**Prefer not to need this.** When PB is available, a brand-new entry
should land through `pb_compile_entry_import` with the body as a
string: the import writes the text projection for you, so ORCA — not
this tool — produces the file, which is the one guarantee worth
keeping. Reach for `pb-format write` when there is no PB in the loop
at all: preparing sources on a machine without PowerBuilder, in CI, or
staging a file for someone else to import.

## Detecting the dialect

When a workspace has no `.pb-format.toml`:

```pwsh
pb-format detect <workspace>
```

It samples `.sr*` files under the path (default 50, `--max-files` to
change), computes the frequency of each dimension, and writes a
starter `.pb-format.toml` with the winning choice for each plus
explanatory comments. Review and commit it.

Never invent a config silently — generating one is an opt-in the user
makes. When the split on a dimension is close to even, that is itself
the finding: a codebase with genuinely mixed casing may want
`keyword_case = "preserve"` rather than a sweep. Say so instead of
picking for them.

## When to leave style alone

- **A pure semantic refactor** (rename, extract function, change a
  signature). Style is a side effect there; do the refactor and let
  the formatter clean the surface afterwards.
- **A workspace with no `.pb-format.toml`.** No config means no
  opt-in. Formatting anyway produces a diff the user did not ask for.
- **A library flagged `outside_source_tree`** by
  `pb_workspace_info` — a vendored snapshot or third-party component.
  A style sweep there is guaranteed to be overwritten, and it makes
  the next dependency update a merge conflict.
- **`.srd` (DataWindow) entries.** The formatter skips them; rely on
  [`pb-src-format`](../pb-src-format/SKILL.md) and the per-entry-type
  wiki pages.
- **A mid-migration codebase** where per-file variance is deliberate.
  `keyword_case = "preserve"` normalizes the other three dimensions
  and leaves casing alone.

## Boundary with `pb-src-format`

| Question | Skill |
|---|---|
| Where does the `forward prototypes` block go? | [`pb-src-format`](../pb-src-format/SKILL.md) |
| What does `$PBExportHeader$` look like? | [`pb-src-format`](../pb-src-format/SKILL.md) |
| Does `if` go before or inside the `function` declaration? | [`pb-src-format`](../pb-src-format/SKILL.md) |
| `IF` or `if`? | this skill |
| Tab or spaces? | this skill |
| `a = b` or `a=b`? | this skill |

The rule: **structural** (positions of blocks, headers, terminators) →
`pb-src-format`; **stylistic** (how individual tokens render) → here.

## Boundary with `pb-scaffold`

[`pb-scaffold`](../pb-scaffold/SKILL.md) provides minimal templates
for new entries, in a readable baseline style. Do not hand-tune a
template's surface to match a target workspace: emit the template, and
if the workspace opted into a style, run the formatter over the file
before importing. Where the workspace has no config, the template's
own style is what lands, and that is fine.

## Why token-based, and what would change that

A real PowerScript parser would allow much more — proper re-indent,
continuation alignment, identifier rewrites — but no stable,
maintained open-source PowerScript grammar exists today. A
token-based normalizer is what can ship safely: it needs no grammar,
so it cannot choke on syntax a grammar does not cover; it owns only
the invariants that genuinely do not need an AST; and it is small
enough to audit in an afternoon. When a maintained grammar lands, an
AST-aware layer can slot in behind the same entry point without
changing anything written here.

## Cross-references

- [`docs/pb-source-format/style-conventions.md`](../../docs/pb-source-format/style-conventions.md) —
  the rule spec, the dialects observed in the wild, and the deferred
  invariants.
- [`docs/pb-source-format/encoding.md`](../../docs/pb-source-format/encoding.md) —
  the on-disk contract the formatter round-trips.
- [`pb-src-format`](../pb-src-format/SKILL.md) — structural format
  rules; the sibling layer of this skill.
- [`pb-scaffold`](../pb-scaffold/SKILL.md) — emits new entry bodies.
- [`pb-apply-plan`](../pb-apply-plan/SKILL.md) — the edit loop this
  skill plugs into.
- [`pb-format`](https://github.com/restoresrl/pb-format) — the tool.
- [`pb-orca-mcp`](https://github.com/restoresrl/pb-orca-mcp) — the
  ORCA bridge that gets the formatted file into the `.pbl`.
