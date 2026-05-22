---
name: style-conventions
status: seeded
description: Style conventions for PowerScript source — indent, keyword case, operator spacing, line endings. Vendor-neutral baseline + the four invariants the planned formatter normalizes when a workspace ships a `.pb-format.toml`. Out of scope for the wiki: blank-line policy, identifier naming, continuation alignment (tracked under "Future invariants").
---

# Style conventions for PowerScript source

PowerBuilder has no official style guide, no public formatter, and the
PB IDE itself only offers a handful of pointwise commands (Make
Uppercase / Lowercase, Increase / Decrease Indent). Real codebases
diverge on the same handful of dimensions: keyword case, indent
character, spacing around operators, line endings inside the body.
This page documents the **invariants** the planned formatter will
normalize, the **dialects** observed in the wild, and the
**configuration surface** through which a workspace selects its target.

It is a Layer 2 cross-cutting page, peer to
[`encoding`](encoding.md). Both apply to every entry type
(`.sra`/`.srw`/`.sru`/`.srf`/`.srd`/`.srm`/`.srs`/`.srq`/`.srj`)
except where called out explicitly.

## Why this page exists

An agent writing PowerScript today produces text that compiles but
drifts in style from what the PB IDE would emit. Each drift is
individually harmless; collectively they show up as noisy diffs
("`If`" vs "`if`", `\t` vs `    `, `a=1` vs `a = 1`) that obscure real
changes during review. The formatter's job is to make those drifts
disappear at write-time. This page is the human-readable spec the
formatter implements.

## The four MVP invariants

| # | Invariant | Default | Configurable |
|---|---|---|---|
| 1 | Indent character | TAB | `"tab"` or `"spaces:N"` (N ∈ {2, 4}) |
| 2 | Body line endings | CRLF | locked — PB IDE rejects LF-only files |
| 3 | Keyword case | lowercase | `"lower"`, `"upper"`, `"preserve"` |
| 4 | Spaces around binary operators | enabled | `true` / `false` |

