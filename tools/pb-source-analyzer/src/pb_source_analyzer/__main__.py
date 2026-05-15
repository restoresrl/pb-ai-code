"""CLI entry point.

Subcommands:

    scan      --root <dir>             [--out scan.json]
    anonymize --in  scan.json          [--out anon.json]
    aggregate --in  anon.json          [--out agg.json]
    render    --in  agg.json --target docs/pb-source-format

A combined ``pipeline`` runs all four in sequence:

    pipeline  --root <dir> --target docs/pb-source-format
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import aggregate as agg_mod
from . import anonymize as anon_mod
from . import render as render_mod
from . import scan as scan_mod


def _cmd_scan(args: argparse.Namespace) -> int:
    records = scan_mod.scan_tree(Path(args.root))
    out_path = Path(args.out)
    out_path.write_text(
        json.dumps([r.to_dict() for r in records], indent=2),
        encoding="utf-8",
    )
    print(f"scan: {len(records)} files -> {out_path}", file=sys.stderr)
    return 0


def _cmd_anonymize(args: argparse.Namespace) -> int:
    raw = json.loads(Path(args.in_path).read_text(encoding="utf-8"))
    cleaned = anon_mod.anonymize_records(raw)
    Path(args.out).write_text(json.dumps(cleaned, indent=2), encoding="utf-8")
    print(f"anonymize: {len(cleaned)} records -> {args.out}", file=sys.stderr)
    return 0


def _cmd_aggregate(args: argparse.Namespace) -> int:
    records = json.loads(Path(args.in_path).read_text(encoding="utf-8"))
    summary = agg_mod.aggregate(records)
    Path(args.out).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"aggregate: {len(summary)} entry types -> {args.out}", file=sys.stderr)
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    summary = json.loads(Path(args.in_path).read_text(encoding="utf-8"))
    target = Path(args.target)
    written = render_mod.render_all(summary, target)
    print(f"render: {len(written)} pages updated under {target}", file=sys.stderr)
    return 0


def _cmd_pipeline(args: argparse.Namespace) -> int:
    workdir = Path(args.workdir) if args.workdir else Path(".pb-analyzer-tmp")
    workdir.mkdir(parents=True, exist_ok=True)
    scan_out = workdir / "scan.json"
    anon_out = workdir / "anon.json"
    agg_out = workdir / "agg.json"
    rc = _cmd_scan(argparse.Namespace(root=args.root, out=str(scan_out)))
    if rc:
        return rc
    rc = _cmd_anonymize(argparse.Namespace(in_path=str(scan_out), out=str(anon_out)))
    if rc:
        return rc
    rc = _cmd_aggregate(argparse.Namespace(in_path=str(anon_out), out=str(agg_out)))
    if rc:
        return rc
    return _cmd_render(argparse.Namespace(in_path=str(agg_out), target=args.target))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pb-source-analyzer")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="walk .sr* tree, decode, identify blocks")
    p_scan.add_argument("--root", required=True, help="directory to walk recursively")
    p_scan.add_argument("--out", default="scan.json", help="output JSON path")
    p_scan.set_defaults(func=_cmd_scan)

    p_anon = sub.add_parser("anonymize", help="strip project-specific identifiers")
    p_anon.add_argument("--in", dest="in_path", required=True)
    p_anon.add_argument("--out", default="anon.json")
    p_anon.set_defaults(func=_cmd_anonymize)

    p_agg = sub.add_parser("aggregate", help="compute per-entry-type statistics")
    p_agg.add_argument("--in", dest="in_path", required=True)
    p_agg.add_argument("--out", default="agg.json")
    p_agg.set_defaults(func=_cmd_aggregate)

    p_render = sub.add_parser("render", help="merge aggregated stats into the wiki")
    p_render.add_argument("--in", dest="in_path", required=True)
    p_render.add_argument("--target", required=True, help="wiki dir (docs/pb-source-format)")
    p_render.set_defaults(func=_cmd_render)

    p_pipe = sub.add_parser("pipeline", help="run scan -> anonymize -> aggregate -> render")
    p_pipe.add_argument("--root", required=True)
    p_pipe.add_argument("--target", required=True)
    p_pipe.add_argument("--workdir", default=None)
    p_pipe.set_defaults(func=_cmd_pipeline)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
