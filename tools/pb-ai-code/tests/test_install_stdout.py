"""The install report, line for line - it is the contract an agent parses.

Nothing in the repository stated the order of these lines until this file
did. The report is a fixed sequence on a single stream (stdout), because an
agent reads it and because splitting a report over stdout and stderr
destroys its ordering the moment the two are redirected separately. Four
modes are pinned as goldens: claude-code, generic, ``--skip-mcp-config``
and ``--dry-run``.

Details that look cosmetic and are not:

* the op field is nine columns wide, and there are **two** spaces before
  ``(merged; other servers preserved)``, before ``[`` and before ``in the
  installed skills``;
* ``Done.`` is deliberately **not** the last line when the gitignore note
  fires;
* ``git check-ignore -q -- '.claude/'`` - with the trailing slash - matches
  a **blank line** in a CRLF ``.gitignore`` and reports the path ignored,
  which is how the hint silently stopped firing (commit 2a365a7, still
  reproducible on git 2.40.1). CRLF ``.gitignore`` files are the norm on
  the Windows PowerBuilder repositories this kit targets, so
  ``test_ledger70_...`` is a regression test, not a hypothetical;
* ``--dry-run`` must create nothing at all, while still reporting the two
  decisions worth previewing: the Appeon index and what the merge would do.

The goldens are written with Windows separators. The report prints native
ones, CI is ``windows-latest`` only, and no support is claimed off Windows
this phase; a golden a reader can compare with a real run by eye is worth
more here than one that is portable to a platform nothing runs on.
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

# --- support -----------------------------------------------------------------
# Duplicated in the sibling test modules on purpose: three test packages in
# this repository are called `tests`, so `from ._support import ...` binds to
# whichever one pytest imported first (verified - it raises ModuleNotFoundError
# in a full run), and a conftest.py here is shared ground. A short copy is the
# cheaper of the two evils.

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_DIR = Path(pb_ai_code.__file__).resolve().parent
PAYLOAD_TREES = ("skills", "commands", "harness", "docs/pb-antipatterns", "docs/pb-source-format")
# Derived, not listed: a new entry in ``DOC_FILES`` is a new file the
# installer looks for, and a hand-kept copy here would fail every test in
# this module the day one is added - which is how it went the first time.
PAYLOAD_FILES = tuple(f"docs/{name}" for name in plan_mod.DOC_FILES)

MARKER_NAME = "_installed-from-pb-ai-code.txt"


def stage_kit(root: Path) -> Path:
    """A throwaway checkout: the payload, plus the package under test."""
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
    """Which kit to run, and a machine with no Appeon index on it."""
    home.mkdir(parents=True, exist_ok=True)
    env = {
        "PB_APPEON_INDEX_DB": str(home / "no-such-index.db"),
        "USERPROFILE": str(home),
        "HOME": str(home),
        # Keeps a __pycache__ out of the staged checkout, which would
        # otherwise make the run report its own source as dirty.
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
    target: Path,
    *args: str,
    kit: Path | None = None,
    home: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    environ = kit_env(home if home is not None else target.parent / "home", kit)
    environ.update(env or {})
    command = ["install", "--target", str(target)]
    if "--harness" not in args:
        command += ["--harness", "claude-code"]
    command += list(args)
    result = run_cli(*command, env=environ)
    assert result.returncode == 0, f"install failed:\n{result.stdout}\n{result.stderr}"
    return result


def git(repo: Path, *args: str) -> str:
    """Git with an identity of its own, so a bare CI machine can commit."""
    proc = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.email=tests@pb-ai-code.invalid",
            "-c",
            "user.name=pb-ai-code tests",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout


@pytest.fixture(scope="module")
def staged_kit(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One throwaway checkout for the goldens.

    It carries no ``docs/appeon-index/index.db``, so the Appeon branch is
    the same here as on CI, and it is not a git repository, so the source
    is never reported dirty. The report is then fully determined by the
    payload and by two values the tests normalise.
    """
    return stage_kit(tmp_path_factory.mktemp("kit"))


@pytest.fixture(scope="module")
def running_version() -> str:
    return run_cli("--version").stdout.strip()


def report_lines(result: subprocess.CompletedProcess[str], target: Path, version: str) -> list[str]:
    """The report with the two machine-specific values masked."""
    text = result.stdout
    for value in (str(target.resolve()), str(target)):
        text = text.replace(value, "<target>")
    return text.replace(version, "<version>").splitlines()


