"""The kit travels inside the wheel, and these are the tests that prove it.

Every other test in this package runs from the checkout, which means
:func:`pb_ai_code.kit._resolve_kit_root` takes branch 2 — the development
loop. Branch 1, the ``pb_ai_code/_kit/`` payload force-included into a built
wheel, is the entire reason this CLI exists: it is what makes

    uvx --from git+https://github.com/restoresrl/pb-ai-code pb-ai-code install

work on a machine with no clone on it. A suite that never exercises it can be
green while the product is unusable, and it was: a wheel built from a clean
checkout before this port carried 18 files and not one that the installer
needs.

Two claims, and they are different claims:

* the wheel carries exactly the tracked files the six ``force-include``
  mappings name, and no database (:func:`test_wheel_payload_matches_git`);
* a wheel installed somewhere with no checkout in reach actually installs the
  kit (:func:`test_the_wheel_installs_with_no_checkout_in_reach`).

Set-equality is packaging; the second test is the product. The ``*.db``
assertion guards a verified trap rather than a hypothetical one:
``force-include`` ignores ``.gitignore`` **and** ignores ``exclude``, so
mapping the ``docs`` root — the obvious thing to write — drags
``docs/appeon-index/index.db`` into the wheel from any developer machine that
has built one. 190 KB becomes 4.8 MB, and that database is deliberately never
redistributed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

# The six mappings in `[tool.hatch.build.targets.wheel.force-include]`, as the
# repository-relative paths `git ls-files` understands. Kept here rather than
# parsed out of pyproject.toml on purpose: if someone edits the table, this
# list should have to be edited too, and the diff should say so.
PAYLOAD_PATHS = (
    "skills",
    "commands",
    "harness",
    "docs/pb-antipatterns",
    "docs/pb-source-format",
    # Spelled out rather than derived: this module is the one that checks the
    # built wheel against what the source tree declares, so importing the
    # declaration to build the expectation would test nothing.
    "docs/wiki-notes.md",
    "docs/plan-file-contract.md",
)

PAYLOAD_PREFIX = "pb_ai_code/_kit/"

pytestmark = pytest.mark.slow


def _uv() -> str:
    found = shutil.which("uv")
    if found is None:
        pytest.skip("uv is not on PATH; it is what builds the wheel")
    return found


def _tracked_payload_files() -> set[str]:
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "--", *PAYLOAD_PATHS],
        capture_output=True,
        text=True,
        check=True,
    )
    return {line.strip() for line in proc.stdout.splitlines() if line.strip()}


@pytest.fixture(scope="module")
def wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the wheel once for this module. Tens of seconds."""
    out = tmp_path_factory.mktemp("wheel")
    proc = subprocess.run(
        [_uv(), "build", "--wheel", "--out-dir", str(out)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"uv build failed:\n{proc.stdout}\n{proc.stderr}"
    built = sorted(out.glob("*.whl"))
    assert len(built) == 1, f"expected one wheel, got {[p.name for p in built]}"
    return built[0]


def test_wheel_payload_matches_git(wheel: Path) -> None:
    """The payload is exactly the tracked files the six mappings name.

    Set-equality, not a count. A count agreeing while the sets differ is the
    shape of a bug that survives review, and both directions matter: a file
    missing means an installer with nothing to install, a file extra means the
    wheel is carrying something the repository does not version.
    """
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()

    payload = {name[len(PAYLOAD_PREFIX) :] for name in names if name.startswith(PAYLOAD_PREFIX)}
    expected = _tracked_payload_files()

    assert payload, (
        "the wheel carries no kit payload at all: "
        "[tool.hatch.build.targets.wheel.force-include] is missing or wrong, "
        "and `uvx --from git+...` would install nothing"
    )
    assert payload == expected, (
        f"payload differs from git\n"
        f"  in the wheel but not tracked: {sorted(payload - expected)}\n"
        f"  tracked but not in the wheel: {sorted(expected - payload)}"
    )


def test_the_wheel_carries_no_database(wheel: Path) -> None:
    """No ``*.db`` anywhere — see the module docstring for why this is real."""
    with zipfile.ZipFile(wheel) as zf:
        databases = [n for n in zf.namelist() if n.lower().endswith((".db", ".sqlite"))]
    assert databases == [], (
        f"a database reached the wheel: {databases}. force-include ignores "
        f".gitignore and exclude, so a mapping of the docs root would do this."
    )


def test_the_wheel_carries_the_code(wheel: Path) -> None:
    """The payload is useless without the modules that read it."""
    with zipfile.ZipFile(wheel) as zf:
        modules = {n for n in zf.namelist() if n.startswith("pb_ai_code/") and n.endswith(".py")}
    assert "pb_ai_code/__main__.py" in modules
    assert "pb_ai_code/kit.py" in modules


def test_the_wheel_installs_with_no_checkout_in_reach(wheel: Path, tmp_path: Path) -> None:
    """The product, not the packaging: install the wheel and run it.

    The environment is built under ``tmp_path``, which is outside the
    repository, so :func:`pb_ai_code.kit._resolve_kit_root` cannot walk up
    into a checkout and find a sentinel. Branch 1 is the only branch left,
    which is the point.

    Run through the console script rather than ``-m pb_ai_code``, because the
    console script is what ``uvx`` invokes.
    """
    uv = _uv()
    venv = tmp_path / "env"
    subprocess.run([uv, "venv", str(venv)], capture_output=True, text=True, check=True)

    bin_dir = venv / ("Scripts" if os.name == "nt" else "bin")
    python = bin_dir / ("python.exe" if os.name == "nt" else "python")
    proc = subprocess.run(
        [uv, "pip", "install", "--python", str(python), str(wheel)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"installing the wheel failed:\n{proc.stdout}\n{proc.stderr}"

    console = bin_dir / ("pb-ai-code.exe" if os.name == "nt" else "pb-ai-code")
    assert console.is_file(), f"the console script was not installed: {sorted(bin_dir.iterdir())}"

    target = tmp_path / "project"
    target.mkdir()
    home = tmp_path / "home"
    home.mkdir()

    env = dict(os.environ)
    env.update(
        {
            # A machine with no Appeon index, whatever this developer has.
            "PB_APPEON_INDEX_DB": str(home / "no-such-index.db"),
            "USERPROFILE": str(home),
            "HOME": str(home),
            "PYTHONIOENCODING": "utf-8",
        }
    )
    # PYTHONPATH could otherwise smuggle the checkout in and let branch 2 win.
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [str(console), "install", "--target", str(target)],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(tmp_path),
    )
    assert result.returncode == 0, f"install failed:\n{result.stdout}\n{result.stderr}"

    bundle = target / ".agents"
    installed_skills = sorted(p.name for p in (bundle / "skills").iterdir())
    assert "pb-review" in installed_skills
    assert (bundle / "skills" / "pb-review" / "SKILL.md").is_file()
    assert (bundle / "commands" / "pb-review.md").is_file()
    assert (bundle / "pb-ai-code-docs" / "pb-antipatterns" / "index.md").is_file()
    assert (bundle / "pb-ai-code-docs" / "wiki-notes.md").is_file()
    assert (target / ".mcp.json").is_file()

    marker_text = (bundle / "_installed-from-pb-ai-code.txt").read_text(encoding="utf-8")
    assert "local checkout" not in marker_text, (
        "the run found a checkout after all, so this test proved nothing about the packaged payload"
    )
