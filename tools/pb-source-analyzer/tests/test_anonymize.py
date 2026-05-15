"""Tests for the anonymization step.

These tests are *the* safety net against leaking proprietary names
into the public wiki. Add fixtures whenever you encounter a new
sensitive identifier shape.
"""

from __future__ import annotations

from pb_source_analyzer.anonymize import (
    KNOWN_CUSTOMER_CODES,
    KNOWN_PREFIXES,
    PB_STANDARD_PARENT_TYPES,
    anonymize_global_type_detail,
    anonymize_parent_type,
    anonymize_record,
    anonymize_text,
    audit,
)


def test_anonymize_text_replaces_mw_prefixed_identifiers() -> None:
    src = "n_mw_logger inherits from n_mw_base"
    out = anonymize_text(src)
    assert "mw" not in out.lower()
    assert audit(out) == []


def test_anonymize_text_replaces_customer_prefixed_identifiers() -> None:
    for code in KNOWN_CUSTOMER_CODES:
        src = f"of_{code}_helper called n_{code}_widget"
        out = anonymize_text(src)
        assert audit(out) == [], f"leak with customer code '{code}': {out!r}"


def test_anonymize_text_replaces_all_known_prefixes() -> None:
    for prefix in KNOWN_PREFIXES:
        src = f"reference to {prefix}_something_useful"
        out = anonymize_text(src)
        assert audit(out) == [], f"leak with prefix '{prefix}': {out!r}"


def test_anonymize_text_preserves_neutral_identifiers() -> None:
    src = "n_userobject_a calls f_helper with parameters"
    out = anonymize_text(src)
    assert out == src


def test_anonymize_text_does_not_break_substrings() -> None:
    # "summary" contains "mw"? No — but "summary" should never be touched.
    # Make a sharper case: "geometry" contains "geb"-like substrings only
    # as substring; ensure word-boundary matching does not clip them.
    src = "summary geometry mlg_sipa stpost"
    out = anonymize_text(src)
    assert "summary" in out
    assert "geometry" in out
    assert audit(out) == []


def test_anonymize_parent_type_keeps_pb_standard_types() -> None:
    counter: dict[str, int] = {}
    for pb_type in ("window", "nonvisualobject", "commandbutton", "userobject"):
        assert anonymize_parent_type(pb_type, counter) == pb_type
    assert sum(counter.values()) == 0


def test_anonymize_parent_type_replaces_custom_userobjects() -> None:
    """Custom userobjects (not in the PB-standard whitelist) leak project
    identity even when their name does not match the sensitive-token
    blacklist. They MUST be replaced.
    """
    counter: dict[str, int] = {}
    # These names look "neutral" to the blacklist — none of their
    # tokens are in KNOWN_PREFIXES or KNOWN_CUSTOMER_CODES — but they
    # are still project-specific class hierarchy names.
    for custom in ("u_pdo_anc", "u_wizard_page_anc", "n_impexp_ws"):
        out = anonymize_parent_type(custom, counter)
        assert out != custom
        assert out not in PB_STANDARD_PARENT_TYPES  # got a placeholder, not a real PB type
        # And the placeholder still looks PB-shaped.
        assert out.startswith(("u_", "n_", "of_", "ue_", "w_", "m_", "f_", "s_", "d_", "anon_"))


def test_anonymize_global_type_detail() -> None:
    counter: dict[str, int] = {}
    # Custom parent: anonymized.
    out = anonymize_global_type_detail("u_pdo_select_anc from u_pdo_anc", counter)
    assert "u_pdo" not in out
    assert " from " in out

    # Standard parent: kept; only name anonymized.
    counter = {}
    out = anonymize_global_type_detail("n_my_logger from nonvisualobject", counter)
    assert "from nonvisualobject" in out
    assert "n_my_logger" not in out  # name still gets a placeholder


def test_anonymize_record_strips_path_and_block_details() -> None:
    record = {
        "path": r"C:\projects\magware\mw21r2\ws_objects\src\mw_main.pbl.src\n_mw_logger.sru",
        "entry_type": "userobject",
        "encoding_ok": True,
        "crlf_ok": True,
        "header_ok": True,
        "header_value": "n_mw_logger.sru",
        "line_count": 42,
        "blocks": [
            {"kind": "global_type", "line": 2, "detail": "n_mw_logger from n_mw_base"},
            {"kind": "event", "line": 10, "detail": "ue_mw_init"},
        ],
    }
    out = anonymize_record(record)
    full_text = (
        out["path"]
        + " "
        + (out.get("header_value") or "")
        + " "
        + " ".join(b["detail"] or "" for b in out["blocks"])
    )
    assert audit(full_text) == []
    assert "mw" not in full_text.lower() or "_method_" in full_text.lower()
