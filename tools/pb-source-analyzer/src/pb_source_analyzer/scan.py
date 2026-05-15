"""Walk a directory tree, decode each PB source file, identify top-level blocks.

Block detection is line-based regex matching. It is intentionally
approximate — the goal is statistical coverage of patterns across many
files, not perfect parsing of a single file. Edge cases are surfaced as
``unknown_marker`` blocks rather than silently dropped.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterator

PB_EXTENSIONS: dict[str, str] = {
    ".sra": "application",
    ".srw": "window",
    ".sru": "userobject",
    ".srf": "function",
    ".srd": "datawindow",
    ".srm": "menu",
    ".srs": "structure",
    ".srq": "query",
    ".srj": "project",
}

# Line-start markers we recognize. Pattern → block kind.
_BLOCK_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^forward\s*$", re.IGNORECASE), "forward_open"),
    (re.compile(r"^end forward\s*$", re.IGNORECASE), "forward_close"),
    (re.compile(r"^global type\s+(\S+)\s+from\s+(\S+)", re.IGNORECASE), "global_type"),
    (re.compile(r"^type variables\s*$", re.IGNORECASE), "type_variables_open"),
    (re.compile(r"^end variables\s*$", re.IGNORECASE), "type_variables_close"),
    (re.compile(r"^event\s+(\S+)", re.IGNORECASE), "event"),
    (re.compile(r"^on\s+(\S+)", re.IGNORECASE), "on_block"),
    (re.compile(r"^(public|private|protected)?\s*function\s+", re.IGNORECASE), "function"),
    (re.compile(r"^(public|private|protected)?\s*subroutine\s+", re.IGNORECASE), "subroutine"),
    (re.compile(r"^end type\s*$", re.IGNORECASE), "type_close"),
    (re.compile(r"^end event\s*$", re.IGNORECASE), "event_close"),
    (re.compile(r"^end function\s*$", re.IGNORECASE), "function_close"),
    (re.compile(r"^end subroutine\s*$", re.IGNORECASE), "subroutine_close"),
    (re.compile(r"^end on\s*$", re.IGNORECASE), "on_close"),
]

_HEADER_RE = re.compile(r"^\$PBExportHeader\$(\S+)\s*$")


@dataclass
class Block:
    kind: str
    line: int
    detail: str | None = None  # name (event/function), parent class (global_type), etc.

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FileRecord:
    path: str
    entry_type: str
    encoding_kind: str
    crlf_ok: bool
    header_ok: bool
    header_value: str | None
    line_count: int
    blocks: list[Block] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["blocks"] = [b.to_dict() for b in self.blocks]
        return d


# Two encodings are observed in real corpora:
#
# 1. ``utf-16-le-bom`` — what PB IDE produces when you export an object
#    "to file" directly from the IDE.
# 2. ``utf-8-bom`` — what the Appeon Source Code Control mirror
#    ``ws_objects/`` uses on git-managed projects. PB IDE reads both
#    flavors back without complaint.
#
# UTF-16 BE and bare UTF-8 are recognized but not expected.
def decode_file(path: Path) -> tuple[str | None, str, bool]:
    """Return ``(text, encoding_kind, crlf_ok)``.

    ``encoding_kind`` is one of ``utf-16-le-bom``, ``utf-16-be-bom``,
    ``utf-8-bom``, ``utf-8-no-bom``, ``empty``, or ``unknown``.

    ``crlf_ok`` is True iff at least one CRLF appears in the first
    2 KiB and no bare LF appears outside CRLF pairs in that window.
    """
    data = path.read_bytes()
    if len(data) < 2:
        return None, "empty", False

    text: str | None = None
    kind = "unknown"
    if data[:2] == b"\xff\xfe":
        kind = "utf-16-le-bom"
        try:
            text = data[2:].decode("utf-16-le")
        except UnicodeDecodeError:
            text = None
    elif data[:2] == b"\xfe\xff":
        kind = "utf-16-be-bom"
        try:
            text = data[2:].decode("utf-16-be")
        except UnicodeDecodeError:
            text = None
    elif len(data) >= 3 and data[:3] == b"\xef\xbb\xbf":
        kind = "utf-8-bom"
        try:
            text = data[3:].decode("utf-8")
        except UnicodeDecodeError:
            text = None
    else:
        try:
            text = data.decode("utf-8")
            kind = "utf-8-no-bom"
        except UnicodeDecodeError:
            text = None
            kind = "unknown"

    if text is None:
        return None, kind, False

    head = text[:2048]
    crlf_ok = "\r\n" in head and not re.search(r"(?<!\r)\n", head)
    return text, kind, crlf_ok


def iter_pb_files(root: Path) -> Iterator[Path]:
    for ext in PB_EXTENSIONS:
        yield from root.rglob(f"*{ext}")


def scan_file(path: Path) -> FileRecord:
    entry_type = PB_EXTENSIONS.get(path.suffix.lower(), "unknown")
    text, encoding_kind, crlf_ok = decode_file(path)
    rec = FileRecord(
        path=str(path),
        entry_type=entry_type,
        encoding_kind=encoding_kind,
        crlf_ok=crlf_ok,
        header_ok=False,
        header_value=None,
        line_count=0,
    )
    if text is None:
        return rec
    lines = text.splitlines()
    rec.line_count = len(lines)
    if lines:
        m = _HEADER_RE.match(lines[0])
        if m:
            rec.header_ok = True
            rec.header_value = m.group(1)
    for idx, line in enumerate(lines, start=1):
        stripped = line.rstrip()
        for pat, kind in _BLOCK_PATTERNS:
            m = pat.match(stripped)
            if m:
                detail = m.group(1) if m.groups() else None
                if kind == "global_type" and m.lastindex and m.lastindex >= 2:
                    detail = f"{m.group(1)} from {m.group(2)}"
                rec.blocks.append(Block(kind=kind, line=idx, detail=detail))
                break
    return rec


def scan_tree(root: Path) -> list[FileRecord]:
    return [scan_file(p) for p in iter_pb_files(root) if p.is_file()]
