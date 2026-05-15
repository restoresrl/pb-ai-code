"""pb-source-analyzer — reverse-engineer PB source-file structure from real corpora.

Pipeline:

    scan      -> walk a .sr* tree, decode each file, identify top-level blocks
    anonymize -> strip project-specific identifiers from the scan output
    aggregate -> compute per-entry-type statistics and variant patterns
    render    -> merge aggregated stats into the docs/pb-source-format/ wiki

Each step is a CLI subcommand exposed by ``python -m pb_source_analyzer``.

The analyzer is intended to be run privately on a real PB codebase. Its
output (Markdown merged into the wiki) is what becomes public — the raw
intermediate JSON stays local. See ``docs/pb-source-format/index.md`` for
how the wiki is structured.
"""

from __future__ import annotations

__version__ = "0.0.1"
