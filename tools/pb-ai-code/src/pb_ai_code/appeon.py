"""Find the Appeon documentation index, and say so either way.

The PowerShell script asked three questions about the checkout it was
running from: is there a ``.venv\\Scripts\\python.exe``, a
``docs/appeon-index/index.db``, and a ``tools/pb-appeon-index`` module? A
CLI installed by ``uvx`` from a git URL has none of those, so the probe is
re-rooted on the one thing that is genuinely per-machine: **the
database**. Everything else now travels in the wheel and is reached
through ``uvx``.

Discovery order:

1. ``PB_APPEON_INDEX_DB`` — an explicit answer beats a guess;
2. ``~/.pb-appeon-index/index.db`` — what ``pb_appeon_index.mcp_server``
   already falls back to;
3. ``<checkout>/docs/appeon-index/index.db`` — only when running from a
   clone, where existing developers' databases live.

Every answer is **absolute**, ``~`` and all. The path is not for us: it
goes into a server entry that an MCP client launches with a working
directory of its own choosing, so a relative one is a server that starts
and finds no database — and the failure is silent, which is this module's
whole subject. The script could not produce anything else (``Join-Path
$source 'docs\\appeon-index\\index.db'``, ps1:481) and step 1 is the only
step here that ever could.

The database is **referenced, never copied**. One file serves every
project, so rebuilding the index once updates every project already
configured, with no re-install; copying it would give N stale copies
instead of one live file.

``harness/mcp-servers.json`` cannot carry this server: it is committed and
shared, and this entry needs an absolute database path. The file we write
is neither — ``<target>/.mcp.json`` is generated and gitignored, so it is
per-machine by construction and absolute paths belong in it perfectly
well.

The failure is silent by nature: a missing MCP server is not an error
anywhere. Hence a note on both branches, and the same note in the marker.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import VCS_URL
from . import report as report_mod
from .kit import Kit

#: The key this server occupies in the merged ``mcpServers`` object.
SERVER_KEY = "pb-appeon-index"

#: Environment variable naming the database, read first and answered
#: first; also the variable the written server entry sets. Its value is
#: taken as given except for being made absolute — see :func:`_absolute`.
ENV_VAR = "PB_APPEON_INDEX_DB"

#: Per-user location, relative to the home directory.
USER_DB_REL = (".pb-appeon-index", "index.db")

#: In-checkout location, relative to the kit root.
CHECKOUT_DB_REL = ("docs", "appeon-index", "index.db")


def _absolute(path: Path) -> Path:
    """``~`` expanded and the result made absolute — but not *resolved*.

    ``os.path.abspath`` rather than ``Path.resolve`` on purpose: it is
    purely lexical, so a path that was already absolute comes back the way
    the user wrote it, 8.3 components, junctions and drive substitutions
    intact. This string is printed on stdout, recorded in the marker and
    written into the server entry; rewriting a path the user recognises
    into one they do not is a cost with no matching benefit, and
    ``resolve()`` does exactly that on Windows (``C:/Users/CARLO~1.TOR/...``
    comes back spelled out).

    ``os.path.expanduser`` rather than ``Path.expanduser`` for the same
    reason the tests own ``USERPROFILE``/``HOME``: it consults them on
    every call, and it returns the path unchanged instead of raising when
    there is no home to expand against.
    """
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def find_index_db(kit: Kit, environ: Mapping[str, str] | None = None) -> Path | None:
    """The first database that exists, in discovery order, absolute, or ``None``.

    Absolute on every branch. Only the environment variable can arrive
    relative or ``~``-prefixed; the other two are absolute by construction
    and go through the same call to say so rather than to change anything.
    A ``~`` value used to fall through silently to step 2 as well, because
    no such file exists under that literal name.
    """
    env: Mapping[str, str] = os.environ if environ is None else environ
    explicit = env.get(ENV_VAR)
    if explicit:
        candidate = _absolute(Path(explicit))
        if candidate.is_file():
            return candidate
    user_db = _absolute(Path.home().joinpath(*USER_DB_REL))
    if user_db.is_file():
        return user_db
    if kit.is_checkout:
        checkout_db = _absolute(kit.root.joinpath(*CHECKOUT_DB_REL))
        if checkout_db.is_file():
            return checkout_db
    return None


def server_entry(db: Path, ref: str | None = None) -> dict[str, Any]:
    """The ``pb-appeon-index`` server, pointed at ``db``.

    Call it as ``server_entry(db, identity.update_ref)``. The pin belongs
    in the written entry for the same reason ``harness/mcp-servers.json``
    carries one for ``pb-orca-mcp``: an unpinned requirement is
    documentation, not configuration, and it makes every server start
    re-resolve a moving branch. A development build has no tag,
    ``update_ref`` is then ``None``, and the bare URL is written — which
    is honest about what it was installed from and is the shape the spec's
    own JSON block quotes.

    The written entry only ever runs ``serve-mcp``, which needs the
    database and nothing else. Verified against a built wheel under
    ``uvx``: the server starts and answers, while ``pb-appeon-index
    update`` / ``build`` do **not** run that way — see :func:`note`.
    """
    source = VCS_URL if ref is None else f"{VCS_URL}@{ref}"
    return {
        "command": "uvx",
        "args": ["--from", source, "pb-appeon-index", "serve-mcp"],
        "env": {ENV_VAR: str(db)},
    }


def note(db: Path | None, *, existing_entry_in_target: bool = False) -> str:
    """What the stdout block and the marker's ``# Appeon:`` line say.

    The third shape exists because an entry from an earlier install falls
    into ``kept`` and is written back untouched while the installer
    simultaneously reports the server NOT configured — possibly pointing
    at a checkout that no longer exists. The preservation is right; the
    report was not. Ask :func:`pb_ai_code.mcpconfig.existing_server_names`
    for the flag.

    The build recipe printed alongside the failure branch
    (``report.appeon_missing``) clones and installs editable on purpose.
    ``uvx --from git+… pb-appeon-index update`` cannot work and was
    confirmed broken against a built wheel: ``config.toml`` lives at
    ``tools/pb-appeon-index/config.toml`` and neither ``packages`` nor
    ``force-include`` puts it in the wheel, so
    ``__main__._DEFAULT_CONFIG`` resolves to ``<site-packages>/../
    config.toml`` and the run dies with ``FileNotFoundError: …
    Lib\\config.toml`` before it fetches a page. ``serve-mcp`` is
    unaffected — it reads the database and never the config.
    """
    if db is not None:
        return report_mod.appeon_configured_note(str(db))
    if existing_entry_in_target:
        return report_mod.APPEON_NOTE_EXISTING_ENTRY
    return report_mod.APPEON_NOTE_MISSING_DB
