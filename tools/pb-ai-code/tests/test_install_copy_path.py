"""What the installer copies, where it puts it, and what it must not touch.

Every rule checked here is one somebody paid for once.

* Commit e04a11d removed a "review-only" subset of the skills because
  seven cross-links died with it; the skills are copied as whole trees,
  all of them, or the ones that ship point at ones that do not.
* Commit 308ff22 forgot ``docs/wiki-notes.md`` and produced exactly five
  dead links in the installed bundle while the repository itself was
  clean.
* PowerShell's recursive copy *nests* into an existing directory
  (``dst/tree/tree/...``), so the trees are deleted before they are
  copied - which is also what makes a file deleted upstream disappear
  from an installed bundle. ``shutil.copytree(dirs_exist_ok=True)``
  dodges the first bug and silently reintroduces the second, so this file
  plants a ghost and a hand edit and insists both are gone.
* ``harness/claude-code/settings.json`` is copied over the target's file
  verbatim, no merge and no backup. That is deliberate, undocumented and
  destructive, and the only thing standing between it and a surprise is a
  test that says so out loud.

The CLI is driven as a subprocess throughout, never by calling ``main()``:
a test that does not cross the boundary does not prove the boundary works,
and the subprocess exercises the entry point ``uvx`` will use.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

import pb_ai_code
from pb_ai_code import marker
from pb_ai_code import plan as plan_mod

# --- support -----------------------------------------------------------------
# Duplicated in the sibling test modules on purpose: three test packages in
# this repository are called `tests`, so `from ._support import ...` binds to
# whichever one pytest imported first (verified - it raises ModuleNotFoundError
# in a full run), and a conftest.py here is shared ground. A short copy is the
# cheaper of the two evils.

REPO_ROOT = Path(__file__).resolve().parents[3]

#: The package under test, wherever it is installed from. Staged copies of
#: the kit carry *this* package, so the tests follow the code they run.
PACKAGE_DIR = Path(pb_ai_code.__file__).resolve().parent

#: Everything the wheel's force-include table maps into the payload.
PAYLOAD_TREES = ("skills", "commands", "harness", "docs/pb-antipatterns", "docs/pb-source-format")
# Derived, not listed: a new entry in ``DOC_FILES`` is a new file the
# installer looks for, and a hand-kept copy here would fail every test in
# this module the day one is added - which is how it went the first time.
PAYLOAD_FILES = tuple(f"docs/{name}" for name in plan_mod.DOC_FILES)

MARKER_NAME = "_installed-from-pb-ai-code.txt"


def stage_kit(root: Path) -> Path:
    """Build a throwaway checkout: the payload, plus the package under test.

    Tests that plant or remove payload inputs must never do it in the
    repository, and ``kit.kit_root()`` finds a checkout by searching
    upward from the module file - so the module has to live in the
    throwaway tree too. ``_kit`` is left out so the checkout branch is the
    one taken, exactly as in the development loop.
    """
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


def kit_env(home: Path, kit: Path | None = None) -> dict[str, str]:
    """Environment for one run: which kit, and a machine with no index.

    ``PB_APPEON_INDEX_DB`` points at nothing and the home directory is
    empty, so the Appeon probe answers the same way on a developer's
    machine as on CI. Pass ``kit`` to run against a staged checkout.
    """
    home.mkdir(parents=True, exist_ok=True)
    env = {
        "PB_APPEON_INDEX_DB": str(home / "no-such-index.db"),
        "USERPROFILE": str(home),
        "HOME": str(home),
        # A staged checkout is a git repository in the dirty-source tests,
        # and a __pycache__ written into it by the run itself would make
        # every run report uncommitted changes.
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if kit is not None:
        env["PYTHONPATH"] = str(kit / "tools" / "pb-ai-code" / "src")
    return env


def run_cli(
    *args: str, cwd: Path | None = None, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    environ = dict(os.environ)
    environ.update(env or {})
    return subprocess.run(
        [sys.executable, "-m", "pb_ai_code", *args],
        capture_output=True,
        text=True,
        cwd=None if cwd is None else str(cwd),
        env=environ,
    )


def install(
    target: Path, *args: str, kit: Path | None = None, home: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """One successful install into ``target``; fails the test if it is not."""
    result = run_cli(
        "install",
        "--target",
        str(target),
        *args,
        env=kit_env(home if home is not None else target.parent / "home", kit),
    )
    assert result.returncode == 0, f"install failed:\n{result.stdout}\n{result.stderr}"
    return result


def files_under(root: Path) -> set[str]:
    """Every file below ``root``, target-relative, ``/``-separated."""
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


# --- ledger 15, 16: the skills -----------------------------------------------


def test_ledger15_every_skill_is_copied_as_a_whole_tree(tmp_path: Path) -> None:
    """Ledger 15: whole directories, never a bare SKILL.md.

    A skill is a directory. Installing only ``SKILL.md`` would leave the
    59 ``../<skill>/SKILL.md`` cross-links intact and every reference file
    they lean on missing.
    """
    kit = stage_kit(tmp_path / "kit")
    planted = kit / "skills" / "pb-review" / "references" / "planted.md"
    planted.parent.mkdir(parents=True)
    planted.write_bytes(b"# planted reference\n")
    target = tmp_path / "target"
    target.mkdir()

    install(target, kit=kit, home=tmp_path / "home")

    installed = target / ".claude" / "skills"
    assert (installed / "pb-review" / "references" / "planted.md").read_bytes() == (
        b"# planted reference\n"
    )
    payload_skills = {p.name for p in (kit / "skills").iterdir() if p.is_dir()}
    assert {p.name for p in installed.iterdir() if p.is_dir()} == payload_skills
    for name in payload_skills:
        assert (installed / name / "SKILL.md").is_file()


def test_ledger16_skill_set_is_globbed_at_run_time_and_sorted_case_insensitively(
    tmp_path: Path,
) -> None:
    """Ledger 16: the set is a glob, and the order is the marker's order.

    ``iterdir()`` order is not guaranteed and a plain ``sorted()`` puts
    every capitalised name in front of every lowercase one. The three
    planted names are chosen so that the required order differs from both
    wrong answers on this platform: NTFS hands ``_planted`` back *last*,
    a case-sensitive sort puts ``ZZ-planted`` first, and the contract puts
    ``_planted`` first and ``ZZ-planted`` last.
    """
    kit = stage_kit(tmp_path / "kit")
    for name in ("ZZ-planted", "aa-planted", "_planted"):
        (kit / "skills" / name).mkdir()
        (kit / "skills" / name / "SKILL.md").write_bytes(f"# {name}\n".encode())
    target = tmp_path / "target"
    target.mkdir()

    result = install(target, kit=kit, home=tmp_path / "home")

    installed = [
        line.split()[-1]
        for line in result.stdout.splitlines()
        if line.startswith("Installed skill")
    ]
    assert installed == [
        "_planted",
        "aa-planted",
        "appeon-query",
        "pb-apply-plan",
        "pb-context-build",
        "pb-format",
        "pb-review",
        "pb-scaffold",
        "pb-src-format",
        "ZZ-planted",
    ]
    assert (target / ".claude" / "skills" / "aa-planted" / "SKILL.md").is_file()
    assert (target / ".claude" / "skills" / "ZZ-planted" / "SKILL.md").is_file()


# --- ledger 17: the commands -------------------------------------------------


def test_ledger17_commands_are_flat_md_files_and_do_not_prune(tmp_path: Path) -> None:
    """Ledger 17: ``commands/*.md``, flat, non-recursive, no pre-delete.

    The commands directory is a place the user also keeps their own
    commands, so the copy overwrites what it owns and touches nothing
    else.
    """
    kit = stage_kit(tmp_path / "kit")
    (kit / "commands" / "notes.txt").write_bytes(b"not a command\n")
    (kit / "commands" / "sub").mkdir()
    (kit / "commands" / "sub" / "nested.md").write_bytes(b"# nested\n")
    target = tmp_path / "target"
    (target / ".claude" / "commands").mkdir(parents=True)
    (target / ".claude" / "commands" / "my-command.md").write_bytes(b"# mine\n")

    install(target, kit=kit, home=tmp_path / "home")

    commands = target / ".claude" / "commands"
    assert {p.name for p in commands.iterdir()} == {
        "my-command.md",
        "pb-format.md",
        "pb-review.md",
    }
    assert (commands / "my-command.md").read_bytes() == b"# mine\n"


# --- ledger 18, 19, 20, 54: the knowledge base -------------------------------


def test_ledger18_19_both_doc_trees_and_the_loose_doc_file_are_installed(
    tmp_path: Path,
) -> None:
    """Ledger 18 and 19: two trees as a pair, ``wiki-notes.md`` loose.

    ``wiki-notes.md`` goes into the docs *root*, not into a tree of its
    own: omitting it produced exactly five dead links once
    (commit 308ff22, CHANGELOG 0.1.6).
    """
    target = tmp_path / "target"
    target.mkdir()

    install(target, home=tmp_path / "home")

    docs = target / ".claude" / "pb-ai-code-docs"
    assert (docs / "pb-antipatterns" / "index.md").is_file()
    assert (docs / "pb-source-format" / "index.md").is_file()
    # A nested directory inside a tree proves the copy is recursive.
    assert (docs / "pb-source-format" / "patterns" / "index.md").is_file()
    wiki = docs / "wiki-notes.md"
    assert wiki.is_file(), "wiki-notes.md must sit in the docs root, not in a tree"
    assert wiki.read_bytes() == (REPO_ROOT / "docs" / "wiki-notes.md").read_bytes()


@pytest.mark.parametrize(
    ("skills_dir", "bundle_rel"),
    [
        (".agent/skills", ".agent"),
        ("a/b/skills", "a/b"),
        ("skills", ""),
        (".agent\\skills", ".agent"),
    ],
)
def test_ledger13_20_54_docs_and_marker_follow_the_skills_directory_parent(
    tmp_path: Path, skills_dir: str, bundle_rel: str
) -> None:
    """Ledger 13, 20 and 54: docs and marker land beside the skills directory.

    ``pb-ai-code-docs`` and not ``docs``: that name belongs to the host
    project. The marker sits in the bundle root and never *inside* the
    skills directory, which is what both documents that tell a reader
    where to look already promise, and it keeps a stray ``.txt`` out of
    the place a skill loader enumerates. The last case is spelled with a
    backslash, because a PowerBuilder developer types backslashes and the
    script took whichever separator it was given.
    """
    target = tmp_path / "target"
    target.mkdir()

    install(target, "--harness", "generic", "--skills-dir", skills_dir, home=tmp_path / "home")

    skills_dir = skills_dir.replace("\\", "/")
    bundle = target.joinpath(*bundle_rel.split("/")) if bundle_rel else target
    assert (bundle / "pb-ai-code-docs" / "pb-antipatterns" / "index.md").is_file()
    assert (bundle / MARKER_NAME).is_file()
    assert not (target.joinpath(*skills_dir.split("/")) / MARKER_NAME).exists()
    assert not (bundle / "docs").exists()
    # The doc trees link back to the skills with `../../skills/<name>/`, and
    # nothing rewrites those: they resolve only because the docs sit beside
    # the skills directory rather than inside it.
    index = bundle / "pb-ai-code-docs" / "pb-antipatterns" / "index.md"
    assert (index.parent / "../../skills/pb-review/SKILL.md").resolve().is_file()


# --- ledger 21: the copy set is closed ---------------------------------------


def test_ledger21_the_copy_set_is_closed(tmp_path: Path) -> None:
    """Ledger 21: exactly the payload, and nothing else in the repository.

    ``docs/install.md``, ``docs/appeon-index/`` (with a 4.8 MB
    ``index.db`` on a developer machine), ``harness/README.md``, the root
    prose, ``tools/``, ``tests/`` and ``scripts/`` never reach a target.
    """
    target = tmp_path / "target"
    target.mkdir()

    install(target, home=tmp_path / "home")

    installed = files_under(target)
    # AGENTS.md joins the set deliberately: it is the project's own
    # instruction file, created only when absent and never rewritten, and
    # it is where the PowerBuilder version lives - the one fact the sources
    # cannot be asked for, since an object keeps the release it was last
    # saved under.
    expected = {
        ".mcp.json",
        "AGENTS.md",
        f".claude/{MARKER_NAME}",
        ".claude/settings.json",
    }
    for skill in (REPO_ROOT / "skills").iterdir():
        if not skill.is_dir():
            continue
        expected |= {
            f".claude/skills/{skill.name}/{p.relative_to(skill).as_posix()}"
            for p in skill.rglob("*")
            if p.is_file()
        }
    expected |= {
        f".claude/commands/{p.name}" for p in (REPO_ROOT / "commands").glob("*.md") if p.is_file()
    }
    for tree in ("pb-antipatterns", "pb-source-format"):
        root = REPO_ROOT / "docs" / tree
        expected |= {
            f".claude/pb-ai-code-docs/{tree}/{p.relative_to(root).as_posix()}"
            for p in root.rglob("*")
            if p.is_file()
        }
    expected |= {f".claude/pb-ai-code-docs/{name}" for name in plan_mod.DOC_FILES}
    assert installed == expected

    forbidden = ("install.md", "README.md", "CHANGELOG.md", "install-skills.ps1")
    assert not [name for name in installed if name.rsplit("/", 1)[-1] in forbidden]
    # AGENTS.md is written, not copied, and the difference matters: this
    # repository has one of its own - instructions for working on the kit -
    # and shipping it into a customer's PowerBuilder project would tell an
    # agent to go and edit the kit.
    written = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert "PowerBuilder facts an agent needs" in written
    assert "pb-ai-code" not in written.splitlines()[0]
    assert not [name for name in installed if name.endswith(".db")]
    assert not [name for name in installed if "appeon-index/" in name]


# --- ledger 22, 23: settings.json --------------------------------------------


def test_ledger22_23_settings_json_is_a_verbatim_overwrite(tmp_path: Path) -> None:
    """Ledger 22 and 23: full overwrite, opaque bytes, one WARN line.

    No merge, no backup - the single most destructive undocumented
    behaviour in the script, kept because the file is the kit's, and
    changed only by saying so on stdout. ``settings.local.json`` is not
    ours and is never touched.
    """
    target = tmp_path / "target"
    (target / ".claude").mkdir(parents=True)
    (target / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"allow": ["Bash(rm:*)"]}}), encoding="utf-8"
    )
    (target / ".claude" / "settings.local.json").write_text("{}", encoding="utf-8")

    result = install(target, home=tmp_path / "home")

    canonical = (REPO_ROOT / "harness" / "claude-code" / "settings.json").read_bytes()
    installed = (target / ".claude" / "settings.json").read_bytes()
    assert installed == canonical, "settings.json is copied as opaque bytes, never re-serialised"
    assert b"_comment" in installed
    assert "Bash(rm:*)" not in installed.decode("utf-8")
    assert (
        "WARN: replaced an existing .claude\\settings.json whose content differed." in result.stdout
    )
    assert (target / ".claude" / "settings.local.json").read_text(encoding="utf-8") == "{}"

    # The stdout line scrolls past; the marker line is what someone finds
    # months later, next to a settings file they do not recognise. Both, or
    # the observability bought back for the overwrite is worth one session.
    marker_text = (target / ".claude" / "_installed-from-pb-ai-code.txt").read_text(
        encoding="utf-8"
    )
    assert marker.settings_replaced_warning(".claude\\settings.json") in marker_text

    # And the negative, which is what makes the warning mean something: the
    # file is now identical to ours, so a second install replaced nothing and
    # must say nothing. A WARN that fires on every run is noise, and noise is
    # how a real one gets skipped.
    again = install(target, home=tmp_path / "home")
    assert "WARN: replaced an existing" not in again.stdout
    marker_again = (target / ".claude" / "_installed-from-pb-ai-code.txt").read_text(
        encoding="utf-8"
    )
    assert "was replaced; its content differed" not in marker_again


def test_ledger22_generic_harness_writes_no_settings_file(tmp_path: Path) -> None:
    """Ledger 22: the settings file is claude-code's, and only claude-code's."""
    target = tmp_path / "target"
    target.mkdir()

    result = install(
        target, "--harness", "generic", "--skills-dir", ".agent/skills", home=tmp_path / "home"
    )

    assert not [name for name in files_under(target) if name.endswith("settings.json")]
    assert "Installed settings" not in result.stdout


# --- ledger 24, 25, 26: re-installing over a populated target ----------------


def test_ledger24_trees_are_deleted_before_they_are_copied(tmp_path: Path) -> None:
    """Ledger 24: a fresh slate for ``skill`` and ``docs`` rows.

    Two bugs at once. A recursive copy into an existing directory nests
    (``pb-review/pb-review/...``), and without the delete a file dropped
    upstream lives on in every installed bundle for ever. The ghost and
    the hand edit below are the two halves of that.
    """
    target = tmp_path / "target"
    target.mkdir()
    install(target, home=tmp_path / "home")

    ghost = target / ".claude" / "pb-ai-code-docs" / "pb-antipatterns" / "ghost.md"
    ghost.write_bytes(b"# upstream deleted me\n")
    edited = target / ".claude" / "skills" / "pb-review" / "SKILL.md"
    edited.write_bytes(b"# hand-edited\n")

    install(target, home=tmp_path / "home")

    assert not ghost.exists(), "a file removed upstream must not survive a re-install"
    assert edited.read_bytes() != b"# hand-edited\n"
    assert not (target / ".claude" / "skills" / "pb-review" / "pb-review").exists()
    assert not (
        target / ".claude" / "pb-ai-code-docs" / "pb-antipatterns" / "pb-antipatterns"
    ).exists()


def test_ledger25_readonly_destinations_are_replaced(tmp_path: Path) -> None:
    """Ledger 25: a read-only destination is cleared, not refused.

    ``Remove-Item -Force`` deleted read-only files and ``Copy-Item
    -Force`` overwrote them; ``shutil.rmtree`` and ``copyfile`` raise
    ``PermissionError`` instead. A bundle somebody committed, or a target
    checked out read-only, would break the port where the script worked.
    """
    target = tmp_path / "target"
    target.mkdir()
    install(target, home=tmp_path / "home")

    readonly = [
        target / ".claude" / "skills" / "pb-review" / "SKILL.md",
        target / ".claude" / "pb-ai-code-docs" / "pb-antipatterns" / "index.md",
        target / ".claude" / "settings.json",
        target / ".claude" / "commands" / "pb-review.md",
        target / ".claude" / MARKER_NAME,
    ]
    for path in readonly:
        path.write_bytes(b"clobbered\n")
        os.chmod(path, stat.S_IREAD)

    result = run_cli("install", "--target", str(target), env=kit_env(tmp_path / "home"))

    assert result.returncode == 0, f"read-only target broke the install:\n{result.stderr}"
    for path in readonly:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        assert path.read_bytes() != b"clobbered\n", f"{path} was not replaced"


def test_ledger26_install_is_additive_and_never_prunes(tmp_path: Path) -> None:
    """Ledger 26: deletion is scoped to what is about to be written.

    Five shapes, all verified against the script: a skill dropped
    upstream, the user's own skill, a doc tree that is not ours, a loose
    file at the docs root, and the user's own command. None of them
    appears in the marker's Contents either.
    """
    target = tmp_path / "target"
    target.mkdir()
    install(target, home=tmp_path / "home")

    bundle = target / ".claude"
    survivors = [
        bundle / "skills" / "pb-obsolete" / "SKILL.md",
        bundle / "skills" / "my-own-skill" / "SKILL.md",
        bundle / "pb-ai-code-docs" / "my-tree" / "note.md",
        bundle / "pb-ai-code-docs" / "my-notes.md",
        bundle / "commands" / "my-command.md",
    ]
    for path in survivors:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"# mine\n")

    install(target, home=tmp_path / "home")

    for path in survivors:
        assert path.read_bytes() == b"# mine\n", f"{path} did not survive the re-install"
    contents = (bundle / MARKER_NAME).read_text(encoding="utf-8-sig")
    for name in ("pb-obsolete", "my-own-skill", "my-tree", "my-notes.md", "my-command.md"):
        assert name not in contents, f"{name} is the user's, and the marker must not claim it"


# --- ledger 27, 28, 29: the link rewrite -------------------------------------


def test_ledger27_28_link_rewrite_count_scope_and_byte_exactness(tmp_path: Path) -> None:
    """Ledger 27 and 28: five files rewritten, everything else byte-exact.

    The substitution is literal, ordinal and case-sensitive, applies to
    every occurrence, and is scoped to ``<skills>/<name>/SKILL.md``.
    Everything else must arrive byte-identical: the tree legitimately
    mixes line endings (``wiki-notes.md`` is CRLF, the skills are LF) and
    Python's text mode would CRLF-ify exactly the rewritten files.
    """
    target = tmp_path / "target"
    target.mkdir()

    result = install(target, home=tmp_path / "home")

    assert "Rewrote knowledge-base links in 5 skill file(s)." in result.stdout
    bundle = target / ".claude"
    for path in bundle.rglob("*"):
        if path.is_file():
            assert b"../../docs/" not in path.read_bytes(), f"{path} still points at ../../docs/"
    src_format = (bundle / "skills" / "pb-src-format" / "SKILL.md").read_bytes()
    assert src_format.count(b"../../pb-ai-code-docs/") == 13

    changed = []
    for skill in (REPO_ROOT / "skills").iterdir():
        if not skill.is_dir():
            continue
        payload = (skill / "SKILL.md").read_bytes()
        rewritten = payload.replace(b"../../docs/", b"../../pb-ai-code-docs/")
        installed = (bundle / "skills" / skill.name / "SKILL.md").read_bytes()
        assert installed == rewritten, f"{skill.name} differs by more than the links"
        if rewritten != payload:
            changed.append(skill.name)
    assert sorted(changed) == [
        "pb-apply-plan",
        "pb-format",
        "pb-review",
        "pb-scaffold",
        "pb-src-format",
    ]
    # Nothing else is rewritten, and nothing else is re-encoded.
    for rel in ("commands/pb-format.md", "commands/pb-review.md"):
        assert (bundle / rel).read_bytes() == (REPO_ROOT / rel).read_bytes()
    for tree in ("pb-antipatterns", "pb-source-format"):
        root = REPO_ROOT / "docs" / tree
        for payload_file in root.rglob("*"):
            if payload_file.is_file():
                landed = bundle / "pb-ai-code-docs" / tree / payload_file.relative_to(root)
                assert landed.read_bytes() == payload_file.read_bytes()


def test_ledger29_self_install_copies_the_docs_and_rewrites_the_links(tmp_path: Path) -> None:
    """Ledger 29: the docs copy and the rewrite are unconditional.

    Two comments in the PowerShell script say a self-install skips them.
    They are stale - the commit that wrote them recanted them in the same
    breath - and a port that implements the comments fails exactly here.
    Run from inside the checkout with no ``--target``, which is also what
    proves the target defaults to the current directory.
    """
    kit = stage_kit(tmp_path / "kit")

    result = run_cli("install", cwd=kit, env=kit_env(tmp_path / "home", kit))

    assert result.returncode == 0, f"self-install failed:\n{result.stdout}\n{result.stderr}"
    assert (kit / ".claude" / "pb-ai-code-docs" / "pb-antipatterns" / "index.md").is_file()
    assert (kit / ".claude" / "pb-ai-code-docs" / "wiki-notes.md").is_file()
    installed = (kit / ".claude" / "skills" / "pb-src-format" / "SKILL.md").read_bytes()
    assert installed.count(b"../../pb-ai-code-docs/") == 13
    assert b"../../docs/" not in installed
    # The canonical copy is the source of truth and is not touched.
    assert (kit / "skills" / "pb-src-format" / "SKILL.md").read_bytes().count(b"../../docs/") == 13


# --- ledger 14: validate everything before writing ---------------------------


@pytest.mark.parametrize(
    "missing",
    ["docs/wiki-notes.md", "docs/pb-antipatterns", "harness/claude-code/settings.json"],
)
@pytest.mark.parametrize("extra", [(), ("--dry-run",)])
def test_ledger14_a_missing_payload_input_stops_before_the_first_copy(
    tmp_path: Path, missing: str, extra: tuple[str, ...]
) -> None:
    """Ledger 14: the whole plan is validated before anything is written.

    Deliberately so that ``--dry-run`` catches it too - it walks the same
    code. A half-installed bundle carrying a marker that confidently
    describes it is the failure this prevents.
    """
    kit = stage_kit(tmp_path / "kit")
    doomed = kit.joinpath(*missing.split("/"))
    if doomed.is_dir():
        shutil.rmtree(doomed)
    else:
        doomed.unlink()
    target = tmp_path / "target"
    target.mkdir()

    result = run_cli(
        "install", "--target", str(target), *extra, env=kit_env(tmp_path / "home", kit)
    )

    assert result.returncode != 0
    assert result.stdout == "", "nothing is printed on a failure path"
    assert os.listdir(target) == [], "the target must be untouched"
    assert result.stderr.startswith("pb-ai-code: ")
    assert len(result.stderr.strip().splitlines()) == 1
    assert "Traceback" not in result.stderr
