"""The marker file: the only record a consumer keeps of where the kit came from.

``_installed-from-pb-ai-code.txt`` is read three ways. A human opens it
months later next to a ``.claude/`` nobody remembers installing;
``skills/pb-review`` copies its ``# Source:`` line into a plan header, where
"n/d" is explicitly forbidden; ``pb-ai-code status`` parses it back with no
network and no git. So its bytes are a contract, not a convenience:

* the values are aligned at column 14 and the file is ASCII, because it is
  read by eye;
* it is UTF-8 **without** a BOM and CRLF throughout on every platform - two
  machines installing the same kit must produce the same bytes;
* ``# Contents:`` lists the plan destinations, in plan order, and neither
  ``.mcp.json`` nor the marker itself, because those are not plan rows;
* the ``To update:`` recipe used to name ``scripts\\install-skills.ps1
  -Target <this-project>``, which required a clone on the machine. A port
  that copied that block unchanged would ship an instruction that no longer
  works.

The two dirty-source warnings are deliberately different strings - present
tense on stdout, past tense here - and this file insists on both.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import pb_ai_code
from pb_ai_code import harness, marker
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
    command = ["install", "--target", str(target)]
    if "--harness" not in args:
        command += ["--harness", "claude-code"]
    command += list(args)
    result = run_cli(
        *command,
        env=kit_env(home if home is not None else target.parent / "home", kit),
    )
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
    """One throwaway checkout for the cases a developer's machine would skew.

    A staged kit carries no ``docs/appeon-index/index.db``, so the Appeon
    probe answers "not found" here exactly as it does on CI, and the
    outcome list is the same in both places.
    """
    return stage_kit(tmp_path_factory.mktemp("kit"))


def marker_lines(path: Path) -> list[str]:
    """The marker, decoded and split, with the line endings left behind."""
    return path.read_bytes().decode("ascii").splitlines()


def contents_entries(lines: list[str]) -> list[str]:
    """The ``#   <destination>`` block, in the order it was written."""
    entries: list[str] = []
    inside = False
    for line in lines:
        if line == "# Contents:":
            inside = True
            continue
        if inside:
            if not line.startswith("#   "):
                break
            entries.append(line[len("#   ") :])
    return entries


def value_of(lines: list[str], key: str) -> str:
    """The value of ``# <key>:``, which starts at column 14 for every key."""
    prefix = f"# {key}:"
    for line in lines:
        if line.startswith(prefix):
            return line[13:]
    raise AssertionError(f"no '{prefix}' line in the marker:\n" + "\n".join(lines))


RECIPE_HEADING = "# To update: from inside this project, run"


def recipe_of(lines: list[str]) -> str:
    """The one command line under the ``To update:`` heading."""
    assert RECIPE_HEADING in lines, "the update recipe lost its heading"
    return lines[lines.index(RECIPE_HEADING) + 1]


def only_match(pattern: re.Pattern[str], text: str, what: str) -> str:
    """Group 1 of the first match, or an assertion naming what went missing."""
    match = pattern.search(text)
    assert match is not None, f"{what} is no longer in the document"
    return match.group(1)


# --- ledger 61, 62: the bytes ------------------------------------------------


@pytest.mark.parametrize(
    ("args", "marker_rel"),
    [
        ((), ".claude"),
        (("--harness", "generic", "--skills-dir", ".agents/skills"), ".agents"),
    ],
)
def test_ledger61_marker_bytes_are_ascii_utf8_nobom_and_crlf(
    tmp_path: Path, args: tuple[str, ...], marker_rel: str
) -> None:
    """Ledger 61: UTF-8 without a BOM, CRLF throughout, one trailing CRLF.

    On every platform, deliberately: the marker is a generated file inside
    a gitignored bundle, and parity between two machines beats being
    native on one. Ledger 62 rides along - the write is atomic through a
    temp file beside the marker, and the debris must not be left behind.
    """
    target = tmp_path / "target"
    target.mkdir()

    install(target, *args, home=tmp_path / "home")

    marker = target / marker_rel / MARKER_NAME
    raw = marker.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "the marker must carry no BOM"
    assert raw.replace(b"\r\n", b"").count(b"\n") == 0, "no bare LF anywhere"
    assert raw.endswith(b"\r\n") and not raw.endswith(b"\r\n\r\n"), "exactly one trailing CRLF"
    # Ledger 55: all ASCII, so no hyphen can have become an em dash.
    raw.decode("ascii")
    assert [p.name for p in marker.parent.glob("*.tmp")] == [], "atomic write left debris"


