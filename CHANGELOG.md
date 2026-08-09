# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Tags on this repository are what a team pins to. The version here selects the
whole toolchain: which skill bundle, and — through the pinned URLs in
`harness/` — which `pb-orca-mcp` and which `pb-format`. Two developers
installed from the same tag have the same setup, and the marker file the
installer leaves in a target records which tag that was.

## [Unreleased]

## [0.1.2] - 2026-08-09

Everything here came out of the first real review the kit ran on a real
library. The findings about the *code* were the point; these are the findings
about the *kit*, which is what a dogfooding run is actually for.

### Added

- **The pre-flight now looks at git's line-ending translation.**
  `pb-orca-mcp` v0.2.3 makes `pb_workspace_info` report `source_protection`,
  and the skills act on it: `pb-context-build` reports it in the workspace
  summary, `pb-review` measures how far the normalization has already gone
  (`git ls-files --eol`, count the `i/lf w/crlf` files) and says it must be
  fixed before the apply loop, and **`pb-apply-plan` stops** when it is
  `unprotected` rather than writing a diff the user cannot trust.

  The review that found this ran against a repository where 56 of 61 sources
  were being normalized by git, and nothing in the chain said a word. A review
  is read-only, so it was harmless there — but it ends by handing off to the
  one skill that writes, and that skill would have produced changes invisible
  to `git status`.

  The `.gitattributes` fix is never folded into a fix commit: it rewrites every
  source in the index, so it would bury the change under a whole-tree diff.

- `tests/test_pins_in_sync.py` also checks bare `@vX.Y.Z` mentions, not just
  full URLs. The prose sentence explaining what the pin is for had drifted a
  version behind on the very release that added the URL check — the test
  watched the copies it knew about and missed the one in the sentence next to
  them. Changelogs are exempt: recording what a past version pinned is their
  job.

### Corrected

- **`appeon-query` told half the story.** The Appeon index is deliberately not
  configured by the installer — it needs an absolute interpreter path and a
  database each developer builds — but the skill's fallback only explained how
  to *populate* the index, not how to *add the server*, and pointed at a
  document that is not part of a vendored install. On the real run this cost
  two findings, which could not be checked against the language reference. The
  skill now carries the whole recipe inline, and `pb-review` states the rule
  that made those two findings safe anyway: **never assert PowerScript
  behaviour from memory inside a finding** — mark it unverified and name the
  experiment that would settle it. A wrong finding costs more than a missing
  one, because it looks exactly like a right one and arrives with an edit
  attached.
- `harness/claude-code/settings.json` pre-approves `mcp__pb-appeon-index__*`
  tools and names the server in `enabledMcpjsonServers`, for a server the
  installer never writes. That is intentional — it is inert until someone adds
  the server by hand, and then it saves them a step — but nothing said so.
  Now it does.

## [0.1.1] - 2026-08-05

Cut because v0.1.0 pins `pb-orca-mcp@v0.2.1`, which cannot start — so the tag
that is supposed to name a working toolchain named a broken one.

### Added

- **The installer now writes the MCP server configuration**, from a new
  canonical [`harness/mcp-servers.json`](harness/mcp-servers.json), instead of
  leaving readers to copy a JSON block out of the documentation. The pin is the
  reason: a block copied by hand stays on whatever tag was current the day it
  was copied, so the canonical file moves and nobody follows, and the pin
  quietly becomes documentation rather than configuration. Installed with the
  skills, the two are updated by one command and cannot drift.

  `-Harness claude-code` merges it into `<target>/.mcp.json`; `-Harness
  generic` prints it, because inventing a path for a client whose contract we
  have not verified would look like it worked. Servers the project already had
  are preserved — only the `pb-orca` key is written — and a target file that
  does not parse is left alone with the block printed for a manual merge.
  `-SkipMcpConfig` opts out entirely, for projects whose servers are managed at
  user scope.

  Consequence, and the point of the change: **a project using this kit commits
  nothing agentic.** No `.claude/`, no `.mcp.json`, no neutral stand-in file.
  Re-running the installer is the whole synchronization story. This repository
  now follows its own rule — its root `.mcp.json` is generated and gitignored,
  like `.claude/`.

- `tests/test_pins_in_sync.py`: every `restoresrl/<repo>@<tag>` reference in
  the tree must agree, and the file the installer materializes is the one that
  decides. A pin that disagrees with itself is worse than none — it tells two
  developers two different stories, each of which looks authoritative.

### Corrected

