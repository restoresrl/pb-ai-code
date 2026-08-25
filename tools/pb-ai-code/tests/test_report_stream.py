"""The report's stream: it must not die on its own text, or paint garbage.

Two failures the goldens in ``test_install_stdout.py`` cannot see, because
both depend on what the *stream* is and pytest's capture is neither a
console nor an ANSI code page.

**Encoding.** A redirected ``sys.stdout`` on Windows is opened with the
ANSI code page and a strict error handler. One character outside it - a
Japanese target path, a preserved MCP server key, an accented user name -
raised ``UnicodeEncodeError`` from the middle of the report. Reproduced on
the machine this port was verified on: ``install`` into a target named
with three CJK characters exited 1 with a traceback after printing two
lines, and the seeded-``.mcp.json`` case exited 1 *after* the skills were
copied and ``.mcp.json`` rewritten, leaving a fully populated target with
no marker - the state ledger 62 exists to forbid. ``Write-Host`` was lossy
but alive: redirected, it wrote ``???`` and exited 0.

**Colour.** ``Write-Host -ForegroundColor`` goes through the console API
and emits no escape bytes; the port emitted raw SGR escapes whenever
``isatty()`` said yes. A conhost console starts without
ENABLE_VIRTUAL_TERMINAL_PROCESSING, so those escapes were four visible
characters each. ``isatty()`` is therefore not the question - "will this
terminal render an escape" is.

The two encoding tests run the CLI as a **subprocess** with a redirected
stream and ``PYTHONIOENCODING=cp1252``. In process they prove nothing:
pytest's capture object encodes nothing. cp1252 is named rather than
inherited so the test is the same on a machine whose ANSI code page is
already UTF-8.

Every string in this file is ASCII, escapes included. A module about text
a code page cannot carry is the last one that should assume its own
source survives a round trip through somebody's editor.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from pb_ai_code import report as report_mod
from pb_ai_code.report import Line, Reporter

# --- support -----------------------------------------------------------------
# Duplicated from the sibling test modules on purpose, as they duplicate it
# from each other: three test packages in this repository are called `tests`,
# so a shared `_support` binds to whichever one pytest imported first.

MARKER = Path(".claude") / "_installed-from-pb-ai-code.txt"

#: Three characters no single-byte code page can encode.
CJK = "\u65e5\u672c\u8a9e"

#: What ``backslashreplace`` makes of them, and so what the report must now
#: say. Written out rather than derived from ``CJK``: deriving it would make
#: the test agree with whatever error handler the code picked, which is the
#: one thing it is here to hold still.
CJK_ESCAPED = "\\u65e5\\u672c\\u8a9e"

ESC = b"\x1b"


def install_bytes(target: Path, home: Path) -> subprocess.CompletedProcess[bytes]:
    """Run ``install`` with stdout on a pipe that cannot encode :data:`CJK`.

    ``capture_output`` without ``text`` keeps the bytes: the point of these
    tests is which bytes came out, and decoding them here would hide the
    very failure being pinned.
    """
    home.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.pop("PYTHONUTF8", None)
    env["PYTHONIOENCODING"] = "cp1252"
    env["PB_APPEON_INDEX_DB"] = str(home / "no-such-index.db")
    env["USERPROFILE"] = str(home)
    env["HOME"] = str(home)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
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
        env=env,
    )


def report_text(result: subprocess.CompletedProcess[bytes]) -> str:
    """The report as the redirected consumer sees it."""
    return result.stdout.decode("cp1252")


def diagnose(result: subprocess.CompletedProcess[bytes]) -> str:
    return (
        f"rc={result.returncode}\n"
        f"--- stdout ---\n{result.stdout.decode('cp1252', 'backslashreplace')}\n"
        f"--- stderr ---\n{result.stderr.decode('utf-8', 'backslashreplace')}"
    )


class LyingTty:
    """A stream that says it is a terminal. It is a file, or nothing at all.

    Stands in for the case the port got wrong: something that answers
    ``isatty()`` truthfully enough to pass the old check while having no
    console behind it.
    """

    def __init__(self, backing: Any = None) -> None:
        self._backing = backing
        self.written: list[str] = []

    def write(self, text: str) -> int:
        self.written.append(text)
        return len(text)

    def isatty(self) -> bool:
        return True

    def fileno(self) -> int:
        if self._backing is None:
            raise OSError("no file descriptor")
        return int(self._backing.fileno())

    @property
    def text(self) -> str:
        return "".join(self.written)


# --- Encoding ----------------------------------------------------------------


def test_a_target_path_the_console_cannot_encode_does_not_kill_the_report(
    tmp_path: Path,
) -> None:
    """Repro A: the crash landed in the header, three lines in.

    Before the fix: exit 1, ``UnicodeEncodeError`` on stderr, ``Source:``
    on stdout and nothing after it, no marker. The install had not started,
    so the target was at least clean - which is the *lucky* case.
    """
    target = tmp_path / f"{CJK}-target"
    target.mkdir()

    result = install_bytes(target, tmp_path / "home")

    assert result.returncode == 0, diagnose(result)
    assert (target / MARKER).is_file(), diagnose(result)

    text = report_text(result)
    assert f"{CJK_ESCAPED}-target" in text, diagnose(result)
    assert "Done." in text, diagnose(result)


def test_a_preserved_server_key_the_console_cannot_encode_does_not_kill_the_report(
    tmp_path: Path,
) -> None:
    """Repro B, the one ledger 62 is about.

    The offending text reaches stdout in the ``Installed mcp`` row, which
    is printed *after* the skills are copied and after ``.mcp.json`` has
    been rewritten. Before the fix this exited 1 with a fully populated
    target and no marker: a re-run could not tell it was already installed,
    and ``status`` reported nothing there.
    """
    target = tmp_path / "kept-server-target"
    target.mkdir()
    kept = f"{CJK}-server"
    (target / ".mcp.json").write_text(
        json.dumps({"mcpServers": {kept: {"command": "noop"}}}, ensure_ascii=False),
        encoding="utf-8",
    )

    result = install_bytes(target, tmp_path / "home")

    assert result.returncode == 0, diagnose(result)
    assert (target / MARKER).is_file(), diagnose(result)
    assert f"kept: {CJK_ESCAPED}-server" in report_text(result), diagnose(result)

    document = json.loads((target / ".mcp.json").read_text(encoding="utf-8-sig"))
    assert kept in document["mcpServers"], "the unencodable server was not preserved"


def test_a_redirected_report_carries_no_escape_bytes(tmp_path: Path) -> None:
    """The other half of the contract: lossy is allowed, escape bytes are not."""
    target = tmp_path / "plain-target"
    target.mkdir()

    result = install_bytes(target, tmp_path / "home")

    assert result.returncode == 0, diagnose(result)
    assert ESC not in result.stdout, diagnose(result)


def test_make_lossy_ignores_a_stream_that_cannot_be_reconfigured() -> None:
    """``io.StringIO`` has no ``reconfigure``; that is not an error."""
    stream = io.StringIO()

    report_mod.make_lossy(stream)
    Reporter(stream, color=False).line(Line("still works"))

    assert stream.getvalue() == "still works\n"


# --- Colour ------------------------------------------------------------------


@pytest.mark.parametrize("value", ["1", "0", "please"])
def test_no_color_beats_a_console_that_would_have_rendered(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """``NO_COLOR`` wins on *presence*, whatever it says - no-color.org.

    The console probe is stubbed out, so this test is about one decision
    and no other. Without the stub it passed with the ``NO_COLOR`` branch
    deleted: on Windows the probe rejects a :class:`LyingTty` on its own,
    and the assertion held for the wrong reason.
    """
    monkeypatch.setattr(report_mod, "ansi_is_understood", lambda stream: True)

    monkeypatch.delenv("NO_COLOR", raising=False)
    would = LyingTty()
    Reporter(would).line(Line("Done.", "green"))
    assert would.text == "\x1b[32mDone.\x1b[0m\n", "the stubbed console should colour"

    monkeypatch.setenv("NO_COLOR", value)
    silenced = LyingTty()
    Reporter(silenced).line(Line("Done.", "green"))
    assert silenced.text == "Done.\n"


@pytest.mark.skipif(sys.platform != "win32", reason="the console check is a Windows one")
def test_no_escapes_when_the_handle_is_not_a_console(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fix in one assertion: a TTY claim is not a promise to render.

    Before the fix ``isatty()`` alone turned colour on, so this wrote
    ``\\x1b[32mDone.\\x1b[0m`` - which is what a cmd.exe user saw, letter
    for letter. A file handle fails ``GetConsoleMode`` exactly as a dead
    or non-console handle does, and a conhost that will not confirm
    ENABLE_VIRTUAL_TERMINAL_PROCESSING on read-back is refused the same
    way.
    """
    monkeypatch.delenv("NO_COLOR", raising=False)
    with (tmp_path / "sink.txt").open("w", encoding="utf-8") as backing:
        stream = LyingTty(backing)
        Reporter(stream).line(Line("Done.", "green"))

    assert stream.text == "Done.\n"