# --- ledger 55, 56: the shape of a key line ----------------------------------


def test_ledger55_the_two_header_lines_are_verbatim(tmp_path: Path) -> None:
    """Ledger 55: the fixed header, spelled out rather than imported.

    These two lines are the whole of what tells a human who found a
    ``.claude/`` they do not recognise what it is and that editing it is
    pointless. Every other line of the file is pinned by a test; assert
    the literals, so a reword made in ``marker.HEADER_LINES`` and here at
    once still has to be deliberate.
    """
    target = tmp_path / "target"
    target.mkdir()

    install(target, home=tmp_path / "home")

    lines = marker_lines(target / ".claude" / MARKER_NAME)
    assert lines[:3] == [
        "# Skills, commands, knowledge base and MCP config installed from pb-ai-code.",
        "# Generated - do not edit. Change things in pb-ai-code and re-run.",
        "#",
    ]


def test_ledger55_56_keys_are_aligned_at_column_14_and_the_timestamp_is_local(
    tmp_path: Path,
) -> None:
    """Ledger 55 and 56: values at column 14, ``+02:00`` and not ``+0200``.

    Python's ``%z`` gives ``+0200``; the script's ``zzz`` gave ``+02:00``
    and the line is read by people, so the colon is spliced back in.
    """
    target = tmp_path / "target"
    target.mkdir()

    install(target, home=tmp_path / "home")

    lines = marker_lines(target / ".claude" / MARKER_NAME)
    assert all(line == "" or line.startswith("#") for line in lines)
    for key in ("Installed", "Version", "Source", "Harness", "MCP", "Appeon"):
        line = next(line for line in lines if line.startswith(f"# {key}:"))
        assert len(line) > 13 and line[13] != " ", f"'{key}' value does not start at column 14"
        assert line[:13].endswith(" "), f"'{key}' is padded to column 14, never past it"
    stamp = value_of(lines, "Installed")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [+-]\d{2}:\d{2}", stamp), stamp


# --- ledger 57: the one line that is read by hand ----------------------------


def test_ledger57_version_and_source_lines(tmp_path: Path) -> None:
    """Ledger 57: ``# Version:`` is the machine-readable token.

    ``# Source:`` keeps the ``pb-ai-code @ `` prefix its two documented
    readers look for, and now names a version rather than a bare sha - a
    tag is strictly better than a sha for ``observed-against``.
    """
    target = tmp_path / "target"
    target.mkdir()

    install(target, home=tmp_path / "home")
    running = run_cli("--version").stdout.strip()

    lines = marker_lines(target / ".claude" / MARKER_NAME)
    assert value_of(lines, "Version") == running
    source = value_of(lines, "Source")
    assert source.startswith(f"pb-ai-code @ {running}")
    assert "n/d" not in source
    assert value_of(lines, "Harness") == "claude-code"


def test_ledger57_source_names_the_checkout_the_sha_and_the_branch(tmp_path: Path) -> None:
    """Ledger 57: the checkout shape carries origin, sha and branch."""
    kit = stage_kit(tmp_path / "kit")
    git(kit, "init", "-q", "-b", "main")
    git(kit, "add", "-A")
    git(kit, "commit", "-q", "-m", "staged kit")
    sha = git(kit, "rev-parse", "--short", "HEAD").strip()
    target = tmp_path / "target"
    target.mkdir()

    install(target, kit=kit, home=tmp_path / "home")

    source = value_of(marker_lines(target / ".claude" / MARKER_NAME), "Source")
    assert source.endswith(f"(local checkout {kit}, {sha} on main)"), source


#: A marker key named in prose, e.g. ``the `# Version:` line``. The two
#: documents below are the only payload files that quote one.
DOC_MARKER_KEY_RE = re.compile(r"`(# [A-Za-z][A-Za-z ]*:)`")

#: The wiki-note field, in the template and in the worked example.
OBSERVED_AGAINST_RE = re.compile(r"\*\*observed-against\*\*: `pb-ai-code @ ([^`]+)`")

#: The plan header's reproducibility field, whose placeholder says what to read.
SOURCE_SKILL_RE = re.compile(r"\*\*source skill\*\*: pb-review @ <([^>]+)>")

BARE_SHA_RE = re.compile(r"[0-9a-f]{7,40}")


