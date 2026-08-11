"""Every relative Markdown link resolves — in the repository *and* once installed.

This repository ships two documentation trees that the skills link into, and
`scripts/install-skills.ps1` copies them somewhere else and rewrites the links
to match. So a link can be correct here and dead in the only place a consumer
ever reads it, which is not a hypothetical: an audit in 2026-08 found **28**
dead links in an installed bundle while the repository itself was clean, and
adding one guide in 2026-08 produced five more the same way.

Checking the canonical tree alone therefore proves very little. The second test
below runs the installer into a temporary directory, for both harness layouts,
and checks what actually lands.

Links inside fenced code blocks are ignored: those illustrate generated output
— a plan file's `([plan](.pb-review/…))` bullets, for instance — and are not
links the document is making.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
SKIP_SCHEMES = ("http://", "https://", "#", "mailto:")


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
        ["git", "-C", str(REPO_ROOT), "ls-files", "--cached", "--others", "--exclude-standard", "*.md"],
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
        ("generic", ["-SkillsDir", ".agent/skills"], ".agent"),
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
    """
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    if pwsh is None:
        pytest.skip("no PowerShell available to run the installer")

    result = subprocess.run(
        [
            pwsh,
            "-NoProfile",
            "-File",
            str(REPO_ROOT / "scripts" / "install-skills.ps1"),
            "-Target",
            str(tmp_path),
            "-Harness",
            harness,
            *extra_args,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"installer failed:\n{result.stdout}\n{result.stderr}"

    base = tmp_path / installed_subdir
    assert base.is_dir(), f"installer wrote no {installed_subdir}/"
    files = [p for p in base.rglob("*.md") if p.is_file()]
    assert files, f"no Markdown installed into {installed_subdir}/"

    dead = dead_links(files, base)
    assert not dead, (
        f"dead relative links in the {harness} install:\n  " + "\n  ".join(dead)
    )
