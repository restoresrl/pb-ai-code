# Plan: pb-ai-code installs itself, from the project that consumes it

Status: **phases 0, 1 and 2 done in v0.5.0.** Updated 2026-08-12.

## The goal, restated so it can be checked

1. A user opens a PowerBuilder repository with any agentic editor (Claude
   Code, Codex, OpenCode, …).
2. They tell the agent: *I want to work in this repository using pb-ai-code,
   which is at <https://github.com/restoresrl/pb-ai-code>*.
3. The agent reads that repository, follows the instructions it finds there,
   installs and configures. From that moment on, work can start.
4. Later, still from inside the project, the user asks whether there is a new
   version; the agent follows the instructions on GitHub and updates.

The constraints, stated explicitly because each one rules something out:

- **The direction inverts.** It used to install *from* a checkout of
  pb-ai-code towards a target. It has to start from the consumer repository.
- **Total independence from the machine.** No pre-existing checkout, no user
  skills in `~/.claude`, no memory outside the repository.
- **There is a way back.** The skills have to know how to open an issue or a
  PR against pb-ai-code when kit defects, new wiki material or antipatterns
  come up during work. What comes back reaches every user at their next
  update.
- **pb-format is first class**, like pb-orca, not optional.

## The three things that made the flow impossible

### 1. All three repositories were private: CLOSED 2026-08-12

`pb-ai-code`, `pb-orca-mcp` and `pb-format` were made **public**. Step 3 of
the goal became possible with that: an agent can read the instructions over
the web with no credentials, and `uvx --from git+https://...` no longer needs
a configured credential helper.

This was phase 0 and it blocked everything else, because public and private
produce two different bootstraps.

What made the choice safe is still true: pb-ai-code holds no customer code:
skills, format documentation, two Python tools. Customers' PowerBuilder
sources stay in their own repositories.

### 2. The installer was PowerShell and lived in the checkout: CLOSED in v0.5.0

`scripts/install-skills.ps1` resolved its source from `$PSScriptRoot/..`: it
assumed it was running *inside* pb-ai-code and pointing at a target. Exactly
the opposite of the direction wanted, and it tied everything to PowerShell.

Replaced by a Python CLI shipped in the wheel and run from the consumer
project. The script stays in the tree for one release with a deprecation
banner and is deleted after.

### 3. One adapter only: STILL OPEN

`harness/` holds `claude-code` and nothing else (`generic` is not a directory,
it is a branch of the installer). Codex, OpenCode and the rest have different
layouts for skills, commands and MCP configuration, so step 1 of the goal is
fully true only for Claude Code. `generic` covers the others honestly rather
than completely: it writes the bundle where told and prints the MCP block
instead of guessing a path and a dialect.

## The architecture

### The core: pb-ai-code became a self-installing CLI

The same mechanism the kit already used for `pb-orca-mcp`, applied to itself:

```pwsh
uvx --from git+https://github.com/restoresrl/pb-ai-code pb-ai-code install
```

One command, from any directory. Nothing to clone first, no PowerShell, no
absolute path to work out: `uv` fetches the repository, runs the CLI, and the
CLI installs **into the current directory**. The direction is right because
the working directory is the consumer project.

The blocker, found by building a wheel rather than by reasoning about one:
`[tool.hatch.build.targets.wheel]` packaged only the two tool packages, so a
wheel built from a clean checkout carried 18 files and **not one** the
installer needs. Fixed with six `force-include` mappings, and never a mapping
of the `docs` root: `force-include` ignores `.gitignore` *and* `exclude`, so
that one line would drag a 4.5 MB index database in from any machine that had
built one.

Verbs today: `install`, `status`. Deferred: `check-update`, `update`,
`report`.

### The bootstrap: what the agent reads

`README.md` gained a section written **for a machine**, at the top and
recognisable: prerequisites with the command that checks each one, how to
pick a layout, the one command to run, a mechanical verification
(`status --json`), what to say about restarting, and a failure branch for each
way it can go wrong. `AGENTS.md` carries a pointer to it, because that is the
file most harnesses read first.

