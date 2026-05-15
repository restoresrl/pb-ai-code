"""Fetch HTML pages from docs.appeon.com into a local cache.

The cache is laid out per-version:

    <cache_dir>/
        <slug>/
            <section>/
                <page>.html
        <slug>/.etag.json    # url -> etag mapping for conditional GET

Re-running the scrape is idempotent: pages with unchanged ETag /
Last-Modified headers are not re-downloaded. Rate-limit between
requests is configurable.

Crawl model: start from each section's index page, follow links that
stay under ``<base_url>/<section>/`` and target ``.html`` files.
Loops are prevented by a visited-set.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .config import Config, VersionConfig

log = logging.getLogger(__name__)

_HTML_LINK_RE = re.compile(r"\.html?(?:[#?].*)?$", re.IGNORECASE)


@dataclass
class ScrapeStats:
    fetched: int = 0
    cached_hit: int = 0
    not_modified: int = 0
    skipped: int = 0
    errors: int = 0


def _slug_cache_dir(cache_root: Path, slug: str) -> Path:
    d = cache_root / slug
    d.mkdir(parents=True, exist_ok=True)
    return d


def _etag_cache_path(cache_root: Path, slug: str) -> Path:
    return _slug_cache_dir(cache_root, slug) / ".etag.json"


def _load_etag_cache(cache_root: Path, slug: str) -> dict[str, dict[str, str]]:
    path = _etag_cache_path(cache_root, slug)
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            return loaded
    except (json.JSONDecodeError, OSError):
        log.warning("etag cache at %s is corrupt; ignoring", path)
    return {}


def _save_etag_cache(cache_root: Path, slug: str, cache: dict[str, dict[str, str]]) -> None:
    path = _etag_cache_path(cache_root, slug)
    path.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def _url_to_cache_path(cache_root: Path, slug: str, base_url: str, url: str) -> Path | None:
    """Map a URL under ``base_url`` to its local cache path. ``None`` if outside."""
    if not url.startswith(base_url):
        return None
    rel = url[len(base_url):]
    # Strip query/fragment, default to index.html for directory URLs.
    rel = rel.split("?", 1)[0].split("#", 1)[0]
    if not rel or rel.endswith("/"):
        rel = rel + "index.html"
    safe_parts = [p for p in rel.split("/") if p not in ("", ".", "..")]
    return _slug_cache_dir(cache_root, slug).joinpath(*safe_parts)


def _extract_internal_links(html: str, page_url: str, section_base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[str] = []
    for a in soup.find_all("a", href=True):
        href = str(a.get("href", "")).strip()
        if not href or href.startswith(("mailto:", "javascript:", "#")):
            continue
        absolute = urljoin(page_url, href)
        if not absolute.startswith(section_base_url):
            continue
        if not _HTML_LINK_RE.search(urlparse(absolute).path):
            continue
        # Drop fragment.
        absolute = absolute.split("#", 1)[0]
        out.append(absolute)
    return out


def _fetch_with_conditional_get(
    session: requests.Session,
    url: str,
    etag_entry: dict[str, str] | None,
) -> tuple[int, str | None, dict[str, str]]:
    headers: dict[str, str] = {}
    if etag_entry:
        if etag := etag_entry.get("etag"):
            headers["If-None-Match"] = etag
        if last_modified := etag_entry.get("last_modified"):
            headers["If-Modified-Since"] = last_modified
    resp = session.get(url, headers=headers, timeout=30)
    new_validators: dict[str, str] = {}
    if etag := resp.headers.get("ETag"):
        new_validators["etag"] = etag
    if last_modified := resp.headers.get("Last-Modified"):
        new_validators["last_modified"] = last_modified
    if resp.status_code == 304:
        return 304, None, etag_entry or {}
    resp.raise_for_status()
    return resp.status_code, resp.text, new_validators


def scrape_version(
    cfg: Config,
    version: VersionConfig,
    cache_root: Path,
) -> ScrapeStats:
    """Crawl all configured sections of ``version`` into the local cache.

    Returns stats; the caller decides what to log/print.
    """
    stats = ScrapeStats()
    session = requests.Session()
    session.headers["User-Agent"] = cfg.scraper.user_agent
    etag_cache = _load_etag_cache(cache_root, version.slug)
    delay_s = cfg.scraper.request_delay_ms / 1000.0
    max_pages = cfg.scraper.max_pages_per_run

    for section in version.sections:
        section_base_url = urljoin(version.base_url, section + "/")
        seed_urls = [section_base_url + "index.html"]
        to_visit: list[str] = list(seed_urls)
        visited: set[str] = set()

        while to_visit:
            if stats.fetched + stats.not_modified >= max_pages:
                log.warning("max_pages_per_run reached (%d)", max_pages)
                break
            url = to_visit.pop(0)
            if url in visited:
                continue
            visited.add(url)

            cache_path = _url_to_cache_path(cache_root, version.slug, version.base_url, url)
            if cache_path is None:
                stats.skipped += 1
                continue

            entry = etag_cache.get(url)
            try:
                status, body, new_validators = _fetch_with_conditional_get(session, url, entry)
            except requests.RequestException as e:
                log.warning("fetch failed %s: %s", url, e)
                stats.errors += 1
                continue

            if status == 304:
                stats.not_modified += 1
                if cache_path.exists():
                    body = cache_path.read_text(encoding="utf-8", errors="replace")
                else:
                    body = None
            else:
                stats.fetched += 1
                if body is not None:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_text(body, encoding="utf-8")

            etag_cache[url] = new_validators

            if body:
                for link in _extract_internal_links(body, url, section_base_url):
                    if link not in visited:
                        to_visit.append(link)

            time.sleep(delay_s)

    _save_etag_cache(cache_root, version.slug, etag_cache)
    return stats
