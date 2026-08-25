"""The repository models the Git rules recommended to PowerBuilder projects."""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def attributes(path: str, *names: str) -> dict[str, str]:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "check-attr", "-z", *names, "--", path],
        capture_output=True,
        text=True,
        check=True,
    )
    parts = result.stdout.split("\0")
    if parts and parts[-1] == "":
        parts.pop()
    return {parts[index + 1]: parts[index + 2] for index in range(0, len(parts), 3)}


def test_powerbuilder_source_bytes_are_preserved_without_disabling_diff() -> None:
    result = attributes("ws_objects/app.pbl.src/sample.srw", "text", "diff")
    assert result == {"text": "unset", "diff": "unspecified"}


def test_binary_libraries_disable_translation_and_diff() -> None:
    for path in ("app.pbl", "app.pbd"):
        result = attributes(path, "text", "diff", "merge")
        assert result == {"text": "unset", "diff": "unset", "merge": "unset"}


def test_ordinary_repository_text_is_canonical_lf() -> None:
    result = attributes("README.md", "text", "eol")
    assert result == {"text": "auto", "eol": "lf"}
