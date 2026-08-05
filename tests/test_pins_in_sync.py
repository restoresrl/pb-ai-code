"""Every pinned reference to a sibling repository agrees with the others.

The version pin is what makes "we are all on the same toolchain" a checkable
statement. It is also written down in several places — the canonical
`harness/mcp-servers.json` the installer materializes, plus the copies
`docs/install.md` quotes for readers and the commands the skills tell you to
run. Copies of the same fact drift, and a pin that disagrees with itself is
worse than none: it tells two developers two different stories, each of which
looks authoritative.

So: gather every `github.com/restoresrl/<repo>@<tag>` in the tracked tree and
assert that a given repository is pinned to exactly one tag. This is the whole
test. It does not check that the tag *exists* — that needs the network, and
`pb-orca-mcp doctor` answers it far better.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# github.com/restoresrl/<repo>@<ref>, in a URL that may be followed by a quote,
# whitespace, a backtick or a closing paren.
PIN_RE = re.compile(r"github\.com/restoresrl/(?P<repo>[A-Za-z0-9._-]+?)@(?P<ref>[^\s\"'`),]+)")

# Binary-ish and generated trees never carry a pin worth checking. Generated
# ones especially: .claude/ is a copy of skills/, so a stale install would
# report a drift that does not exist in the source.
SKIP_SUFFIXES = {".pbl", ".pbd", ".png", ".jpg", ".gif", ".ico", ".db", ".sqlite"}


def _tracked_files() -> list[Path]:
    """Everything git would consider part of the repository.

    `--others --exclude-standard` includes files that are new and not yet
    staged, so a doc added with the wrong pin fails now rather than after
    someone remembers to `git add` it. Ignored paths stay out, which is what
    keeps the generated `.claude/` — a copy of `skills/` — from reporting a
    drift that does not exist in the source.
    """
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [REPO_ROOT / line for line in out.splitlines() if line]


def _pins() -> dict[str, dict[str, list[str]]]:
    """{repo: {ref: [where it was seen, ...]}}"""
    found: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for path in _tracked_files():
        if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        for m in PIN_RE.finditer(text):
            found[m.group("repo")][m.group("ref")].append(rel)
    return found


def test_each_sibling_repo_is_pinned_to_one_ref() -> None:
    for repo, refs in sorted(_pins().items()):
        if len(refs) > 1:
            detail = "\n".join(
                f"    @{ref}: {', '.join(sorted(set(where)))}"
                for ref, where in sorted(refs.items())
            )
            pytest.fail(
                f"{repo} is pinned to {len(refs)} different refs:\n{detail}\n"
                "Pick one and update every place above."
            )


def test_mcp_config_is_the_canonical_pin_for_pb_orca_mcp() -> None:
    """The file the installer materializes is the one that decides.

    Anywhere else naming a `pb-orca-mcp` version is a copy for human readers;
    this is the copy a machine acts on, so a disagreement means the docs are
    wrong, not the config.
    """
    canonical = REPO_ROOT / "harness" / "mcp-servers.json"
    block = json.loads(canonical.read_text(encoding="utf-8"))
    args = block["mcpServers"]["pb-orca"]["args"]

    from_url = [PIN_RE.search(a) for a in args if isinstance(a, str)]
    matches = [m for m in from_url if m]
    assert len(matches) == 1, f"expected exactly one pinned URL in {canonical.name}, got {matches}"
    assert matches[0].group("repo") == "pb-orca-mcp"
    pinned = matches[0].group("ref")

    seen = _pins().get("pb-orca-mcp", {})
    # The canonical file must be among the files that were actually scanned.
    # Without this the test still passes if the file is renamed out of the
    # scan, having quietly stopped comparing anything to it.
    assert "harness/mcp-servers.json" in seen.get(pinned, []), (
        "harness/mcp-servers.json was not picked up by the scan — is it ignored, "
        "or has it moved? The comparison below would be vacuous."
    )
    assert set(seen) == {pinned}, (
        f"harness/mcp-servers.json pins pb-orca-mcp@{pinned}, "
        f"but the tree also mentions {sorted(set(seen) - {pinned})}"
    )


def test_x86_interpreter_is_requested_everywhere_pb_orca_mcp_runs() -> None:
    """`--python 3.12-x86` is not optional: `pborc.dll` is 32-bit, and ctypes
    in a 64-bit interpreter cannot load it. A command line that pins the
    version but forgets the architecture fails with a DLL-load error that
    looks like a missing file, so it is worth catching in the tree."""
    offenders = []
    for path in _tracked_files():
        if path.suffix.lower() not in {".md", ".json", ".ps1"} or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        for line_no, line in enumerate(text.splitlines(), 1):
            if "pb-orca-mcp@" not in line:
                continue
            # The invocation may wrap; look at a small window after the URL.
            window = "\n".join(text.splitlines()[line_no - 1 : line_no + 3])
            if "3.12-x86" not in window:
                offenders.append(f"{rel}:{line_no}")
    assert not offenders, (
        "pb-orca-mcp is invoked without --python 3.12-x86 near: " + ", ".join(offenders)
    )
