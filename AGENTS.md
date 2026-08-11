# AGENTS.md: pb-ai-code

Instructions for AI coding agents working on **this repository's own
content** — the [AGENTS.md](https://agents.md) cross-tool format, read
by Codex, Cursor, Copilot, Zed, Claude Code and others. It is not the
guide for *using* the dev kit on a PowerBuilder project: that is the
[README](README.md) and [`docs/install.md`](docs/install.md).

## Context

`pb-ai-code` is an **agentic dev kit for PowerBuilder**: skills,
ingested Appeon documentation, a reverse-engineered source-format wiki,
an antipattern catalog, and slash commands that let a coding assistant
do design, coding, review and debugging work on a PB codebase.

Its primary use case is **code review and refactoring of legacy PB
codebases**. Greenfield PowerBuilder development is rare; the realistic
audience is people maintaining decades-old monolithic applications who
need to read, understand, refactor and extend existing code.

It sits **above** [`pb-orca-mcp`](https://github.com/restoresrl/pb-orca-mcp),
which exposes PowerBuilder's ORCA API as MCP tools. Every action on a
`.pbl` goes through that server.

Audience: anyone developing PowerBuilder who wants an agentic workflow.
Any assistant, any model.

## Repository layout

Canonical, agent-neutral, committed:

```text
skills/<name>/SKILL.md    Agent Skills (agentskills.io) format
commands/<name>.md        slash-command wrappers — thin, they delegate
                          to the skill of the same name
harness/<harness>/        per-assistant config (e.g. Claude Code
                          permissions)
docs/                     the knowledge base (see below)
tools/                    two local Python tools
scripts/install-skills.ps1
.mcp.json                 the one required MCP server, wired through uvx
```

`.mcp.json` deliberately carries only `pb-orca`. The optional Appeon index
needs a Python environment and a database that a fresh clone does not have, so
it is documented in [`docs/install.md`](docs/install.md) rather than shipped —
a committed config should not contain an entry that cannot start.

Generated, **gitignored**, never hand-edited: `.claude/`, `.cursor/`,
and anything else an install produces. The installer materializes the
canonical files into the layout a given assistant reads. **Edit
`skills/` and `commands/`, then re-run
`scripts/install-skills.ps1`** — a fix applied to a generated copy is
lost on the next install.

`docs/` holds three things: `pb-source-format/` (a wiki on the textual
layout of each `.sr*` entry type, grown incrementally as cases are
met), `pb-antipatterns/` (PB-specific hazards with fixes, consulted
during review), and `appeon-index/` (setup for the local Appeon doc
index).

## Architectural constraints

- **No PowerScript syntax lives here.** This is a repository of
  workflow, knowledge and orchestration. Snippets in skills and docs are
  illustrative, never executed. Anything that has to *understand* the
  language belongs in another tool.
- **No reimplementation of ORCA primitives.** If something is missing,
  it gets added to `pb-orca-mcp`, not duplicated here. The boundary is
  written down in that repository's `docs/integrating.md`, which is the
  contract this project is built against.
- **No PowerScript formatting either.** Style normalization belongs to
  [`pb-format`](https://github.com/restoresrl/pb-format), a separate
  optional tool. This repository documents the rules
  (`docs/pb-source-format/style-conventions.md`) and the workflow (the
  `pb-format` skill); it does not implement them.
- **Never hand-assemble a `.sr*` file.** ORCA writes those files. The
  loop is `pb_object_export_file` → edit the file → `pb_object_import_file`.
  Anything in a skill that tells the reader to build a header block, pick
  a BOM, or propagate a change to a second file by hand is a bug: the
  server does that in the same call.
- **No assumptions about the developer's machine.** Skills and tools
  must work on any Windows machine with a PB IDE. No user-specific
  paths, no dependency on two repositories being sibling directories.
- **No vendor-internal references.** No company-specific project names,
  library names, or personal paths. A *pattern* observed in a private
  codebase can be an inspiration, but it has to be restated in
  vendor-neutral terms.
- **Optional dependencies stay optional.** The Appeon index and
  `pb-format` are both optional. A skill that needs one says so and
  degrades; it never makes the core flow conditional on them.

## Writing skills

- **Agent-neutral.** No "Claude", no client-specific tool names, no
  assumption that skills are auto-discovered rather than read from a
  path. Interactive prompts are quoted in English, with the standing
  note that the agent speaks the user's language.
- **The skill is the content, the command is sugar.** A flow lives in
  `skills/<name>/SKILL.md`; `commands/<name>.md` is a few lines that
  say "read that skill and follow it". Do not duplicate the flow into
  the command.
- **Frontmatter matters.** `name` plus a `description` that says *when*
  to use the skill — that description is what a discovery mechanism
  matches on. Bump `metadata.version` when behaviour changes.
- **Cross-link with relative paths.** `../other-skill/SKILL.md`,
  `../../docs/...`. They resolve identically in the canonical layout and
  in an install, which is why both use sibling directories.
- **Cross-repository links use URLs**, never `../../pb-orca-mcp/...`. A
  relative path out of the repository only works on a machine where both
  checkouts happen to be siblings.
- **State the failure modes.** A skill that only describes the happy
  path is half written. Both response shapes (`error` envelope vs
  `success: false` with compile diagnostics), what a failed compile
  leaves on disk, and what the tool does not guarantee.

## Python code

If a change touches `tools/`: Python 3.10+, `from __future__ import
annotations`, full type hints, `mypy --strict`, `ruff` with line-length
100, src-layout, `hatchling`. Tests with `pytest` — the tests here cover
parsing and orchestration; anything needing a real PowerBuilder lives in
`pb-orca-mcp`.

**Run all four before committing — CI runs exactly these.** The third is
the one that gets forgotten: in the sibling repository it had been failing
for three tagged releases while `ruff check` passed, because nobody ran it
and nobody looked at CI.

```pwsh
pytest                                                    # incl. the link tests
ruff check .
ruff format --check tools tests                           # the forgotten one
mypy tools/pb-source-analyzer/src tools/pb-appeon-index/src
```

And **look at CI after you push** (`gh run list --limit 1`). A green local
run is evidence about one machine.

`pytest` installs the bundle into a temporary directory, for both harness
layouts, and fails on a dead relative link. That check needs PowerShell; it
skips without one, which is why CI runs on Windows.

## Conventions

- **English** for code, comments, docs, commit messages and skill
  content. The audience is international.
- **Markdown**: hard-wrap prose at ~72 characters (the files are read as
  much in a terminal as in a browser), fenced code blocks get a
  language, tables get one space of padding per pipe.
- **No `Co-Authored-By:` trailers** in commits.
- **Never `git commit` or `git push` without being asked.**

## When something in the knowledge base turns out to be wrong

Fix the page and say what changed. These pages are observations, not a
spec — `docs/pb-source-format/` pages carry a `status` field (`stub` →
`seeded` → `populated`) and an "Open questions" section precisely
because they are incomplete. Moving a question into an answer, with the
evidence, is a normal contribution. Silently leaving a page that
contradicts the tools is not.
