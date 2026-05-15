"""Merge aggregated statistics into the wiki Markdown pages.

The wiki page format reserves a *single* section for analyzer output:

    <!-- BEGIN auto-generated: pb-source-analyzer -->
    ...
    <!-- END auto-generated: pb-source-analyzer -->

Anything outside the markers is preserved (canonical form, hand-curated
variants, open questions). The renderer replaces only the auto-generated
section. If the markers are missing, the section is appended before the
"## Cross-references" header (or at the end of the file if that header
is absent).

This split lets the wiki carry both *curated* knowledge (humans /
agents during real work) and *corpus-derived* knowledge (analyzer
output) without one overwriting the other.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_BEGIN = "<!-- BEGIN auto-generated: pb-source-analyzer -->"
_END = "<!-- END auto-generated: pb-source-analyzer -->"

_ENTRY_TYPE_TO_PAGE: dict[str, str] = {
    "application": "application.md",
    "window": "window.md",
    "userobject": "userobject.md",
    "function": "function.md",
    "datawindow": "datawindow.md",
    "menu": "menu.md",
    "structure": "structure.md",
    "query": "query.md",
    "project": "project.md",
}


def _format_section(entry_type: str, stats: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(_BEGIN)
    lines.append("")
    lines.append("## Auto-generated from corpus")
    lines.append("")
    lines.append(
        f"Derived from `pb-source-analyzer` over a private corpus. "
        f"Do not edit by hand; this section is replaced on each render."
    )
    lines.append("")
    lines.append(f"- **File count:** {stats['file_count']}")
    lines.append(f"- **CRLF OK:** {stats['crlf_ok_ratio']:.1%}")
    lines.append(f"- **`$PBExportHeader$` present:** {stats['header_ok_ratio']:.1%}")
    lines.append("")
    if stats.get("encoding_kinds"):
        lines.append("### Encoding distribution")
        lines.append("")
        total = stats["file_count"] or 1
        for kind, count in stats["encoding_kinds"].items():
            pct = count / total
            lines.append(f"- `{kind}`: {count} ({pct:.1%})")
        lines.append("")
    if stats.get("block_kind_frequency"):
        lines.append("### Block-kind frequency (mean occurrences per file)")
        lines.append("")
        lines.append("| Kind | Mean |")
        lines.append("|---|---|")
        for k, v in stats["block_kind_frequency"].items():
            lines.append(f"| `{k}` | {v} |")
        lines.append("")
    if stats.get("top_block_sequences"):
        lines.append("### Most common top-level block sequences")
        lines.append("")
        for s in stats["top_block_sequences"]:
            seq_str = " → ".join(f"`{k}`" for k in s["sequence"])
            lines.append(f"- ({s['count']} files) {seq_str}")
        lines.append("")
    if stats.get("parent_classes"):
        lines.append("### Parent classes observed (`global type ... from ...`)")
        lines.append("")
        for parent, cnt in stats["parent_classes"].items():
            lines.append(f"- `{parent}` ({cnt})")
        lines.append("")
    lines.append(_END)
    return "\n".join(lines)


def _replace_or_insert(existing: str, section: str) -> str:
    if _BEGIN in existing and _END in existing:
        pattern = re.compile(
            re.escape(_BEGIN) + r".*?" + re.escape(_END),
            re.DOTALL,
        )
        return pattern.sub(section, existing)
    # Insert before "## Cross-references" if present.
    crossref_re = re.compile(r"^## Cross-references\s*$", re.MULTILINE)
    m = crossref_re.search(existing)
    if m:
        return existing[: m.start()] + section + "\n\n" + existing[m.start() :]
    return existing.rstrip() + "\n\n" + section + "\n"


def render_all(summary: dict[str, Any], target_dir: Path) -> list[Path]:
    written: list[Path] = []
    for entry_type, page_name in _ENTRY_TYPE_TO_PAGE.items():
        if entry_type not in summary:
            continue
        page = target_dir / page_name
        if not page.exists():
            continue
        existing = page.read_text(encoding="utf-8")
        section = _format_section(entry_type, summary[entry_type])
        new_content = _replace_or_insert(existing, section)
        if new_content != existing:
            page.write_text(new_content, encoding="utf-8")
            written.append(page)
    return written
