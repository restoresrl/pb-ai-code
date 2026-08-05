# `harness/`

Configuration that is *about* an assistant rather than about PowerBuilder.
Nothing here is read by any tool in place: `scripts/install-skills.ps1`
materializes these files into the locations a given assistant expects, the
same way it does for `skills/` and `commands/`.

| File | Materialized as | Scope |
| --- | --- | --- |
| `mcp-servers.json` | `<target>/.mcp.json` (`-Harness claude-code`) | every MCP client — the block is identical, only its location differs |
| `claude-code/settings.json` | `<target>/.claude/settings.json` | Claude Code only |

`mcp-servers.json` sits at the top level, not under `claude-code/`, because
the `mcpServers` block is the same JSON for Cursor, Codex CLI, Copilot and
the rest. A per-harness copy would be the same content in several files,
which is the drift this layout exists to avoid. What differs per harness is
the destination path, and that is the installer's job. For a harness whose
path we do not know, `-Harness generic` prints the block instead of guessing
where to put it.

## Why the installer writes the MCP config at all

The version pin in `mcp-servers.json` is what makes "we are all on the same
toolchain" a checkable statement rather than a hope. A neutral file that each
developer copies by hand defeats it: when the canonical file moves to a new
tag, every hand-made copy stays on the old one, and the pin becomes
documentation instead of configuration.

So a project using this kit commits **nothing** agentic — no `.claude/`, no
`.mcp.json`, no neutral stand-in. Re-running the installer is the only
synchronization step, and it updates the skills and the server pin together,
so the two cannot drift apart.

That applies to this repository too: its own root `.mcp.json` is generated
and gitignored, exactly like `.claude/`. Edit it here, then re-run
`scripts\install-skills.ps1`.

## Changing the pin

Edit the tag in `mcp-servers.json`, then re-run the installer everywhere the
kit is installed. `docs/install.md` quotes the same block for readers, and
`tests/test_pins_in_sync.py` fails if the two disagree.
