"""pb-ai-code — install the kit into the places an AI assistant actually reads.

The canonical copies live in this repository, in agent-neutral locations
(``skills/``, ``commands/``, ``docs/``, ``harness/``). No assistant reads
those paths. This CLI copies them into the layout a given harness expects,
so one source of truth serves every tool. It replaces
``scripts/install-skills.ps1`` and is run from *inside* the consumer repo::

    uvx --from git+https://github.com/restoresrl/pb-ai-code pb-ai-code install

Verbs:

    install   copy skills, commands, knowledge base, harness settings and
              the MCP server block into the target, then write a marker
    status    read the marker back and say what is installed there
    search    set up or refresh project-versioned Appeon documentation
    update    check GitHub Releases and update the persistent tool and project

Each verb is a subcommand of ``python -m pb_ai_code`` or of the console
script ``pb-ai-code``.

There is deliberately **no** ``__version__`` literal here. The two sibling
tools carry a stale ``0.0.1``, and a literal like that is what made
pb-orca-mcp v0.2.0 introduce itself as 0.1.0. :mod:`pb_ai_code.provenance`
derives everything from ``importlib.metadata.version("pb-ai-code")``, which
hatch-vcs stamps from the git tag at build time.
"""

from __future__ import annotations

#: Distribution name, as ``importlib.metadata`` knows it.
DIST_NAME = "pb-ai-code"

#: Canonical repository. Written without a ``@ref`` on purpose: a bare URL
#: is invisible to ``tests/test_pins_in_sync.py``, which reads every
#: ``github.com/restoresrl/<repo>@<ref>`` in the tree as a pin that must
#: agree with every other one. Compose the ref at run time instead.
REPO_URL = "https://github.com/restoresrl/pb-ai-code"

#: The same repository as a PEP 508 / uv VCS requirement.
VCS_URL = "git+" + REPO_URL

# --- Exit codes (spec §4). ---------------------------------------------------
# 0 covers every warning path: a duplicate ORCA server, an unparseable target
# .mcp.json, a missing Appeon index, no commands directory, a bundle that is
# not gitignored and a dirty source are all reported and all exit 0. Three
# existing assertions in tests/test_installer_mcp_merge.py depend on it.

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_NOT_INSTALLED = 3


class PbAiCodeError(Exception):
    """An anticipated failure.

    Printed as one line, ``pb-ai-code: <message>``, on stderr, with no
    traceback. Anything *not* derived from this keeps its traceback, which
    is the house rule: an unexpected exception is a bug report, not a
    diagnostic.
    """

    exit_code: int = EXIT_ERROR


class UsageError(PbAiCodeError):
    """The invocation itself is wrong — exit 2.

    Target missing or not a directory, an absolute or escaping
    ``--skills-dir``/``--commands-dir``, a
    ``--commands-dir`` that is not a sibling of ``--skills-dir``, a skills
    directory passed to ``claude-code``, an unknown harness.
    """

    exit_code: int = EXIT_USAGE


class NotInstalled(PbAiCodeError):
    """``status`` found no marker under the target — exit 3.

    A documented deviation from the two-code taxonomy: agents branch on
    "installed?" without wanting to parse anything.
    """

    exit_code: int = EXIT_NOT_INSTALLED
