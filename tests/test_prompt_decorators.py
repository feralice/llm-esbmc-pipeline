from __future__ import annotations

from pathlib import Path

from research_pipeline.llm.prompt_variants import VARIANTS
from research_pipeline.llm.prompts import build_user_prompt, load_system_prompt
from research_pipeline.preprocess import preprocess_file

SOURCE = '''import uuid


class Base:
    @staticmethod
    def make_id() -> str:
        return "id-" + str(uuid.uuid4())[:8]

    def plain(self, x: int) -> int:
        return x
'''


def _units(tmp_path: Path) -> dict:
    path = tmp_path / "base.py"
    path.write_text(SOURCE, encoding="utf-8")
    return {u.qualname: u for u in preprocess_file(path)}


def test_unit_records_decorators_without_changing_source_or_lines(tmp_path: Path) -> None:
    unit = _units(tmp_path)["Base.make_id"]
    assert unit.decorators == ["@staticmethod"]
    assert unit.source.startswith("def make_id()")
    assert unit.start_line == 6
    assert _units(tmp_path)["Base.plain"].decorators == []


def test_default_prompt_does_not_depend_on_decorators(tmp_path: Path) -> None:
    unit = _units(tmp_path)["Base.make_id"]
    bare = _units(tmp_path)["Base.make_id"]
    bare.decorators = []
    assert build_user_prompt(unit, include_smells=False, v2_variants=("A1", "A2")) == \
        build_user_prompt(bare, include_smells=False, v2_variants=("A1", "A2"))


def test_a22_shows_the_decorators_to_the_model(tmp_path: Path) -> None:
    unit = _units(tmp_path)["Base.make_id"]
    prompt = build_user_prompt(unit, include_smells=False, v2_variants=("A22",))
    assert "@staticmethod" in prompt


def test_a22_adds_nothing_for_a_function_without_decorators(tmp_path: Path) -> None:
    unit = _units(tmp_path)["Base.plain"]
    assert build_user_prompt(unit, include_smells=False, v2_variants=("A22",)) == \
        build_user_prompt(unit, include_smells=False, v2_variants=())


def test_a22_is_a_registered_variant_that_explains_the_section() -> None:
    assert "A22" in VARIANTS
    system = load_system_prompt(include_smells=False, v2_detection=True, v2_variants=("A22",))
    assert "decorator" in system.lower()
    assert system != load_system_prompt(include_smells=False, v2_detection=True, v2_variants=())
