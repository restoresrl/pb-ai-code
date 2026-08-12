"""The command surface: what each invocation exits with, and what it says.

The taxonomy is the deviation this port is judged on. The PowerShell script
exited 1 for everything that was not success - including a parameter it could
not bind - and printed a multi-line coloured banner at anyone who mistyped a
path. Here 0 covers success *including every warning path*, 2 is a usage error
with one line on stderr and no traceback, 3 is `status` finding no marker, and
1 is left for the unexpected, where a traceback is a bug report rather than a
diagnostic.

Four refusals in the table are new, and all four were silent before:
`--skills-dir` accepted an absolute path that `Join-Path` turned into
`C:\\tgt\\D:\\abs\\skills` (Python's join would have *implemented* it and
installed outside the target); a `--commands-dir` that is not a sibling of
`--skills-dir` produced two dead links that nothing validated; a `--skills-dir`
not named `skills` produced eleven more, in the knowledge base, that the
sibling rule never looked at; and a whitespace-padded component made the script
create two directories and fill the one nothing else on the machine can type.

Everything here runs `python -m pb_ai_code` in a subprocess: a test that does
not cross the boundary does not prove the boundary works, and exit codes only
exist on the other side of it.
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
from pb_ai_code import harness, kit, marker, provenance, report

CLAUDE_MARKER = (".claude", "_installed-from-pb-ai-code.txt")


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pb_ai_code", *args],
        capture_output=True,
        text=True,
        cwd=None if cwd is None else str(cwd),
    )


def _install(target: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    result = _run("install", "--target", str(target), *extra)
    assert result.returncode == 0, f"install failed:\n{result.stdout}\n{result.stderr}"
    return result


def _fields(target: Path, *rel: str) -> marker.MarkerFields:
    path = target.joinpath(*(rel or CLAUDE_MARKER))
    return marker.parse(path.read_text(encoding="utf-8-sig"))


# --- Usage errors (ledger 8, 10, 11, 14, 30, 74) -----------------------------


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        pytest.param(
            ["--harness", "generic"],
            report.err_generic_requires_skills_dir(),
            id="generic-without-skills-dir",
        ),
        pytest.param(
            ["--harness", "generic", "--skills-dir", "C:\\tmp\\x"],
            report.err_dir_must_be_target_relative("--skills-dir", "C:\\tmp\\x"),
            id="drive-qualified-skills-dir",
        ),
        pytest.param(
            ["--harness", "generic", "--skills-dir", "\\\\server\\share"],
            report.err_dir_must_be_target_relative("--skills-dir", "\\\\server\\share"),
            id="unc-skills-dir",
        ),
        pytest.param(
            ["--harness", "generic", "--skills-dir", "/rooted/skills"],
            report.err_dir_must_be_target_relative("--skills-dir", "/rooted/skills"),
            id="rooted-skills-dir",
        ),
        pytest.param(
            ["--harness", "generic", "--skills-dir", "../../x"],
            report.err_dir_escapes_target("--skills-dir", "../../x"),
            id="escaping-skills-dir",
        ),
        pytest.param(
            ["--harness", "generic", "--skills-dir", "."],
            report.err_dir_must_name_a_directory("--skills-dir", "."),
            id="skills-dir-is-the-target",
        ),
        pytest.param(
            ["--harness", "generic", "--skills-dir", "agents/skills", "--commands-dir", "prompts"],
            report.err_commands_dir_not_sibling("prompts", "agents/skills"),
            id="commands-dir-is-not-a-sibling",
        ),
        pytest.param(
            [
                "--harness",
                "generic",
                "--skills-dir",
                ".agent/kb",
                "--commands-dir",
                ".agent/commands",
            ],
            harness.err_skills_dir_last_segment(".agent/kb"),
            id="skills-dir-not-named-skills",
        ),
        pytest.param(
            ["--harness", "generic", "--skills-dir", "sk "],
            harness.err_dir_component_has_whitespace("--skills-dir", "sk "),
            id="skills-dir-component-with-a-trailing-space",
        ),
        pytest.param(
            ["--harness", "generic", "--skills-dir", ".agent/ /skills"],
            harness.err_dir_component_has_whitespace("--skills-dir", ".agent/ /skills"),
            id="skills-dir-with-a-blank-component",
        ),
        pytest.param(
            ["--harness", "generic", "--skills-dir", "skills", "--commands-dir", " commands"],
            harness.err_dir_component_has_whitespace("--commands-dir", " commands"),
            id="commands-dir-component-with-a-leading-space",
        ),
        pytest.param(
            ["--skills-dir", ".agent/skills"],
            report.err_dir_not_accepted("--skills-dir", "claude-code"),
            id="skills-dir-with-a-fixed-layout",
        ),
        pytest.param(
            ["--commands-dir", ".agent/commands"],
            report.err_dir_not_accepted("--commands-dir", "claude-code"),
            id="commands-dir-with-a-fixed-layout",
        ),
    ],
)
def test_ledger10_11_14_30_74_a_usage_error_is_one_line_and_exit_2(
    tmp_path: Path, extra: list[str], message: str
) -> None:
    """Ledger 10, 11, 14, 30, 74: exit 2, one line, no traceback, no output.

    Nothing is printed before every decision that can fail has been made, so
    a refused invocation leaves stdout empty and the target untouched - an
    agent reading the report cannot mistake a half-printed plan for a run.
    The empty-target assertion is ledger 14 itself: `--commands-dir "  "`
    used to copy seven skill trees and *then* die in `shutil.copy2`, leaving
    a target with skills and no docs, no settings and no marker.
    """
    result = _run("install", "--target", str(tmp_path), *extra)

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == f"{report.ERROR_PREFIX}{message}\n"
    assert "Traceback" not in result.stderr
    assert list(tmp_path.iterdir()) == []


def test_ledger8_a_target_that_is_not_a_directory_exits_2_and_is_never_created(
    tmp_path: Path,
) -> None:
    """Ledger 8: the target must already exist. The installer never makes one.

    A mistyped path that silently becomes a new directory full of skills is
    worse than an error: nothing reads it and nothing says so.
    """
    missing = tmp_path / "no-such-project"
    result = _run("install", "--target", str(missing))
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == (
        f"{report.ERROR_PREFIX}{report.err_target_not_a_directory(str(missing))}\n"
    )
    assert not missing.exists()

    a_file = tmp_path / "not-a-directory.txt"
    a_file.write_text("", encoding="utf-8")
    on_a_file = _run("install", "--target", str(a_file))
    assert on_a_file.returncode == 2
    assert on_a_file.stdout == ""


def test_ledger6_an_unknown_harness_exits_2_naming_the_legal_set(tmp_path: Path) -> None:
    """Ledger 6: argparse owns the choice, and it names what it would accept."""
    result = _run("install", "--target", str(tmp_path), "--harness", "codex")
    assert result.returncode == 2
    assert result.stdout == ""
    assert "invalid choice: 'codex'" in result.stderr
    for name in harness.HARNESS_IDS:
        assert name in result.stderr
    assert "Traceback" not in result.stderr


def test_a_verb_is_required() -> None:
    """No subcommand is a usage error, not a default install into the cwd."""
    result = _run()
    assert result.returncode == 2
    assert result.stdout == ""


def test_ledger1_74_a_payload_that_cannot_be_found_is_exit_1_and_still_one_line(
    tmp_path: Path,
) -> None:
    """Ledger 1, 74: code 1 is the last row of the table, and it is not a crash.

    A distribution whose kit did not travel with it is the failure the whole
    `force-include` table exists to prevent - and it is an *anticipated* one,
    so it prints one line and keeps its traceback to itself. The code is
    copied somewhere with no payload above it to produce exactly that.
    """
    src = tmp_path / "src"
    shutil.copytree(
        Path(pb_ai_code.__file__).parent,
        src / "pb_ai_code",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    target = tmp_path / "project"
    target.mkdir()

    result = subprocess.run(
        [sys.executable, "-m", "pb_ai_code", "install", "--target", str(target)],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(src), "PYTHONDONTWRITEBYTECODE": "1"},
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert "Traceback" not in result.stderr
    assert result.stderr.startswith(f"{report.ERROR_PREFIX}cannot find the pb-ai-code payload")
    assert list(target.iterdir()) == []


# --- The accepted surface (ledger 6, 7, 9, 12) -------------------------------


def test_ledger6_the_harness_name_is_case_insensitive_and_normalised(tmp_path: Path) -> None:
    """Ledger 6: `--harness CLAUDE-CODE` works; the marker records `claude-code`.

    The marker is read months later by someone deciding what a target has.
    Recording the user's spelling rather than the resolved one makes that a
    guess.
    """
    result = _install(tmp_path, "--harness", "CLAUDE-CODE")
    assert "Harness: claude-code" in result.stdout
    assert _fields(tmp_path).harness == "claude-code"


def test_ledger7_the_target_defaults_to_the_current_directory(tmp_path: Path) -> None:
    """Ledger 7: this runs from *inside* the consumer repo.

    The script's "no target means install into the source" concept does not
    survive the port: there is no source on the machine to install into.
    """
    result = _run("install", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / ".claude" / "skills").is_dir()
    assert (tmp_path / ".claude" / "_installed-from-pb-ai-code.txt").is_file()


def test_ledger9_claude_code_writes_exactly_its_own_layout(tmp_path: Path) -> None:
    """Ledger 9: five fixed destinations plus the vendored knowledge base.

    Nothing else at the target root - the bundle is one directory a consumer
    can gitignore in one line, plus the MCP config that has to sit at the root
    because that is where the client looks for it.
    """
    _install(tmp_path)
    # AGENTS.md is the third path at the root, and the only one written
    # rather than copied: the project's own instruction file, created when
    # absent and never rewritten afterwards.
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        ".claude",
        ".mcp.json",
        "AGENTS.md",
    ]
    assert sorted(path.name for path in (tmp_path / ".claude").iterdir()) == [
        "_installed-from-pb-ai-code.txt",
        "commands",
        "pb-ai-code-docs",
        "settings.json",
        "skills",
    ]


def test_ledger12_a_harness_without_a_commands_directory_says_so(tmp_path: Path) -> None:
    """Ledger 12: a notice naming the count, and never an error.

    Every flow is reachable as a skill of the same name, so the commands are
    a convenience; dying over them would fail an install that is complete.
    """
    result = _install(tmp_path, "--harness", "generic", "--skills-dir", ".agent/skills")
    expected = len(kit.load_kit().iter_command_files())
    assert (
        f"Note: no commands directory for this harness; skipping {expected} command file(s)."
        in result.stdout
    )
    assert report.COMMANDS_FALLBACK_LINE in result.stdout
    assert not (tmp_path / ".agent" / "commands").exists()


def test_ledger12_14_a_blank_commands_dir_is_no_commands_directory(tmp_path: Path) -> None:
    """Ledger 12 and 14: `--commands-dir "  "` is the flag not given, and it installs.

    ps1:348 gates the commands destination on `IsNullOrWhiteSpace`, so a
    blank-but-not-empty value has always meant "no commands directory": the
    notice prints and the run completes. Verified against the script itself
    - `-CommandsDir "  "` exits 0 and leaves `skills/` and
    `pb-ai-code-docs/` behind.

    The port instead built a plan whose command destination was a directory
    named `  `, copied every skill into place and died in `shutil.copy2`
    with a traceback, exit 1, and a target holding skills and nothing else.
    A root-level skills directory is the shape that reaches the copy step,
    because a nested one dies earlier in the sibling check with a message
    reading `   is not a sibling of .agent/skills`.
    """
    result = _install(
        tmp_path, "--harness", "generic", "--skills-dir", "skills", "--commands-dir", "  "
    )

    expected = len(kit.load_kit().iter_command_files())
    assert (
        f"Note: no commands directory for this harness; skipping {expected} command file(s)."
        in result.stdout
    )
    assert report.COMMANDS_FALLBACK_LINE in result.stdout
    assert "Traceback" not in result.stderr
    # The whole install, not the half of it that runs before the crash.
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "AGENTS.md",
        "_installed-from-pb-ai-code.txt",
        "pb-ai-code-docs",
        "skills",
    ]


def test_a_blank_directory_flag_is_the_flag_not_given_for_every_harness(tmp_path: Path) -> None:
    """One rule, decided once, before any harness looks at the value.

    `claude-code` refuses `--skills-dir` because its layout is fixed - but a
    blank value names no layout, and a wrapper script that always passes
    `--skills-dir "$SKILLS"` with `SKILLS` unset is the case the script's
    own `IsNullOrWhiteSpace` idiom exists for. So blank means absent here
    too, and the fixed layout is written.
    """
    result = _install(tmp_path, "--skills-dir", "", "--commands-dir", "   ")
    assert "Harness: claude-code" in result.stdout
    assert (tmp_path / ".claude" / "commands" / "pb-review.md").is_file()
    assert _fields(tmp_path).harness == "claude-code"


def test_the_version_flag_prints_the_running_distribution() -> None:
    """`--version` is what `status` compares a marker against."""
    result = _run("--version")
    assert result.returncode == 0
    assert result.stdout.strip() == provenance.distribution_version()
    assert result.stderr == ""


# --- status (ledger 77) ------------------------------------------------------


def test_ledger77_status_reads_back_what_install_wrote(tmp_path: Path) -> None:
    """Ledger 77: a verb the script never had, and the marker is its whole source.

    No network, no git, no guessing: everything printed comes out of the file
    the install left behind.
    """
    _install(tmp_path)
    result = _run("status", "--target", str(tmp_path))

    assert result.returncode == 0
    assert result.stderr == ""

    fields = _fields(tmp_path)
    lines = result.stdout.splitlines()
    assert lines[0] == f"pb-ai-code {provenance.distribution_version()} (running)"
    assert f"Target:    {tmp_path.resolve()}" in lines
    assert f"Marker:    {Path(*CLAUDE_MARKER)}" in lines
    assert f"Installed: {fields.installed_at}" in lines
    assert f"Version:   {fields.version}" in lines
    assert f"Source:    {fields.source}" in lines
    assert "Harness:   claude-code" in lines
    assert f"MCP:       {fields.mcp}" in lines
    assert f"Appeon:    {fields.appeon}" in lines
    assert f"Contents:  {len(fields.contents)} entries" in lines
    assert lines[-1] == "Up to date: yes"


def test_ledger77_status_json_is_the_only_thing_on_stdout(tmp_path: Path) -> None:
    """Ledger 77: `--json` restores the house convention the install deviates from.

    An agent branches on `installed` without parsing prose, which is the
    whole reason the verb exists.
    """
    _install(tmp_path)
    result = _run("status", "--target", str(tmp_path), "--json")

    assert result.returncode == 0
    assert result.stderr == ""
    payload = json.loads(result.stdout)

    fields = _fields(tmp_path)
    running = provenance.distribution_version()
    assert payload["installed"] is True
    assert payload["target"] == str(tmp_path.resolve())
    assert Path(payload["marker_path"]) == tmp_path.resolve().joinpath(*CLAUDE_MARKER)
    assert payload["installed_at"] == fields.installed_at
    assert payload["version"] == fields.version == running
    assert payload["source"] == fields.source
    assert payload["sha"] == fields.sha
    assert payload["branch"] == fields.branch
    assert payload["dirty"] == fields.dirty
    assert payload["harness"] == "claude-code"
    assert payload["mcp"] == fields.mcp
    assert payload["appeon"] == fields.appeon
    assert payload["contents"] == list(fields.contents)
    assert payload["running_version"] == running
    assert payload["up_to_date"] is True


def test_ledger54_77_status_finds_the_generic_marker_at_the_bundle_root(tmp_path: Path) -> None:
    """Ledger 54, 77: the marker moved out of the skills directory, and is found.

    A stray `.txt` where a skill loader enumerates skills is a hazard, and
    both documents that tell a reader where to look already promise the
    bundle root.
    """
    _install(tmp_path, "--harness", "generic", "--skills-dir", ".agent/skills")
    assert (tmp_path / ".agent" / "_installed-from-pb-ai-code.txt").is_file()
    assert not (tmp_path / ".agent" / "skills" / "_installed-from-pb-ai-code.txt").exists()

    result = _run("status", "--target", str(tmp_path))
    assert result.returncode == 0
    assert f"Marker:    {Path('.agent') / '_installed-from-pb-ai-code.txt'}" in result.stdout
    assert "Harness:   generic" in result.stdout


@pytest.mark.parametrize(
    "extra", [pytest.param([], id="text"), pytest.param(["--json"], id="json")]
)
def test_ledger77_status_exits_3_when_nothing_is_installed(
    tmp_path: Path, extra: list[str]
) -> None:
    """Ledger 77: a documented third code, so "installed?" needs no parsing.

    The error path is the same shape in both forms: one line on stderr and
    nothing on stdout. A `--json` caller that got half a document on an
    uninstalled target would have to parse to find that out.
    """
    result = _run("status", "--target", str(tmp_path), *extra)
    assert result.returncode == 3
    assert result.stdout == ""
    assert result.stderr == (
        f"{report.ERROR_PREFIX}{report.err_no_marker(str(tmp_path.resolve()))}\n"
    )
    assert "Traceback" not in result.stderr


def test_ledger77_status_on_a_missing_target_is_a_usage_error(tmp_path: Path) -> None:
    """Ledger 8, 77: the same refusal as `install`, and the same code."""
    missing = tmp_path / "no-such-project"
    result = _run("status", "--target", str(missing))
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == (
        f"{report.ERROR_PREFIX}{report.err_target_not_a_directory(str(missing))}\n"
    )
