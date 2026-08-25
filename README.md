# pb-ai-code

`pb-ai-code` adds PowerBuilder workflows to an MCP-capable coding assistant.
It installs review and refactoring skills, a PowerBuilder knowledge base, and
the MCP configuration needed to use `pb-orca-mcp`.

## Start here

Set up the machine once, then install the kit in each PowerBuilder project.
The normal path uses `uv tool install`, so `pb-ai-code` and
`pb-appeon-index` are available from PowerShell and Command Prompt.

### Set up the machine

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) once:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Open a new terminal, then install this release and check that both commands
are available:

```powershell
uv tool install git+https://github.com/restoresrl/pb-ai-code@v0.11.1
pb-ai-code --version
pb-appeon-index --help
```

The `@v0.11.1` suffix pins the install to that release. If you omit it, `uv`
installs the repository's default branch, not GitHub's latest release. The two
checks do not change anything: `pb-ai-code --version` prints the installed kit
version, and `pb-appeon-index --help` verifies the optional PB Search command
without downloading documentation.

Build the optional PB Search database once. It is shared by every project for
this Windows user:

```powershell
pb-appeon-index update --all
```

The database is created at `%USERPROFILE%\.pb-appeon-index\index.db`. Building
it downloads Appeon documentation and can take several minutes. Skip this step
if language-reference search is not needed yet; run it later and reinstall the
project bundle.

### Set up a PowerBuilder project

Run these commands from the project root, or provide `--target`:

```powershell
cd C:\Projects\MyPowerBuilderApp
pb-ai-code install --pb-version 22.0
pb-ai-code status --json
```

The default generic layout writes `.agents/skills`, `.agents/commands`, and
`.mcp.json` at the project root. Add the generated paths to `.gitignore` when
the installer asks. Restart the assistant after installation so it reloads
skills and MCP servers.

For Claude Code, use its explicit layout instead:

```powershell
pb-ai-code install --harness claude-code --pb-version 22.0
```

The project directory must already exist. The installer does not create it.

### Update

Install a newer release globally, then rerun the project install in every
project that should receive it:

```powershell
uv tool install --force git+https://github.com/restoresrl/pb-ai-code@v0.11.1
pb-ai-code install --target C:\Projects\MyPowerBuilderApp
```

Replace `v0.11.1` with the release tag you want. Keep the tag unless you
intentionally want the current default branch instead of a release. Refresh PB
Search separately when needed:

```powershell
pb-appeon-index update --all
```

The complete procedures, including one-off `uvx` use, are in
[`docs/install.md`](docs/install.md).

## For coding agents

An agent must not assume the machine setup exists. It should check `uv`, ask
before changing a user's machine-wide tools or downloading the PB Search
index, then install the bundle in the project and ask the user to restart the
session. Follow [`docs/agent-setup.md`](docs/agent-setup.md).

## What it provides

- `pb-review`: structured review that produces an actionable plan.
- `pb-apply-plan`: controlled application of accepted review fixes.
- `pb-context-build` and `pb-impact-analysis`: scoped context and impact
  analysis for large legacy workspaces.
- `pb-src-format` and `pb-format`: source-format knowledge and optional style
  normalization guidance.
- `appeon-query`: local search of the optional Appeon documentation index.

Every write to a `.pbl` goes through
[`pb-orca-mcp`](https://github.com/restoresrl/pb-orca-mcp). The kit reads the
PowerBuilder-managed `ws_objects/` projection but never edits it directly.

## Documentation

[`docs/README.md`](docs/README.md) is the documentation index. It separates
installation and operation guides, the PowerBuilder knowledge base, and
maintainer-only design records.

## Requirements

Working with `.pbl` files requires Windows and a PowerBuilder IDE installation
from 2019 or later. A runtime-only installation does not include the ORCA DLL.
The knowledge base and optional formatter do not require PowerBuilder.

The default generic MCP file is neutral JSON. Claude Code can read it directly.
Other clients may require their own MCP format; see
[`docs/install-reference.md`](docs/install-reference.md#mcp-client-compatibility).

## Contributing

Installed skills and knowledge are generated snapshots. Do not edit them in a
consumer project because the next install replaces them. Record discoveries in
a review plan and follow [`docs/wiki-notes.md`](docs/wiki-notes.md) to bring
them back to this repository.

For work on this repository itself, read [`AGENTS.md`](AGENTS.md).

## License

MIT. See [`LICENSE`](LICENSE).
