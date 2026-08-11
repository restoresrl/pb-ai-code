"""Parse a cached Appeon doc page into a structured ``Page`` record.

The Appeon doc site has a fairly regular template per topic kind
(function, event, object, statement). The parser extracts the
sections that show up consistently on a function page:

    H1 / title
    Description (lead paragraph)
    Syntax (code block)
    Arguments (table or definition list)
    Return value
    Examples (one or more code blocks)
    See also (link list)

For pages that do not follow this template (index pages, overview
pages, statement reference), the parser falls back to a generic
"title + body text" record. The downstream FTS indexer doesn't
require every field — missing fields just don't contribute to the
match.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag


@dataclass
class Page:
    version: str
    url: str
    category: str
    kind: str  # 'function', 'event', 'object', 'statement', 'index', 'unknown'
    name: str
    description: str = ""
    syntax: str = ""
    arguments: str = ""  # plain-text rendering of the args table
    return_value: str = ""
    examples: str = ""
    see_also: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_KIND_BY_SUFFIX: dict[str, str] = {
    "_func": "function",
    "_event": "event",
    "_obj": "object",
    "_stmt": "statement",
    "_keyword": "keyword",
    "_prop": "property",
}


def _infer_kind_and_name(html_path: Path) -> tuple[str, str]:
    stem = html_path.stem
    for suffix, kind in _KIND_BY_SUFFIX.items():
        if stem.endswith(suffix):
            return kind, stem[: -len(suffix)]
    if stem == "index":
        return "index", html_path.parent.name
    return "unknown", stem


def _is_appeon_section_header(tag: object) -> bool:
    """BeautifulSoup hands back `PageElement`, which may be a bare string.

    Taking `object` and narrowing here — rather than at each of the three call
    sites — keeps the callers readable and makes the answer for a
    `NavigableString` what it should be: no, that is not a section header.
    """
    if not isinstance(tag, Tag):
        return False
    return _is_appeon_section_header_tag(tag)


def _is_appeon_section_header_tag(tag: Tag) -> bool:
    """Appeon doc pages use ``<p><span class="bold"><strong>Section</strong></span></p>``
    as section headers, not real heading tags. This identifies them."""
    if not isinstance(tag, Tag) or tag.name != "p":
        return False
    span = tag.find("span", class_="bold")
    if span is None:
        return False
    strong = span.find("strong")
    return strong is not None


def _find_appeon_section_header(soup: BeautifulSoup, label: str) -> Tag | None:
    label_l = label.lower()
    for p in soup.find_all("p"):
        if not isinstance(p, Tag) or not _is_appeon_section_header(p):
            continue
        text = p.get_text(" ", strip=True).lower()
        if text == label_l or text.startswith(label_l + " "):
            return p
    return None


def _is_table_div(tag: object) -> bool:
    return isinstance(tag, Tag) and tag.name == "div" and "table" in (tag.get("class") or [])


def _appeon_section(
    soup: BeautifulSoup,
    label: str,
    *,
    exclude_tables: bool = False,
) -> str:
    """Find a Section-titled paragraph and return joined text of its
    successor siblings up to the next section header. When
    ``exclude_tables`` is True, ``<div class="table">`` elements are
    skipped — useful when the table actually belongs to a separate
    logical section (e.g. on Appeon function pages the Arguments table
    lives between the ``Syntax`` and ``Return value`` headers without
    its own bold-strong header).
    """
    header = _find_appeon_section_header(soup, label)
    if header is None:
        return ""
    parts: list[str] = []
    for sib in header.next_siblings:
        if _is_appeon_section_header(sib):
            break
        if isinstance(sib, Tag):
            if exclude_tables and _is_table_div(sib):
                continue
            text = sib.get_text(" ", strip=True)
            if text:
                parts.append(text)
    return "\n".join(parts).strip()


def _appeon_first_table_after(soup: BeautifulSoup, label: str) -> str:
    """Return the text of the first ``<div class="table">`` that follows
    the ``label`` section header, stopping at the next bold header. Used
    to extract the Arguments table that has no header of its own."""
    header = _find_appeon_section_header(soup, label)
    if header is None:
        return ""
    for sib in header.next_siblings:
        if _is_appeon_section_header(sib):
            return ""
        if _is_table_div(sib):
            return sib.get_text(" ", strip=True)
    return ""


def _appeon_section_links(soup: BeautifulSoup, label: str) -> list[str]:
    label_l = label.lower()
    header: Tag | None = None
    for p in soup.find_all("p"):
        if not _is_appeon_section_header(p):
            continue
        text = p.get_text(" ", strip=True).lower()
        if text == label_l or text.startswith(label_l + " "):
            header = p
            break
    if header is None:
        return []
    out: list[str] = []
    for sib in header.next_siblings:
        if _is_appeon_section_header(sib):
            break
        if isinstance(sib, Tag):
            for a in sib.find_all("a", href=True):
                href = str(a.get("href", "")).strip()
                if href and not href.startswith(("#", "mailto:", "javascript:")):
                    out.append(href)
    return out


def _text_after_heading(soup: BeautifulSoup, heading_text: str) -> str:
    """Generic fallback: find first <h1..h4> whose visible text matches."""
    heading_lower = heading_text.lower()
    heading: Tag | None = None
    for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
        if tag.get_text(strip=True).lower() == heading_lower:
            heading = tag
            break
    if heading is None:
        return ""
    parts: list[str] = []
    for sib in heading.next_siblings:
        if isinstance(sib, Tag) and sib.name in ("h1", "h2", "h3", "h4"):
            break
        if isinstance(sib, Tag):
            text = sib.get_text(" ", strip=True)
            if text:
                parts.append(text)
    return "\n".join(parts).strip()


def _main_title(soup: BeautifulSoup) -> str:
    # Priority 1: Appeon's <meta name="Section-title" content="...">.
    meta = soup.find("meta", attrs={"name": "Section-title"})
    if isinstance(meta, Tag):
        content = meta.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    # Priority 2: <h3 class="title"> used by Appeon for the actual page heading.
    for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
        classes = tag.get("class") or []
        if "title" in classes:
            text: str = tag.get_text(strip=True)
            if text:
                return text
    # Priority 3: <h1> (note: on Appeon pages this is the breadcrumb).
    h1 = soup.find("h1")
    if h1 is not None:
        text = h1.get_text(strip=True)
        if text:
            return text
    # Last resort: <title>, stripping the " - PowerScript Reference" suffix.
    title = soup.find("title")
    if title is not None:
        raw = title.get_text(strip=True)
        for suffix in (" - PowerScript Reference", " -  - PowerScript Reference"):
            if raw.endswith(suffix):
                return raw[: -len(suffix)].strip()
        return raw
    return ""


def _lead_paragraph(soup: BeautifulSoup) -> str:
    """First plain <p> that comes after the actual page title.

    On Appeon pages the title is an ``<h3 class="title">``; on generic
    fallback pages it is the first ``<h1>``/``<h2>``.
    """
    title_tag = None
    for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
        classes = tag.get("class") or []
        if "title" in classes:
            title_tag = tag
            break
    if title_tag is None:
        title_tag = soup.find(["h1", "h2"])
    # No title found: scan the whole document rather than what follows it.
    target_iter = soup.find_all("p") if title_tag is None else title_tag.find_all_next("p")
    for p in target_iter:
        if not isinstance(p, Tag):
            continue
        if _is_appeon_section_header(p):
            continue
        text = p.get_text(" ", strip=True)
        if text:
            return text
    return ""


def parse_page(html_path: Path, version: str, category: str, url: str) -> Page:
    """Parse a cached HTML page. ``url`` is the original source URL.

    Tries the Appeon-specific extraction first (``<meta Section-title>``
    + bold-strong section headers); falls back to generic heading-based
    extraction for non-Appeon-shaped pages.
    """
    html = html_path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    kind, derived_name = _infer_kind_and_name(html_path)
    title = _main_title(soup) or derived_name

    syntax = _appeon_section(soup, "Syntax", exclude_tables=True) or _text_after_heading(
        soup, "Syntax"
    )
    # On Appeon function pages the Arguments table is the first
    # <div class="table"> that follows the Syntax header (no header of
    # its own). Fall back to a bold-strong Arguments section for
    # pages that do declare one, then to generic heading-based lookup.
    arguments = (
        _appeon_first_table_after(soup, "Syntax")
        or _appeon_section(soup, "Arguments")
        or _appeon_section(soup, "Argument")
        or _text_after_heading(soup, "Argument")
        or _text_after_heading(soup, "Arguments")
    )
    return_value = (
        _appeon_section(soup, "Return value")
        or _appeon_section(soup, "Return Value")
        or _text_after_heading(soup, "Return value")
    )
    examples = (
        _appeon_section(soup, "Examples", exclude_tables=True)
        or _appeon_section(soup, "Example", exclude_tables=True)
        or _text_after_heading(soup, "Examples")
        or _text_after_heading(soup, "Example")
    )
    see_also = _appeon_section_links(soup, "See also") or _appeon_section_links(soup, "See Also")
    description = (
        _appeon_section(soup, "Description")
        or _lead_paragraph(soup)
        or _text_after_heading(soup, "Description")
    )

    return Page(
        version=version,
        url=url,
        category=category,
        kind=kind,
        name=title or derived_name,
        description=description,
        syntax=syntax,
        arguments=arguments,
        return_value=return_value,
        examples=examples,
        see_also=see_also,
    )
