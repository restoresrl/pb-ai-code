"""The skills agree that PowerBuilder, not the agent, owns ws_objects."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

WRITE_SKILLS = (
    "pb-apply-plan",
    "pb-format",
    "pb-scaffold",
    "pb-src-format",
)


def read(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def test_normative_page_states_the_pbl_projection_boundary() -> None:
    text = read("docs/pb-source-format/authority-and-sync.md")
    assert "the `.pbl` is the operational authority" in text
    assert "PowerBuilder owns its contents" in text
    assert "Removing the `.sr*` by hand" in text
    assert "not a fallback" in text


def test_every_write_skill_uses_scratch_and_forbids_projection_writes() -> None:
    for name in WRITE_SKILLS:
        text = read(f"skills/{name}/SKILL.md")
        assert "scratch" in text, name
        assert "ws_objects" in text, name

    assert "Never copy the scratch file into `ws_objects`" in read("skills/pb-apply-plan/SKILL.md")
    assert "Never copy the result into `ws_objects/`" in read("skills/pb-src-format/SKILL.md")
    assert "Do not run `format` directly over `ws_objects/`" in read("skills/pb-format/SKILL.md")


def test_retired_projection_authority_instructions_do_not_return() -> None:
    files = [
        REPO_ROOT / "skills" / name / "SKILL.md"
        for name in (*WRITE_SKILLS, "pb-context-build", "pb-review")
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
    forbidden = (
        "those are the source of truth",
        "creates a source projection that did not exist",
        "import that file so ORCA rewrites the `.pbl`",
    )
    for phrase in forbidden:
        assert phrase not in combined