def test_an_explicit_color_argument_bypasses_detection() -> None:
    """``color=`` is the caller's business - the goldens rely on it."""
    stream = LyingTty()

    Reporter(stream, color=True).line(Line("Done.", "green"))

    assert stream.text == "\x1b[32mDone.\x1b[0m\n"


@pytest.mark.skipif(sys.platform != "win32", reason="the console check is a Windows one")
def test_a_real_console_has_vt_turned_on_and_says_so() -> None:
    """The half of the decision no CI runner can reach: a live console.

    Everything else here pins the refusal. This pins the acceptance, and
    it is the reason colour was kept rather than dropped: on the console
    that renders the port's escapes as literal characters, one
    ``SetConsoleMode`` makes them colour. Skipped where there is no
    console to ask - a GitHub runner has none - and where the flag does
    not exist: ENABLE_VIRTUAL_TERMINAL_PROCESSING arrived in Windows 10
    build 10586.
    """
    if sys.getwindowsversion().build < 10586:
        pytest.skip("no ENABLE_VIRTUAL_TERMINAL_PROCESSING before build 10586")
    try:
        console = open("CONOUT$", "w", encoding="utf-8")  # noqa: SIM115 - closed below
    except OSError:
        pytest.skip("no console attached to this process")

    with console:
        assert report_mod.ansi_is_understood(console) is True
        assert console_mode(console) & 0x0004, "the flag was reported set but is not"


def console_mode(stream: Any) -> int:
    """Read the console mode without going through the code under test."""
    import ctypes
    import msvcrt

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    mode = ctypes.c_uint32()
    handle = ctypes.c_void_p(msvcrt.get_osfhandle(stream.fileno()))
    assert kernel32.GetConsoleMode(handle, ctypes.byref(mode)), "not a console handle"
    return int(mode.value)
