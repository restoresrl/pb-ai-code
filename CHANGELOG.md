# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Tags on this repository are what a team pins to. The version here selects the
whole toolchain: which skill bundle, and — through the pinned URLs in
`.mcp.json` and `harness/` — which `pb-orca-mcp` and which `pb-format`. Two
developers installed from the same tag have the same setup, and the marker file
the installer leaves in a target records which tag that was.

## [Unreleased]

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