def collapse_json_block(lines: list[str]) -> tuple[list[str], str]:
    """Replace the printed MCP block with a placeholder, and hand it back.

    The block quotes ``harness/mcp-servers.json``, pins and all, and that
    file's pin moves on its own schedule; the golden pins the report's
    shape around it and the JSON is checked as JSON.
    """
    start = lines.index("{")
    end = lines.index("}", start)
    collapsed = [*lines[:start], "<mcp-json-block>", *lines[end + 1 :]]
    return collapsed, "\n".join(lines[start : end + 1])


def plan_rows(bundle: str, *, commands: bool) -> list[str]:
    """The copy rows, in plan order, for a single-root harness.

    Derived from the payload rather than written out: the set of skills is
    a run-time glob (ledger 16), while the *shape* of each line is the
    contract this file pins.
    """
    skills = sorted((p.name for p in (REPO_ROOT / "skills").iterdir() if p.is_dir()), key=str.lower)
    rows = [
        f"skill     <src>\\skills\\{name} -> <dst>\\{bundle}\\skills\\{name}" for name in skills
    ]
    if commands:
        rows += [
            f"command   <src>\\commands\\{p.name} -> <dst>\\{bundle}\\commands\\{p.name}"
            for p in sorted((REPO_ROOT / "commands").glob("*.md"), key=lambda p: p.name.lower())
        ]
    rows += [
        f"docs      <src>\\docs\\{tree} -> <dst>\\{bundle}\\pb-ai-code-docs\\{tree}"
        for tree in ("pb-antipatterns", "pb-source-format")
    ]
    rows += [
        f"docfile   <src>\\docs\\{name} -> <dst>\\{bundle}\\pb-ai-code-docs\\{name}"
        for name in plan_mod.DOC_FILES
    ]
    return rows


def installed_rows(*, commands: bool, settings: bool) -> list[str]:
    """One ``Installed <op> <leaf>`` line per plan row - the leaf, never the path."""
    skills = sorted((p.name for p in (REPO_ROOT / "skills").iterdir() if p.is_dir()), key=str.lower)
    rows = [f"Installed skill     {name}" for name in skills]
    if commands:
        rows += [
            f"Installed command   {p.name}"
            for p in sorted((REPO_ROOT / "commands").glob("*.md"), key=lambda p: p.name.lower())
        ]
    rows += [
        "Installed docs      pb-antipatterns",
        "Installed docs      pb-source-format",
        *(f"Installed docfile   {name}" for name in plan_mod.DOC_FILES),
    ]
    if settings:
        rows.append("Installed settings  settings.json")
    return rows


#: The failure branch of the Appeon probe, verbatim (ledger 51). The recipe
#: is one command: the tool used to resolve its config.toml by walking
#: up from its own module, which only finds a file inside a checkout, so a
#: clone was genuinely required to build an index on a machine that already
#: had the tool. The config ships in the wheel now.
APPEON_MISSING = [
    "",
    "Note: pb-appeon-index NOT configured - missing the index database",
    "      The PowerScript reference lookups degrade to reading the",
    "      database directly, or to web fetches. To build the index",
    "      (once per machine - it scrapes docs.appeon.com, so give it",
    "      a few minutes):",
    "        pb-ai-code search setup",
    "      Then re-run this installer and the server is configured.",
]


#: Every golden target below is a plain directory, so the install ends by
#: saying the project is not under version control. Silence used to be the
#: rule here; what it missed is that `git init` on any later day sweeps the
#: generated bundle - and an .mcp.json holding absolute paths - into the
#: first commit with nothing in the way.
def not_a_repo_note(
    bundle_root: str, *, mcp: bool = True, mcp_path: str | None = None
) -> list[str]:
    lines = [
        "",
        f"Note: this project is not a git repository, so nothing ignores {bundle_root}.",
        "      Nothing to do today. If it ever becomes one, the bundle is generated",
        "      and does not want committing - these are the lines:",
        f"        {bundle_root}/",
    ]
    if mcp or mcp_path is not None:
        lines.append(
            f"        {mcp_path or '.mcp.json'}          # carries absolute paths for this machine"
        )
    return lines


RESTART_HINT = (
    "Restart your assistant to pick up the MCP config, "
    "then confirm the pb_* tools are listed (/mcp)."
)

GITIGNORE_BODY = [
    "      The bundle is generated - update it by re-running pb-ai-code install, not by",
    "      editing it - so it does not want committing. Suggested .gitignore lines:",
]


# --- ledger 64, 65, 66, 67, 68: the goldens ----------------------------------


