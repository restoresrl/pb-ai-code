# pb-ai-code

An agentic dev kit for **PowerBuilder**: skills, ingested
documentation, and named flows that let an AI coding assistant read,
review, refactor and extend a real PB codebase.

Where [`pb-orca-mcp`](https://github.com/restoresrl/pb-orca-mcp)
exposes PowerBuilder's ORCA API as MCP tools — the engine —
`pb-ai-code` is the layer above it: what to do with those tools, in
what order, and what to know before touching a 25-year-old monolith.

It is **assistant-agnostic and model-agnostic by construction.** The
skills are plain Markdown in the [Agent Skills](https://agentskills.io)
`SKILL.md` format, they name MCP tools rather than client features, and
an installer materializes them into whatever directory your assistant
reads. Nothing here assumes a particular vendor.

## Agents: setting this up in a PowerBuilder project

**If you are an AI coding agent and someone has asked you to set this kit up
in the project they have open, this section is the whole job.** It is written
for a machine to follow: every branch is stated, and every step has a check
that is mechanical rather than "see if it looks right". Nothing below needs a
clone of this repository.

### 1. Check the prerequisites

| Needed for | Check | If it is missing |
| --- | --- | --- |
| Running the installer at all | `uv --version` | Stop and tell the user. `uv` is installed with `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"`, but that is their machine — ask before running it |
| Anything that touches a `.pbl` | Windows, and a PowerBuilder **IDE** install, 2019 or later | Say so and continue. The install still works and the knowledge base is still useful; only the ORCA tools will not start |

Do not check for a PowerBuilder workspace first. A repository holding PB
sources is a valid target whether or not a `.pbw` is where you expect it.

### 2. Decide which layout to write

| You are | Use |
| --- | --- |
| Claude Code | nothing — it is the default |
| anything else (Codex CLI, OpenCode, Cursor, Windsurf, Continue, Aider, …) | `--harness generic --skills-dir <dir> --commands-dir <dir>` |

Be straight with the user about what that second row means today: only Claude
Code's on-disk contract is verified here, so `generic` writes the skills and
the knowledge base where you say, and **prints** the MCP server block instead
of guessing which file your client reads. You place that block. Inventing a
path for a client nobody has tested would look like it worked.

The two directories must be siblings and the skills one must be named
`skills` — the knowledge base contains links that spell that segment out, and
the installer refuses rather than writing a bundle whose cross-links are dead.
`.agent/skills` and `.agent/commands` are the conventional answer.

### 3. Ask the user which PowerBuilder version this project uses

**Ask. Do not work it out.** You will be tempted, because the answer looks
readable: an exported object carries `appruntimeversion`. It is not the
project's version. PowerBuilder migrates the objects it touches and leaves the
rest, so an object holds the release it was *last saved under* — a project
built with 2022 can contain DataWindows still marked release 6. An answer read
off one object is plausible, specific, and sometimes four majors wrong.

It matters because `pb_session_open` takes the version explicitly and has no
auto-pick, and these machines routinely carry 19, 22 and 25 side by side.
Opening a library under the wrong one and re-importing an object rewrites it to
that release, quietly.

So put the question to the user — *"which PowerBuilder version is this project
developed with?"* — and pass what they say:

```pwsh
uvx --from git+https://github.com/restoresrl/pb-ai-code pb-ai-code install --pb-version 22.0
```

If they do not know, install without the flag. The version is then recorded as
**not stated**, which is a gap somebody can close later — and better than a
number nobody checked.

### 4. Install

Run this **from the root of the user's project**, with the version from step 3
if you have one:

```pwsh
uvx --from git+https://github.com/restoresrl/pb-ai-code pb-ai-code install
```

That is the whole install. `uv` fetches this repository, builds it, and runs
the CLI, which writes into the current directory — there is no checkout to
make and no path to work out. Append the tag to the URL to pin a version; with
no tag you get the default branch.

Add `--dry-run` first if you want to show the user what would be written. It
prints the plan and what the MCP merge would do, and writes nothing.

### 5. Verify, mechanically

```pwsh
uvx --from git+https://github.com/restoresrl/pb-ai-code pb-ai-code status --json
```

`"installed": true` and a `"source"` naming a version is the pass. The same
answer in prose, plus what the install did and the PowerBuilder version it was
told, is in `<skills-dir>/_installed-from-pb-ai-code.txt` — that file is the only record
the project keeps of where the kit came from, and `status` reads it back with
no network.

Then read the installer's own output rather than assuming: it names every
file it wrote, says whether each MCP server was added, updated, already
current or left alone, and warns when it replaced a `settings.json` whose
content differed. If it printed a warning, relay it.

### 6. Tell the user to restart you

Skill *bodies* are read from disk when invoked, so they are live immediately.
The **list** of skills and the **MCP servers** are read when your session
starts, so the `pb_*` tools do not exist until the user restarts. Say that
plainly; an agent that starts working without them will report the kit as
broken.

The install also creates an `AGENTS.md` if the project has none — the project's
own instruction file, carrying the PowerBuilder version and what was read off
the disk. If one already exists it is **never** touched: the installer prints
the section instead, for the user to place. Relay it rather than editing their
file yourself.

If the installer said the bundle directory is not ignored by git, offer the
`.gitignore` lines it printed. The bundle is generated: it is updated by
re-running the installer, not by editing it, and it does not want committing.

### 7. When it fails

- **`uvx` cannot resolve the URL** — the machine has no network, or `git` is
  not on PATH. Report which.
- **"Target is not a directory"** — you passed `--target` at a path that does
  not exist. The installer never creates it, on purpose.
- **The MCP config could not be parsed** — the project's existing
  `.mcp.json` is not valid JSON. The installer leaves it untouched and prints
  the block to merge by hand. Do not repair the file without asking; it is the
  user's.
- **Two ORCA servers** — the project already has `pb-orca-mcp` under another
  key. The installer says so and changes nothing. Two of them means two
  processes driving a single-session library; the user picks which to keep.

Then read [`AGENTS.md`](AGENTS.md) if you are going to work on *this*
repository, or [`docs/install.md`](docs/install.md) for the human-facing
version of the above with the reasoning attached.

## What it does

The primary use case is **code review and refactoring of legacy
PowerBuilder**. Greenfield PB development is rare; the realistic
audience is people maintaining decades-old monolithic applications.

The main flow, `/pb-review`, goes: frame the scope with you → build a
*budgeted* context pack from the PBLs (you cannot read a monolith all
at once) → state its understanding and wait for you to confirm it →
review against a catalog of PB-specific hazards → write a plan file and
a CHANGELOG entry that outlive the session → apply the fixes one at a
time, each with a visible diff and a compile check.

Two properties it is built around: **it stops before spending your
budget**, and **its output persists**. A plan file can be edited by
hand, committed, and resumed by a different assistant days later.

## Contents

| | |
| --- | --- |
| [`skills/`](skills/) | The flows. `pb-review` (structured review), `pb-apply-plan` (the edit loop), `pb-context-build` (scoped context from a monolith), `pb-scaffold` (new objects), `pb-src-format` (the `.sr*` format), `pb-format` (style), `appeon-query` (language lookups). |
| [`commands/`](commands/) | Slash-command wrappers — thin; each delegates to the skill of the same name. |
| [`docs/pb-source-format/`](docs/pb-source-format/) | A wiki on the textual layout of each `.sr*` entry type. No upstream spec exists, so it is reverse-engineered and grows as cases are met. |
| [`docs/pb-antipatterns/`](docs/pb-antipatterns/) | PB-specific hazards with reproductions and idiomatic fixes — the bugs that compile fine and bite in production. |
| [`tools/pb-appeon-index/`](tools/pb-appeon-index/) | Scrapes `docs.appeon.com` once into a local SQLite FTS5 database and serves it as four MCP tools. A language lookup costs ~400 tokens instead of a few thousand. |
| [`tools/pb-source-analyzer/`](tools/pb-source-analyzer/) | Bootstraps the format wiki from a real `.sr*` corpus, anonymizing project-specific identifiers on the way in. |

## Install

From the root of your PowerBuilder project:

```pwsh
uvx --from git+https://github.com/restoresrl/pb-ai-code pb-ai-code install
```

There is nothing to clone. `uv` fetches this repository, and the CLI writes
the skills, the knowledge base and the MCP server configuration into the
directory you ran it from. `pb-ai-code status` says what landed; re-running
`install` is also how you update.

Or hand the job to your assistant: point it at this repository's URL and ask
it to set the kit up. The [section above](#agents-setting-this-up-in-a-powerbuilder-project)
is written for exactly that, which is why it reads like a checklist.

**[`docs/install.md`](docs/install.md)** is the same thing with the reasoning
attached: why each step exists, where the `mcpServers` block goes for each
client, how to verify the stack before trusting it, and what to do when your
assistant has no slash commands or no skill discovery.

One thing worth knowing before you begin: everything that touches a `.pbl`
needs Windows with a PowerBuilder **IDE** install. The knowledge base and the
formatter work anywhere.

## Dependencies

- **[`pb-orca-mcp`](https://github.com/restoresrl/pb-orca-mcp)** —
  required. Every `.pbl` operation goes through it; no ORCA primitive is
  reimplemented here. Consumed like any other MCP server, from its
  GitHub repository.
- **[`pb-format`](https://github.com/restoresrl/pb-format)** — optional.
  A standalone PowerScript style formatter. Without it, the dev kit
  simply does not normalize style.
- **The Appeon doc index** — optional, built locally from
  [`tools/pb-appeon-index/`](tools/pb-appeon-index/). Without it, the
  `appeon-query` skill says so instead of guessing.
- **An MCP-capable assistant.** Skill auto-discovery is a bonus, not a
  requirement.

## Requirements

Windows and a PowerBuilder **IDE** install (2019 or later) for anything
that touches a `.pbl` — ORCA is a Windows DLL, and runtime-only packages
do not ship it. Classic workspaces only, not the PB 2025 solution
format. The knowledge pages and the formatter work anywhere.

## Status

Alpha, in internal dogfooding. The review flow and the knowledge base are
written and being exercised against real codebases. Public since v0.5.0, which
is also the release that made the kit install itself from this URL rather than
from a clone — the two go together, since an agent cannot follow instructions
it cannot read. Testing orchestration and runtime trace analysis are designed
but deferred — see [`PLAN.md`](PLAN.md).

## Contributing

The knowledge base is the part most worth contributing to, and it needs
no AI: a corrected format page, a new antipattern with a reproduction,
or a variant the wiki has not seen are all directly useful.

If the discovery happened while working on your own PowerBuilder project
rather than in this repository, you were reading an installed
**snapshot** — the next install overwrites it. The route back is a note
in the review's plan file, and
[`docs/wiki-notes.md`](docs/wiki-notes.md) explains the shape and what to
do with one.

If you are an agent working on this repository, read
[`AGENTS.md`](AGENTS.md).

## License

MIT — see [`LICENSE`](LICENSE).

## Author

Carlo Torrese — Restore srl — `carlo.torrese@re-store.it`
