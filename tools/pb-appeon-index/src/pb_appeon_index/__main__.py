"""CLI entry point.

Subcommands:

    scrape    [--version <slug>] [--all] [--config <path>] [--cache <dir>]
    build     [--config <path>] [--cache <dir>] [--db <path>]
    update    [--version <slug>] [--all] [--config <path>] [--cache <dir>] [--db <path>]
              (= scrape + build in one shot)
    search    --query <q> [--version <slug>] [--limit N] [--db <path>]
    serve-mcp [--db <path>]
    versions  [--db <path>]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import index as index_mod
from . import mcp_server as mcp_mod
from . import scrape as scrape_mod
from .config import Config, VersionConfig, load_config

_DEFAULT_CONFIG = Path(__file__).resolve().parent.parent.parent / "config.toml"
_DEFAULT_CACHE = Path(".appeon-cache")
_DEFAULT_DB = Path("docs/appeon-index/index.db")


def _resolve_versions(cfg: Config, slug: str | None, all_flag: bool) -> list[VersionConfig]:
    if all_flag:
        return list(cfg.versions)
    if slug:
        v = cfg.find_version(slug)
        if v is None:
            print(f"unknown version slug: {slug}", file=sys.stderr)
            sys.exit(2)
        return [v]
    return [cfg.default_version()]


def _cmd_scrape(args: argparse.Namespace) -> int:
    cfg = load_config(Path(args.config))
    cache_root = Path(args.cache)
    for v in _resolve_versions(cfg, args.version, args.all):
        print(f"scrape: {v.slug}", file=sys.stderr)
        stats = scrape_mod.scrape_version(cfg, v, cache_root)
        print(
            f"  fetched={stats.fetched} cached={stats.not_modified} "
            f"errors={stats.errors} skipped={stats.skipped}",
            file=sys.stderr,
        )
    return 0


def _cmd_build(args: argparse.Namespace) -> int:
    cfg = load_config(Path(args.config))
    n = index_mod.build_index(cfg, Path(args.cache), Path(args.db))
    print(f"build: {n} pages indexed -> {args.db}", file=sys.stderr)
    return 0


def _cmd_update(args: argparse.Namespace) -> int:
    rc = _cmd_scrape(args)
    if rc:
        return rc
    return _cmd_build(args)


def _cmd_search(args: argparse.Namespace) -> int:
    conn = index_mod.connect(Path(args.db), read_only=True)
    try:
        hits = index_mod.search(conn, args.query, args.version, args.limit)
    finally:
        conn.close()
    print(json.dumps([h.to_dict() for h in hits], indent=2))
    return 0


def _cmd_serve_mcp(args: argparse.Namespace) -> int:
    db_path = Path(args.db) if args.db else None
    mcp_mod.run_stdio(db_path)
    return 0


def _cmd_versions(args: argparse.Namespace) -> int:
    conn = index_mod.connect(Path(args.db), read_only=True)
    try:
        rows = index_mod.list_versions(conn)
    finally:
        conn.close()
    print(json.dumps(rows, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pb-appeon-index")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def _add_version_args(p: argparse.ArgumentParser) -> None:
        g = p.add_mutually_exclusive_group()
        g.add_argument("--version", help="single version slug (e.g. pb2022r3)")
        g.add_argument("--all", action="store_true", help="every version in the config")

    def _add_path_args(p: argparse.ArgumentParser, with_db: bool = True) -> None:
        p.add_argument("--config", default=str(_DEFAULT_CONFIG))
        p.add_argument("--cache", default=str(_DEFAULT_CACHE))
        if with_db:
            p.add_argument("--db", default=str(_DEFAULT_DB))

    p_scrape = sub.add_parser("scrape", help="download HTML to local cache")
    _add_version_args(p_scrape)
    _add_path_args(p_scrape, with_db=False)
    p_scrape.set_defaults(func=_cmd_scrape)

    p_build = sub.add_parser("build", help="(re)build the SQLite index from the cache")
    _add_path_args(p_build)
    p_build.set_defaults(func=_cmd_build)

    p_update = sub.add_parser("update", help="scrape + build in one shot")
    _add_version_args(p_update)
    _add_path_args(p_update)
    p_update.set_defaults(func=_cmd_update)

    p_search = sub.add_parser("search", help="run a keyword query against the index")
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--version")
    p_search.add_argument("--limit", type=int, default=10)
    p_search.add_argument("--db", default=str(_DEFAULT_DB))
    p_search.set_defaults(func=_cmd_search)

    p_serve = sub.add_parser("serve-mcp", help="run the MCP server over stdio")
    p_serve.add_argument("--db", default=None)
    p_serve.set_defaults(func=_cmd_serve_mcp)

    p_versions = sub.add_parser("versions", help="list versions present in the index")
    p_versions.add_argument("--db", default=str(_DEFAULT_DB))
    p_versions.set_defaults(func=_cmd_versions)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
