# Troubleshooting installation

## `uv` is not recognized

Install `uv` and open a new terminal:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Run `uv --version`. Do not assume an already-running assistant receives the
new `PATH`; restart it before continuing.

## `pb-ai-code` or `pb-appeon-index` is not recognized

Install the persistent tool:

```powershell
uv tool install git+https://github.com/restoresrl/pb-ai-code@v0.11.4
```

Open a new terminal. If the commands are still unavailable, locate the tool
executable directory:

```powershell
uv tool dir --bin
```

Add that directory to the current user's `PATH`, then open another terminal.

## The installer cannot access GitHub

`uv` downloads a release from GitHub. Check the network connection and confirm
that GitHub is reachable from the machine. If the repository becomes private,
ensure Git credentials are configured for the Windows user running the command.

## The target does not exist

`pb-ai-code install` never creates a target directory. Create or clone the
project first, then run the install again with the correct `--target` path.

## `pb-orca-mcp doctor` cannot find PowerBuilder

Install a supported PowerBuilder IDE. Runtime-only packages do not include the
ORCA DLL. The ORCA server also requires a 32-bit Python process, which the
installed server entry requests with `--python 3.12-x86`.

Run:

```powershell
uvx --from git+https://github.com/restoresrl/pb-orca-mcp@v0.2.8 `
  --python 3.12-x86 pb-orca-mcp doctor
```

## The assistant shows no `pb_*` tools

Check the project installation first:

```powershell
pb-ai-code status --json
```

Confirm that the project root contains `.mcp.json`. Then restart the assistant
session. Most clients read MCP configuration and their skill inventory only at
startup.

For a client that does not use `.mcp.json` as its native format, translate the
server values into that client's configuration. See
[`install-reference.md`](install-reference.md#mcp-client-compatibility).

## `.mcp.json` is invalid

The installer leaves an invalid `.mcp.json` untouched and prints a server block
to merge by hand. Fix or merge the file only with the project owner's approval.
Do not delete unrelated MCP servers.

## The installer reports another ORCA server

A project already has an MCP server that appears to launch `pb-orca-mcp` or
`pb-appeon-index` under another name. The installer preserves it. Two ORCA
servers can compete for a single-session ORCA library. Ask the project owner
which entry should remain before removing anything.

## PB Search is not configured

Build the shared database:

```powershell
pb-appeon-index update --all
```

Then rerun the project install and restart the assistant:

```powershell
pb-ai-code install --target C:\Projects\MyApp
```

The core ORCA tools do not depend on PB Search. Only the optional
`appeon-query` skill loses its local documentation lookup.

## PB Search tools fail with a database error

Check that this file exists for the current Windows user:

```text
%USERPROFILE%\.pb-appeon-index\index.db
```

Rebuild it with `pb-appeon-index update --all`. If the project uses a custom
location, set `PB_APPEON_INDEX_DB` before reinstalling the project so the MCP
entry records that path.

## The PowerBuilder IDE locks the library

Close the PowerBuilder IDE or the process that holds the `.pbl` lock before
asking the assistant to modify a library. Read-only analysis may still work,
but imports cannot proceed safely.

## Generated files appear in Git status

Add the installer-suggested entries to `.gitignore`. At minimum, generic
installs normally need `.agents/` and `.mcp.json`; Claude Code installs need
`.claude/` and `.mcp.json`. Do not commit generated skills or local MCP paths.
