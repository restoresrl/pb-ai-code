# pb-ai-code

An agentic dev kit for **PowerBuilder**: skills, ingested
documentation, and named flows that let an AI coding assistant read,
review, refactor and extend a real PB codebase.

Where [`pb-orca-mcp`](https://github.com/restoresrl/pb-orca-mcp)
exposes PowerBuilder's ORCA API as MCP tools — the engine —
`pb-ai-code` is the layer above it: what to do with those tools, in
what order, and what to know before touching a 25-year-old monolith.

It is **assistant-agnostic and model-agnostic by construction.** The
skills are plain Markdown in the [Agent Skills](https://agentskills.io)
`SKILL.md` format, they name MCP tools rather than client features, and
an installer materializes them into whatever directory your assistant
reads. Nothing here assumes a particular vendor.

## What it does

The primary use case is **code review and refactoring of legacy
PowerBuilder**. Greenfield PB development is rare; the realistic
audience is people maintaining decades-old monolithic applications.

The main flow, `/pb-review`, goes: frame the scope with you → build a
*budgeted* context pack from the PBLs (you cannot read a monolith all
at once) → state its understanding and wait for you to confirm it →
review against a catalog of PB-specific hazards → write a plan file and
a CHANGELOG entry that outlive the session → apply the fixes one at a
time, each with a visible diff and a compile check.

Two properties it is built around: **it stops before spending your
budget**, and **its output persists**. A plan file can be edited by
hand, committed, and resumed by a different assistant days later.

## Contents

| | |
| --- | --- |
| [`skills/`](skills/) | The flows. `pb-review` (structured review), `pb-apply-plan` (the edit loop), `pb-context-build` (scoped context from a monolith), `pb-scaffold` (new objects), `pb-src-format` (the `.sr*` format), `pb-format` (style), `appeon-query` (language lookups). |
| [`commands/`](commands/) | Slash-command wrappers — thin; each delegates to the skill of the same name. |
| [`docs/pb-source-format/`](docs/pb-source-format/) | A wiki on the textual layout of each `.sr*` entry type. No upstream spec exists, so it is reverse-engineered and grows as cases are met. |
| [`docs/pb-antipatterns/`](docs/pb-antipatterns/) | PB-specific hazards with reproductions and idiomatic fixes — the bugs that compile fine and bite in production. |
| [`tools/pb-appeon-index/`](tools/pb-appeon-index/) | Scrapes `docs.appeon.com` once into a local SQLite FTS5 database and serves it as four MCP tools. A language lookup costs ~400 tokens instead of a few thousand. |
| [`tools/pb-source-analyzer/`](tools/pb-source-analyzer/) | Bootstraps the format wiki from a real `.sr*` corpus, anonymizing project-specific identifiers on the way in. |

## Install

Three steps, in order: connect the MCP server, install the skills, and
optionally add the doc index and the formatter.

```pwsh
git clone https://github.com/restoresrl/pb-ai-code
cd pb-ai-code
.\scripts\install-skills.ps1 -Target ..\my-pb-app -Bundle review
```

**The full walkthrough, per assistant, is
[`docs/install.md`](docs/install.md).** Start there — it covers the
`mcpServers` block (including the one flag you cannot get wrong), where
it goes for each client, how to verify the stack before trusting it, and
what to do when your assistant has no slash commands or no skill
discovery.

## Dependencies

- **[`pb-orca-mcp`](https://github.com/restoresrl/pb-orca-mcp)** —
  required. Every `.pbl` operation goes through it; no ORCA primitive is
  reimplemented here. Consumed like any other MCP server, from its
  GitHub repository.
- **[`pb-format`](https://github.com/restoresrl/pb-format)** — optional.
  A standalone PowerScript style formatter. Without it, the dev kit
  simply does not normalize style.
- **The Appeon doc index** — optional, built locally from
  [`tools/pb-appeon-index/`](tools/pb-appeon-index/). Without it, the
  `appeon-query` skill says so instead of guessing.
- **An MCP-capable assistant.** Skill auto-discovery is a bonus, not a
  requirement.

## Requirements

Windows and a PowerBuilder **IDE** install (2019 or later) for anything
that touches a `.pbl` — ORCA is a Windows DLL, and runtime-only packages
do not ship it. Classic workspaces only, not the PB 2025 solution
format. The knowledge pages and the formatter work anywhere.

## Status

Alpha, in internal dogfooding. The review flow and the knowledge base
are written and being exercised against real codebases; the repository
is private until real use confirms the shape. Testing orchestration and
runtime trace analysis are designed but deferred — see
[`PLAN.md`](PLAN.md).

## Contributing

The knowledge base is the part most worth contributing to, and it needs
no AI: a corrected format page, a new antipattern with a reproduction,
or a variant the wiki has not seen are all directly useful. If you are
an agent working on this repository, read [`AGENTS.md`](AGENTS.md).

## License

MIT — see [`LICENSE`](LICENSE).

## Author

Carlo Torrese — Restore srl — `carlo.torrese@re-store.it`
