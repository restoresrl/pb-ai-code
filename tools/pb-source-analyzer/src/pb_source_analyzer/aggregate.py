"""Compute per-entry-type statistics from anonymized scan records.

The output is a dict keyed by entry type, each value carrying:

- ``file_count``: number of files of this type in the corpus.
- ``encoding_ok_ratio``, ``crlf_ok_ratio``, ``header_ok_ratio``:
  share of files that respect the encoding rules.
- ``block_kind_frequency``: how often each block kind appears
  per file (mean).
- ``top_block_sequences``: most common ordered sequences of
  top-level blocks (signature of a "typical" file of this type).
- ``parent_classes``: for entry types that declare ``global type
  ... from <parent>``, the histogram of parent classes after
  anonymization.

The output is JSON-serializable and is the direct input to ``render``.
"""

from __future__ import annotations

from collections import Counter
from typing import Any


def _sequence(blocks: list[dict[str, Any]]) -> tuple[str, ...]:
    """Reduce a block list to its kind-sequence, collapsing immediate dupes."""
    seq: list[str] = []
    for b in blocks:
        kind = b["kind"]
        if not seq or seq[-1] != kind:
            seq.append(kind)
    return tuple(seq)


def aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_type: dict[str, list[dict[str, Any]]] = {}
    for r in records:
        by_type.setdefault(r.get("entry_type", "unknown"), []).append(r)

    result: dict[str, Any] = {}
    for entry_type, recs in by_type.items():
        n = len(recs)
        encoding_kinds: Counter[str] = Counter(
            r.get("encoding_kind", "unknown") for r in recs
        )
        crlf_ok = sum(1 for r in recs if r.get("crlf_ok"))
        header_ok = sum(1 for r in recs if r.get("header_ok"))

        kind_counts: Counter[str] = Counter()
        for r in recs:
            for b in r.get("blocks", []):
                kind_counts[b["kind"]] += 1

        seqs: Counter[tuple[str, ...]] = Counter()
        for r in recs:
            seqs[_sequence(r.get("blocks", []))] += 1

        parents: Counter[str] = Counter()
        for r in recs:
            for b in r.get("blocks", []):
                if b["kind"] == "global_type" and b.get("detail"):
                    # detail format: "<name> from <parent>"
                    parts = b["detail"].split(" from ", 1)
                    if len(parts) == 2:
                        parents[parts[1].strip()] += 1

        result[entry_type] = {
            "file_count": n,
            "encoding_kinds": dict(encoding_kinds.most_common()),
            "crlf_ok_ratio": round(crlf_ok / n, 3) if n else 0.0,
            "header_ok_ratio": round(header_ok / n, 3) if n else 0.0,
            "block_kind_frequency": {
                k: round(v / n, 3) for k, v in kind_counts.most_common()
            } if n else {},
            "top_block_sequences": [
                {"sequence": list(seq), "count": cnt}
                for seq, cnt in seqs.most_common(5)
            ],
            "parent_classes": dict(parents.most_common(10)),
        }
    return result