def test_ledger64_68_stdout_golden_claude_code(
    tmp_path: Path, staged_kit: Path, running_version: str
) -> None:
    """Ledger 64-68: the whole claude-code report, in order, on stdout.

    Twenty steps in a fixed sequence, single stream, stderr empty. The
    order was a contract nothing stated; this is where it is stated.
    """
    target = tmp_path / "target"
    target.mkdir()

    result = install(target, kit=staged_kit, home=tmp_path / "home")

    assert result.stderr == "", "the report is one stream; stderr carries only failures"
    assert report_lines(result, target, running_version) == [
        "",
        "Source:  pb-ai-code <version>",
        "Target:  <target>",
        "Harness: claude-code",
        "",
        *plan_rows(".claude", commands=True),
        "settings  <src>\\harness\\claude-code\\settings.json -> <dst>\\.claude\\settings.json",
        "mcp       <src>\\harness\\mcp-servers.json -> <dst>\\.mcp.json"
        "  (merged; other servers preserved)",
        f"marker    <dst>\\.claude\\{MARKER_NAME}",
        "rewrite   ../../docs/ -> ../../pb-ai-code-docs/  in the installed skills",
        "",
        *installed_rows(commands=True, settings=True),
        "Rewrote knowledge-base links in 5 skill file(s).",
        "Installed mcp       .mcp.json  [pb-orca (added)]",
        *APPEON_MISSING,
        "agents    AGENTS.md  (created; the project's own file, never rewritten)",
        "          PowerBuilder release not stated - fill it in there, or",
        "          re-run with --pb-version pb2022r3",
        "",
        "Done.",
        RESTART_HINT,
        *not_a_repo_note(".claude"),
    ]


def test_ledger12_47_stdout_golden_generic(
    tmp_path: Path, staged_kit: Path, running_version: str
) -> None:
    """Ledger 12 and 47: the generic report writes the neutral MCP file."""
    target = tmp_path / "target"
    target.mkdir()

    result = install(
        target,
        "--harness",
        "generic",
        "--skills-dir",
        ".agents/skills",
        kit=staged_kit,
        home=tmp_path / "home",
    )

    lines = report_lines(result, target, running_version)
    block = ""
    assert result.stderr == ""
    assert lines == [
        "",
        "Source:  pb-ai-code <version>",
        "Target:  <target>",
        "Harness: generic",
        "",
        *plan_rows(".agents", commands=True),
        "mcp       <src>\\harness\\mcp-servers.json -> <dst>\\.mcp.json"
        "  (merged; other servers preserved)",
        f"marker    <dst>\\.agents\\{MARKER_NAME}",
        "rewrite   ../../docs/ -> ../../pb-ai-code-docs/  in the installed skills",
        "",
        *installed_rows(commands=True, settings=False),
        "Rewrote knowledge-base links in 5 skill file(s).",
        "Installed mcp       .mcp.json  [pb-orca (added)]",
        *APPEON_MISSING,
        "agents    AGENTS.md  (created; the project's own file, never rewritten)",
        "          PowerBuilder release not stated - fill it in there, or",
        "          re-run with --pb-version pb2022r3",
        "",
        "Done.",
        *not_a_repo_note(".agents", mcp_path=".mcp.json"),
    ]
    assert "pb-orca" in json.loads((target / ".mcp.json").read_text())["mcpServers"]
    assert block == ""


def test_ledger48_stdout_golden_skip_mcp_config(
    tmp_path: Path, staged_kit: Path, running_version: str
) -> None:
    """Ledger 48: four suppressions, one sentence, and still exit 0.

    ``--skip-mcp-config`` silences the merge, the Appeon report, the
    restart hint and the ``.mcp.json`` line in the gitignore hint. The plan
    row says so too, so a dry run shows the flag took effect.
    """
    target = tmp_path / "target"
    target.mkdir()

    result = install(target, "--skip-mcp-config", kit=staged_kit, home=tmp_path / "home")

    assert result.stderr == ""
    assert report_lines(result, target, running_version) == [
        "",
        "Source:  pb-ai-code <version>",
        "Target:  <target>",
        "Harness: claude-code",
        "",
        *plan_rows(".claude", commands=True),
        "settings  <src>\\harness\\claude-code\\settings.json -> <dst>\\.claude\\settings.json",
        "mcp       skipped (--skip-mcp-config)",
        f"marker    <dst>\\.claude\\{MARKER_NAME}",
        "rewrite   ../../docs/ -> ../../pb-ai-code-docs/  in the installed skills",
        "",
        *installed_rows(commands=True, settings=True),
        "Rewrote knowledge-base links in 5 skill file(s).",
        "Skipped MCP config (--skip-mcp-config). The skills expect the pb_* tools to be reachable.",
        "agents    AGENTS.md  (created; the project's own file, never rewritten)",
        "          PowerBuilder release not stated - fill it in there, or",
        "          re-run with --pb-version pb2022r3",
        "",
        "Done.",
        *not_a_repo_note(".claude", mcp=False),
    ]
    assert not (target / ".mcp.json").exists()


