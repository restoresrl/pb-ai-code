"""Check published releases and update the persistent tool or a project.

The GitHub Releases API is the authority for ``pb-ai-code update``. Tags are
not enough: a repository can have experimental or maintenance tags that are
not releases a user should receive automatically.

A successful check is cached for 24 hours in the current user's local data
folder. The cache makes a session-start check cheap and avoids turning GitHub
availability into a prerequisite for ordinary PowerBuilder work.
"""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import VCS_URL, PbAiCodeError

__all__ = [
    "CACHE_SECONDS",
    "CheckResult",
    "Release",
    "UpdateCheckError",
    "check",
    "global_install_command",
    "project_install_command",
    "run",
    "schedule_after_exit",
]

CACHE_SECONDS = 24 * 60 * 60
_API_URL = "https://api.github.com/repos/restoresrl/pb-ai-code/releases/latest"
_USER_AGENT = "pb-ai-code update check"
_TAG_RE = re.compile(r"^v(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)$")
_VERSION_RE = re.compile(r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)")


class UpdateCheckError(PbAiCodeError):
    """The published release could not be determined."""


@dataclass(frozen=True)
class Release:
    """One stable GitHub release, reduced to the fields the CLI needs."""

    tag: str
    version: str
    number: tuple[int, int, int]
    url: str | None


@dataclass(frozen=True)
class CheckResult:
    """The installed version compared with the latest stable release."""

    running_version: str
    latest: Release
    update_available: bool
    from_cache: bool


def _cache_path() -> Path:
    """A machine-local cache, never a project file."""
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "pb-ai-code" / "update-check.json"
    profile = os.environ.get("USERPROFILE")
    if profile:
        return Path(profile) / "AppData" / "Local" / "pb-ai-code" / "update-check.json"
    return Path.home() / ".cache" / "pb-ai-code" / "update-check.json"


def _release_from_payload(payload: object) -> Release | None:
    if not isinstance(payload, dict):
        return None
    tag = payload.get("tag_name")
    if not isinstance(tag, str):
        return None
    match = _TAG_RE.fullmatch(tag)
    if match is None:
        return None
    url = payload.get("html_url")
    return Release(
        tag=tag,
        version=tag[1:],
        number=tuple(int(match.group(name)) for name in ("major", "minor", "patch")),
        url=url if isinstance(url, str) else None,
    )


def _read_cache(now: float) -> Release | None:
    try:
        raw = _cache_path().read_text(encoding="utf-8")
        payload = json.loads(raw)
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    checked_at = payload.get("checked_at")
    if not isinstance(checked_at, (int, float)) or now - checked_at > CACHE_SECONDS:
        return None
    return _release_from_payload(payload.get("release"))


def _write_cache(now: float, payload: dict[str, Any]) -> None:
    path = _cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"checked_at": now, "release": payload}, separators=(",", ":")),
            encoding="utf-8",
        )
    except OSError:
        # A read-only profile must not stop an update check; the next check
        # simply reaches GitHub again.
        return


def _fetch_release() -> tuple[Release, dict[str, Any]]:
    request = Request(
        _API_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": _USER_AGENT},
    )
    try:
        with urlopen(request, timeout=5) as response:
            payload: object = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            raise UpdateCheckError("no published pb-ai-code release was found on GitHub") from exc
        raise UpdateCheckError(
            f"GitHub returned HTTP {exc.code} while checking for updates"
        ) from exc
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise UpdateCheckError(f"cannot check GitHub for updates: {exc}") from exc
    if not isinstance(payload, dict):
        raise UpdateCheckError("GitHub returned an invalid release response")
    release = _release_from_payload(payload)
    if release is None:
        raise UpdateCheckError("GitHub's latest pb-ai-code release has an invalid tag")
    return release, payload


def _version_number(version: str) -> tuple[int, int, int] | None:
    match = _VERSION_RE.match(version)
    if match is None:
        return None
    return tuple(int(match.group(name)) for name in ("major", "minor", "patch"))


def check(running_version: str, *, refresh: bool = False) -> CheckResult:
    """Return the newest published stable release, using the cache when safe."""
    now = time.time()
    cached = None if refresh else _read_cache(now)
    if cached is None:
        latest, payload = _fetch_release()
        _write_cache(now, payload)
        from_cache = False
    else:
        latest = cached
        from_cache = True
    current = _version_number(running_version)
    return CheckResult(
        running_version=running_version,
        latest=latest,
        update_available=current is None or current < latest.number,
        from_cache=from_cache,
    )


def global_install_command(release: Release) -> list[str]:
    """The persistent-tool install pinned to the selected GitHub release."""
    return ["uv", "tool", "install", "--force", f"{VCS_URL}@{release.tag}"]


def project_install_command(release: Release, install_args: list[str]) -> list[str]:
    """Run the selected release directly, so its new payload reaches the project."""
    return ["uvx", "--from", f"{VCS_URL}@{release.tag}", "pb-ai-code", "install", *install_args]


def run(command: list[str]) -> int:
    """Run an update child process without hiding its diagnostics from the user."""
    try:
        return subprocess.run(command, check=False).returncode
    except OSError as exc:
        raise UpdateCheckError(f"cannot run {command[0]}: {exc}") from exc


def _powershell_literal(value: str) -> str:
    """A single-quoted PowerShell string, including paths with apostrophes."""
    return "'" + value.replace("'", "''") + "'"


def _powershell_call(command: list[str]) -> str:
    """Render one external command with an array of literal arguments."""
    executable, *args = command
    values = ", ".join(_powershell_literal(arg) for arg in args)
    return f"& {_powershell_literal(executable)} @({values})"


def schedule_after_exit(global_command: list[str], project_command: list[str] | None) -> None:
    """Run the update after the Windows console launcher releases its files.

    ``uv tool install --force`` replaces the persistent tool's ``Scripts``
    directory. Windows keeps the currently executing ``pb-ai-code.exe`` open,
    so running uv as a child fails with access denied. A PowerShell child waits
    for this process to leave, then runs the global update and, only after it
    succeeds, the pinned project install. It inherits the terminal so uv's
    output remains visible.
    """
    if os.name != "nt":
        raise UpdateCheckError("deferred updates are only needed on Windows")
    commands = [_powershell_call(global_command)]
    if project_command is not None:
        commands += [
            "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }",
            _powershell_call(project_command),
        ]
    commands.append("exit $LASTEXITCODE")
    script = "\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            f"Wait-Process -Id {os.getpid()}",
            "Start-Sleep -Milliseconds 750",
            *commands,
        ]
    )
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-EncodedCommand", encoded],
        )
    except OSError as exc:
        raise UpdateCheckError(f"cannot schedule the Windows update: {exc}") from exc
