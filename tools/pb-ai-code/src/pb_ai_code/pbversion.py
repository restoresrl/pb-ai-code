"""Which PowerBuilder the project is developed with — asked, never guessed.

Every ORCA call needs it: ``pb_session_open`` takes it explicitly and there is
no auto-pick, so a session opened against the wrong install reads and writes a
library under a runtime nobody chose. On a machine with 19, 22 and 25 side by
side — the normal state in this audience — that is one wrong answer away.

**It cannot be deduced from the sources, and this is the part that looks
solvable and is not.** An object carries the release it was last saved under,
not the release of the IDE now working on it: PowerBuilder migrates what it
touches and leaves the rest, so a project built with 2022 can hold DataWindows
still marked release 6. Reading ``appruntimeversion`` off one exported object
gives an answer that is plausible, specific, and sometimes off by four major
versions. Asking gives an answer that is right.

So the flag is the interface, the prompt is the courtesy, and neither is
allowed to invent a value. Where the answer is written down is
:mod:`pb_ai_code.agentsmd` — the project's own file, because a migration done
later in the IDE or with PowerGen changes this fact and nothing here will
notice.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass

#: `19.2`, `22.0`, `25.0` — what `pb_session_open` and `pb-orca-mcp
#: --pb-version` take. A bare major is accepted and normalised, because
#: "22" is what a person says.
_SHAPE = re.compile(r"^(?P<major>\d{2})(?:\.(?P<minor>\d{1,2}))?$")

#: Majors that exist. Not a guess about the future: an unknown major is
#: accepted with a warning rather than refused, because this file being
#: out of date must not stop an install.
KNOWN_MAJORS = frozenset({"17", "19", "21", "22", "25"})

UNKNOWN = "not stated"


@dataclass(frozen=True)
class PbVersion:
    """A normalised answer, plus whether it is one we recognise."""

    value: str
    recognised: bool

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class InvalidPbVersion(ValueError):
    """The text does not look like a PowerBuilder version at all."""


def parse(raw: str) -> PbVersion:
    """``22`` and ``22.0`` both give ``22.0``; ``PB 22`` and ``2022`` do not.

    Deliberately strict about shape and lenient about which major: the
    shape is what every downstream tool consumes, while the list of
    releases grows without this file being edited.
    """
    text = raw.strip()
    match = _SHAPE.match(text)
    if match is None:
        raise InvalidPbVersion(
            f"{raw!r} is not a PowerBuilder version. Give the IDE's version as "
            f"<major>.<minor> — 22.0, 19.2, 25.0 — or just the major, 22."
        )
    major = match.group("major")
    minor = match.group("minor") or "0"
    return PbVersion(value=f"{major}.{minor}", recognised=major in KNOWN_MAJORS)


def ask(default: str | None = None) -> PbVersion | None:
    """Ask the person running the installer. ``None`` when there is nobody.

    Interactive only when stdin *and* stdout are terminals: an agent driving
    this through ``uvx`` has neither, and a prompt written into a pipe is a
    hang with no explanation. In that case the caller records
    :data:`UNKNOWN` and prints how to state it, which is the honest outcome
    — an installer that invented a version would be worse than one that
    admits it does not know.
    """
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return None

    suffix = f" [{default}]" if default else ""
    # The prompt goes to stderr on purpose: stdout carries the install
    # report, which an agent parses, and an interactive question is not
    # part of that report.
    print(
        "\nWhich PowerBuilder version is this project developed with?\n"
        "  It cannot be read from the sources: objects keep the release they\n"
        "  were last saved under, so a 2022 project can hold release 6\n"
        "  DataWindows. Give the IDE's version.",
        file=sys.stderr,
    )
    try:
        answer = input(f"  Version{suffix} (blank to skip): ").strip()
    except (EOFError, KeyboardInterrupt):
        print(file=sys.stderr)
        return None
    if not answer:
        return parse(default) if default else None
    try:
        return parse(answer)
    except InvalidPbVersion as exc:
        print(f"  {exc}", file=sys.stderr)
        return ask(default)
