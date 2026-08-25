"""Git must preserve PowerBuilder projections without making their diffs opaque."""

from __future__ import annotations

import subprocess
from pathlib import Path

from pb_ai_code import gitignore


def init_repo(path: Path) -> None:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True, capture_output=True)


def write_utf8_source(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xef\xbb\xbf$PBExportHeader$sample.srw\r\none\r\ntwo\r\n")


def test_no_attribute_rule_is_unprotected(tmp_path: Path) -> None:
    root = tmp_path / "project"
    init_repo(root)
    write_utf8_source(root / "ws_objects" / "app.pbl.src" / "sample.srw")

    result = gitignore.source_protection(root)

    assert result.status == "unprotected"
    assert result.checked_files == 1
    assert result.unprotected_files == ("ws_objects/app.pbl.src/sample.srw",)


def test_minus_text_preserves_bytes_and_keeps_utf8_diffable(tmp_path: Path) -> None:
    root = tmp_path / "project"
    init_repo(root)
    (root / ".gitattributes").write_text("*.sr* -text\n", encoding="utf-8")
    source = root / "ws_objects" / "app.pbl.src" / "sample.srw"
    write_utf8_source(source)
    before = source.read_bytes()

    result = gitignore.source_protection(root)

    assert result.status == "protected"
    assert source.read_bytes() == before
    assert result.checked_files == 1
    assert result.unprotected_files == ()
    assert result.nondiffable_files == ()


def test_binary_macro_is_safe_but_not_diffable(tmp_path: Path) -> None:
    root = tmp_path / "project"
    init_repo(root)
    (root / ".gitattributes").write_text("*.sr* binary\n", encoding="utf-8")
    write_utf8_source(root / "ws_objects" / "app.pbl.src" / "sample.srw")

    result = gitignore.source_protection(root)

    assert result.status == "nondiffable"
    assert result.nondiffable_files == ("ws_objects/app.pbl.src/sample.srw",)


def test_scoped_rule_is_checked_on_the_real_projection_path(tmp_path: Path) -> None:
    root = tmp_path / "project"
    init_repo(root)
    (root / ".gitattributes").write_text("src/ws_objects/** -text\n", encoding="utf-8")
    write_utf8_source(root / "src" / "ws_objects" / "app.pbl.src" / "sample.srw")

    result = gitignore.source_protection(root)

    assert result.status == "protected"
    assert result.checked_files == 1


def test_nested_override_makes_the_result_mixed(tmp_path: Path) -> None:
    root = tmp_path / "project"
    init_repo(root)
    (root / ".gitattributes").write_text("*.sr* -text\n", encoding="utf-8")
    write_utf8_source(root / "ws_objects" / "one.pbl.src" / "safe.srw")
    overridden = root / "ws_objects" / "two.pbl.src"
    write_utf8_source(overridden / "normalized.srw")
    (overridden / ".gitattributes").write_text("*.sr* text\n", encoding="utf-8")

    result = gitignore.source_protection(root)

    assert result.status == "mixed"
    assert result.checked_files == 2
    assert result.unprotected_files == ("ws_objects/two.pbl.src/normalized.srw",)


def test_utf16_and_nul_bearing_exports_are_byte_safe_but_binary_to_git(tmp_path: Path) -> None:
    root = tmp_path / "project"
    init_repo(root)
    (root / ".gitattributes").write_text("*.sr* -text\n", encoding="utf-8")
    source = root / "ws_objects" / "legacy.pbl.src" / "legacy.srw"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"\xff\xfe" + "one\r\ntwo\r\n".encode("utf-16-le"))

    result = gitignore.source_protection(root)

    assert result.status == "nondiffable"
    assert result.nondiffable_files == ("ws_objects/legacy.pbl.src/legacy.srw",)


def test_renormalizing_the_index_does_not_rewrite_powerbuilder_files(tmp_path: Path) -> None:
    root = tmp_path / "project"
    init_repo(root)
    subprocess.run(["git", "-C", str(root), "config", "core.autocrlf", "true"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
    source = root / "ws_objects" / "app.pbl.src" / "sample.srw"
    write_utf8_source(source)
    subprocess.run(
        ["git", "-C", str(root), "add", "--", "ws_objects/app.pbl.src/sample.srw"],
        check=True,
    )
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "normalized base"], check=True)
    before = source.read_bytes()
    attributes = root / ".gitattributes"
    attributes.write_text("*.sr* -text\n", encoding="utf-8")

    subprocess.run(["git", "-C", str(root), "add", ".gitattributes"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "--renormalize", "--", "ws_objects"], check=True)
    indexed = subprocess.run(
        ["git", "-C", str(root), "show", ":ws_objects/app.pbl.src/sample.srw"],
        check=True,
        capture_output=True,
    ).stdout

    assert source.read_bytes() == before
    assert indexed == before


def test_empty_projection_is_unknown_and_the_check_writes_nothing(tmp_path: Path) -> None:
    root = tmp_path / "project"
    init_repo(root)
    projection = root / "ws_objects"
    projection.mkdir()
    attributes = root / ".gitattributes"
    attributes.write_bytes(b"*.sr* -text\r\n")
    before = attributes.read_bytes()

    result = gitignore.source_protection(root)

    assert result.status == "unknown"
    assert result.checked_files == 0
    assert attributes.read_bytes() == before
    assert list(projection.iterdir()) == []


def test_no_git_and_no_projection_are_distinct(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    assert gitignore.source_protection(plain).status == "no_git"

    repo = tmp_path / "repo"
    init_repo(repo)
    assert gitignore.source_protection(repo).status == "no_projection"