def test_ledger57_the_two_documented_readers_agree_with_the_marker(tmp_path: Path) -> None:
    """Ledger 57: the coordinated change, checked against the installed copies.

    ``# Source:`` stopped being ``pb-ai-code @ <short-sha> (<branch>)``,
    so the two documents that tell an agent to lift a sha out of it had to
    change in the same commit. Nothing parses the marker on their side -
    they are instructions to an LLM reading by eye, which is exactly why
    this needs a test: a document that sends an agent to a line the
    installer no longer writes gets the kit reported as broken, and the
    suite would not have noticed. Read the *installed* copies, because
    those are what the consumer gets.

    (``pb-ai-code status`` does parse the marker, by regex, in
    ``marker.parse`` - so "no machine reader" is true of the payload
    documents only, and only until someone writes one.)
    """
    target = tmp_path / "target"
    target.mkdir()

    install(target, home=tmp_path / "home")

    bundle = target / ".claude"
    lines = marker_lines(bundle / MARKER_NAME)
    skill = (bundle / "skills" / "pb-review" / "SKILL.md").read_text(encoding="utf-8")
    wiki = (bundle / "pb-ai-code-docs" / "wiki-notes.md").read_text(encoding="utf-8")

    # Whatever line a document sends its reader to, the marker must have it.
    for doc, name in ((skill, "pb-review/SKILL.md"), (wiki, "wiki-notes.md")):
        named = sorted(set(DOC_MARKER_KEY_RE.findall(doc)))
        assert named, f"{name} no longer names the marker line it reads"
        for key in named:
            assert any(line.startswith(key) for line in lines), (
                f"{name} sends its reader to '{key}', which the marker does not write"
            )

    # The two placeholders ask for the version, which is what is there now.
    placeholder = only_match(SOURCE_SKILL_RE, skill, "the plan header's 'source skill' field")
    assert "version" in placeholder.lower() and "sha" not in placeholder.lower(), placeholder
    assert only_match(OBSERVED_AGAINST_RE, skill, "the wiki-note template") == "<version>"

    # And the worked example is a version, of the shape actually written.
    example = only_match(OBSERVED_AGAINST_RE, wiki, "the wiki-note example")
    assert not BARE_SHA_RE.fullmatch(example), f"the example is a bare sha again: {example}"
    assert re.match(r"\d+\.\d+", example), example


# --- ledger 3, 4, 5: the two dirty warnings ----------------------------------


def test_ledger3_4_5_dirty_source_warns_on_stdout_and_in_the_marker(tmp_path: Path) -> None:
    """Ledger 3, 4 and 5: two warnings, two tenses, one untracked file.

    Untracked files count: an untracked skill is unversioned work that the
    install carries into the target. The stdout line is present tense and
    sits immediately after ``Source:``; the marker's is past tense and
    sits immediately after ``# Appeon:``. Do not unify them - one
    describes the repository while the installer is looking at it, the
    other describes a fact about an install that already happened.
    """
    kit = stage_kit(tmp_path / "kit")
    git(kit, "init", "-q", "-b", "main")
    git(kit, "add", "-A")
    git(kit, "commit", "-q", "-m", "staged kit")

    clean_target = tmp_path / "clean"
    clean_target.mkdir()
    clean = install(clean_target, kit=kit, home=tmp_path / "home")
    clean_marker = marker_lines(clean_target / ".claude" / MARKER_NAME)
    assert "uncommitted changes" not in clean.stdout
    assert not [line for line in clean_marker if line.startswith("# WARN:")]

    (kit / "skills" / "untracked-note.md").write_bytes(b"# not committed\n")
    dirty_target = tmp_path / "dirty"
    dirty_target.mkdir()
    dirty = install(dirty_target, kit=kit, home=tmp_path / "home")

    stdout = dirty.stdout.splitlines()
    warn = "WARN: source repo has uncommitted changes; the install may include unversioned work."
    assert stdout.count(warn) == 1
    assert stdout[stdout.index(warn) - 1].startswith("Source:")

    lines = marker_lines(dirty_target / ".claude" / MARKER_NAME)
    marker_warn = "# WARN: source repo had uncommitted changes at install time."
    assert lines.count(marker_warn) == 1
    assert lines[lines.index(marker_warn) - 1].startswith("# Appeon:")


# --- ledger 58: the four shapes of the MCP line ------------------------------


def test_ledger58_marker_mcp_line_merged(tmp_path: Path, staged_kit: Path) -> None:
    """Ledger 58: ``.mcp.json  [<outcomes>]`` - two spaces before the bracket."""
    target = tmp_path / "target"
    target.mkdir()

    install(target, kit=staged_kit, home=tmp_path / "home")

    lines = marker_lines(target / ".claude" / MARKER_NAME)
    assert value_of(lines, "MCP") == ".mcp.json  [pb-orca (added)]"


