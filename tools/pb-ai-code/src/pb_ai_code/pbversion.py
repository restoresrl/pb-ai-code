"""Canonical PowerBuilder release slugs and their derived ORCA versions.

A project records one value only: the Appeon documentation slug, such as
``pb2022r3``. That is precise enough to select documentation and maps
unambiguously to the version token ORCA accepts (``22.0``). A bare ORCA token
is deliberately not accepted: ``22.0`` cannot distinguish 2022, 2022 R2, and
2022 R3.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class PbVersion:
    """One exact PB release and the ORCA token derived from it."""

    value: str
    label: str
    orca_version: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class InvalidPbVersion(ValueError):
    """The value is not a published Appeon PowerBuilder release slug."""


_RELEASES: tuple[PbVersion, ...] = (
    PbVersion("pb2017", "PowerBuilder 2017", "17.0"),
    PbVersion("pb2017r2", "PowerBuilder 2017 R2", "17.0"),
    PbVersion("pb2017r3", "PowerBuilder 2017 R3", "17.0"),
    PbVersion("pb2019", "PowerBuilder 2019", "19.0"),
    PbVersion("pb2019r2", "PowerBuilder 2019 R2", "19.0"),
    PbVersion("pb2019r3", "PowerBuilder 2019 R3", "19.0"),
    PbVersion("pb2021", "PowerBuilder 2021", "21.0"),
    PbVersion("pb2022", "PowerBuilder 2022", "22.0"),
    PbVersion("pb2022r2", "PowerBuilder 2022 R2", "22.0"),
    PbVersion("pb2022r3", "PowerBuilder 2022 R3", "22.0"),
    PbVersion("pb2025", "PowerBuilder 2025", "25.0"),
    PbVersion("pb2025r2", "PowerBuilder 2025 R2", "25.0"),
)
_BY_SLUG = {release.value: release for release in _RELEASES}
_BY_BUILD_FLAG = {
    "2017": "pb2017",
    "2017 r2": "pb2017r2",
    "2017 r3": "pb2017r3",
    "2019": "pb2019",
    "2019 r2": "pb2019r2",
    "2019 r3": "pb2019r3",
    "2021": "pb2021",
    "2022": "pb2022",
    "2022 r2": "pb2022r2",
    "2022 r3": "pb2022r3",
    "2025": "pb2025",
    "2025 r2": "pb2025r2",
}

UNKNOWN = "not stated"


def all_releases() -> tuple[PbVersion, ...]:
    """Every documented release, in chronological order."""
    return _RELEASES


def parse(raw: str) -> PbVersion:
    """Resolve an exact Appeon slug; numeric ORCA versions are ambiguous."""
    value = raw.strip().lower()
    found = _BY_SLUG.get(value)
    if found is not None:
        return found
    raise InvalidPbVersion(
        f"{raw!r} is not a PowerBuilder release slug. Use an exact Appeon slug such as "
        "pb2022r3; 22.0 is ambiguous between PB 2022, 2022 R2, and 2022 R3."
    )


def from_build_flag(build_flag: str) -> PbVersion | None:
    """Map an Appeon Registry ``BuildFlag`` such as ``2022 R3`` to a slug."""
    slug = _BY_BUILD_FLAG.get(" ".join(build_flag.lower().split()))
    return _BY_SLUG.get(slug) if slug is not None else None


def discover_installed() -> tuple[PbVersion, ...]:
    """Read Appeon's installation records and return exact known releases.

    This reads only the product metadata used to offer documentation choices;
    it does not open ORCA or inspect a library. The ORCA server remains the
    authority for whether a selected installation can open a session.
    """
    if sys.platform != "win32":
        return ()
    try:
        import winreg

        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Appeon\AutoCompiler")
    except OSError:
        return ()
    found: list[PbVersion] = []
    try:
        index = 0
        while True:
            try:
                name = winreg.EnumKey(key, index)
            except OSError:
                break
            index += 1
            try:
                with winreg.OpenKey(key, name) as child:
                    build_flag, _ = winreg.QueryValueEx(child, "BuildFlag")
            except OSError:
                continue
            if not isinstance(build_flag, str):
                continue
            release = from_build_flag(build_flag)
            if release is not None and release not in found:
                found.append(release)
    finally:
        winreg.CloseKey(key)
    return tuple(found)


def ask(default: str | None = None) -> PbVersion | None:
    """Ask for an exact release slug when the installer is interactive."""
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return None
    choices = discover_installed()
    print("\nWhich exact PowerBuilder release maintains this project?", file=sys.stderr)
    if choices:
        for index, release in enumerate(choices, start=1):
            print(f"  {index}. {release.label} ({release.value})", file=sys.stderr)
    suffix = f" [{default}]" if default else ""
    try:
        answer = input(f"  Release slug{suffix} (blank to skip): ").strip()
    except (EOFError, KeyboardInterrupt):
        print(file=sys.stderr)
        return None
    if not answer:
        return parse(default) if default else None
    if answer.isdigit() and choices and 1 <= int(answer) <= len(choices):
        return choices[int(answer) - 1]
    try:
        return parse(answer)
    except InvalidPbVersion as exc:
        print(f"  {exc}", file=sys.stderr)
        return ask(default)
