"""Tests for the file scanner.

Synthetic fixtures only — no real PB files in the test corpus.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pb_source_analyzer.scan import (
    PB_EXTENSIONS,
    decode_file,
    iter_pb_files,
    scan_file,
    scan_tree,
)


def _write_pb_file(path: Path, body: str) -> None:
    """Write a fake .sr* file with UTF-16 LE BOM + CRLF line endings."""
    crlf_body = body.replace("\n", "\r\n")
    payload = b"\xff\xfe" + crlf_body.encode("utf-16-le")
    path.write_bytes(payload)


def test_decode_file_recognizes_utf16_le_bom(tmp_path: Path) -> None:
    f = tmp_path / "a.sru"
    _write_pb_file(f, "$PBExportHeader$a.sru\nforward\nend forward\n")
    text, kind, crlf_ok = decode_file(f)
    assert kind == "utf-16-le-bom"
    assert crlf_ok is True
    assert text is not None
    assert text.startswith("$PBExportHeader$a.sru")


def test_decode_file_recognizes_utf8_bom(tmp_path: Path) -> None:
    """ws_objects/ mirror on git-managed projects uses UTF-8 BOM, not UTF-16."""
    f = tmp_path / "a.sru"
    body = "$PBExportHeader$a.sru\r\nforward\r\nend forward\r\n"
    f.write_bytes(b"\xef\xbb\xbf" + body.encode("utf-8"))
    text, kind, crlf_ok = decode_file(f)
    assert kind == "utf-8-bom"
    assert crlf_ok is True
    assert text is not None
    assert text.startswith("$PBExportHeader$a.sru")


def test_decode_file_checks_line_endings_across_the_complete_file(tmp_path: Path) -> None:
    f = tmp_path / "late-lf.sru"
    body = "$PBExportHeader$late-lf.sru\r\n" + ("x\r\n" * 1200) + "late\n"
    f.write_bytes(b"\xef\xbb\xbf" + body.encode("utf-8"))

    _, _, crlf_ok = decode_file(f)

    assert crlf_ok is False


def test_decode_file_rejects_a_bare_cr_terminator(tmp_path: Path) -> None:
    f = tmp_path / "bare-cr.sru"
    body = "$PBExportHeader$bare-cr.sru\r\none\rtwo\r\n"
    f.write_bytes(b"\xef\xbb\xbf" + body.encode("utf-8"))

    _, _, crlf_ok = decode_file(f)

    assert crlf_ok is False


def test_decode_file_flags_unknown_for_truly_invalid_bytes(tmp_path: Path) -> None:
    f = tmp_path / "a.sru"
    f.write_bytes(b"\x80\x81\x82\x83")  # Not a valid BOM, not valid UTF-8
    _, kind, _ = decode_file(f)
    assert kind == "unknown"


def test_scan_file_extracts_blocks(tmp_path: Path) -> None:
    f = tmp_path / "w_test.srw"
    body = (
        "$PBExportHeader$w_test.srw\n"
        "forward\n"
        "global type w_test from window\n"
        "end type\n"
        "end forward\n"
        "global type w_test from window\n"
        "end type\n"
        "type variables\n"
        "  integer ii_state\n"
        "end variables\n"
        "event ue_ready();return\n"
        "end event\n"
        "on w_test.create\n"
        "end on\n"
    )
    _write_pb_file(f, body)
    rec = scan_file(f)
    assert rec.entry_type == "window"
    assert rec.encoding_kind == "utf-16-le-bom"
    assert rec.crlf_ok is True
    assert rec.header_ok is True
    assert rec.header_value == "w_test.srw"
    kinds = [b.kind for b in rec.blocks]
    assert "forward_open" in kinds
    assert "forward_close" in kinds
    assert "global_type" in kinds
    assert "type_variables_open" in kinds
    assert "type_variables_close" in kinds
    assert "event" in kinds
    assert "on_block" in kinds
    # global_type detail captures "<name> from <parent>"
    global_types = [b for b in rec.blocks if b.kind == "global_type"]
    assert global_types
    assert all(gt.detail is not None and "from" in gt.detail for gt in global_types)


def test_iter_pb_files_picks_up_all_extensions(tmp_path: Path) -> None:
    for ext in PB_EXTENSIONS:
        (tmp_path / f"sample{ext}").write_bytes(b"\xff\xfe")
    (tmp_path / "ignored.txt").write_bytes(b"nope")
    found = sorted(p.suffix.lower() for p in iter_pb_files(tmp_path))
    assert found == sorted(PB_EXTENSIONS.keys())


def test_scan_tree_returns_one_record_per_file(tmp_path: Path) -> None:
    _write_pb_file(tmp_path / "a.sru", "$PBExportHeader$a.sru\n")
    _write_pb_file(tmp_path / "b.srw", "$PBExportHeader$b.srw\n")
    records = scan_tree(tmp_path)
    assert len(records) == 2
    assert {r.entry_type for r in records} == {"userobject", "window"}


@pytest.mark.parametrize(
    "ext,expected_type",
    list(PB_EXTENSIONS.items()),
)
def test_pb_extensions_mapping_is_consistent(ext: str, expected_type: str) -> None:
    f = Path("dummy" + ext)
    assert PB_EXTENSIONS[f.suffix] == expected_type
