# CLAUDE.md — pb-ai-code

The agent instructions for this repository live in
[`AGENTS.md`](AGENTS.md), in the cross-tool
[agents.md](https://agents.md) format. **Read it now** — it is the
source of truth for context, layout, architectural constraints and
conventions, and this file deliberately does not repeat any of it.

Two Claude Code specifics worth knowing while working here:

- The `.claude/` directory is **generated** by
  `scripts/install-skills.ps1` from `skills/`, `commands/` and
  `harness/claude-code/`, and it is gitignored. Edit the canonical
  files and re-run the installer; an edit made inside `.claude/` is
  lost on the next install.
- `.mcp.json` at the repository root wires up both MCP servers
  (`pb-orca`, `pb-appeon-index`). See
  [`docs/install.md`](docs/install.md) for what each one needs.

If a restart is unavoidable, prefer `claude --resume` / `-c` over
starting fresh: the transcript is usually worth more than a handoff
note.
