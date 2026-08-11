"""Load the multi-version scrape config from ``config.toml``.

Schema:

    [[versions]]
    slug = "pb2022r3"
    base_url = "https://docs.appeon.com/pb2022r3/"
    sections = ["powerscript_reference"]
    priority = 1

    [scraper]
    request_delay_ms = 200
    max_pages_per_run = 5000
    user_agent = "..."

The config is the single place new PB versions are declared. Adding a
version is a TOML edit, not a code change.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - 3.10 reads the same TOML through a backport
    import tomli as tomllib  # type: ignore[import-not-found,no-redef,unused-ignore]


@dataclass(frozen=True)
class VersionConfig:
    slug: str
    base_url: str
    sections: tuple[str, ...]
    priority: int = 100


@dataclass(frozen=True)
class ScraperConfig:
    request_delay_ms: int = 200
    max_pages_per_run: int = 5000
    user_agent: str = "pb-appeon-index/0.0.1"


@dataclass(frozen=True)
class Config:
    versions: tuple[VersionConfig, ...]
    scraper: ScraperConfig = field(default_factory=ScraperConfig)

    def find_version(self, slug: str) -> VersionConfig | None:
        for v in self.versions:
            if v.slug == slug:
                return v
        return None

    def default_version(self) -> VersionConfig:
        """Lowest-priority-number version. Raises if no versions are configured."""
        if not self.versions:
            raise ValueError("config has no [[versions]] entries")
        return min(self.versions, key=lambda v: v.priority)


def load_config(path: Path) -> Config:
    # No version guard here: the import above falls back to `tomli` on 3.10,
    # and `requires-python` says 3.10. A guard that refuses the oldest Python
    # the package claims to support is a contradiction, and this one survived
    # the import being fixed — CI caught it on its first run, which no local
    # run could, this machine being on 3.14.
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    versions_raw = data.get("versions", [])
    if not versions_raw:
        raise ValueError(f"{path}: no [[versions]] entries found")
    versions = tuple(
        VersionConfig(
            slug=v["slug"],
            base_url=v["base_url"].rstrip("/") + "/",
            sections=tuple(v.get("sections", [])),
            priority=int(v.get("priority", 100)),
        )
        for v in versions_raw
    )
    scraper_raw = data.get("scraper", {})
    scraper = ScraperConfig(
        request_delay_ms=int(scraper_raw.get("request_delay_ms", 200)),
        max_pages_per_run=int(scraper_raw.get("max_pages_per_run", 5000)),
        user_agent=str(scraper_raw.get("user_agent", "pb-appeon-index/0.0.1")),
    )
    return Config(versions=versions, scraper=scraper)
