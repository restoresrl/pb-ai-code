"""Locate and describe the bundled payload — the kit this CLI installs.

The PowerShell script derived every input from ``$PSScriptRoot/..``: it
could only ever run from a checkout. This CLI runs from a wheel that
``uvx`` built out of a git URL, on a machine with no clone on it, so the
kit travels inside the distribution at ``pb_ai_code/_kit/`` (see the
``force-include`` table in ``pyproject.toml``).

Two branches, in this order:

1. the packaged payload, resolved through ``importlib.resources``;
2. a checkout, found by searching upward for a **sentinel**.

The sentinel matters. ``Path(__file__).parents[4]`` happens to be the
repository root today only because the layout is
``tools/<name>/src/<pkg>/``; move the package one directory and the count
is wrong in a way no test would notice until an install produced an empty
bundle. Searching for ``skills/`` plus ``harness/mcp-servers.json``
answers the question that is actually being asked.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from . import PbAiCodeError
from . import report as report_mod

#: Directory the wheel's ``force-include`` maps the kit into.
PAYLOAD_DIR_NAME = "_kit"

#: Present in a checkout and in the payload alike; absent everywhere else.
_SENTINEL_DIR = "skills"
_SENTINEL_FILE = ("harness", "mcp-servers.json")


class KitNotFound(PbAiCodeError):
    """Neither a packaged payload nor a checkout could be found."""


def _has_sentinel(root: Path) -> bool:
    return (root / _SENTINEL_DIR).is_dir() and (root.joinpath(*_SENTINEL_FILE)).is_file()


def _resolve_kit_root() -> tuple[Path, bool]:
    """Return ``(root, is_checkout)``."""
    # 1. Packaged payload (wheel / uvx). Verified: nothing is inside a zip
    #    in a uv ephemeral environment, so the Traversable is a real
    #    directory and the path stays valid after the context manager exits.
    #    Should that ever stop being true, branch 2 still answers for the
    #    dev loop and the failure is a clean KitNotFound rather than a
    #    half-copied bundle.
    try:
        with resources.as_file(resources.files(__package__) / PAYLOAD_DIR_NAME) as payload:
            if (payload / _SENTINEL_DIR).is_dir():
                return payload, False
    except (OSError, TypeError, ValueError):  # pragma: no cover - loader-specific
        pass

    # 2. Editable install, or running straight from a clone. force-include
    #    content does NOT exist in an editable install (verified), so this
    #    is the development loop.
    for parent in Path(__file__).resolve().parents:
        if _has_sentinel(parent):
            return parent, True

    raise KitNotFound(report_mod.err_kit_not_found(str(Path(__file__).resolve())))


def kit_root() -> Path:
    """The directory the kit's canonical top-level layout sits in."""
    root, _ = _resolve_kit_root()
    return root


@dataclass(frozen=True)
class Kit:
    """The payload, wherever it was found.

    ``is_checkout`` records that branch 2 was taken. It gates two things:
    provenance may ask git about the tree (a wheel has no ``.git``), and
    the Appeon index discovery may fall back to
    ``<checkout>/docs/appeon-index/index.db``.
    """

    root: Path
    is_checkout: bool

    @property
    def skills_dir(self) -> Path:
        return self.root / "skills"

    @property
    def commands_dir(self) -> Path:
        return self.root / "commands"

    @property
    def docs_dir(self) -> Path:
        """The docs root.

        In the payload this holds exactly the three inputs the installer
        copies; in a checkout it holds everything, which is why the copy
        set is a closed list and not a glob of this directory.
        """
        return self.root / "docs"

    @property
    def harness_dir(self) -> Path:
        return self.root / "harness"

    @property
    def mcp_servers_file(self) -> Path:
        """The single canonical source of the server set, whatever the dialect."""
        return self.harness_dir / "mcp-servers.json"

    def settings_file(self, harness_id: str) -> Path:
        """``harness/<harness>/settings.json`` — claude-code only, today."""
        return self.harness_dir / harness_id / "settings.json"

    def iter_skills(self) -> list[Path]:
        """Every immediate subdirectory of ``skills/``, case-insensitively sorted.

        Enumerated at run time rather than listed in code, so a new skill
        ships with no code change. Sorted explicitly because ``iterdir()``
        order is not guaranteed and this order *is* the marker's Contents
        order.
        """
        return sorted((p for p in self.skills_dir.iterdir() if p.is_dir()), key=_case_key)

    def iter_command_files(self) -> list[Path]:
        """``commands/*.md``, flat, files only, case-insensitively sorted."""
        return sorted(
            (p for p in self.commands_dir.iterdir() if p.is_file() and p.suffix == ".md"),
            key=_case_key,
        )


def _case_key(path: Path) -> str:
    return path.name.lower()


def load_kit() -> Kit:
    """Find the payload. Raises :class:`KitNotFound` when there is none."""
    root, is_checkout = _resolve_kit_root()
    return Kit(root=root, is_checkout=is_checkout)
