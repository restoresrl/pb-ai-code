# Install

`pb-ai-code` is a set of **skills, commands and knowledge** plus two
small local tools. It has no runtime of its own: an assistant reads the
skills, and the skills drive MCP tools. So installing it means three
things, in this order:

1. Check that [`pb-orca-mcp`](https://github.com/restoresrl/pb-orca-mcp) —
   the only required dependency — can reach your PowerBuilder.
2. Run the installer, which puts the skills where your assistant reads them
   **and** writes the MCP server configuration.
3. Optionally add the Appeon doc index and the `pb-format` formatter.

Nothing here is specific to one assistant or one model. Where a step
differs per client, the difference is called out.

## Quickstart

The whole sequence, with nothing explained. You need Windows and a
PowerBuilder **IDE** install; everything else is below. The rest of this page
is why each step exists and what to do when one fails.

```pwsh
# 0. Once per machine: uv, and git credentials for the private repositories.
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
git ls-remote https://github.com/restoresrl/pb-orca-mcp    # priming git auth;
                                                           # writes nothing

# 1. Is PowerBuilder reachable? No assistant involved yet.
uvx --from git+https://github.com/restoresrl/pb-orca-mcp@v0.2.4 --python 3.12-x86 `
    pb-orca-mcp doctor

# 2. Does it work on YOUR project? Writes nothing.
uvx --from git+https://github.com/restoresrl/pb-orca-mcp@v0.2.4 --python 3.12-x86 `
    pb-orca-mcp check C:\your\project\workspace.pbw --pb-version 22.0

# 3. Install the skills AND the MCP config into your PowerBuilder project.
git clone https://github.com/restoresrl/pb-ai-code
cd pb-ai-code
.\scripts\install-skills.ps1 -Target C:\your\project
```

Steps 1 and 2 must print `Doctor OK` and `Check OK`. **If they do not, stop
there** — nothing downstream can work around a PowerBuilder that is not
reachable, and both commands tell you what is wrong.

There is no fourth step. The installer writes the `pb-orca` server entry into
your project's `.mcp.json`, so you do not create it by hand; any other MCP
servers already in that file are left alone.

Open your assistant **with your PowerBuilder project as the working
directory** — not this repository — confirm the `pb_*` tools are listed (in
Claude Code, `/mcp`), and ask for a review: `/pb-review`, or the same request
in your own words, naming an object, a `.pbl` or a `.pbt`.

From then on you work in your own project. You come back here only to re-run
the installer when the kit has changed.

Four things that trip people up, each covered in detail below. Step 0 needs a
new shell afterwards, because the installer puts `uv` on `PATH` and the current
session will not see it. These repositories are **private**, so step 1 fails
with a git authentication error until access has been granted — that is what
the `ls-remote` in step 0 is for, and if *it* is refused, ask for access rather
than debugging anything else. `--python 3.12-x86` is **not
optional**, because PowerBuilder's ORCA DLL is 32-bit and `ctypes` cannot load
it from a 64-bit interpreter. And `--pb-version` is only needed when several
PowerBuilder versions are installed, which `check` will tell you.

## Requirements

| | |
| --- | --- |
| OS | Windows, for anything that touches a `.pbl` (ORCA is a Windows DLL). The knowledge pages and `pb-format` work anywhere. |
| PowerBuilder | An **IDE** install, 2019 or later. Runtime-only packages do not ship `pborc.dll`. Classic workspaces only — not the PB 2025 solution format. |
| Assistant | Anything that speaks MCP and can follow a Markdown instruction file. Skill auto-discovery is a bonus, not a requirement. |
| `uv` | Recommended, for `uvx`. [Install it](https://docs.astral.sh/uv/getting-started/installation/) or substitute your own Python environment management. |
| Python | 3.10+, only for the two local tools in [`tools/`](../tools/). `uv` fetches its own for everything else. |
| PowerShell | Only to run `scripts/install-skills.ps1`. `pwsh` runs on macOS and Linux too, and the script's job is copying two directories — doing it by hand is a fine substitute. |

### These repositories are private

`pb-orca-mcp`, `pb-format` and this repository are private during internal
dogfooding. Every `git+https://github.com/restoresrl/...` URL below is
therefore an **authenticated** fetch: `uv` shells out to `git`, so it uses
whatever credential helper your `git` already uses. If you can
`git clone` the repository, `uvx` can fetch it.

If you have not authenticated to GitHub on this machine, the first `uvx`
command fails with a git authentication error rather than anything about
PowerBuilder. `git clone https://github.com/restoresrl/pb-orca-mcp` once,
let the credential helper store the result, and retry.

## 1. Connect `pb-orca-mcp`

One `mcpServers` entry, which **the installer writes for you** in step 2.
This is what it writes — canonically
[`harness/mcp-servers.json`](../harness/mcp-servers.json):

```json
{
  "mcpServers": {
    "pb-orca": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/restoresrl/pb-orca-mcp@v0.2.4",
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

**The `@v0.2.4` is the pin, and it is the point.** Without it the URL means
"whatever the default branch happens to be right now", so two developers who
run the same command on different days get different servers, and any commit
reaches everyone the moment it lands. With it, a version is something a team
decides to move to. Drop the `@tag` if you would rather track the latest, and
`pb-orca-mcp --version` tells you which build you actually have.

Bumping it is one edit in one file — that file — followed by re-running the
installer wherever the kit is installed.

### Why the installer writes it, instead of you

Because the pin only works if it moves. A block copied by hand stays on
whatever tag was current the day it was copied, so the canonical file moves to
a new version and nobody follows: the pin quietly becomes documentation rather
than configuration, which is the opposite of what it is for. Installed
alongside the skills, the two are updated by the same command and cannot drift.

The consequence is worth stating plainly: **a project using this kit commits
nothing agentic** — no `.claude/`, no `.mcp.json`, no neutral stand-in file.
Re-running the installer is the entire synchronization story. This repository
follows its own rule, so its root `.mcp.json` is generated and gitignored, just
like `.claude/`.

Where the installer puts it:

| Client | Location |
| --- | --- |
| Claude Code | `.mcp.json` at the project root — written by `-Harness claude-code`. For a user-wide or machine-local entry instead, `claude mcp add` writes it for you; then use `-SkipMcpConfig`. |
| Cursor | `.cursor/mcp.json` (project) or `~/.cursor/mcp.json` (user) |
| Codex CLI, Gemini CLI, Copilot, others | that client's MCP config file — the JSON shape is the same |

Only Claude Code's location is written automatically, because it is the one
whose on-disk contract this repository has actually verified. `-Harness
generic` prints the block and tells you it is yours to place: inventing a path
for a client we have not tested would look like it worked.

Servers already in the target file are preserved — only the `pb-orca` key is
written. A target `.mcp.json` that does not parse is left untouched and the
block is printed instead, because a project's MCP config may hold servers that
have nothing to do with PowerBuilder.

The optional Appeon index in step 3 is deliberately **not** in the canonical
file: it needs a local Python environment and a database you build yourself, so
installing it everywhere would give every project one server that works and one
that fails to start.

**Verify before going further.** `pb-orca-mcp` has two CLI commands
that need no MCP client at all:

```pwsh
uvx --from git+https://github.com/restoresrl/pb-orca-mcp@v0.2.4 --python 3.12-x86 pb-orca-mcp doctor
uvx --from git+https://github.com/restoresrl/pb-orca-mcp@v0.2.4 --python 3.12-x86 pb-orca-mcp check <path-to.pbw>
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
docs/pb-antipatterns/       the knowledge the skills consult
docs/pb-source-format/
harness/mcp-servers.json    the pb-orca MCP server, pinned — every client
harness/<harness>/          per-assistant config (permissions, ...)
```

No assistant reads those paths. `scripts/install-skills.ps1` copies them
into the layout a given assistant expects, so one source of truth serves
every tool:

```pwsh
# Into this repository itself, to work on the skills:
.\scripts\install-skills.ps1

# Into a PowerBuilder workspace:
.\scripts\install-skills.ps1 -Target ..\my-pb-app

# Anything else: point it at the directory your assistant reads
.\scripts\install-skills.ps1 -Target ..\my-pb-app -Harness generic -SkillsDir .agent\skills

# The MCP servers are managed elsewhere (e.g. `claude mcp add` at user scope):
.\scripts\install-skills.ps1 -Target ..\my-pb-app -SkipMcpConfig

# See the plan without writing:
.\scripts\install-skills.ps1 -Target ..\my-pb-app -DryRun
```

`-Harness claude-code` (the default) writes `<target>/.claude/skills/`,
`<target>/.claude/commands/`, `<target>/.claude/settings.json` and
`<target>/.mcp.json`. `-Harness generic` writes the skills wherever you point
it, skips the assistant-specific settings file, and prints the MCP block
rather than placing it.

**The install also vendors the knowledge base**, as `pb-ai-code-docs/` beside
the skills, and rewrites the links inside the installed skills to point at it.
Without that, `pb-review` would tell the assistant to work through an
antipattern catalog that is not there, and `pb-src-format` — which is almost
entirely pointers into the format wiki — would be inert.

It lands beside the skills rather than in the project's own `docs/`, which
belongs to the host project. And it happens on a self-install too, not only
when vendoring: the installed tree is one level deeper than the canonical one
either way, so `../../docs/` — correct from `skills/<name>/` — would resolve
to a `docs/` inside the harness directory once installed.

That copy is a **snapshot**. When a skill grows the wiki, the change belongs
upstream in this repository; an edit inside an installed `pb-ai-code-docs/` is
discarded by the next install.

Every skill is installed, not a subset: a skill left out is a dangling
cross-reference in the ones that ship, and the saving is a handful of
Markdown files.

Two things the script does deliberately:

- It writes a **marker file** recording the source commit and what it did
  with the MCP config, so drift between an installed copy and this
  repository is auditable. Make changes here and re-run; do not patch the
  installed copy.
- **Everything it writes is build output, and belongs in the target's
  `.gitignore`** — `.claude/`, `.mcp.json`, the vendored knowledge base.
  A project that uses this kit commits nothing agentic; re-running the
  installer is what keeps a team on one version. The marker file records
  the source commit, so "are we all on the same toolchain" is answered by
  reading it rather than by trusting that everyone re-installed.

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

It takes two steps you have to do yourself, and the paths it needs are
machine-specific, which is why it is not in `harness/mcp-servers.json`:

```pwsh
# 1. A Python environment with this repository's tools installed
uv venv
uv pip install -e ".[dev]"

# 2. Scrape and index (idempotent — re-run it to pick up doc changes)
.venv\Scripts\pb-appeon-index update
```

Then add a second server entry by hand, pointing at that interpreter. The
installer only ever writes the keys it owns, so an entry you add here survives
re-installs. Use an **absolute** path unless you are certain your client
launches servers with the repository as their working directory:

```json
"pb-appeon-index": {
  "command": "C:\\path\\to\\pb-ai-code\\.venv\\Scripts\\python.exe",
  "args": ["-m", "pb_appeon_index", "serve-mcp"],
  "env": { "PB_APPEON_INDEX_DB": "C:\\path\\to\\pb-ai-code\\docs\\appeon-index\\index.db" }
}
```

On macOS or Linux the interpreter is `.venv/bin/python` instead.

The database is never redistributed: each developer builds it locally from
the live site. Full detail, including the multi-version config, is in
[`appeon-index/README.md`](appeon-index/README.md).

## 4. Optional: the `pb-format` formatter

[`pb-format`](https://github.com/restoresrl/pb-format) normalizes
PowerScript style (indent, keyword case, operator spacing, line
endings). It is a standalone CLI, independent of PowerBuilder and ORCA.

```pwsh
uv tool install git+https://github.com/restoresrl/pb-format@v0.1.0
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

**From the PowerBuilder workspace.** Run the installer against it — which
places the skills and the MCP config together — and work with the project as
the working directory. This is the natural setup for day-to-day work, and it
is what lets `.pb-review/` plan files and `CHANGELOG.md` land in the right
repository.

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