### Harness adapters

A declarative manifest per harness saying where things go:

| harness | skills | commands | MCP | instructions |
|---|---|---|---|---|
| claude-code | `.claude/skills/` | `.claude/commands/` | `.mcp.json` | `.claude/settings.json` |
| codex | via AGENTS.md | - | `~/.codex/config.toml` | `AGENTS.md` |
| opencode | `.opencode/` | - | `opencode.json` | `AGENTS.md` |
| generic | `.agents/skills/` | - | `.agents/mcp.json` | `AGENTS.md` |

Only `claude-code` and `generic` exist today. The abstraction is shaped so the
others slot in without rework.

One thing the research corrected, which three documents in this repository had
wrong: **the MCP block is not the same JSON everywhere.** Codex is TOML,
OpenCode fuses the command into one array and calls the env key
`environment`, Continue is YAML with a `name` inside the entry, Aider has no
MCP at all. Only Cursor shares Claude Code's shape. That sentence was exactly
what would make someone build a one-shape emitter.

### The Appeon index as a release asset: NOT DONE

`docs/appeon-index/index.db` is 4.5 MB and every user builds it by scraping
docs.appeon.com: slow, fragile, and on the critical path of an install. As a
**release asset** attached to each tag, the CLI would download it into a
machine cache: derived data, not configuration.

v0.5.0 only re-rooted the *discovery* (env var → `~/.pb-appeon-index/index.db`
→ a checkout) and rewrote the server entry to use `uvx` instead of a
checkout's `.venv`.

### pb-format first class: NOT DONE

It should become a pinned dependency like `pb-orca-mcp`, installed by the CLI,
with its skill no longer saying "optional, probably not installed".

Open: whether `install` should also generate a starter `.pb-format.toml`, or
whether the per-workspace opt-in stays.

### The way back: contributing from inside the consumer: NOT DONE

Four pieces: a `CONTRIBUTING.md` written for agents as well as people; issue
templates for the four shapes of report (kit defect, wiki note, proposed
antipattern, unverified PowerScript semantic); a `pb-ai-code report` verb that
opens the issue with `gh` and, when `gh` is absent, writes the text to a file
rather than losing it; and the hook in the skills that offers to send an
accumulated note.

The delicate part, to be designed rather than bolted on: an automatic report
can contain customer code. The template has to ask for a minimal, anonymised
example, and the command has to show what it is about to send.

## Phases

- **Phase 0, decide repository visibility. DONE 2026-08-12**: all three
  public.
- **Phase 1, the CLI, `install` and `status`. DONE in v0.5.0.** Behavioural
  parity with the PowerShell script, verified by running both against
  identically seeded targets and diffing.
- **Phase 2, the agent-first bootstrap. DONE in v0.5.0.** README and
  AGENTS.md written for a machine. The honest test of it is a fresh session in
  a clean repository holding nothing but the URL, which is a thing to run
  rather than a thing to write.
- **Phase 3, adapters.** codex, opencode, then the rest. Testable only by
  opening a repository with that editor.
- **Phase 4, `check-update` and `update`.** Query the tags, compare with the
  marker, re-install. The marker already records the version and a recipe that
  names the harness.
- **Phase 5, the index as a release asset.**
- **Phase 6, pb-format first class.**
- **Phase 7, the way back.**
- **Phase 8: end-to-end on the two test repositories, from zero.**

## What can be tested here, and what cannot

**Can**, on `test-pb-orca-mcp-git` and `test-pb-orca-mcp-nogit`: remove the
kit entirely, install from the consumer side, diff the result against an
install from the other direction, and repeat for the update path. The Claude
Code route is testable in full.

**Cannot**: the Codex and OpenCode adapters. Being that harness is the only
way to observe what it actually reads. The manifest can be written from their
documentation and a verification checklist prepared; the confirmation comes
from opening a repository with that editor.

**Cannot either**: genuinely simulate an agent that has never seen
pb-ai-code. A session that helped build the thing knows all the answers. The
honest test of phase 2 is a new session in a clean repository with nothing but
the URL: someone else runs that one.
