"""The PowerBuilder release is stated, and `AGENTS.md` is not ours to rewrite.

Two behaviours, and both exist because of the same fact: **an object keeps the
release it was last saved under**, not the release of the IDE working on it.
PowerBuilder migrates what it touches and leaves the rest, so a project built
with 2022 can hold DataWindows still marked release 6 — a real shape, seen in
real projects. Reading `appruntimeversion` off one exported object therefore
gives an answer that is plausible, specific, and sometimes four majors wrong,
and `pb_session_open` has no auto-pick to fall back on. So it is asked.

Which means it has to be written somewhere that survives, and somewhere a
person will maintain when they migrate — because nothing here will notice a
migration done in the IDE or with PowerGen. That is `AGENTS.md`, the project's
own file, which the installer therefore creates when absent and **never**
touches when present: an installer that appended to a hand-maintained
instruction file would corrupt instructions a little on every update, and an
agent would read the corruption as instruction.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

import pb_ai_code
from pb_ai_code import agentsmd, pbversion
from pb_ai_code import plan as plan_mod

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_DIR = Path(pb_ai_code.__file__).resolve().parent
MARKER_NAME = "_installed-from-pb-ai-code.txt"

# Duplicated from the sibling modules on purpose; test_install_marker.py
# carries the reason.
PAYLOAD_TREES = ("skills", "commands", "harness", "docs/pb-antipatterns", "docs/pb-source-format")
# Derived, not listed: a new entry in ``DOC_FILES`` is a new file the
# installer looks for, and a hand-kept copy here would fail every test in
# this module the day one is added - which is how it went the first time.
PAYLOAD_FILES = tuple(f"docs/{name}" for name in plan_mod.DOC_FILES)


def kit_env(home: Path) -> dict[str, str]:
    home.mkdir(parents=True, exist_ok=True)
    return {
        "PB_APPEON_INDEX_DB": str(home / "no-such-index.db"),
        "USERPROFILE": str(home),
        "HOME": str(home),
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def run_install(target: Path, *args: str) -> subprocess.CompletedProcess[str]:
    environ = dict(os.environ)
    environ.update(kit_env(target.parent / "home"))
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
            *args,
        ],
        capture_output=True,
        text=True,
        env=environ,
    )


# --- parsing -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "slug", "orca"),
    [
        ("pb2022r3", "pb2022r3", "22.0"),
        (" PB2022R3 ", "pb2022r3", "22.0"),
        ("pb2019r3", "pb2019r3", "19.0"),
        ("pb2025r2", "pb2025r2", "25.0"),
    ],
)
def test_an_exact_release_slug_derives_the_orca_token(raw: str, slug: str, orca: str) -> None:
    release = pbversion.parse(raw)
    assert release.value == slug
    assert release.orca_version == orca


@pytest.mark.parametrize("raw", ["PB 22", "2022", "22.0", "", "twenty-two", "v22"])
def test_an_orca_token_cannot_replace_an_exact_release_slug(raw: str) -> None:
    with pytest.raises(pbversion.InvalidPbVersion):
        pbversion.parse(raw)


# --- the flag ----------------------------------------------------------------


def test_the_version_reaches_both_agents_md_and_the_marker(tmp_path: Path) -> None:
    """Stated once, recorded where a person maintains it and where status reads it."""
    target = tmp_path / "target"
    target.mkdir()

    result = run_install(target, "--pb-version", "pb2022r3")
    assert result.returncode == 0, result.stderr

    written = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert "PowerBuilder release: `pb2022r3`" in written
    assert "install-time snapshot" in written
    assert "migrated to another" in written

    marker = (target / ".claude" / MARKER_NAME).read_text(encoding="utf-8")
    assert "# PB:        pb2022r3" in marker


def test_created_agents_md_is_utf8_without_bom_and_crlf(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()

    assert run_install(target, "--pb-version", "pb2022r3").returncode == 0

    raw = (target / "AGENTS.md").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert raw.count(b"\n") == raw.count(b"\r\n")
    assert raw.endswith(b"\r\n") and not raw.endswith(b"\r\n\r\n")


def test_a_bad_version_exits_2_and_writes_nothing(tmp_path: Path) -> None:
    """Ledger 14: everything that can fail fails before the first copy.

    Validated at the top of the run rather than where it is used, because
    where it is used the bundle has already landed - and a traceback there
    would leave the half-installed target the rule exists to prevent.
    """
    target = tmp_path / "target"
    target.mkdir()

    result = run_install(target, "--pb-version", "PB 22")

    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    assert len(result.stderr.strip().splitlines()) == 1
    assert list(target.iterdir()) == []


def test_without_a_version_the_file_says_so_rather_than_guessing(tmp_path: Path) -> None:
    """No terminal, no flag, no value - and no invention.

    An installer that picked a plausible version would be worse than one
    that admits it does not know: `pb_session_open` would open the library
    under a runtime nobody chose, and nothing downstream would question it.
    """
    target = tmp_path / "target"
    target.mkdir()

    result = run_install(target)
    assert result.returncode == 0

    written = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert "PowerBuilder release: **not stated**" in written
    assert "**PowerBuilder release: **" not in written
    assert "Ask before opening an ORCA session" in written
    assert "PowerBuilder release not stated" in result.stdout

    marker = (target / ".claude" / MARKER_NAME).read_text(encoding="utf-8")
    assert "not stated - see AGENTS.md" in marker


def test_a_reinstall_keeps_the_version_without_being_asked_again(tmp_path: Path) -> None:
    """The answer is read back out of AGENTS.md, so an update is not an interrogation.

    This is also what stops a non-interactive re-install - the shape an
    agent runs - from silently downgrading a stated version to "not stated".
    """
    target = tmp_path / "target"
    target.mkdir()
    assert run_install(target, "--pb-version", "pb2019r3").returncode == 0

    assert agentsmd.read_version(target) == "pb2019r3"

    result = run_install(target)
    assert result.returncode == 0
    assert "# PB:        pb2019r3" in (target / ".claude" / MARKER_NAME).read_text(encoding="utf-8")


# --- the file is theirs ------------------------------------------------------


def test_an_existing_agents_md_is_never_touched(tmp_path: Path) -> None:
    """The whole safety property, in one test.

    An `AGENTS.md` is read by every agent that opens the project and is
    maintained by hand. Rewriting it, appending to it, or backing it up and
    replacing it would all destroy work - so the block is printed instead,
    for a person to place.
    """
    target = tmp_path / "target"
    target.mkdir()
    original = "# my project\n\nDo not touch this.\n"
    (target / "AGENTS.md").write_text(original, encoding="utf-8")

    result = run_install(target, "--pb-version", "pb2022r3")
    assert result.returncode == 0

    assert (target / "AGENTS.md").read_text(encoding="utf-8") == original
    assert "already exists, so it was left alone" in result.stdout
    # And the section it should carry is printed for the user to place.
    assert agentsmd.SECTION_HEADING in result.stdout
    assert "PowerBuilder release: `pb2022r3`" in result.stdout


def test_an_existing_agents_md_reports_a_conflicting_version(tmp_path: Path) -> None:
    """The command-line version wins, but a stale project file cannot stay silent."""
    target = tmp_path / "target"
    target.mkdir()
    original = "# app\n\n- PowerBuilder release: `pb2019r3`\n"
    (target / "AGENTS.md").write_text(original, encoding="utf-8")

    result = run_install(target, "--pb-version", "pb2022r3")

    assert result.returncode == 0
    assert (target / "AGENTS.md").read_text(encoding="utf-8") == original
    assert "records PowerBuilder release pb2019r3, but this install uses pb2022r3" in result.stdout
    assert "Without --pb-version" in result.stdout
    assert "will reuse pb2019r3" in result.stdout
    marker = (target / ".claude" / MARKER_NAME).read_text(encoding="utf-8")
    assert "# PB:        pb2022r3" in marker


def test_the_written_file_records_the_workspace_not_loose_target_files(tmp_path: Path) -> None:
    """The workspace is useful; a shallow glob of target files is not.

    The workspace declares the real target list. Looking for nearby `.pbt`
    files can include orphaned targets and miss valid ones in deeper
    directories, so the generated file records only the workspace.
    """
    target = tmp_path / "target"
    (target / "src").mkdir(parents=True)
    (target / "src" / "app.pbw").write_text("", encoding="utf-8")
    (target / "src" / "orphaned.pbt").write_text("", encoding="utf-8")

    assert run_install(target, "--pb-version", "pb2022r3").returncode == 0

    written = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert "`src/app.pbw`" in written
    assert "Targets:" not in written
    assert "orphaned.pbt" not in written
    assert "Text projection: **not found**" in written
    assert "Version control: **Git or SVN working copy not found**" in written


def test_an_svn_workspace_is_not_reported_as_unversioned(tmp_path: Path) -> None:
    target = tmp_path / "target"
    (target / ".svn").mkdir(parents=True)

    assert run_install(target, "--pb-version", "pb2022r3").returncode == 0

    written = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert "Version control: Subversion working copy" in written
    assert "Git source protection" not in written


def test_the_written_file_keeps_the_operating_rules_short(tmp_path: Path) -> None:
    """Stable operating rules belong here; detailed recovery guidance does not."""
    target = tmp_path / "target"
    target.mkdir()

    assert run_install(target, "--pb-version", "pb2022r3").returncode == 0

    written = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert "## Approval before changes" in written
    assert "Start every request about this project with read-only inspection" in written
    assert "Do not edit files, import PowerBuilder objects" in written
    assert "The original request is not approval" in written
    assert "Treat questions about code as analysis only" in written
    assert "## PowerBuilder workflow" in written
    assert "installed `pb-*` skills" in written
    assert "configured `pb_*` ORCA tools" in written
    assert "Never edit or delete files under `ws_objects/`" in written
    assert "Never edit or replace a `.pbl` file directly" in written
    assert "pb-apply-plan" not in written
    assert len(written.splitlines()) <= 45


def test_a_workspace_with_projection_and_git_records_both_facts(tmp_path: Path) -> None:
    """The project section is a short snapshot of the install-time facts."""
    target = tmp_path / "target"
    projection = target / "ws_objects" / "app.pbl.src"
    projection.mkdir(parents=True)
    (projection / "sample.srw").write_bytes(b"$PBExportHeader$sample.srw\r\n")
    subprocess.run(["git", "init", "-q", str(target)], check=True, capture_output=True)

    assert run_install(target, "--pb-version", "pb2022r3").returncode == 0

    written = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert "Text projection: `ws_objects/` found" in written
    assert "Version control: Git" in written
    assert "Git source protection: **missing for `.sr*` files**" in written
    assert "never edits `.gitattributes`" in written


def test_agents_md_distinguishes_byte_protection_from_diffability(tmp_path: Path) -> None:
    target = tmp_path / "target"
    projection = target / "ws_objects" / "app.pbl.src"
    projection.mkdir(parents=True)
    (projection / "sample.srw").write_bytes(b"$PBExportHeader$sample.srw\r\n")
    (target / ".gitattributes").write_text("*.sr* binary\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(target)], check=True, capture_output=True)

    assert run_install(target, "--pb-version", "pb2022r3").returncode == 0

    written = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert "Source diffs: **some `.sr*` files are binary to Git**" in written
    assert "Git source protection: **missing" not in written


def test_the_kits_own_agents_md_is_never_the_one_installed(tmp_path: Path) -> None:
    """This repository has an AGENTS.md; it is about working on the kit.

    Copying it into a customer's PowerBuilder project would hand an agent
    instructions for editing pb-ai-code instead of instructions for the
    project it is standing in.
    """
    target = tmp_path / "target"
    target.mkdir()
    assert run_install(target, "--pb-version", "pb2022r3").returncode == 0

    written = (target / "AGENTS.md").read_text(encoding="utf-8")
    ours = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert written != ours
    assert "Architectural constraints" not in written


def test_a_target_that_cannot_take_the_file_still_installs(tmp_path: Path) -> None:
    """The bundle landed; one more file did not. That is a note, not a failure."""
    target = tmp_path / "target"
    target.mkdir()
    # A directory where the file should go: creating it raises OSError, and
    # the run has to survive that.
    (target / "AGENTS.md").mkdir()

    result = run_install(target, "--pb-version", "pb2022r3")

    assert result.returncode == 0
    assert (target / ".claude" / MARKER_NAME).is_file()


def test_survey_reads_the_disk_and_nothing_else(tmp_path: Path) -> None:
    """The unit under the subprocess tests, for the shapes they cannot reach."""
    root = tmp_path / "proj"
    (root / "ws_objects").mkdir(parents=True)
    (root / "app.pbw").write_text("", encoding="utf-8")

    facts = agentsmd.survey(root, pb_version=None, is_git=True)

    assert facts.workspaces == ("app.pbw",)
    assert facts.has_projection is True
    assert facts.is_git is True
    assert facts.is_svn is False
    assert facts.pb_version is None


def test_read_version_is_forgiving_about_a_file_people_edit(tmp_path: Path) -> None:
    """It is a hand-maintained document, so the parser meets it where it is.

    A person who migrates writes the new number in their own words. What
    must keep working is finding it - that is what stops a re-install from
    quietly resetting the answer to "not stated".
    """
    root = tmp_path / "proj"
    root.mkdir()
    (root / "AGENTS.md").write_text(
        "# app\n\nnotes\n\n- PowerBuilder release: pb2025r2 (migrated in June)\n",
        encoding="utf-8",
    )
    assert agentsmd.read_version(root) == "pb2025r2"

    (root / "AGENTS.md").write_text("# app\n\nnothing about PB here\n", encoding="utf-8")
    assert agentsmd.read_version(root) is None
    assert agentsmd.read_version(tmp_path / "nowhere") is None