- Pinned `pb-orca-mcp` to **v0.2.2**. v0.2.1 could not start as an MCP server
  at all: `mcp` 2.0.0 removed `mcp.server.fastmcp` and the dependency had no
  upper bound. The CLI (`doctor`, `check`) kept working because it never
  imports that layer, which is exactly why this survived the install audit.
- **The optional Appeon doc index could not start either**, and for the same
  reason: `pb_appeon_index.mcp_server` imports `mcp.server.fastmcp`, and this
  repository's own `mcp` dependency had no upper bound. `__main__` imports that
  module at module scope, so it was not only `serve-mcp` that failed but every
  subcommand — including the `pb-appeon-index update` that `docs/install.md`
  tells you to run to build the database in the first place. Pinned `mcp<2`,
  and added a test that builds the server and registers its four tools, since
  the whole suite was green while the CLI could not import.
- The antipattern catalog's index linked `/pb-review` at
  `../../commands/pb-review.md`, which does not exist in a `-Harness generic`
  install — that harness has no commands directory. Points at the skill
  instead, which every layout has.

## [0.1.0] - 2026-08-05

First tagged release. Nothing is published to any package index; the delivery
mechanism is a git clone plus `scripts/install-skills.ps1`.

### Added

- **Seven skills** in [`skills/`](skills/), in the
  [Agent Skills](https://agentskills.io) `SKILL.md` format so any skill-aware
  assistant can load them: `pb-review` (structured code review producing a
  persistent plan file), `pb-apply-plan` (the confirm-per-fix edit loop),
  `pb-context-build` (a budgeted context pack out of a monolithic workspace),
  `pb-scaffold` (validated minimal bodies for six entry types), `pb-src-format`
  (the on-disk source format), `pb-format` (style normalization), and
  `appeon-query` (language and runtime API lookups).
- **Slash-command wrappers** in [`commands/`](commands/) — thin by design: each
  delegates to the skill of the same name, so nothing is lost on an assistant
  that has no slash commands.
- **A PowerScript antipattern catalog** under
  [`docs/pb-antipatterns/`](docs/pb-antipatterns/): six hazards that compile
  cleanly and bite in production, each with a reproduction and an idiomatic
  fix. Two of them cite Appeon's own SDI application template, so every
  application scaffolded from the wizard carries them.
- **A reverse-engineered `.sr*` format wiki** under
  [`docs/pb-source-format/`](docs/pb-source-format/): one page per entry type
  plus the two cross-cutting ones, encoding and style conventions. No upstream
  specification exists, so the pages carry a `status` field and an open-questions
  section, and grow as cases are met.
- **`tools/pb-appeon-index/`** — scrapes `docs.appeon.com` once into a local
  SQLite FTS5 database and serves it as four MCP tools. A language lookup costs
  roughly 400 tokens instead of several thousand. Optional; the `appeon-query`
  skill says so when the index is absent rather than guessing.
- **`tools/pb-source-analyzer/`** — bootstraps the format wiki from a real
  `.sr*` corpus, anonymizing project identifiers on the way in.
- **`scripts/install-skills.ps1`** — materializes the canonical files into
  whatever directory an assistant reads (`-Harness claude-code` or `generic`),
  vendors the two documentation trees beside the skills, rewrites their links to
  match, and leaves a marker recording the source commit.
- **[`docs/install.md`](docs/install.md)** — a Quickstart that is the whole
  sequence with nothing explained, then the reasons: per-client MCP config
  locations, how to verify the stack before trusting it, and what to do when an
  assistant has neither slash commands nor skill discovery.
- **[`AGENTS.md`](AGENTS.md)** in the cross-tool
  [agents.md](https://agents.md) format. One agent-instruction file, no
  per-assistant variant.

### Notes

- **Agent- and model-agnostic by construction, not by aspiration.** The
  canonical artefacts live in agent-neutral directories; everything under
  `.claude/` is generated and gitignored. Cross-repository links are URLs, and
  interactive prompts inside skills are written in neutral English with the
  standing instruction to speak the user's language.
- **Verified from a clean clone.** All three repositories were cloned into an
  empty directory and the documentation followed as written, which is how the
  install command was found to be broken (`cryptography` stopped publishing
  32-bit Windows wheels, and this stack must run x86 for `pborc.dll`), and how a
  vendored install was found to be missing the knowledge base its own skills
  link to.
- **Exercised end to end once**, on a small real workspace: pre-flight, scope
  framing, context pack, understanding gate, review, plan file, CHANGELOG entry,
  and the apply loop through `pb_object_export_file` → edit →
  `pb_object_import_file`. That run found four defects in these skills, all
  fixed here. It has not yet been run against a large legacy target, so the
  budget caps, caller discovery at size, and `outside_source_tree` handling are
  written but unproven.
