# Installation reference

Use [`install.md`](install.md) for the normal procedure. This page records the
CLI surface, generated files, and client limitations without repeating the
setup walkthrough.

## Commands

```text
pb-ai-code [--version] {install,status,update}
pb-appeon-index {scrape,build,update,search,serve-mcp,versions}
```

### `pb-ai-code install`

```text
pb-ai-code install [--target PATH]
                   [--harness {generic,claude-code}]
                   [--skills-dir REL]
                   [--commands-dir REL]
                   [--pb-version VERSION]
                   [--skip-mcp-config]
                   [--dry-run]
```

| Option | Effect |
| --- | --- |
| `--target PATH` | Existing project directory. Defaults to the current directory. |
| `--harness generic` | Default layout. |
| `--harness claude-code` | Claude Code layout and its generated settings file. |
| `--skills-dir REL` | Generic only. Defaults to `.agents/skills`; must be target-relative and end with `skills`. |
| `--commands-dir REL` | Generic only. Defaults to `.agents/commands`; must be a sibling of the skills directory. |
| `--pb-version VERSION` | Project's PowerBuilder IDE version, for example `22.0`. |
| `--skip-mcp-config` | Leave `.mcp.json` unchanged. |
| `--dry-run` | Show the planned writes and MCP merge without writing files. |

### `pb-ai-code status`

```text
pb-ai-code status [--target PATH] [--json]
```

`--json` writes only machine-readable status to standard output. The command
reads the marker created during installation and does not contact the network.

### `pb-ai-code update`

```text
pb-ai-code update [--target PATH] [--check] [--json] [--refresh] [--yes]
```

Without `--check`, the command finds the latest stable GitHub Release and asks
before updating. In an installed project, it updates both the persistent tool
and the project bundle; elsewhere, it updates only the persistent tool.

| Option | Effect |
| --- | --- |
| `--target PATH` | Project to inspect or update. Defaults to the current directory. |
| `--check` | Report availability only; make no changes. |
| `--json` | Machine-readable result for `--check`. |
| `--refresh` | Ignore the successful 24-hour local release-check cache. |
| `--yes` | Skip the confirmation prompt for an approved update. |

### `pb-appeon-index`

The usual command is:

```powershell
pb-appeon-index update --all
```

It updates the shared database at
`%USERPROFILE%\.pb-appeon-index\index.db`. Use `--version <slug>` to refresh
one configured Appeon version and `--db PATH` to use a non-default database.
See [`appeon-index/README.md`](appeon-index/README.md) for the index format and
version list.

## Generated project files

Generic installation creates:

```text
.agents/skills/
.agents/commands/
.agents/pb-ai-code-docs/
.agents/_installed-from-pb-ai-code.txt
.mcp.json
```

Claude Code installation creates:

```text
.claude/skills/
.claude/commands/
.claude/pb-ai-code-docs/
.claude/settings.json
.claude/_installed-from-pb-ai-code.txt
.mcp.json
```

The installer creates `AGENTS.md` only when the project has no existing file.
It never rewrites an existing `AGENTS.md`.

All generated files are machine-local configuration. Keep them out of version
control. The installer prints the relevant `.gitignore` entries. Re-run the
installer to update a bundle; do not hand-edit an installed skill or knowledge
page.

## MCP client compatibility

The installer merges a neutral `mcpServers` JSON object into root `.mcp.json`.
It preserves unrelated servers in a valid file.

| Client | Result |
| --- | --- |
| Claude Code | Reads `.mcp.json` directly. `--harness claude-code` also creates `.claude/settings.json`. |
| Generic clients that accept this JSON shape | Can use the generated `.mcp.json` and `.agents/` bundle. |
| Codex CLI | Requires its native TOML configuration. Translate the command, arguments, and environment values. |
| OpenCode | Requires its native JSON configuration. Translate the server values. |
| Continue | Requires YAML. Translate the server values. |

Do not promise automatic MCP discovery for a client whose native format is not
implemented. The generic skill bundle still provides Markdown instructions; the
MCP configuration needs client-specific translation.

## MCP merge behavior

The installer owns `pb-orca` and, when the PB Search database exists,
`pb-appeon-index`. It updates only those entries. It leaves other entries in
place and warns when it finds another entry that appears to launch one of the
same server packages.

If `.mcp.json` is invalid JSON, the installer does not change it. It prints the
server block for manual merging and still installs skills.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Completed. Warnings can still be present. |
| `2` | Invalid command line or target. |
| `3` | `status` found no installation marker. |

See [`troubleshooting.md`](troubleshooting.md) for common warnings and
recovery steps.
