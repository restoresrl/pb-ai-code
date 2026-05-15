"""Tests for the Appeon page parser, using a synthetic HTML fixture
that mirrors the structure observed on docs.appeon.com function pages.
"""

from __future__ import annotations

from pathlib import Path

from pb_appeon_index.parse import parse_page

_LEFT_FIXTURE = """<!doctype html>
<html>
<head>
  <title>Left -  - PowerScript Reference</title>
  <meta name="Section-title" content="Left" />
</head>
<body>
<h1>PowerScript Reference<br />PowerScript Functions</h1>
<h3 class="title"><a id="left_func"></a>Left</h3>
<p>Obtains a specified number of characters from the beginning of a string.</p>

<p><span class="bold"><strong>Syntax</strong></span></p>
<pre class="programlisting">Left ( string, n )</pre>

<p><span class="bold"><strong>Arguments</strong></span></p>
<table>
  <tr><th>Argument</th><th>Description</th></tr>
  <tr><td>string</td><td>The string from which you want characters returned.</td></tr>
  <tr><td>n</td><td>A long whose value specifies the number of characters to return.</td></tr>
</table>

<p><span class="bold"><strong>Return value</strong></span></p>
<p>String. Returns the leftmost n characters in string, or the empty string on error.</p>

<p><span class="bold"><strong>Examples</strong></span></p>
<pre class="programlisting">Left("BABE RUTH", 4)</pre>
<p>Returns "BABE".</p>

<p><span class="bold"><strong>See also</strong></span></p>
<ul>
  <li><a href="mid_func.html">Mid</a></li>
  <li><a href="pos_func.html">Pos</a></li>
  <li><a href="right_func.html">Right</a></li>
</ul>
</body></html>
"""


def test_parse_function_page_extracts_all_sections(tmp_path: Path) -> None:
    html_path = tmp_path / "left_func.html"
    html_path.write_text(_LEFT_FIXTURE, encoding="utf-8")
    page = parse_page(
        html_path=html_path,
        version="pb2022r3",
        category="powerscript_reference",
        url="https://docs.appeon.com/pb2022r3/powerscript_reference/left_func.html",
    )
    assert page.kind == "function"
    assert page.name == "Left"
    assert page.version == "pb2022r3"
    assert "Obtains a specified number of characters" in page.description
    assert "Left ( string, n )" in page.syntax
    assert "string" in page.arguments and "long" in page.arguments
    assert "leftmost" in page.return_value
    assert "BABE RUTH" in page.examples
    assert "mid_func.html" in page.see_also


def test_parse_index_page_falls_back_gracefully(tmp_path: Path) -> None:
    html_path = tmp_path / "index.html"
    html_path.write_text(
        "<html><body><h1>PowerScript Reference</h1>"
        "<p>Index of functions and statements.</p></body></html>",
        encoding="utf-8",
    )
    page = parse_page(
        html_path=html_path,
        version="pb2022r3",
        category="powerscript_reference",
        url="https://docs.appeon.com/pb2022r3/powerscript_reference/index.html",
    )
    assert page.kind == "index"
    assert page.name == "PowerScript Reference"
    assert "Index of functions" in page.description
