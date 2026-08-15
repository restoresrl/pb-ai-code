"""`AGENTS.md` — what the project is, as opposed to how PowerBuilder works.

The bundle answers the second question: skills, the antipattern catalog, the
source-format wiki, all of it generated and overwritten on every install. It
says nothing about *this* project, and an agent that walks into a PowerBuilder
repository needs both.

`AGENTS.md` is the cross-tool convention — Codex, Cursor, Copilot, Zed and
Claude Code all read it — so it is the right file for a kit that refuses to
assume a vendor.

**Two rules, and the second one is the whole design.**

1. Write only what was *established*: the version the user stated, the
   workspace and target files actually on disk, whether there is a text
   projection, whether there is git. Never a deduction dressed as a fact.
2. **Never touch a file that exists.** It is the project's document,
   hand-maintained, and an installer that rewrote it would destroy work on
   every update. When one is already there the block is printed instead, for
   the user to place.

The cost of getting rule 1 wrong is worth stating, because it is not obvious:
an agent trusts this file. A generated `AGENTS.md` that quietly goes stale
does not fail — it misinforms every session from then on, with authority.
Which is exactly why the PowerBuilder version is asked rather than sniffed,
and why the block below says out loud that a migration invalidates it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

FILE_NAME = "AGENTS.md"

#: The marker that makes our section findable again on a later install.
SECTION_HEADING = "## PowerBuilder facts an agent needs"


@dataclass(frozen=True)
class WorkspaceFacts:
    """Everything the block states, and nothing else.

    ``pb_version`` is what the user said, or ``None`` when nobody said.
    The rest is read off the disk, so it is checkable rather than believed.
    """

    pb_version: str | None
    workspaces: tuple[str, ...]
    targets: tuple[str, ...]
    has_projection: bool
    is_git: bool
    #: ``None`` when nothing true can be said — no git, or not a repository.
    sources_protected: bool | None = None


def survey(
    target: Path,
    *,
    pb_version: str | None,
    is_git: bool,
    sources_protected: bool | None = None,
) -> WorkspaceFacts:
    """Look at the project, shallowly and cheaply.

    Two levels deep: PowerBuilder workspaces sit at the root or one
    directory down (`src/`), and a recursive walk of a repository holding
    `.pbl` files and a decade of build output is not worth the seconds.
    """
    workspaces = sorted(
        str(p.relative_to(target)).replace("\\", "/")
        for p in (*target.glob("*.pbw"), *target.glob("*/*.pbw"))
    )
    targets = sorted(
        str(p.relative_to(target)).replace("\\", "/")
        for p in (*target.glob("*.pbt"), *target.glob("*/*.pbt"))
    )
    projection = any(target.glob("ws_objects")) or any(target.glob("*/ws_objects"))
    return WorkspaceFacts(
        pb_version=pb_version,
        workspaces=tuple(workspaces),
        targets=tuple(targets),
        has_projection=projection,
        is_git=is_git,
        sources_protected=sources_protected,
    )


def _lines(facts: WorkspaceFacts) -> list[str]:
    version = facts.pb_version or "**not stated** — see below"
    out = [
        SECTION_HEADING,
        "",
        "Written by `pb-ai-code install`. Everything here was either stated by a",
        "person or read off the disk; nothing was deduced. Edit it freely — the",
        "installer never rewrites this file once it exists.",
        "",
        f"- **PowerBuilder version: {version}**",
    ]
    if facts.pb_version is None:
        out += [
            "  Nobody stated it, so no agent should assume one. `pb_session_open`",
            "  requires it explicitly and there is no auto-pick, so the wrong",
            "  answer opens the library under a runtime nobody chose. Fill it in.",
        ]
    out += [
        "  It cannot be read back from the sources: an object keeps the release it",
        "  was last saved under, so a 2022 project can hold release 6 DataWindows.",
        "  **If this project is ever migrated** — in the IDE, or with a tool like",
        "  PowerGen — change the line above. Nothing else will notice, and every",
        "  agent that reads this file afterwards will be wrong.",
        "",
    ]

    if facts.workspaces:
        out.append(f"- Workspace: {', '.join(f'`{w}`' for w in facts.workspaces)}")
    else:
        out.append("- No `.pbw` was found at the root or one level down.")
    if facts.targets:
        out.append(f"- Targets: {', '.join(f'`{t}`' for t in facts.targets)}")

    if facts.has_projection:
        out.append(
            "- There is a `ws_objects/` text projection, so the sources are readable "
            "and diffable outside PowerBuilder."
        )
        if facts.sources_protected is False:
            # Said here because the line above, alone, reads as reassurance:
            # the projection is diffable, and the diffs are being rewritten
            # under it. An agent that trusts a clean `git status` on this
            # workspace is trusting a comparison git makes against its own
            # normalized copy, not against the bytes ORCA wrote.
            out += [
                "  **But git is translating their line endings.** No",
                "  `.gitattributes` rule exempts the `.sr*` files, so the index holds LF",
                "  while the working tree holds CRLF, and a change that lands in both the",
                "  `.pbl` and its projection can leave `git status` clean — surfacing as",
                "  drift on somebody else's checkout. The fix is `*.sr* -text` (plus",
                "  `*.pbl`, `*.pbd` as `binary`) and `git add --renormalize`, in its own",
                "  commit, before any write loop.",
            ]
    else:
        out.append(
            "- **No text projection.** The `.pbl` is the only artefact, so a change "
            "cannot be read as a diff after it lands."
        )
    if not facts.is_git:
        out.append("- **Not under version control.** Nothing here has history.")

    if not (facts.has_projection and facts.is_git):
        # Said in full, because half of it read on its own produces the
        # wrong conclusion - and did: an agent told the user an import here
        # was unrecoverable and to take a manual copy, while the apply loop
        # sitting in the same install already takes one.
        out += [
            "",
            "  What that does and does not mean, because the two halves get confused:",
            "",
            "  - A **failed** import is not a hazard here. `pb-apply-plan` snapshots the",
            "    `.pbl` before each fix and restores it byte for byte if the import or the",
            "    compile fails, so the library has either advanced by exactly that fix or is",
            "    identical to what it was. No manual copy is needed for that.",
            "  - A **successful** change that later turns out to be wrong is the real risk:",
            "    there is no history to go back to and no diff to read. That is what a copy,",
            "    or `git init`, actually buys.",
            "  - Anything written by hand, or by a tool other than the apply loop, has",
            "    neither protection.",
        ]
    out.append("")
    return out


def block(facts: WorkspaceFacts) -> str:
    """The section, as text, with a trailing newline."""
    return "\n".join(_lines(facts)) + "\n"


def read_version(target: Path) -> str | None:
    """The version an earlier install (or a person) wrote, if any.

    Used as the default when asking again, so a re-install is a keypress
    rather than an interrogation. Deliberately forgiving about the
    surrounding text: this is a file people edit.
    """
    path = target / FILE_NAME
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = re.search(r"PowerBuilder version:\s*\**\s*(\d{2}(?:\.\d{1,2})?)", text)
    return match.group(1) if match else None


def create(target: Path, facts: WorkspaceFacts) -> bool:
    """Write `AGENTS.md` when there is none. ``False`` when one exists.

    The check is the whole safety property, so it is one line and it is here
    rather than at the call site: an existing file is never opened, never
    appended to, never backed up and rewritten.
    """
    path = target / FILE_NAME
    if path.exists():
        return False
    header = [
        f"# {target.name}",
        "",
        "Instructions for AI coding agents working on this project.",
        "",
    ]
    path.write_text("\n".join(header) + "\n" + block(facts), encoding="utf-8", newline="\r\n")
    return True
