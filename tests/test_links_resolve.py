"""Every relative Markdown link resolves — in the repository *and* once installed.

This repository ships two documentation trees that the skills link into, and
the installer copies them somewhere else and rewrites the links to match. So a
link can be correct here and dead in the only place a consumer ever reads it,
which is not a hypothetical: an audit in 2026-08 found **28** dead links in an
installed bundle while the repository itself was clean, and adding one guide in
2026-08 produced five more the same way.

Checking the canonical tree alone therefore proves very little. The second test
below installs into a temporary directory, for both harness layouts, and checks
what actually lands.

What installs is `python -m pb_ai_code install`, run as a subprocess. It used
to be `scripts/install-skills.ps1`, which meant the whole knowledge-base
contract was being verified against the installer that is being replaced: the
port could drop a doc tree, misplace `pb-ai-code-docs/` or narrow the rewrite
and this file would stay green. The `shutil.which("pwsh")` guard went with it —
it was the mechanism by which the check could silently no-op, and a check whose
entire job is to catch what only appears post-install has no business skipping
itself (`docs/cli-port-spec.md` §6).

`scripts/install-skills.ps1` stays in the tree for one more release
(cli-port-spec §7) and is still what `README.md` and `docs/install.md` tell a
consumer to run, so it keeps a guard of its own — the third test, which pins
the one thing about it that can rot while it sits there frozen.

Links inside fenced code blocks are ignored: those illustrate generated output
— a plan file's `([plan](.pb-review/…))` bullets, for instance — and are not
links the document is making.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from pb_ai_code import harness as harness_mod
from pb_ai_code import plan as plan_mod

REPO_ROOT = Path(__file__).resolve().parent.parent

MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
SKIP_SCHEMES = ("http://", "https://", "#", "mailto:")

#: How a skill reaches the knowledge base in *this* tree, and therefore the
#: form that must not survive an install: two levels up from `skills/<name>/`
#: is the repository root here and the bundle directory there. The installer
#: rewrites it to `../../pb-ai-code-docs/`; anything left spelled this way is
#: a link the rewrite did not reach.
PRE_REWRITE_DOCS_PREFIX = "../../docs/"


def _prose_only(markdown: str) -> str:
    """Drop fenced code blocks, keeping the text that makes real links."""
    kept, fenced = [], False
    for line in markdown.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            kept.append(line)
    return "\n".join(kept)


def dead_links(markdown_files: list[Path], base: Path) -> list[str]:
    """Relative link targets that do not exist, as `file -> target` strings."""
    dead = []
    for md in markdown_files:
        try:
            text = _prose_only(md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        for target in MD_LINK.findall(text):
            if target.startswith(SKIP_SCHEMES):
                continue
            if not (md.parent / target.split("#")[0]).resolve().exists():
                dead.append(f"{md.relative_to(base)} -> {target}")
    return dead


def _tracked_markdown() -> list[Path]:
    """Markdown git considers part of the repository.

    Using git rather than a glob keeps `.venv/` out — third-party packages ship
    their own broken links and they are not ours to fix — and keeps the
    generated `.claude/` out, which is a copy of `skills/` and would double
    every finding.
    """
    out = subprocess.run(
        [
            "git",
            "-C",
            str(REPO_ROOT),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "*.md",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [REPO_ROOT / line for line in out.splitlines() if line and (REPO_ROOT / line).is_file()]


def test_canonical_tree_has_no_dead_links() -> None:
    files = _tracked_markdown()
    assert files, "no tracked Markdown found — is this a git checkout?"
    dead = dead_links(files, REPO_ROOT)
    assert not dead, "dead relative links in the repository:\n  " + "\n  ".join(dead)


@pytest.mark.parametrize(
    ("harness", "extra_args", "installed_subdir"),
    [
        ("claude-code", [], ".claude"),
        # The generic layout has to name both directories, and they have to be
        # siblings: the commands link into the skills as `../skills/<name>/`.
        (
            "generic",
            ["--skills-dir", ".agent/skills", "--commands-dir", ".agent/commands"],
            ".agent",
        ),
    ],
)
def test_installed_layout_has_no_dead_links(
    tmp_path: Path, harness: str, extra_args: list[str], installed_subdir: str
) -> None:
    """The layout a consumer actually reads.

    Installed, `skills/<name>/SKILL.md` sits one level deeper than it does
    here, so `../../docs/` stops meaning the repository root — which is why the
    installer rewrites those links, and why this has to be checked against the
    result rather than reasoned about.

    Driven as a subprocess, never by calling `main()`: a test that does not
    cross the boundary does not prove the boundary works, and the subprocess
    exercises the entry point `uvx` will use.
    """
    env = dict(os.environ)
    # This asserts on what lands on disk, not on what the console can render;
    # pinning the child's stdout encoding keeps a cp1252 console from turning a
    # link regression into an encoding traceback (that failure has a test of
    # its own).
    env["PYTHONIOENCODING"] = "utf-8"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pb_ai_code",
            "install",
            "--target",
            str(tmp_path),
            "--harness",
            harness,
            *extra_args,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert result.returncode == 0, f"installer failed:\n{result.stdout}\n{result.stderr}"

    base = tmp_path / installed_subdir
    assert base.is_dir(), f"installer wrote no {installed_subdir}/"
    files = [p for p in base.rglob("*.md") if p.is_file()]
    assert files, f"no Markdown installed into {installed_subdir}/"

    dead = dead_links(files, base)
    assert not dead, f"dead relative links in the {harness} install:\n  " + "\n  ".join(dead)

    # The rewrite is literal, case-sensitive and reaches inside fenced blocks,
    # so this is the raw text: one surviving occurrence is one link that will
    # resolve to a `docs/` directory the consumer's project does not have.
    stale = [
        str(p.relative_to(base))
        for p in files
        if PRE_REWRITE_DOCS_PREFIX in p.read_text(encoding="utf-8", errors="replace")
    ]
    assert not stale, (
        f"{PRE_REWRITE_DOCS_PREFIX!r} survived the rewrite in the {harness} install:\n  "
        + "\n  ".join(stale)
    )


def test_frozen_powershell_installer_still_copies_the_same_knowledge_base() -> None:
    """`scripts/install-skills.ps1` is frozen, which is not the same as safe.

    It stays in the tree for one release (cli-port-spec §7) and consumers are
    still pointed at it, but nothing drives it any more — so the one way it can
    rot is invisible. The links the tests above check are made by the
    *payload*: a documentation tree added under `docs/` reaches the CLI through
    `plan.DOC_TREES` and the script through a literal of its own (ps1:118-126),
    and updating the first without the second gives every bundle the script
    installs a fresh set of dead links. That is the 2026-08 incident exactly.

    Grepping a frozen file is a poor test in general and the right one here: it
    costs nothing, it cannot silently no-op, and it goes red the day the script
    is deleted — which is the day to delete this test with it.
    """
    script = REPO_ROOT / "scripts" / "install-skills.ps1"
    assert script.is_file(), (
        "scripts/install-skills.ps1 is gone: delete this test with it — the CLI "
        "is covered by test_installed_layout_has_no_dead_links"
    )
    text = script.read_text(encoding="utf-8")

    missing = [
        name
        for name in (*plan_mod.DOC_TREES, *plan_mod.DOC_FILES)
        if f"'{name}'" not in text and f'"{name}"' not in text
    ]
    assert not missing, (
        "the knowledge base the CLI installs is not the one the PowerShell "
        f"script installs; it never names {missing}"
    )
    assert harness_mod.DOCS_FOLDER_NAME in text, (
        "the script would install the docs under a different folder name than "
        f"{harness_mod.DOCS_FOLDER_NAME!r}, which the rewritten links point at"
    )
    assert PRE_REWRITE_DOCS_PREFIX in text, "the script no longer rewrites the knowledge-base links"