def test_ledger75_stdout_golden_dry_run_and_it_writes_nothing(
    tmp_path: Path, staged_kit: Path, running_version: str
) -> None:
    """Ledger 75: the plan, the two previews, and an untouched directory.

    Wider than the script's dry run, which was silent about exactly the two
    decisions a user wants previewed - whether the Appeon index was found,
    and what the merge would do to the servers already in the target.
    """
    target = tmp_path / "target"
    target.mkdir()

    result = install(target, "--dry-run", kit=staged_kit, home=tmp_path / "home")

    assert os.listdir(target) == [], "a dry run creates nothing at all"
    assert result.stderr == ""
    assert report_lines(result, target, running_version) == [
        "",
        "Source:  pb-ai-code <version>",
        "Target:  <target>",
        "Harness: claude-code",
        "",
        *plan_rows(".claude", commands=True),
        "settings  <src>\\harness\\claude-code\\settings.json -> <dst>\\.claude\\settings.json",
        "mcp       <src>\\harness\\mcp-servers.json -> <dst>\\.mcp.json"
        "  (merged; other servers preserved)",
        f"marker    <dst>\\.claude\\{MARKER_NAME}",
        "rewrite   ../../docs/ -> ../../pb-ai-code-docs/  in the installed skills",
        "",
        "Dry run. No changes written.",
        "Note: pb-appeon-index NOT configured - missing the index database",
        "MCP: would add pb-orca",
        "Would create AGENTS.md  (the project's own file, never rewritten)",
        "Would say nothing about .gitignore: the target is not a git repository",
    ]


def test_ledger75_dry_run_leaves_an_existing_mcp_config_byte_identical(
    tmp_path: Path, staged_kit: Path
) -> None:
    """Ledger 75: the preview reads the target's config and writes nothing."""
    target = tmp_path / "target"
    target.mkdir()
    before = b'{\n  "mcpServers": {\n    "pb-orca": {"command": "old"}\n  }\n}\n'
    (target / ".mcp.json").write_bytes(before)

    result = install(target, "--dry-run", kit=staged_kit, home=tmp_path / "home")

    assert (target / ".mcp.json").read_bytes() == before
    assert os.listdir(target) == [".mcp.json"]
    assert "MCP: would update pb-orca" in result.stdout


# --- ledger 51: the Appeon report --------------------------------------------


def test_ledger50_51_appeon_index_is_referenced_not_copied(
    tmp_path: Path, staged_kit: Path
) -> None:
    """Ledger 50 and 51: two lines, an absolute path, and no copy.

    One database serves every project: rebuilding it once updates every
    project already configured. Copying it would give N stale copies
    instead of one live file.
    """
    target = tmp_path / "target"
    target.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    db = home / "index.db"
    db.write_bytes(b"SQLite format 3\x00")
    env = kit_env(home, staged_kit)
    env["PB_APPEON_INDEX_DB"] = str(db)

    result = run_cli("install", "--target", str(target), env=env)

    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert f"Appeon index      {db}" in lines
    index = lines.index(f"Appeon index      {db}")
    assert lines[index + 1] == (
        "                  referenced, not copied - rebuilding it once updates every project"
    )
    assert not [p for p in target.rglob("*") if p.suffix == ".db"]
    written = json.loads((target / ".mcp.json").read_text(encoding="utf-8"))
    assert written["mcpServers"]["pb-appeon-index"]["env"]["PB_APPEON_INDEX_DB"] == str(db)


# --- ledger 69, 70, 71, 72, 73: the gitignore hint ---------------------------


def test_ledger70_hint_fires_against_a_crlf_gitignore_with_a_blank_line(
    tmp_path: Path, staged_kit: Path
) -> None:
    """Ledger 70: the regression that made the hint silently never fire.

    ``git check-ignore -q -- '.claude/'`` - with the trailing slash -
    matches a **blank line** in a CRLF ``.gitignore`` and answers
    "ignored". Reproduced on git 2.40.1; CRLF ``.gitignore`` files are the
    norm on the Windows PowerBuilder repositories this kit targets. The
    query is made without the slash, which is only correct after the copy,
    because it relies on the directory existing.
    """
    target = tmp_path / "target"
    target.mkdir()
    git(target, "init", "-q", "-b", "main")
    (target / ".gitignore").write_bytes(b"# rules\r\n\r\n*.log\r\n")

    result = install(target, kit=staged_kit, home=tmp_path / "home")

    lines = result.stdout.splitlines()
    # Ledger 68: the note prints after `Done.`, so `Done.` is not the last
    # line. Ledger 71: the check queried `.claude` without a trailing slash
    # and the suggested rule is printed with one.
    assert lines[-8:] == [
        "Done.",
        RESTART_HINT,
        "",
        "Note: '.claude' is not ignored by git in this project.",
        *GITIGNORE_BODY,
        "        .claude/",
        "        .mcp.json",
    ]


