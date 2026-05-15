"""Strip project-specific identifiers from scan output.

The wiki is public; the corpus used to build it may be proprietary.
This module removes names that would leak project identity:

- Vendor / product prefixes commonly seen in real codebases.
- Customer-code prefixes (explicit allow-list).
- Generic PB ``of_*`` member-function prefixes that include vendor
  tokens.

Anything matching is replaced with a generic placeholder of the
appropriate shape (``n_userobject_N``, ``w_window_N``, etc.).

Two layers of defense:

1. *Replace*: known proprietary tokens are mapped to placeholders.
2. *Detect*: the ``audit`` function reports any token that still
   looks vendor-shaped (long underscore-separated identifiers with
   a short prefix). Used by tests to catch leaks the replace step
   missed.

This module is **conservative on purpose**. If you add a new
proprietary corpus, extend ``KNOWN_PREFIXES`` / ``KNOWN_CUSTOMER_CODES``
before running. Spot-check the output before committing.
"""

from __future__ import annotations

import re
from typing import Any

# Identifiers that, if present in the corpus, would leak project identity.
# Lowercase; matched case-insensitively as whole tokens.
KNOWN_PREFIXES: tuple[str, ...] = (
    "mw",
    "n_mw",
    "mw21r2",
    "rstpb",
    "pbgettext",
    "pbunit",
    "magware",
    "restore",
)

# Customer-code prefixes (PB Magware ecosystem). Extend if you ingest
# other proprietary corpora.
KNOWN_CUSTOMER_CODES: tuple[str, ...] = (
    "mlg",
    "alpi",
    "alsol",
    "dtrmsh",
    "geb",
    "mlg_sipa",
    "paoli",
    "plg",
    "plg_alea",
    "s2k",
    "siggi",
    "stpost",
)

# Whitelist of PB-standard parent types. Used when anonymizing
# ``global type <name> from <parent>`` blocks: anything outside this set
# is presumed to be a project-specific custom userobject and is replaced
# with a generic placeholder, regardless of whether it matches the
# blacklist above. This protects against leak of proprietary class
# hierarchies whose names do not include known sensitive prefixes.
PB_STANDARD_PARENT_TYPES: frozenset[str] = frozenset(
    {
        # Visual
        "application", "window", "userobject", "picture", "picturebutton",
        "commandbutton", "statictext", "singlelineedit", "multilineedit",
        "editmask", "datawindow", "dragobject", "dropdownlistbox",
        "dropdownpicturelistbox", "listbox", "listview", "treeview",
        "picturelistbox", "tab", "tabpage", "radiobutton", "checkbox",
        "groupbox", "richtextedit", "graph", "linenumbered", "line",
        "rectangle", "roundrectangle", "oval", "olecustomcontrol",
        "olecontrol", "oleobject", "olestorage", "olestream",
        "vscrollbar", "hscrollbar", "menu", "menucascade", "window_panel",
        # Non-visual
        "nonvisualobject", "transaction", "errorobject", "mailsession",
        "mailmessage", "mailrecipient", "mailfileattachment", "connection",
        "error", "inet", "pipeline", "service", "transport",
        "internetresult", "oletxnobject", "dynamicdescriptionarea",
        "dynamicstagingarea", "connectivity", "powerobject", "structure",
        "exception", "throwable", "runtimeerror", "nullobjecterror",
        "dividebyzeroerror", "coderesource", "contextkeyword",
        "contextinformation", "messaging", "javavm", "transportobject",
    }
)

# Generic placeholder bases by entry-type-style prefix. Counter is appended
# per anonymization run.
# Order matters: longer prefixes first, because ``startswith`` checks them
# in iteration order and ``of_`` / ``ue_`` would otherwise lose to ``o_`` /
# ``u_`` if those were ever added.
_PLACEHOLDER_BY_PB_PREFIX: dict[str, str] = {
    "of_": "of_method",
    "ue_": "ue_event",
    "n_": "n_userobject",
    "w_": "w_window",
    "u_": "u_userobject",
    "m_": "m_menu",
    "f_": "f_function",
    "s_": "s_structure",
    "d_": "d_datawindow",
}

# Build a single regex of all sensitive tokens. We match underscore-bounded
# identifier *tokens*, not substrings; that protects e.g. "summary" from
# being clipped because it contains "mw".
_SENSITIVE_TOKENS = sorted(
    set(KNOWN_PREFIXES) | set(KNOWN_CUSTOMER_CODES),
    key=len,
    reverse=True,
)
# NOTE: ``\b`` is unusable here because ``_`` is a "word character", so
# ``\bmw\b`` would not match ``mw`` inside ``n_mw_logger``. Use explicit
# lookarounds that treat letters and digits as boundary blockers but
# allow ``_`` (and any non-alphanumeric) as a boundary.
_SENSITIVE_RE = re.compile(
    r"(?<![A-Za-z0-9])("
    + "|".join(re.escape(t) for t in _SENSITIVE_TOKENS)
    + r")(?![A-Za-z0-9])",
    re.IGNORECASE,
)


