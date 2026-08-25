"""Provenance for an install that came from git — the shape every user gets.

A consumer who follows the README runs ``uvx --from git+https://... pb-ai-code
install``. There is no checkout on that machine, so the identity chain falls
past its first branch and answers from PEP 610: the ``direct_url.json`` the
installer records next to the distribution, holding the URL, the revision that
was *asked for* and the commit that was *got*.

That branch decides two things a consumer reads months later — the marker's
``# Source:`` line and the ``To update:`` recipe — and until this file existed
nothing exercised it. Every other test runs from the checkout and takes the
first branch instead, so the shape shipped to users was the one shape never
tried.

Two tests, and the second is the one that could have been wrong:

* :func:`test_source_and_recipe_come_from_direct_url` stages a
  ``direct_url.json`` and pins the exact strings;
* :func:`test_uv_records_direct_url_for_a_vcs_install` installs this
  repository *as a VCS dependency* and checks that a real installer writes
  that file at all. The spec flagged this unverified and the fallback path
  depended on the answer: if uv wrote nothing, every uvx consumer would
  silently get the version-only ``# Source:`` and a recipe that could not name
  a tag.

  It has since been measured, and both shapes are as the code assumes. From a
  bare URL uv records ``url`` and ``commit_id`` and **no**
  ``requested_revision`` — so the recipe synthesises ``v<version>``, which is
  the branch the parametrised test above covers. From ``@v0.4.0`` it records
  ``requested_revision`` verbatim and the recipe pins it. The test keeps
  running because "uv still does this" is the premise, not a one-off finding.

  It needs the network, which is why ``git+file://`` was tried first — uv
  panics on that URL (``AmbiguousAuthority``), so the real URL it is.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import pb_ai_code
from pb_ai_code import plan as plan_mod

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_DIR = Path(pb_ai_code.__file__).resolve().parent

# Duplicated from the sibling test modules on purpose; the reason is written
# out in test_install_marker.py — three test packages in this repository are
# called `tests`, so a relative import binds to whichever pytest saw first.
PAYLOAD_TREES = ("skills", "commands", "harness", "docs/pb-antipatterns", "docs/pb-source-format")
# Derived, not listed: a new entry in ``DOC_FILES`` is a new file the
# installer looks for, and a hand-kept copy here would fail every test in
# this module the day one is added - which is how it went the first time.
PAYLOAD_FILES = tuple(f"docs/{name}" for name in plan_mod.DOC_FILES)
MARKER_NAME = "_installed-from-pb-ai-code.txt"

VCS_URL = "https://github.com/restoresrl/pb-ai-code"
COMMIT = "c26d4b6e3f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c"
STAGED_VERSION = "0.5.0"


def stage_kit(root: Path) -> Path:
    for rel in PAYLOAD_TREES:
        shutil.copytree(REPO_ROOT / rel, root.joinpath(*rel.split("/")))
    for rel in PAYLOAD_FILES:
        dst = root.joinpath(*rel.split("/"))
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / rel, dst)
    shutil.copytree(
        PACKAGE_DIR,
        root / "tools" / "pb-ai-code" / "src" / "pb_ai_code",
        ignore=shutil.ignore_patterns("__pycache__", "_kit"),
    )
    return root


def stage_dist_info(src_dir: Path, *, revision: str | None) -> None:
    """A distribution that says it came from git, next to the package.

    ``importlib.metadata`` discovers ``*.dist-info`` on ``sys.path``, and
    PYTHONPATH is searched before site-packages, so this shadows the editable
    install this test suite runs against.
    """
    dist_info = src_dir / f"pb_ai_code-{STAGED_VERSION}.dist-info"
    dist_info.mkdir(parents=True)
    (dist_info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: pb-ai-code\nVersion: {STAGED_VERSION}\n",
        encoding="utf-8",
    )
    vcs_info: dict[str, str] = {"vcs": "git", "commit_id": COMMIT}
    if revision is not None:
        vcs_info["requested_revision"] = revision
    (dist_info / "direct_url.json").write_text(
        json.dumps({"url": VCS_URL, "vcs_info": vcs_info}), encoding="utf-8"
    )


def install_from_staged(root: Path, target: Path, home: Path) -> subprocess.CompletedProcess[str]:
    home.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update(
        {
            "PYTHONPATH": str(root / "tools" / "pb-ai-code" / "src"),
            "PB_APPEON_INDEX_DB": str(home / "no-such-index.db"),
            "USERPROFILE": str(home),
            "HOME": str(home),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "utf-8",
        }
    )
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pb_ai_code",
            "install",
            "--target",
            str(target),
            "--harness",
            "claude-code",
        ],
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.mark.parametrize(
    ("revision", "expected_ref"),
    [
        # The ordinary case: pinned to a tag, so the recipe pins the same tag.
        ("v0.5.0", "v0.5.0"),
        # No requested revision recorded — installed from a bare URL. The
        # recipe then synthesises `v<version>` from the release version, which
        # is the only honest ref available.
        (None, "v0.5.0"),
    ],
)
def test_source_and_recipe_come_from_direct_url(
    tmp_path: Path, revision: str | None, expected_ref: str
) -> None:
    """Ledger 57 and 60, on the branch a uvx consumer actually takes."""
    root = stage_kit(tmp_path / "kit")
    stage_dist_info(root / "tools" / "pb-ai-code" / "src", revision=revision)

    target = tmp_path / "project"
    target.mkdir()
    result = install_from_staged(root, target, tmp_path / "home")
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    marker = (target / ".claude" / MARKER_NAME).read_text(encoding="utf-8")

    # The staged kit is not a git repository, so the checkout branch must have
    # declined. If it had not, this test would be re-proving branch 1.
    assert "local checkout" not in marker
    assert f"# Source:    pb-ai-code @ {STAGED_VERSION} (git+{VCS_URL}, {COMMIT[:7]})" in marker
    assert f"uvx --from git+{VCS_URL}@{expected_ref} pb-ai-code install" in marker

    # A build from a pinned revision has no working tree, so it cannot be
    # dirty and must never carry the warning the checkout branch can raise.
    assert "WARN: source repo had uncommitted changes" not in marker


def test_a_distribution_with_no_direct_url_still_writes_a_wellformed_source(
    tmp_path: Path,
) -> None:
    """Third branch: no checkout, no PEP 610. The version stands alone.

    Nothing is wrong with this answer — it is what an install from a plain
    wheel produces — so it must be a clean line rather than a gap. The recipe
    has no ref to name and says so instead of guessing one.
    """
    root = stage_kit(tmp_path / "kit")
    target = tmp_path / "project"
    target.mkdir()

    result = install_from_staged(root, target, tmp_path / "home")
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    marker = (target / ".claude" / MARKER_NAME).read_text(encoding="utf-8")
    source = next(line for line in marker.splitlines() if line.startswith("# Source:"))
    assert "local checkout" not in source
    assert "n/d" not in source and "unknown" not in source.lower()
    assert source.startswith("# Source:    pb-ai-code @ ")


@pytest.mark.slow
def test_uv_records_direct_url_for_a_vcs_install(tmp_path: Path) -> None:
    """The premise the whole uvx story rests on, checked against GitHub.

    Measured on 2026-08-12: a bare URL yields ``url`` + ``commit_id`` with no
    ``requested_revision``; ``@v0.4.0`` yields the revision verbatim. Both are
    what :mod:`pb_ai_code.provenance` assumes, and this test is what notices if
    uv stops doing it.

    Needs the network. A network failure skips; uv writing nothing fails, and
    the two are told apart deliberately — a skip that hides a real regression
    is worse than no test.
    """
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is not on PATH")

    venv = tmp_path / "env"
    subprocess.run([uv, "venv", str(venv)], capture_output=True, text=True, check=True)
    bin_dir = venv / ("Scripts" if os.name == "nt" else "bin")
    python = bin_dir / ("python.exe" if os.name == "nt" else "python")

    url = f"git+{VCS_URL}@v0.4.0"
    proc = subprocess.run(
        [uv, "pip", "install", "--python", str(python), url],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.lower()
        offline = any(
            token in stderr
            for token in ("network", "resolve host", "connection", "timed out", "dns", "proxy")
        )
        if offline:
            pytest.skip(f"no network to github.com:\n{proc.stderr}")
        pytest.fail(f"installing {url} failed for a reason that is not the network:\n{proc.stderr}")

    found = list(venv.rglob("pb_ai_code-*.dist-info/direct_url.json"))
    assert found, (
        "uv recorded no direct_url.json for a VCS install. The PEP 610 branch "
        "of provenance.resolve is then dead code for real consumers, and the "
        "marker's To update: recipe cannot name the ref it came from."
    )

    recorded = json.loads(found[0].read_text(encoding="utf-8"))
    assert recorded.get("url") == VCS_URL, recorded
    vcs_info = recorded.get("vcs_info")
    assert isinstance(vcs_info, dict), recorded
    assert vcs_info.get("vcs") == "git", recorded
    assert vcs_info.get("commit_id"), recorded
    assert vcs_info.get("requested_revision") == "v0.4.0", (
        "uv no longer records the requested revision, so the To update: recipe "
        f"would stop pinning the tag it came from: {recorded}"
    )
