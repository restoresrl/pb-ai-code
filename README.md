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
uv tool install git+https://github.com/restoresrl/pb-ai-code@v0.13.0
pb-ai-code --version
pb-appeon-index --help
```

The `@v0.13.0` suffix pins the install to that release. If you omit it, `uv`
installs the repository's default branch, not GitHub's latest release. The two
checks do not change anything: `pb-ai-code --version` prints the installed kit
version, and `pb-appeon-index --help` verifies the optional PB Search command
without downloading documentation.

Set up the optional PB Search database once. It detects the exact
PowerBuilder releases installed on this machine and indexes their matching
Appeon documentation:

```powershell
pb-ai-code search setup
```

The database is created at `%USERPROFILE%\.pb-appeon-index\index.db`. Building
it downloads documentation and can take several minutes. Skip this step if
language-reference search is not needed yet; run it later. A database refresh
does not require a project reinstall.

### Set up a PowerBuilder project

Run these commands from the project root, or provide `--target`:

```powershell
cd C:\Projects\MyPowerBuilderApp
pb-ai-code install --pb-version pb2022r3
pb-ai-code status
```

`pb2022r3` is the project's exact Appeon release slug. It selects the
matching documentation and derives ORCA's `22.0` token automatically; do not
pass `22.0` to `pb-ai-code install`, because it cannot distinguish PB 2022,
2022 R2, and 2022 R3.

The default generic layout writes `.agents/skills`, `.agents/commands`, and
`.mcp.json` at the project root. Add the generated paths to `.gitignore` when
the installer asks. Restart the assistant after installation so it reloads
skills and MCP servers.

For Claude Code, use its explicit layout instead:

```powershell
pb-ai-code install --harness claude-code --pb-version pb2022r3
```

The project directory must already exist. The installer does not create it.

### Update

From inside an installed project, let the tool find the latest published
GitHub Release, update the persistent command, and then refresh that project's
bundle:

```powershell
cd C:\Projects\MyPowerBuilderApp
pb-ai-code update
```

The command shows what it will change and asks before it proceeds. On Windows,
it schedules the work after the running command exits because the executable
would otherwise lock its own files. Keep the terminal open until `uv` finishes.
Use `--yes` only when you have already approved those machine-wide and project
changes:

```powershell
pb-ai-code update --yes
```

Outside an installed project, the same command updates only the persistent
tool. To check without changing anything, use:

```powershell
pb-ai-code update --check
```

The release check uses GitHub Releases and is cached locally for 24 hours. Use
`--refresh` when you need a fresh result.

To run startup checks before an assistant session, use:

```powershell
pb-ai-code session-start
```

That command reports the installed bundle, checks for updates, and asks before
running `pb-ai-code update`. Run it manually, wire it into a client startup
hook, or ask your local assistant to create a hook for its harness. The
generated `AGENTS.md` does not trigger the preflight automatically, because
that would make the first answer about updates instead of the user's request.

To select a particular release instead, install its tag explicitly and then
refresh each project that should receive it:

```powershell
uv tool install --force git+https://github.com/restoresrl/pb-ai-code@v0.13.0
pb-ai-code install --target C:\Projects\MyPowerBuilderApp
```

Keep the tag unless you intentionally want the current default branch instead
of a release. Refresh documentation for the releases installed on this machine when needed:

```powershell
pb-ai-code search update
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