def anonymize_token(name: str, counter: dict[str, int]) -> str:
    """Replace a single identifier-shaped token if it carries sensitive content.

    The PB prefix (``n_`` / ``w_`` / ...) is preserved so downstream
    examples still look like idiomatic PB names; only the discriminator
    suffix is replaced with a counter.
    """
    if not _SENSITIVE_RE.search(name):
        return name
    return _force_anonymize_token(name, counter)


def _force_anonymize_token(name: str, counter: dict[str, int]) -> str:
    """Always replace ``name`` with a PB-shaped generic placeholder.

    Used when whitelist logic (e.g. for parent types) has already
    decided the name carries project identity. Bypasses the
    sensitive-token check.
    """
    for pb_prefix, placeholder in _PLACEHOLDER_BY_PB_PREFIX.items():
        if name.lower().startswith(pb_prefix):
            counter[placeholder] = counter.get(placeholder, 0) + 1
            return f"{placeholder}_{counter[placeholder]}"
    counter["anon"] = counter.get("anon", 0) + 1
    return f"anon_{counter['anon']}"


def anonymize_parent_type(
    name: str,
    counter: dict[str, int],
    mapping: dict[str, str] | None = None,
) -> str:
    """Anonymize a parent-type identifier using the PB-standard whitelist.

    Only PB-standard types (``window``, ``nonvisualobject``,
    ``commandbutton``, ...) survive verbatim. Anything else is treated
    as a custom userobject and replaced with a generic placeholder,
    regardless of whether its name matches the sensitive-token blacklist.

    If ``mapping`` is provided, the same input name always maps to the
    same placeholder across calls. This preserves aggregate statistics
    (e.g. "this parent class appears in 252 files") that would
    otherwise be corrupted by independent per-record counters mapping
    different real parents to the same placeholder.
    """
    if name.lower() in PB_STANDARD_PARENT_TYPES:
        return name
    if mapping is None:
        return _force_anonymize_token(name, counter)
    if name not in mapping:
        mapping[name] = _force_anonymize_token(name, counter)
    return mapping[name]


def anonymize_global_type_detail(
    detail: str,
    counter: dict[str, int],
    mapping: dict[str, str] | None = None,
) -> str:
    """Anonymize a ``<name> from <parent>`` global-type block detail."""
    parts = detail.split(" from ", 1)
    if len(parts) != 2:
        return anonymize_text(detail, counter)
    name = parts[0].strip()
    parent = parts[1].strip()
    return (
        f"{anonymize_parent_type(name, counter, mapping)} from "
        f"{anonymize_parent_type(parent, counter, mapping)}"
    )


def anonymize_text(text: str, counter: dict[str, int] | None = None) -> str:
    """Replace sensitive tokens anywhere in a freeform string."""
    counter = counter if counter is not None else {}

    def _repl(match: re.Match[str]) -> str:
        # Replace the entire identifier the matched token belongs to.
        return anonymize_token(match.group(0), counter)

    # Match identifier tokens that contain a sensitive prefix anywhere.
    # An "identifier token" is [A-Za-z_][A-Za-z0-9_]*.
    ident_re = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

    def _ident_repl(m: re.Match[str]) -> str:
        ident = m.group(0)
        if _SENSITIVE_RE.search(ident):
            return anonymize_token(ident, counter)
        return ident

    return ident_re.sub(_ident_repl, text)


def anonymize_record(
    record: dict[str, Any],
    counter: dict[str, int] | None = None,
    parent_mapping: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Anonymize the path + block details of a scan record.

    ``counter`` and ``parent_mapping`` can be passed in to keep state
    across records — see ``anonymize_records`` for the cross-record
    variant. When omitted, a fresh local state is used (and aggregate
    statistics computed downstream will lose cross-record coherence
    for parent-type counts).
    """
    counter = counter if counter is not None else {}
    out: dict[str, Any] = dict(record)
    out["path"] = anonymize_text(record.get("path", ""), counter)
    if record.get("header_value"):
        out["header_value"] = anonymize_text(record["header_value"], counter)
    new_blocks: list[dict[str, Any]] = []
    for b in record.get("blocks", []):
        detail = b.get("detail")
        if detail and b.get("kind") == "global_type":
            new_detail: str | None = anonymize_global_type_detail(
                detail, counter, parent_mapping
            )
        elif detail:
            new_detail = anonymize_text(detail, counter)
        else:
            new_detail = None
        new_blocks.append({**b, "detail": new_detail})
    out["blocks"] = new_blocks
    return out


def anonymize_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Anonymize a batch of records with shared state.

    The shared ``parent_mapping`` makes ``global_type`` parent names
    stable across records: the same real parent always maps to the
    same placeholder. The shared ``counter`` keeps placeholder indexes
    monotonic across the run, which helps spot duplicates when
    eyeballing the output.
    """
    counter: dict[str, int] = {}
    parent_mapping: dict[str, str] = {}
    return [anonymize_record(r, counter, parent_mapping) for r in records]


def audit(text: str) -> list[str]:
    """Return the list of sensitive tokens still present in ``text``."""
    return list({m.group(0).lower() for m in _SENSITIVE_RE.finditer(text)})