def test_ledger69_71_hint_is_silent_when_the_bundle_is_already_ignored(
    tmp_path: Path, staged_kit: Path
) -> None:
    """Ledger 69: nothing to say when the project already ignores the bundle."""
    target = tmp_path / "target"
    target.mkdir()
    git(target, "init", "-q", "-b", "main")
    (target / ".gitignore").write_bytes(b".claude/\r\n.mcp.json\r\n")

    result = install(target, kit=staged_kit, home=tmp_path / "home")

    assert "not ignored by git" not in result.stdout
    assert result.stdout.splitlines()[-1] == RESTART_HINT


def test_a_target_that_is_not_a_repository_is_told_so_once(
    tmp_path: Path, staged_kit: Path
) -> None:
    """Ledger 72, amended: not nagged, but not left in silence either.

    The original rule was silence - there is no .gitignore to be wrong
    about, and the install has already succeeded. What that missed is that
    the install just wrote generated files, one of which carries an
    absolute path with a username in it, and `git init` here on any later
    day sweeps them into the first commit with nothing in the way. So the
    note states the fact and the two lines, says there is nothing to do
    today, and decides nothing: writing a .gitignore ourselves would
    decide something, and a team that vendors the bundle on purpose has
    the opposite convention.
    """
    target = tmp_path / "target"
    target.mkdir()

    result = install(target, kit=staged_kit, home=tmp_path / "home")

    assert result.returncode == 0
    # Not the repository wording: there is no repository to name.
    assert "not ignored by git" not in result.stdout
    assert "this project is not a git repository" in result.stdout
    assert "Nothing to do today." in result.stdout
    assert "        .claude/" in result.stdout
    assert ".mcp.json" in result.stdout


def test_the_note_is_absent_when_there_is_no_git_at_all(tmp_path: Path, staged_kit: Path) -> None:
    """The other half of ledger 72, and it keeps its silence.

    A machine with no git on PATH knows nothing about the target's version
    control, so it says nothing about it - as opposed to a machine that
    asked and got an answer. Simulated by handing the subprocess a PATH
    that cannot resolve git.
    """
    target = tmp_path / "target"
    target.mkdir()

    # Not an empty PATH: on Windows that can stop the interpreter starting.
    # The system directory is enough to run and is not where git lives.
    bare = os.environ.get("SYSTEMROOT", "/usr") + os.sep + "System32"
    if shutil.which("git", path=bare) is not None:
        pytest.skip("git is reachable even from a bare PATH here")

    result = install(target, kit=staged_kit, home=tmp_path / "home", env={"PATH": bare})

    assert result.returncode == 0
    assert "not a git repository" not in result.stdout
    assert "not ignored by git" not in result.stdout


def test_ledger73_hint_names_the_enclosing_repository(tmp_path: Path, staged_kit: Path) -> None:
    """Ledger 73: the advice is about whichever ``.gitignore`` decides.

    ``rev-parse --is-inside-work-tree`` answers true for a plain directory
    nested in an enclosing repository, so the note used to say "in this
    project" while talking about the parent's ``.gitignore``.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    target = repo / "sub"
    target.mkdir()

    result = install(target, kit=staged_kit, home=tmp_path / "home")

    assert (
        f"Note: '.claude' is not ignored by git in {repo.resolve()}, "
        "the repository this target sits inside." in result.stdout
    )


def test_ledger48_71_hint_drops_the_mcp_rule_under_skip_mcp_config(
    tmp_path: Path, staged_kit: Path
) -> None:
    """Ledger 48 and 71: no ``.mcp.json`` was written, so none is suggested."""
    target = tmp_path / "target"
    target.mkdir()
    git(target, "init", "-q", "-b", "main")

    result = install(target, "--skip-mcp-config", kit=staged_kit, home=tmp_path / "home")

    lines = result.stdout.splitlines()
    assert lines[-4:] == [
        "Note: '.claude' is not ignored by git in this project.",
        *GITIGNORE_BODY,
        "        .claude/",
    ]
    assert "        .mcp.json" not in lines
