# Set up pb-ai-code as a coding agent

Use this procedure when a user asks you to install `pb-ai-code` in their
PowerBuilder project. It covers both the user's machine and the selected
project.

Do not edit a `.pbl` or `ws_objects/` while setting up the kit. The setup only
writes generated assistant files, MCP configuration, and an `AGENTS.md` file
when the project does not already have one.

## 1. Identify the target and ask the necessary questions

Confirm all of the following before changing files:

1. The project directory to configure.
2. The PowerBuilder IDE version used to maintain the project, such as `22.0`.
   Do not infer it from exported source.
3. The assistant layout: use `generic` unless the user explicitly wants Claude
   Code.
4. Whether the user authorizes machine-level changes. Installing `uv` or a
   persistent `uv` tool changes the current user's profile.
5. Whether the user wants the optional PB Search database. Its first build
   downloads Appeon documentation and can take several minutes.

A project can be configured without PB Search. A project cannot use ORCA tools
without Windows and a PowerBuilder IDE installation.

## 2. Check the machine

Run these checks:

```powershell
uv --version
Get-Command pb-ai-code -ErrorAction SilentlyContinue
Get-Command pb-appeon-index -ErrorAction SilentlyContinue
```

If `uv` is unavailable, explain that setup cannot continue until it is
installed. With authorization, run:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Ask the user to open a new terminal and restart the agent session. Do not
assume the current process receives the updated `PATH`.

If `uv` exists but either persistent command is missing, ask before installing
this release for the current user:

```powershell
uv tool install git+https://github.com/restoresrl/pb-ai-code@v0.11.0
```

Open a new terminal if needed, then verify:

```powershell
pb-ai-code --version
pb-appeon-index --help
```

If the user declines the persistent installation, use the one-off `uvx` command
shown in step 4. Explain that it configures the project but does not leave
`pb-ai-code` or `pb-appeon-index` available in future terminals.

## 3. Build PB Search only with approval

If the user requested PB Search and `~/.pb-appeon-index/index.db` does not
exist, build it once:

```powershell
pb-appeon-index update --all
```

If the persistent command is unavailable by the user's choice, use:

```powershell
uvx --from git+https://github.com/restoresrl/pb-ai-code@v0.11.0 `
  pb-appeon-index update --all
```

Do not copy the resulting database into a project. The installer finds the
shared database and writes its absolute path to the project MCP configuration.

## 4. Install the project bundle

Make sure the target directory already exists. Start with a dry run when the
user wants to inspect the changes:

```powershell
pb-ai-code install --target C:\Projects\MyApp --pb-version 22.0 --dry-run
```

Install the generic layout:

```powershell
pb-ai-code install --target C:\Projects\MyApp --pb-version 22.0
```

For Claude Code:

```powershell
pb-ai-code install --target C:\Projects\MyApp `
  --harness claude-code --pb-version 22.0
```

If the persistent command is unavailable, replace the command in either example
with:

```powershell
uvx --from git+https://github.com/restoresrl/pb-ai-code@v0.11.0 `
  pb-ai-code install
```

Keep the arguments after `install` unchanged.

## 5. Verify the result

Run:

```powershell
pb-ai-code status --target C:\Projects\MyApp --json
```

For a one-off install:

```powershell
uvx --from git+https://github.com/restoresrl/pb-ai-code@v0.11.0 `
  pb-ai-code status --target C:\Projects\MyApp --json
```

Check these facts:

- `installed` is `true`.
- Generic installation created `.agents/skills` and `.agents/commands`.
- The project root contains `.mcp.json` unless `--skip-mcp-config` was used.
- The marker records the selected harness and source version.
- The installer either configured `pb-appeon-index` or clearly reported that
  the optional database is missing.
- The generated files are ignored by Git. Offer the exact `.gitignore` entries
  printed by the installer; do not modify `.gitignore` without permission.

If the project already has an `AGENTS.md`, the installer leaves it unchanged
and prints the PowerBuilder version note to add manually. Report that result to
the user instead of editing their instruction file without permission.

## 6. Explain the client limitation and restart

`.mcp.json` is a neutral project MCP configuration. Claude Code reads it
directly. A client with a different MCP format may require translation into its
own TOML, JSON, or YAML configuration. Say so instead of claiming that tools
will appear automatically.

Finally, ask the user to restart the assistant session. Skill discovery and MCP
servers are usually loaded at session start. After the restart, ask the user to
confirm that `pb_*` tools appear and run a small read-only request before any
library write.

## Failures

- Missing `uv`: obtain authorization, install it, then restart the terminal and
  agent.
- Missing PowerBuilder IDE or ORCA DLL error: the kit can remain installed, but
  `.pbl` operations cannot work. Run `pb-orca-mcp doctor` when possible.
- Invalid `.mcp.json`: the installer leaves it untouched and prints a block for
  a human to merge. Do not overwrite it.
- Duplicate ORCA server warning: the installer preserves the existing entry.
  Tell the user that two servers can compete for a single-session ORCA library.
- Missing PB Search database: core tools still work. Build it later, reinstall
  the project bundle, and restart the assistant.

For user-facing detail, link to [`install.md`](install.md) and
[`troubleshooting.md`](troubleshooting.md).
