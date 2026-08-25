# Install pb-ai-code

There are two installation scopes:

1. Install commands for one Windows user. This provides `pb-ai-code` and
   `pb-appeon-index` in PowerShell and Command Prompt, plus one optional shared
   PB Search database.
2. Install the generated skill bundle and MCP configuration in each
   PowerBuilder project.

The first scope changes the user's profile. The second changes only the chosen
project. Keep them separate: a project install does not make the commands
available globally, and a global install does not modify any project.

## Before you start

For any operation that reads or writes a `.pbl`, use Windows with a
PowerBuilder IDE installation from 2019 or later. Runtime-only packages do not
include `pborc.dll`. The installer itself can run without a PowerBuilder
workspace, but `pb-orca-mcp` cannot operate on libraries until the IDE is
available.

You also need `uv`. Install it once:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Close and reopen the terminal before continuing. Verify the command is on
`PATH`:

```powershell
uv --version
```

## 1. Install commands for the current user

Install a release as a persistent `uv` tool:

```powershell
uv tool install git+https://github.com/restoresrl/pb-ai-code@v0.11.2
```

The `@v0.11.2` part is a Git tag, not a decoration. It makes the install
repeatable: every machine gets the same released code. If you leave the tag
off, `uv` installs the repository's default branch, which may be newer than the
latest GitHub release.

Then check the two commands the tool install puts on the current user's
`PATH`:

```powershell
pb-ai-code --version
pb-appeon-index --help
```

`pb-ai-code --version` confirms which kit version PowerShell can run.
`pb-appeon-index --help` only prints help; it does not download documentation
or create the PB Search database. It is there to catch a `PATH` problem before
you run the longer index build.

If either command is not found, open a new PowerShell or Command Prompt. If it
is still not found, run `uv tool dir --bin` to find the executable directory
and add that directory to the user's `PATH`.

### Build the optional PB Search database

PB Search is the local Appeon documentation index used by the `appeon-query`
skill. Build it once per Windows user:

```powershell
pb-appeon-index update --all
```

The default database location is:

```text
%USERPROFILE%\.pb-appeon-index\index.db
```

The first build downloads documentation from `docs.appeon.com` and can take
several minutes. It is optional. Without it, the core ORCA tools work and the
`appeon-query` skill reports that the index is unavailable rather than
inventing a language-reference answer.

The database is not copied into projects. A project MCP configuration stores
its absolute path, so one rebuilt database serves every project for that user.

### Verify the ORCA prerequisite

Before using a real project, confirm that the 32-bit PowerBuilder integration
is available:

```powershell
uvx --from git+https://github.com/restoresrl/pb-orca-mcp@v0.2.8 `
  --python 3.12-x86 pb-orca-mcp doctor
```

For a specific workspace, use `check` before asking an assistant to change a
library:

```powershell
uvx --from git+https://github.com/restoresrl/pb-orca-mcp@v0.2.8 `
  --python 3.12-x86 pb-orca-mcp check C:\Projects\MyApp\workspace.pbw `
  --pb-version 22.0
```

`--python 3.12-x86` matters. PowerBuilder's ORCA DLL is 32-bit.

## 2. Install into a PowerBuilder project

Ask which PowerBuilder version the project is developed with. Do not infer it
from exported source: an object records the version that last saved that
object, not necessarily the IDE that maintains the project.

From the project root:

```powershell
cd C:\Projects\MyApp
pb-ai-code install --pb-version 22.0
pb-ai-code status --json
```

Or use an explicit target from another directory:

```powershell
pb-ai-code install --target C:\Projects\MyApp --pb-version 22.0
```

The target must already exist. The installer does not create it.

### Default generic layout

The default harness writes:

```text
.agents/skills/
.agents/commands/
.agents/pb-ai-code-docs/
.agents/_installed-from-pb-ai-code.txt
.mcp.json
```

The installer prints any `.gitignore` entries the project needs. Add them when
asked. These files are generated machine-local configuration and should not be
committed.

### Claude Code layout

Use Claude Code only when you want its specific layout and permission file:

```powershell
pb-ai-code install --harness claude-code --pb-version 22.0
```

It writes `.claude/` and the same root `.mcp.json`. Do not run both layouts in
the same project unless you deliberately need both copies of the skill bundle.

### Verify and restart

A successful status check reports `"installed": true`:

```powershell
pb-ai-code status --target C:\Projects\MyApp --json
```

Read the installer output. It reports whether it added, updated, or preserved
MCP servers and whether it found PB Search. Then restart the assistant. Clients
usually load the skill list and MCP servers only when a session starts.

## Updating

Updating has two independent parts: the persistent commands and each generated
project bundle. `pb-ai-code update` handles both when you run it from an
installed project.

### Update commands and the current project bundle

From the project root, run:

```powershell
pb-ai-code update
```

The command checks the latest stable GitHub Release, compares it with the
persistent tool and the project's marker, then asks before changing anything.
When an update is available, it installs the release globally with `uv` and
uses that same release to refresh the project's skills, knowledge base, and MCP
configuration. Restart the assistant afterwards.

Use `--yes` only in an already approved non-interactive flow:

```powershell
pb-ai-code update --yes
```

Run this without an installed project to update only the persistent tool. A
project with no marker is not changed; use `pb-ai-code install` to configure it
for the first time.

### Check without changing anything

```powershell
pb-ai-code update --check
```

For an agent or another program, use the JSON form:

```powershell
pb-ai-code update --check --json
```

The response contains `update_available`, `global_update_available`, and, for
an installed project, `project_update_available`. Checks use GitHub Releases,
not the default Git branch. A successful check is cached in the current user's
local data directory for 24 hours; use `--refresh` to bypass the cache:

```powershell
pb-ai-code update --check --refresh
```

The generated `AGENTS.md` tells an agent to run the JSON check once at the
start of a session. If an update is available, it must offer the update and
wait for the user's approval. It must not update the user's global tool or the
project automatically.

### Pin a particular release

To install a specific release instead of the latest published release, use its
tag explicitly and then install it in each project:

```powershell
uv tool install --force git+https://github.com/restoresrl/pb-ai-code@v0.11.2
pb-ai-code install --target C:\Projects\MyApp
```

Replace `v0.11.2` with the release tag you chose. Do not omit the tag unless
you deliberately want the current default branch instead of a released version.
Re-run the last command for every project that should receive that release. The
marker file records the installed source and `pb-ai-code status` displays it.

### Update PB Search

Refresh the shared database separately:

```powershell
pb-appeon-index update --all
```

No project reinstall is needed after a database refresh because each MCP entry
already points to the same database path. Restart an active assistant session
if it has the server open.

## One-off use without global commands

Use `uvx` if you cannot or do not want to install persistent commands:

```powershell
uvx --from git+https://github.com/restoresrl/pb-ai-code@v0.11.2 `
  pb-ai-code install --target C:\Projects\MyApp --pb-version 22.0
```

This installs the project bundle but does not make `pb-ai-code` available in
future terminals. Build PB Search with the same one-off form if required:

```powershell
uvx --from git+https://github.com/restoresrl/pb-ai-code@v0.11.2 `
  pb-appeon-index update --all
```

For normal development, prefer the persistent installation in step 1.

## MCP client compatibility

The installer writes a neutral JSON `mcpServers` block to the project's root
`.mcp.json`.

- Claude Code reads this project file directly.
- Generic skill installation works for any client that can read the installed
  Markdown skills.
- Some clients use another MCP format. Codex uses TOML, OpenCode uses its own
  JSON shape, and Continue uses YAML. Translate the server values into that
  client's native configuration when required.

The installer preserves other servers in a valid existing `.mcp.json`. If the
file is invalid JSON, it leaves it unchanged and prints the block to merge by
hand.

## Optional formatter

[`pb-format`](https://github.com/restoresrl/pb-format) is a separate optional
PowerScript formatter. Install it independently:

```powershell
uv tool install git+https://github.com/restoresrl/pb-format@v0.1.0
```

The formatter changes no project until the project opts in with a
`.pb-format.toml` file. See
[`pb-source-format/style-conventions.md`](pb-source-format/style-conventions.md).

## Remove a project installation

Close the assistant, then remove the generated directories and file:

```powershell
Remove-Item -Recurse -Force .agents
Remove-Item -Force .mcp.json
```

For a Claude Code installation, remove `.claude` instead of `.agents`. Do not
remove `.mcp.json` if the project uses it for MCP servers that do not belong to
this kit.

For common failures, see [`troubleshooting.md`](troubleshooting.md). For a
coding agent's procedure, see [`agent-setup.md`](agent-setup.md).