The defaults reflect the most common dialect across the corpus
surveyed during design (see [Dialects observed](#dialects-observed)).
They are sensible-but-arbitrary; pick a workspace setting and commit
to it.

### Rule 1 — Indent character

Leading whitespace on each non-blank line is exactly one of:

- **`"tab"`** — one literal `\t` per nesting level.
- **`"spaces:N"`** — `N` ASCII spaces per nesting level (`N = 2` or `4`).

The formatter computes nesting depth from the current source's
leading whitespace (mixed-tab-and-spaces is normalized as if `\t` =
`N` spaces) and re-emits the canonical form. It is idempotent: a
second pass produces the same bytes as the first.

Mid-line tabs (alignment inside `table(…)` blocks in `.srd`, comment
boxes) are **not** rewritten. Only leading whitespace is normalized.

### Rule 2 — Body line endings

Every line in the PowerScript body is terminated with `0D 0A` (CRLF),
including the last line. This is the same rule that already governs
the file header and the `$PBExportComments$` block — see
[`encoding`](encoding.md). The formatter normalizes any input
newline style (`\r\n`, `\n`, `\r`) to CRLF before emit.

This rule is **locked**: PB IDE rejects LF-only files outright. No
`line_endings = "lf"` option exists.

### Rule 3 — Keyword case

PowerScript keywords are case-insensitive at compile time; the IDE's
"Auto Case" feature normalizes them visually as you type, but the
on-disk casing reflects whatever the original author wrote (or the PB
version that last touched the file). The formatter normalizes the
casing of a fixed list of ~100 PowerScript keywords:

- Control flow: `if`, `then`, `else`, `elseif`, `end if`, `do`,
  `loop`, `while`, `until`, `for`, `to`, `step`, `next`,
  `choose case`, `case`, `case else`, `end choose`, `return`,
  `continue`, `exit`, `try`, `catch`, `finally`, `end try`, `throw`,
  `throws`.
- Declarations: `subroutine`, `function`, `event`, `on`, `forward`,
  `prototypes`, `end prototypes`, `type`, `end type`, `variables`,
  `end variables`, `global`, `shared`, `private`, `protected`,
  `public`, `constant`, `readonly`, `ref`.
- Built-in types: `string`, `integer`, `int`, `long`, `unsignedlong`,
  `ulong`, `decimal`, `dec`, `real`, `double`, `boolean`, `date`,
  `time`, `datetime`, `blob`, `any`, `char`, `byte`.
- Reserved values: `true`, `false`, `null`, `super`, `this`,
  `parent`, `parentwindow`.
- Operators-as-words: `and`, `or`, `not`.

**Restrictions** — the formatter never modifies keyword-looking text
inside:

- String literals (`"…"`).
- Line comments (`// …` to end of line).
- Block comments (`/* … */`).
- Member access positions (identifier right after a `.`). A variable
  named `integer` accessed as `obj.integer` keeps the original casing
  because semantically it is a member, not a type.

When the analysis cannot resolve "is this a keyword or an identifier
named like one", the formatter **preserves the original casing**.
Conservative-by-default: never rewrite when ambiguous.

### Rule 4 — Spaces around binary operators

Binary operators get one ASCII space on each side. Affected operators:

```
= + - * / < > <= >= <> ^ && ||
```

**Exclusions**:

- `&` at end of line is the PowerScript **statement continuation**
  marker. The formatter leaves it alone (it must remain immediately
  before the newline; spacing around it would break continuation).
- `-` and `+` as **unary signs** (e.g. `-1`, `+x`) are not rewritten.
  The formatter distinguishes binary vs unary by looking at the
  preceding token: if it is an operator, `(`, `,`, `[`, or the start
  of a statement, the sign is unary.
- Operators inside string literals or comments — same restriction as
  Rule 3.

Idempotency: applying Rule 4 twice gives the same output as once.

## Dialects observed

Two coherent dialects show up across mature codebases — each
internally consistent, neither demonstrably better. The formatter
does not pick one; it lets the workspace decide via configuration.

**Dialect A — "lowercase + Hungarian"**

- `keyword_case = "lower"` ("`if`", "`return`", "`integer`").
- Local variables prefixed by type-hint (`ll_count`, `ls_name`,
  `lb_flag`).
- TAB indent, CRLF.
- Spaces around all binary operators.

**Dialect B — "uppercase + plain"**

- `keyword_case = "upper"` ("`IF`", "`RETURN`", "`INTEGER`").
- Local variables without type-hint prefix.
- TAB indent, CRLF.
- Spaces around all binary operators.

The two dimensions (`keyword_case` and identifier-naming) are
**independent**. A codebase may pick lowercase + plain or uppercase +
Hungarian; both are observed but less common than A or B.

Identifier naming is **not normalized by the formatter** (see
[Future invariants](#future-invariants)) — renaming a local variable
touches every reference and is a semantic rewrite, not a textual one.

## Configuration: `.pb-format.toml`

The formatter reads `.pb-format.toml` from the workspace root
(walking up from the source path). Minimal schema:

```toml
[style]
indent = "tab"              # "tab" | "spaces:2" | "spaces:4"
keyword_case = "lower"      # "lower" | "upper" | "preserve"
line_endings = "crlf"       # locked
spaces_around_operators = true
```

To generate a starter `.pb-format.toml` from an existing codebase:

```
pb-format detect <workspace>
```

The CLI samples N `.sr*` files (default N = 50), computes the
frequency of each dimension's variants, and writes the winning
choices to `.pb-format.toml` with explanatory comments. Edit, commit,
done.

If no `.pb-format.toml` exists in the workspace tree, the formatter
defaults to **no-op** (= the body passes through unchanged, matching
today's behavior of `pb_edit_and_import`). This is the "auto" mode
of `pb_edit_and_import`'s `format` parameter.

## Integration with `pb_edit_and_import`

The MCP tool `pb_edit_and_import` (sibling `pb-orca-mcp`) gains a
`format` parameter with three values:

- `"auto"` (default) — apply normalization iff `.pb-format.toml`
  exists for the workspace. Zero breaking change for workspaces that
  don't opt in.
- `True` — force normalization. Use hard-coded defaults if config
  absent.
- `False` — skip normalization. Body passes through (the current
  behavior).

The normalizer runs **before** the existing header/comment
normalization (`_strip_export_headers`, `_escape_pb_comment`,
`_normalize_pb_comment_newlines`). The output of the body normalizer
feeds straight into the existing pipeline; nothing about
header/comment handling changes.

For the on-disk reformat workflow (re-format an existing entry
without re-importing), see the [`pb-format`](../../.claude/skills/pb-format/SKILL.md)
skill and the `/pb-format` slash command.

## Future invariants

Tracked here as known-but-deferred, in rough order of cost-to-value:

- **Blank-line policy** between methods / events / forward
  declarations. Mostly cosmetic; codebases disagree on 1-vs-2-vs-3
  blank lines. Tractable token-side once the MVP normalizer ships.
- **Continuation alignment** — when a line ends with `&`, where the
  continuation indents. Two observed patterns: "next line at
  current-indent + 1 tab", "next line aligned with the first token
  of the previous line". Requires column tracking on top of token
  stream.
- **Identifier naming** (Hungarian prefix, leading underscore for
  private members, etc.) — out of formatter scope. Renaming touches
  references, which is a semantic refactor. Belongs in a separate
  `pb-lint` skill, not here.
- **`.srd` (DataWindow) body** — DataWindow source is a tabular DSL,
  not PowerScript. The formatter recognizes the extension and
  **skips with a log line**. A future pass could normalize
  `column(…)` block indentation, but only when there is real demand.

When a future invariant graduates from "deferred" to "in scope", it
appends a new Rule N to this page and a new key under `[style]`.
Existing keys never change semantics — only new ones are added.

## Variants observed

(Empty for now; this page is `seeded`. Promote to `populated` once
the formatter ships and real-world deviations from the rules above
get recorded by `pb-apply-plan` / `pb-format`.)

## Open questions

- Do any workspaces in the wild require `keyword_case = "preserve"`
  (i.e. coexisting dialects within one codebase that the formatter
  must respect rather than normalize)? If yes, the `"preserve"`
  option in Rule 3 is load-bearing; if no, it can be dropped.
- Is there a measurable population of `.pbw` files with
  `DefaultExportEncode != "UTF-8"` where the formatter's
  string-literal detection needs to handle non-ASCII characters
  differently? The lexer treats strings as opaque byte sequences,
  but Rule 3's keyword recognizer needs to be ASCII-aware.
- Should `pb-format detect` propose `keyword_case = "preserve"` when
  it sees a roughly 50/50 split in the corpus, or pick the majority
  and let the user override?

## Cross-references

- [[index]] — wiki entry point.
- [[encoding]] — `DefaultExportEncode` + CRLF + `$PBExportHeader$`
  rules. The body normalizer runs on top of the same line-ending
  contract.
- `[[pb-format]]` skill — the consumer-side flow that drives the
  formatter (detect, format, check).
- `[[pb-src-format]]` skill — the writing skill that now delegates
  style normalization to the formatter downstream.
- `[[pb-workflow]]` in sibling `pb-orca-mcp` — the propagation
  layer; the formatter lives inside `pb_edit_and_import`, which
  `pb-workflow` is the documentation of.
