"""Where this install came from: version, identity, dirty flag.

The PowerShell script made three unguarded ``git -C $source`` calls and
died on ``.Trim()`` against ``$null`` when the source was not a repository
— before anything had been copied, with exit 1 and no message worth
reading. A wheel that ``uvx`` built from a git URL has no ``.git``
anywhere, so that shape cannot survive the port: **git is optional here,
and a git that is absent or failing is never fatal.**

Resolution order:

1. running from a checkout and ``git`` answers → short sha, branch, dirty;
2. else PEP 610 — ``direct_url.json`` in the installed distribution
   records the VCS url, the requested revision and the resolved commit;
3. else the distribution version alone, which is still a well-formed
   answer and still stamps a usable ``# Source:`` line.

Whether uv writes ``direct_url.json`` for a VCS install is unverified
(pip does). Branch 3 is therefore not a formality: when branch 2 is
missing, ``update_ref`` synthesises ``v<version>`` from a release version
rather than echoing a revision nobody recorded.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

from . import DIST_NAME
from . import report as report_mod
from .kit import Kit

#: What the version reads as when the distribution is not installed, or when
#: its metadata cannot answer. Honest, and never a crash: nothing downstream
#: needs the number to be parseable, and a marker that says `0+unknown` is
#: more use than a traceback.
UNKNOWN_VERSION = "0+unknown"


def distribution_version() -> str:
    """``importlib.metadata.version("pb-ai-code")``, hatch-vcs-stamped.

    A tagged build reports ``0.5.0``; one commit past a tag reports
    ``0.5.1.dev1+gc26d4b6e3``, which says out loud that it is not a
    release. That is the whole reason there is no ``__version__``
    literal in this package.
    """
    try:
        found = metadata.version(DIST_NAME)
    except metadata.PackageNotFoundError:
        return UNKNOWN_VERSION
    # Observed once, on a venv carrying an empty leftover `*.dist-info`:
    # `version()` picks that one first and hands back None, against its own
    # type. Falling through to UNKNOWN_VERSION beats a TypeError three
    # frames later.
    return found or UNKNOWN_VERSION


@dataclass(frozen=True)
class SourceIdentity:
    """Everything the report and the marker say about where the kit came from."""

    version: str
    origin: str | None
    sha: str | None
    branch: str | None
    dirty: bool
    requested_revision: str | None = None

    @property
    def is_development_build(self) -> bool:
        """True for anything hatch-vcs did not stamp straight off a tag."""
        return ".dev" in self.version or "+" in self.version

    @property
    def update_ref(self) -> str | None:
        """The ref the marker's ``To update:`` recipe should pin.

        The recorded requested revision when there is one, else ``v`` plus
        a release version. ``None`` for a development build, where the
        recipe prints the command with no ref and says why.
        """
        if self.requested_revision:
            return self.requested_revision
        if self.is_development_build or self.version == UNKNOWN_VERSION:
            return None
        return f"v{self.version}"

    @property
    def summary(self) -> str:
        """The stdout ``Source:`` value."""
        return report_mod.source_summary(self.version, self.origin)


def _git(root: Path, *args: str) -> str | None:
    """Run git against ``root``; ``None`` when it is missing or unhappy."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:  # git not on PATH
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _from_checkout(root: Path, version: str) -> SourceIdentity | None:
    sha = _git(root, "rev-parse", "--short", "HEAD")
    if sha is None:
        return None
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    status = _git(root, "status", "--porcelain")
    # Untracked files count as dirty, deliberately: an untracked skill is
    # unversioned work that the install would carry into the target.
    dirty = bool(status is not None and status.strip())
    return SourceIdentity(
        version=version,
        origin=report_mod.checkout_origin(str(root)),
        sha=sha.strip(),
        branch=branch.strip() if branch else None,
        dirty=dirty,
    )


def _from_direct_url(version: str) -> SourceIdentity | None:
    """PEP 610: the installer records what it was asked for, and what it got."""
    try:
        dist = metadata.distribution(DIST_NAME)
        raw = dist.read_text("direct_url.json")
    except (metadata.PackageNotFoundError, OSError):
        return None
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(parsed, dict):
        return None
    vcs_info = parsed.get("vcs_info")
    url = parsed.get("url")
    if not isinstance(vcs_info, dict) or not isinstance(url, str):
        return None
    vcs = vcs_info.get("vcs")
    commit = vcs_info.get("commit_id")
    revision = vcs_info.get("requested_revision")
    origin = f"{vcs}+{url}" if isinstance(vcs, str) else url
    return SourceIdentity(
        version=version,
        origin=origin,
        # Short form, to match what a checkout reports.
        sha=commit[:7] if isinstance(commit, str) else None,
        branch=None,
        # A build from a pinned tag cannot be dirty; there is no tree to be
        # dirty about.
        dirty=False,
        requested_revision=revision if isinstance(revision, str) else None,
    )


def resolve(kit: Kit) -> SourceIdentity:
    """The three-branch identity chain. Never raises for want of git."""
    version = distribution_version()
    if kit.is_checkout:
        identity = _from_checkout(kit.root, version)
        if identity is not None:
            return identity
    identity = _from_direct_url(version)
    if identity is not None:
        return identity
    return SourceIdentity(version=version, origin=None, sha=None, branch=None, dirty=False)