def test_ledger58_53_marker_mcp_line_skipped(tmp_path: Path) -> None:
    """Ledger 58 and 53: skipped, and Appeon reports what was computed.

    The script's marker still claimed the Appeon server was configured
    under ``-SkipMcpConfig``, having computed the note and then written
    nothing.
    """
    target = tmp_path / "target"
    target.mkdir()

    install(target, "--skip-mcp-config", home=tmp_path / "home")

    lines = marker_lines(target / ".claude" / MARKER_NAME)
    assert value_of(lines, "MCP") == "skipped (--skip-mcp-config)"
    assert value_of(lines, "Appeon") == "not evaluated (--skip-mcp-config)"


def test_ledger58_marker_mcp_line_generic(tmp_path: Path) -> None:
    """Generic installs record the neutral MCP file in the marker."""
    target = tmp_path / "target"
    target.mkdir()

    install(
        target, "--harness", "generic", "--skills-dir", ".agents/skills", home=tmp_path / "home"
    )

    lines = marker_lines(target / ".agents" / MARKER_NAME)
    assert value_of(lines, "MCP").startswith(".agents\\mcp.json  [")


def test_ledger58_marker_mcp_line_not_written(tmp_path: Path) -> None:
    """Ledger 58: an unparseable target config is recorded as not written.

    The install still exits 0 - the file is the user's and is left
    byte-for-byte alone - so the marker is the only place that says the
    merge did not happen.
    """
    target = tmp_path / "target"
    target.mkdir()
    (target / ".mcp.json").write_text('{ "mcpServers": { "broken": , } }', encoding="utf-8")

    install(target, home=tmp_path / "home")

    lines = marker_lines(target / ".claude" / MARKER_NAME)
    assert value_of(lines, "MCP") == "NOT written - .mcp.json could not be parsed; merge by hand"


# --- ledger 59: the Contents list --------------------------------------------


def test_ledger59_contents_are_the_plan_destinations_in_plan_order(tmp_path: Path) -> None:
    """Ledger 59: trees as directories, plan order, and nothing invented.

    ``.mcp.json`` and the marker itself are not plan rows, so they are not
    listed. The per-file contents of a tree are not listed either: the
    marker records what was installed, not an inventory - which is exactly
    why ``uninstall`` and ``update`` are deferred.
    """
    target = tmp_path / "target"
    target.mkdir()

    result = install(target, home=tmp_path / "home")

    entries = contents_entries(marker_lines(target / ".claude" / MARKER_NAME))
    skills = sorted((p.name for p in (REPO_ROOT / "skills").iterdir() if p.is_dir()), key=str.lower)
    commands = sorted((p.name for p in (REPO_ROOT / "commands").glob("*.md")), key=str.lower)
    expected = (
        [os.path.join(".claude", "skills", name) for name in skills]
        + [os.path.join(".claude", "commands", name) for name in commands]
        + [
            os.path.join(".claude", "pb-ai-code-docs", "pb-antipatterns"),
            os.path.join(".claude", "pb-ai-code-docs", "pb-source-format"),
            *(os.path.join(".claude", "pb-ai-code-docs", name) for name in plan_mod.DOC_FILES),
            os.path.join(".claude", "settings.json"),
        ]
    )
    assert entries == expected
    assert not [entry for entry in entries if ".mcp.json" in entry or MARKER_NAME in entry]
    # The plan table printed the same destinations, in the same order: the
    # marker's Contents *is* the plan, and the report is how a reader sees
    # it before it happens.
    planned = [
        line.split(" -> ")[1].replace(f"<dst>{os.sep}", "")
        for line in result.stdout.splitlines()
        if " -> <dst>" in line and not line.startswith("mcp ")
    ]
    assert planned == expected


# --- ledger 60: the snapshot paragraph and the update recipe -----------------


