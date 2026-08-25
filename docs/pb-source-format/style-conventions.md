---
name: style-conventions
status: seeded
description: Style conventions for PowerScript source: indent, line endings, keyword case, operator spacing. The four invariants the pb-format tool normalizes when a workspace opts in with a .pb-format.toml, the dialects observed in the wild, and the config surface. Out of scope for the tool: blank-line policy, identifier naming, continuation alignment, .srd bodies (tracked under "Future invariants").
---

# Style conventions for PowerScript source

PowerBuilder has no official style guide and the PB IDE offers only a
few pointwise commands (Make Uppercase / Lowercase, Increase / Decrease
Indent). Real codebases diverge on the same handful of dimensions:
keyword case, indent character, spacing around operators, line endings
inside the body. This page documents the **invariants** a formatter can
normalize, the **dialects** observed in the wild, and the
**configuration surface** through which a workspace selects its target.

It is a cross-cutting page, peer to [`encoding`](encoding.md): that one
covers the file's envelope (BOM, CRLF, the `$PBExport*` header block),
this one covers the body inside it. Both apply to every entry type
except where called out.

## The tool

The engine is [`pb-format`](https://github.com/restoresrl/pb-format): a
standalone, token-based PowerScript formatter, CLI and library,
**independent of PowerBuilder and ORCA**: it works on source files on
disk, on any OS.

It is **optional**. This page describes what it does when a workspace
opts in; nothing here is a prerequisite for anything else in the dev
kit. The agent-side flow is the
[`pb-format`](../../skills/pb-format/SKILL.md) skill.

## Why this page exists

An agent writing PowerScript produces text that compiles but drifts in
style from what the IDE would emit. Each drift is individually
harmless; together they show up as noisy diffs (`If` vs `if`, `\t` vs
four spaces, `a=1` vs `a = 1`) that hide the real change during review.
This page is the human-readable spec of what gets normalized away.

## The four invariants

| # | Invariant | Config key | Values | Default |
|---|---|---|---|---|
| 1 | Indent unit | `indent` | `"tab"`, `"spaces:N"` (1 ≤ N ≤ 16) | `"tab"` |
| 2 | Line endings | `line_endings` | `"crlf"`, `"lf"` | `"crlf"` |
| 3 | Keyword case | `keyword_case` | `"lower"`, `"upper"`, `"preserve"` | `"lower"` |
| 4 | Operator spacing | `spaces_around_operators` | `true`, `false` | `true` |
| none | Input tab width | `tab_width` | positive int | `4` |

The defaults reflect the most common dialect across the corpus surveyed
during design (see [Dialects observed](#dialects-observed)). They are
sensible-but-arbitrary: pick a workspace setting and commit to it.

They apply to the **body** only. The `$PBExportHeader$` and
`$PBExportComments$` lines are preserved verbatim.

### Rule 1: Indent unit

Leading whitespace on each non-blank line is converted between the TAB
form and the `N`-space form:

- **`"tab"`**: one literal `\t` per level.
- **`"spaces:N"`**: `N` ASCII spaces per level.

This is a **1:1 substitution, not a re-indent.** The formatter does not
infer logical nesting: that needs a parser, and no maintained
PowerScript grammar exists (see
[Why token-based](#why-token-based-and-what-would-change-that)). A line
indented wrongly stays indented wrongly, in the other unit. `tab_width`
is the assumed input width when collapsing spaces to TAB; sub-unit
residue (a line indented by 6 with `tab_width = 4`) is preserved rather
than rounded away.

Mid-line whitespace is never rewritten: alignment inside `table(…)`
blocks, comment boxes and column layouts survives untouched. Only
leading whitespace is normalized.

### Rule 2: Line endings

Every line in the body is terminated with `0D 0A` (CRLF), including the
last. This is the same rule that governs the file envelope: see
[`encoding`](encoding.md). Any input newline style (`\r\n`, `\n`, `\r`)
is normalized on emit.

`"lf"` exists because the tool is general-purpose, not because PB wants
it. **Keep `"crlf"` for PowerBuilder.** LF inside a `.pbl` makes the
next export differ from the last commit on every line: a whole-file
phantom diff.

### Rule 3: Keyword case

PowerScript keywords are case-insensitive at compile time. The IDE's
Auto Case normalizes them as you type, but what is on disk reflects
whatever the original author wrote, or the PB version that last touched
the file. The formatter normalizes the casing of ~110 reserved words:

- Control flow: `if`, `then`, `else`, `elseif`, `end if`, `do`, `loop`,
  `while`, `until`, `for`, `to`, `step`, `next`, `choose`, `case`,
  `return`, `continue`, `exit`, `try`, `catch`, `finally`, `throw`,
  `throws`.
- Declarations: `subroutine`, `function`, `event`, `on`, `forward`,
  `prototypes`, `type`, `variables`, `global`, `shared`, `private`,
  `protected`, `public`, `constant`, `readonly`, `ref`,
  `autoinstantiate`, `alias`.
- Built-in types: `string`, `integer`, `int`, `long`, `unsignedlong`,
  `ulong`, `decimal`, `dec`, `real`, `double`, `boolean`, `date`,
  `time`, `datetime`, `blob`, `any`, `char`, `byte`.
- Reserved values: `true`, `false`, `null`, `super`, `this`, `parent`,
  `parentwindow`.
- Operators-as-words: `and`, `or`, `not`.

The list is deliberately conservative. Standard global objects
(`SQLCA`, `Message`, …) and built-in functions are **identifiers, not
keywords**, and are excluded on purpose: touching their case would risk
colliding with user-defined names.

**Never rewritten**, whatever the setting:

- Inside string literals (`"…"`).
- Inside line comments (`// …`) and block comments (`/* … */`).
- In a **member-access position**: the word immediately after `.` or
  `::`. A variable named `integer` accessed as `obj.integer` keeps its
  original casing, because semantically it is a member, not a type.

When the analysis cannot resolve "keyword, or identifier spelled like
one", the original casing is preserved. Conservative by default: never
rewrite when ambiguous.

### Rule 4: Spaces around binary operators

Binary operators get exactly one ASCII space on each side:

```text
=  +  -  *  /  ^  <  >  <=  >=  <>  +=  -=  *=  /=
```

**Left alone:**

- `&` at end of line, the PowerScript statement **continuation**
  marker. It must stay immediately before the newline; padding it would
  break the continuation.
- `,` and `;`: separators, not operators.
- `-` and `+` as **unary signs** (`-1`, `+x`). Binary and unary are told
  apart by the preceding token: after an operator, `(`, `[`, `{`, `,`,
  or at the start of a statement, the sign is unary.
- Anything inside a string literal or a comment, same restriction as
  Rule 3.

Note that PowerScript has no `&&` / `||`: `and` / `or` are words,
handled by Rule 3.

### Idempotency

`format(format(x)) == format(x)` for every input and configuration.
That is what makes it safe to run on every write: re-formatting an
already-formatted file is a no-op, so it never produces a diff of its
own.

## Dialects observed

Two coherent dialects show up across mature codebases: each internally
consistent, neither demonstrably better. The formatter does not pick
one; the workspace decides.

**Dialect A: "lowercase + Hungarian"**

- `keyword_case = "lower"` (`if`, `return`, `integer`).
- Local variables prefixed by type hint (`ll_count`, `ls_name`,
  `lb_flag`).
- TAB indent, CRLF, spaces around binary operators.

**Dialect B: "uppercase + plain"**

- `keyword_case = "upper"` (`IF`, `RETURN`, `INTEGER`).
- Local variables without a type-hint prefix.
- TAB indent, CRLF, spaces around binary operators.

The two dimensions are **independent**: "lowercase + plain" and
"uppercase + Hungarian" both occur, just less often than A or B.

Identifier naming is **not normalized** (see
[Future invariants](#future-invariants)): renaming a local touches every
reference, which makes it a semantic rewrite, not a textual one.

## Configuration: `.pb-format.toml`

Discovery walks **upward** from each source file until a config is
found: the rule Prettier and dprint use. Put it at the workspace root.

```toml
[style]
indent = "tab"                 # "tab" | "spaces:N"  (1 <= N <= 16)
keyword_case = "lower"         # "lower" | "upper" | "preserve"
line_endings = "crlf"          # "crlf" | "lf" — keep crlf for PB
spaces_around_operators = true # true | false
tab_width = 4                  # input tab width when collapsing spaces -> tab
```

Unknown keys under `[style]` are ignored, so a config written for a
newer version stays readable by an older tool. An empty file is valid
and means "the defaults, deliberately".

To generate a starter config from an existing codebase:

```text
pb-format detect <workspace>
```

It samples `.sr*` files under the path (50 by default), computes the
frequency of each dimension's variants, and writes the winning choices
with explanatory comments. Review, adjust, commit.

**Absence of a config means the user has not opted in.** The dev kit
treats "no `.pb-format.toml` anywhere up the tree" as "do not format",
so adding the tool to a workspace changes nothing until someone puts a
config in it.

## How the formatted body reaches the `.pbl`

The formatter only ever touches files on disk. Getting the result into
the library is ORCA's job, through
[`pb-orca-mcp`](https://github.com/restoresrl/pb-orca-mcp), and the
order matters:

```text
pb_object_export_file   -> ORCA writes the .sr*
edit the file
pb-format format <file> -> normalize the body in place
pb_object_import_file   -> compile into the .pbl (and update the
                           text projection in the same call)
```

Formatting **before** the import is what makes it stick: ORCA stores
the source text as given and re-exports it byte-stably, so the
normalized form is what ends up in both the `.pbl` and the text
projection. Formatting the text files *without* importing leaves the
`.pbl` stale: a commit that reviews clean and builds old.

For CI or a pre-commit hook no ORCA is involved: `pb-format check`
exits non-zero on drift.

## Future invariants

Known-but-deferred, in rough order of cost-to-value:

- **Blank-line policy** between methods, events and declarations.
  Mostly cosmetic; codebases disagree on one-vs-two-vs-three. Tractable
  token-side.
- **Continuation alignment**: where a line indents after a trailing
  `&`. Two patterns observed: "current indent + one unit", and "aligned
  with the first token of the previous line". Needs column tracking on
  top of the token stream.
- **Real re-indentation** from logical nesting, rather than the 1:1
  substitution of Rule 1. Needs an AST.
- **Identifier naming** (Hungarian prefixes, leading underscore for
  private members): out of formatter scope entirely. Renaming touches
  references, so it is a semantic refactor; it belongs in a linter.
- **`.srd` (DataWindow) bodies**: a tabular DSL, not PowerScript. The
  tool recognizes the extension and skips it. A future pass could
  normalize `column(…)` indentation, but only on real demand.

When a deferred invariant graduates, it appends a new Rule to this page
and a new key under `[style]`. Existing keys never change semantics:
only new ones are added.

## Why token-based, and what would change that

A real parser would allow much more (proper re-indent, alignment,
identifier rewrites), but no stable, maintained open-source PowerScript
grammar exists today. A token-based normalizer is what can ship safely:
it needs no grammar, so it cannot choke on syntax a grammar does not
cover; it owns only the invariants that genuinely do not need an AST;
and it is small enough to audit in an afternoon.

When a maintained grammar lands, an AST-aware layer can slot in behind
the same entry point without changing anything on this page. The
trigger to revisit: a grammar project cutting a real 1.0 release, or
three concrete cases the token-based approach cannot resolve.

## Variants observed

(Empty for now; this page is `seeded`. Promote it to `populated` once
real-world deviations from the rules above get recorded during review
sessions.)

## Open questions

- Do any workspaces genuinely need `keyword_case = "preserve"` because
  several dialects coexist in one codebase? If so, the option is
  load-bearing; otherwise it can be dropped.
- Should `pb-format detect` propose `"preserve"` on a roughly even
  split, or pick the majority and let the user override? It currently
  picks the majority; an even split is arguably itself the finding.
- Is there a measurable population of workspaces where
  `DefaultExportEncode != "UTF-8"` and non-ASCII characters interact
  badly with keyword recognition? The lexer treats strings as opaque,
  but the recognizer is ASCII-aware.

## Cross-references

- [[index]]: wiki entry point.
- [[encoding]]: the file envelope this body sits inside:
  `DefaultExportEncode`, CRLF, `$PBExportHeader$`.
- [`pb-format`](../../skills/pb-format/SKILL.md) skill, the agent-side
  flow: when to format, how to detect a dialect, when to leave style
  alone.
- [`pb-src-format`](../../skills/pb-src-format/SKILL.md) skill, the
  writing flow, which owns structure and delegates style here.
- [`pb-format`](https://github.com/restoresrl/pb-format): the tool.
