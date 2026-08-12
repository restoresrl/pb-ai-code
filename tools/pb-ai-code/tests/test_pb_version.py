"""The PowerBuilder version is stated, and `AGENTS.md` is not ours to rewrite.

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

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_DIR = Path(pb_ai_code.__file__).resolve().parent
MARKER_NAME = "_installed-from-pb-ai-code.txt"

# Duplicated from the sibling modules on purpose; test_install_marker.py
# carries the reason.
PAYLOAD_TREES = ("skills", "commands", "harness", "docs/pb-antipatterns", "docs/pb-source-format")
PAYLOAD_FILES = ("docs/wiki-notes.md",)


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
        [sys.executable, "-m", "pb_ai_code", "install", "--target", str(target), *args],
        capture_output=True,
        text=True,
        env=environ,
    )


# --- parsing -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("22", "22.0"), ("22.0", "22.0"), ("19.2", "19.2"), ("25.0", "25.0"), ("  22 ", "22.0")],
)
def test_a_bare_major_is_what_a_person_says_and_normalises(raw: str, expected: str) -> None:
    """`22` is the answer someone gives; `22.0` is what every tool consumes."""
    assert pbversion.parse(raw).value == expected


@pytest.mark.parametrize("raw", ["PB 22", "2022", "22.0.1", "", "twenty-two", "v22"])
def test_anything_that_is_not_a_version_is_refused(raw: str) -> None:
    """Strict about shape, because the shape is the interface to ORCA."""
    with pytest.raises(pbversion.InvalidPbVersion):
        pbversion.parse(raw)


def test_an_unknown_major_is_accepted_rather_than_refused() -> None:
    """The list of releases grows without this file being edited.

    A release that ships after this code was written must not stop an
    install; it is flagged as unrecognised and used.
    """
    parsed = pbversion.parse("33.0")
    assert parsed.value == "33.0"
    assert parsed.recognised is False
    assert pbversion.parse("22.0").recognised is True


# --- the flag ----------------------------------------------------------------


def test_the_version_reaches_both_agents_md_and_the_marker(tmp_path: Path) -> None:
    """Stated once, recorded where a person maintains it and where status reads it."""
    target = tmp_path / "target"
    target.mkdir()

    result = run_install(target, "--pb-version", "22")
    assert result.returncode == 0, result.stderr

    written = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert "**PowerBuilder version: 22.0**" in written
    # The reason it has to be maintained by hand, stated in the file itself.
    assert "release 6 DataWindows" in written
    assert "ever migrated" in written

    marker = (target / ".claude" / MARKER_NAME).read_text(encoding="utf-8")
    assert "# PB:        22.0" in marker


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
    assert "not stated" in written
    assert "no agent should assume one" in written
    assert "PowerBuilder version not stated" in result.stdout

    marker = (target / ".claude" / MARKER_NAME).read_text(encoding="utf-8")
    assert "not stated - see AGENTS.md" in marker


def test_a_reinstall_keeps_the_version_without_being_asked_again(tmp_path: Path) -> None:
    """The answer is read back out of AGENTS.md, so an update is not an interrogation.

    This is also what stops a non-interactive re-install - the shape an
    agent runs - from silently downgrading a stated version to "not stated".
    """
    target = tmp_path / "target"
    target.mkdir()
    assert run_install(target, "--pb-version", "19.2").returncode == 0

    assert agentsmd.read_version(target) == "19.2"

    result = run_install(target)
    assert result.returncode == 0
    assert "# PB:        19.2" in (target / ".claude" / MARKER_NAME).read_text(encoding="utf-8")


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

    result = run_install(target, "--pb-version", "22.0")
    assert result.returncode == 0

    assert (target / "AGENTS.md").read_text(encoding="utf-8") == original
    assert "already exists, so it was left alone" in result.stdout
    # And the section it should carry is printed for the user to place.
    assert agentsmd.SECTION_HEADING in result.stdout
    assert "PowerBuilder version: 22.0" in result.stdout


def test_the_written_file_states_what_was_read_off_the_disk(tmp_path: Path) -> None:
    """Facts, not deductions: the workspace files, the projection, git.

    Everything in the block is either something a person said or something
    that can be checked by looking. A generated instruction file that
    guessed would be believed.
    """
    target = tmp_path / "target"
    (target / "src").mkdir(parents=True)
    (target / "src" / "app.pbw").write_text("", encoding="utf-8")
    (target / "src" / "app.pbt").write_text("", encoding="utf-8")

    assert run_install(target, "--pb-version", "22.0").returncode == 0

    written = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert "`src/app.pbw`" in written
    assert "`src/app.pbt`" in written
    # No ws_objects and no git in this target, and both are hazards worth
    # naming rather than omissions worth hiding.
    assert "No text projection" in written
    assert "Not under version control" in written


def test_the_hazard_is_stated_with_the_half_the_kit_already_covers(tmp_path: Path) -> None:
    """Naming the risk without naming the mitigation produces a wrong conclusion.

    It produced one twice. An agent read "a change cannot be undone" next to
    a `pbl_only` workspace and told the user an import here is
    unrecoverable, recommending a manual copy of the `.pbl` - while
    `pb-apply-plan`, installed in the same directory, snapshots the library
    before every fix and restores it byte for byte when the import fails.

    So the file says both halves: a failed import is already covered, and a
    successful change that later proves wrong is the risk that a copy or a
    `git init` actually buys protection against.
    """
    target = tmp_path / "target"
    target.mkdir()
    assert run_install(target, "--pb-version", "22.0").returncode == 0

    written = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert "pb-apply-plan" in written
    assert "No manual copy is needed" in written
    # The two halves, each identified as such.
    assert "**failed** import" in written
    assert "**successful** change" in written
    # And the case neither protects.
    assert "by a tool other than the apply loop" in written


def test_a_workspace_with_both_projection_and_git_is_not_lectured(tmp_path: Path) -> None:
    """The passage is about a hazard; where there is none it does not appear.

    A project with a text projection under version control has a diff to
    read and a history to return to, so the paragraph would be noise - and
    noise in an instruction file is read as instruction.
    """
    target = tmp_path / "target"
    (target / "ws_objects").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(target)], check=True, capture_output=True)

    assert run_install(target, "--pb-version", "22.0").returncode == 0

    written = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert "text projection" in written
    assert "**failed** import" not in written


def test_the_kits_own_agents_md_is_never_the_one_installed(tmp_path: Path) -> None:
    """This repository has an AGENTS.md; it is about working on the kit.

    Copying it into a customer's PowerBuilder project would hand an agent
    instructions for editing pb-ai-code instead of instructions for the
    project it is standing in.
    """
    target = tmp_path / "target"
    target.mkdir()
    assert run_install(target, "--pb-version", "22.0").returncode == 0

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

    result = run_install(target, "--pb-version", "22.0")

    assert result.returncode == 0
    assert (target / ".claude" / MARKER_NAME).is_file()


def test_survey_reads_the_disk_and_nothing_else(tmp_path: Path) -> None:
    """The unit under the subprocess tests, for the shapes they cannot reach."""
    root = tmp_path / "proj"
    (root / "ws_objects").mkdir(parents=True)
    (root / "app.pbw").write_text("", encoding="utf-8")

    facts = agentsmd.survey(root, pb_version=None, is_git=True)

    assert facts.workspaces == ("app.pbw",)
    assert facts.targets == ()
    assert facts.has_projection is True
    assert facts.is_git is True
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
        "# app\n\nnotes\n\n- PowerBuilder version: 25.0 (migrated in June)\n",
        encoding="utf-8",
    )
    assert agentsmd.read_version(root) == "25.0"

    (root / "AGENTS.md").write_text("# app\n\nnothing about PB here\n", encoding="utf-8")
    assert agentsmd.read_version(root) is None
    assert agentsmd.read_version(tmp_path / "nowhere") is None