def test_ledger60_snapshot_block_and_update_recipe(tmp_path: Path) -> None:
    """Ledger 60: the snapshot paragraph verbatim, and a recipe that works.

    ``scripts\\install-skills.ps1 -Target <this-project>`` assumed a clone
    on the machine. This runs from inside the project instead, so the
    recipe is the ``uvx`` command - and a development build says so rather
    than pinning a commit that only ever existed on one machine.
    """
    target = tmp_path / "target"
    target.mkdir()

    install(target, home=tmp_path / "home")

    lines = marker_lines(target / ".claude" / MARKER_NAME)
    text = "\n".join(lines)
    assert (
        "\n".join(
            [
                "#",
                "# The knowledge base above is a SNAPSHOT. The skills grow it as they meet",
                "# undocumented cases - do that in pb-ai-code, not here, or the next",
                "# install discards it.",
                "#",
                "# Source of truth: https://github.com/restoresrl/pb-ai-code",
                "# To update: from inside this project, run",
            ]
        )
        in text
    )
    recipe = lines[lines.index("# To update: from inside this project, run") + 1]
    assert recipe.startswith("#   uvx --from git+https://github.com/restoresrl/pb-ai-code")
    assert recipe.endswith(" pb-ai-code install --harness claude-code")
    assert lines[-1] == "# Make changes in pb-ai-code, not here."
    assert "install-skills.ps1" not in text and "-Target" not in text
    version = value_of(lines, "Version")
    development = ".dev" in version or "+" in version
    note = "# (installed from a development build; pin a tag for a real install)"
    assert (note in lines) is development
    assert ("@" in recipe.split("pb-ai-code install")[0]) is not development


def test_ledger60_the_recipe_reproduces_this_layout_and_not_another(tmp_path: Path) -> None:
    """Ledger 60: the recipe names the harness and the two directory flags.

    ps1:583 wrote ``scripts\\install-skills.ps1 -Target <this-project>
    -Harness $Harness``. A flag-free ``uvx ... pb-ai-code install`` hands
    the reader of a ``generic`` bundle the command that installs the
    *claude-code* layout beside it - ``.claude/`` appears, ``.mcp.json``
    is written, and the bundle the marker describes goes stale - and it
    does so silently, where the PowerShell recipe at least failed loudly,
    since generic now supplies its conventional directories when the flags
    are omitted.

    ``claude-code`` stays fixed: it refuses the directory flags, so naming
    either would be a recipe that exits 2.

    The last assertion is the point of the item: follow the recipe, and
    the target must still hold the one bundle it described.
    """
    home = tmp_path / "home"
    claude_target = tmp_path / "claude"
    claude_target.mkdir()
    install(claude_target, home=home)
    claude_recipe = recipe_of(marker_lines(claude_target / ".claude" / MARKER_NAME))
    assert claude_recipe.endswith(" pb-ai-code install --harness claude-code"), claude_recipe

    bare_target = tmp_path / "bare"
    bare_target.mkdir()
    install(bare_target, "--harness", "generic", "--skills-dir", ".agents/skills", home=home)
    bare_recipe = recipe_of(marker_lines(bare_target / ".agents" / MARKER_NAME))
    assert bare_recipe.endswith(" pb-ai-code install")

    target = tmp_path / "generic"
    target.mkdir()
    install(
        target,
        "--harness",
        "generic",
        "--skills-dir",
        ".agents/skills",
        "--commands-dir",
        ".agents/commands",
        home=home,
    )
    recipe = recipe_of(marker_lines(target / ".agents" / MARKER_NAME))
    assert recipe.endswith(" pb-ai-code install"), recipe

    # Now do what the marker says. `uvx --from <url> pb-ai-code` is this
    # interpreter running the package that is already here.
    command = shlex.split(recipe.lstrip("# "))
    assert command[:5] == ["uvx", "--from", command[2], "pb-ai-code", "install"], command
    before = sorted(path.name for path in target.iterdir())
    again = run_cli(*command[4:], "--target", str(target), env=kit_env(home))
    assert again.returncode == 0, again.stdout + again.stderr
    assert sorted(path.name for path in target.iterdir()) == before, (
        "following the update recipe installed a second, different layout"
    )
    assert before == [".agents", "AGENTS.md"]


def test_ledger60_a_directory_with_a_space_stays_pasteable() -> None:
    """Ledger 60: the recipe is meant to be copied and run, verbatim.

    ``--skills-dir`` is whatever the caller typed, and a Windows developer
    types directories with spaces in them. The last segment has to be
    ``skills``, but nothing constrains the ones above it: unquoted, this
    recipe would install into ``.agents/my`` - a third layout, in a third
    place. ``claude-code`` names no flags at all, because it is the
    explicit fixed-layout harness and it refuses both directory flags.
    """
    adapter = harness.build_generic(".agents/my kit/skills", ".agents/my kit/commands")

    flags = marker.install_flags(adapter)

    assert flags == (
        "--harness",
        "generic",
        "--skills-dir",
        '".agents/my kit/skills"',
        "--commands-dir",
        '".agents/my kit/commands"',
    )
    assert shlex.split(" ".join(flags))[3] == ".agents/my kit/skills"
    assert marker.install_flags(harness.CLAUDE_CODE) == ("--harness", "claude-code")
