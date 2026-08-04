# Install

`pb-ai-code` is a set of **skills, commands and knowledge** plus two
small local tools. It has no runtime of its own: an assistant reads the
skills, and the skills drive MCP tools. So installing it means three
things, in this order:

1. Connect the [`pb-orca-mcp`](https://github.com/restoresrl/pb-orca-mcp)
   MCP server — the only required dependency.
2. Install the skills into whatever directory your assistant reads.
3. Optionally add the Appeon doc index and the `pb-format` formatter.

Nothing here is specific to one assistant or one model. Where a step
differs per client, the difference is called out.

## Requirements

| | |
| --- | --- |
| OS | Windows, for anything that touches a `.pbl` (ORCA is a Windows DLL). The knowledge pages and `pb-format` work anywhere. |
| PowerBuilder | An **IDE** install, 2019 or later. Runtime-only packages do not ship `pborc.dll`. Classic workspaces only — not the PB 2025 solution format. |
| Assistant | Anything that speaks MCP and can follow a Markdown instruction file. Skill auto-discovery is a bonus, not a requirement. |
| `uv` | Recommended, for `uvx`. [Install it](https://docs.astral.sh/uv/getting-started/installation/) or substitute your own Python environment management. |

## 1. Connect `pb-orca-mcp`

One `mcpServers` entry:

```json
{
  "mcpServers": {
    "pb-orca": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/restoresrl/pb-orca-mcp",
        "--python", "3.12-x86",
        "pb-orca-mcp"
      ]
    }
  }
}
```

**`--python 3.12-x86` is not optional.** PowerBuilder's `pborc.dll` is
32-bit through PB 2025, and `ctypes` in a 64-bit Python cannot load it.
Getting this wrong produces a DLL-load error that looks like a missing
file.

Where the block goes:

| Client | Location |
| --- | --- |
| Claude Code | `.mcp.json` at the project root (shared, committable), or `~/.claude/mcp.json` (user-level) |
| Cursor | `.cursor/mcp.json` (project) or `~/.cursor/mcp.json` (user) |
| Codex CLI, Gemini CLI, Copilot, others | that client's MCP config file — the JSON shape is the same |

This repository ships a working `.mcp.json` at its root with both
servers wired up. Copy from it.

**Verify before going further.** `pb-orca-mcp` has two CLI commands
that need no MCP client at all:

```pwsh
uvx --from git+https://github.com/restoresrl/pb-orca-mcp --python 3.12-x86 pb-orca-mcp doctor
uvx --from git+https://github.com/restoresrl/pb-orca-mcp --python 3.12-x86 pb-orca-mcp check <path-to.pbw>
```

`doctor` reports every PB install it can see and exits non-zero when
none is usable. `check` validates the whole stack against a real
project. If either fails, fix that first — no skill can work around it.
Then confirm your client lists the `pb_*` tools (in Claude Code:
`/mcp`).

## 2. Install the skills

The canonical copies live in agent-neutral directories:

```text
skills/<name>/SKILL.md      Agent Skills (agentskills.io) format
commands/<name>.md          slash-command wrappers
harness/<harness>/          per-assistant config (permissions, ...)
```

No assistant reads those paths. `scripts/install-skills.ps1` copies them
into the layout a given assistant expects, so one source of truth serves
every tool:

```pwsh
# Into this repository itself, to work on the skills:
.\scripts\install-skills.ps1

# Into a PowerBuilder workspace, review bundle only:
.\scripts\install-skills.ps1 -Target ..\my-pb-app -Bundle review

# Anything else: point it at the directory your assistant reads
.\scripts\install-skills.ps1 -Target ..\my-pb-app -Harness generic -SkillsDir .agent\skills

# See the plan without writing:
.\scripts\install-skills.ps1 -Target ..\my-pb-app -DryRun
```

`-Harness claude-code` (the default) writes `<target>/.claude/skills/`,
`<target>/.claude/commands/` and `<target>/.claude/settings.json`.
`-Harness generic` writes wherever you point it and skips the
assistant-specific settings file.

`-Bundle review` installs only what a code review needs (`pb-review`,
`pb-context-build`, `pb-apply-plan`, `appeon-query`, `pb-src-format`);
`-Bundle full` — the default — installs everything.

Two things the script does deliberately:

- It writes a **marker file** recording the source commit, so drift
  between an installed copy and this repository is auditable. Make
  changes here and re-run; do not patch the installed copy.
- Installed directories are **gitignored in this repository**. They are
  build output. In a consumer project you may well want to commit them,
  so the whole team gets the same bundle — that is the vendored-snapshot
  pattern, and it is a deliberate choice, not an accident.

### If your assistant has no slash commands

Not a problem. Every flow exists as a skill of the same name:
`/pb-review` is a three-line wrapper around the `pb-review` skill, and
`/pb-format` around `pb-format`. Ask for the skill by name, or just
describe the task — the skill descriptions are written to be matched.

### If your assistant has no skill discovery

Point it at the file. `skills/pb-review/SKILL.md` is a self-contained
instruction document: "read `skills/pb-review/SKILL.md` and follow it,
target = `<x>`" is a complete invocation. The cross-references between
skills are ordinary relative links, so an assistant that can read files
can follow the whole chain.

### Permissions (Claude Code)

`harness/claude-code/settings.json` pre-approves the read-only and
session-setup MCP tools, so a review does not stop for a prompt on every
call. Everything that writes into a `.pbl`, creates a source projection,
or builds an artefact stays interactive on purpose.

If you rename the MCP server from `pb-orca` to something else, update
the `mcp__pb-orca__*` prefixes to match — the permission strings embed
the server key.

## 3. Optional: the Appeon doc index

The Appeon documentation, scraped once into a local SQLite FTS5 database
and served as four MCP tools. It makes a language lookup cost ~400
tokens instead of a few thousand. Without it, the `appeon-query` skill
tells you it is not built rather than guessing.

Setup — including how to build the DB — is in
[`appeon-index/README.md`](appeon-index/README.md). The database is
never redistributed: each developer builds it locally from the live
site.

## 4. Optional: the `pb-format` formatter

[`pb-format`](https://github.com/restoresrl/pb-format) normalizes
PowerScript style (indent, keyword case, operator spacing, line
endings). It is a standalone CLI, independent of PowerBuilder and ORCA.

```pwsh
uv tool install git+https://github.com/restoresrl/pb-format
```

It is not on PyPI yet, so it installs from its repository — the same
arrangement as `pb-orca-mcp` above. Once it is published, `uv tool install
pb-format` (or `pipx install pb-format`) will be the shorter form.

It only does anything where a workspace has opted in with a
`.pb-format.toml` — generate a starter with `pb-format detect
<workspace>`. Without the tool, or without a config, the dev kit simply
does not format, and nothing else changes. See
[`pb-source-format/style-conventions.md`](pb-source-format/style-conventions.md)
for the rules.

## Where to run the assistant from

Two working arrangements, both fine:

**From the PowerBuilder workspace.** Install the skills there
(`-Bundle review`), put the MCP config there, and work with the project
as the working directory. This is the natural setup for day-to-day work,
and it is what lets `.pb-review/` plan files and `CHANGELOG.md` land in
the right repository.

**From this repository.** Install into itself, and point the skills at a
workspace elsewhere by absolute path. Convenient while developing the
skills, since edits take effect on the next install.

## Verifying end to end

1. `pb-orca-mcp doctor` — a usable PB install is found.
2. Your client lists the `pb_*` tools.
3. Ask for `pb_workspace_info` on one `.pbl` of a real project: it needs
   no ORCA session and no PB install, so it is the cheapest possible
   round trip through the whole chain.
4. Run the `pb-review` flow on something small. It stops for
   confirmation before any expensive work, so an early scope-framing
   question is a sign it is working, not a sign it is stuck.

## When something is wrong

- **DLL load error, or "no PB install found"** — architecture mismatch
  or a runtime-only install. `pb-orca-mcp doctor` says which.
- **A tool call fails with a state guard** — the ORCA session was not
  brought up in order: `pb_session_open`, then
  `pb_set_library_list`, then `pb_set_current_application`.
- **The `.pbl` is locked** — the PB IDE has it open. Close the IDE.
- **A one-line fix produced a whole-file diff** — line endings got
  translated somewhere. See
  [`pb-source-format/encoding.md`](pb-source-format/encoding.md).
- **`.pbw` shows up modified after a session** —
  `pb_set_current_application` rewrites it. Revert it unless you really
  added or removed a target.

`pb-orca-mcp`'s `docs/troubleshooting.md` covers the ORCA layer in
depth.
