"""Guards against schema.py / categories.py / system_prompt.txt drift.

Three independent places declare the same 11 category names: the frozensets
in categories.py, the JSON-schema enum in schema.py, and the checklist
embedded in system_prompt.txt (sent to every backend). They agree today, but
nothing enforced that beyond code review -- schema.py's enum used to be a
fourth hardcoded copy. This file is the enforcement: it fails loudly the
moment a category is added or renamed in only one of the three places.
"""

from __future__ import annotations

from pathlib import Path

from research_pipeline.llm.categories import (
    FORMAL_CATEGORIES,
    SMELL_CATEGORIES,
    SUPPORTED_CATEGORIES,
)
from research_pipeline.llm.schema import FINDINGS_JSON_SCHEMA

SYSTEM_PROMPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "research_pipeline" / "prompts" / "system_prompt.txt"
)


def _schema_category_enum() -> list[str]:
    return FINDINGS_JSON_SCHEMA["schema"]["properties"]["findings"]["items"]["properties"]["category"]["enum"]


def test_categories_partition_formal_and_smell_without_overlap():
    assert not (FORMAL_CATEGORIES & SMELL_CATEGORIES)
    assert SUPPORTED_CATEGORIES == FORMAL_CATEGORIES | SMELL_CATEGORIES


def test_schema_enum_matches_categories_module_exactly():
    assert set(_schema_category_enum()) == SUPPORTED_CATEGORIES


def test_schema_enum_has_no_duplicates():
    enum = _schema_category_enum()
    assert len(enum) == len(set(enum))


def test_every_supported_category_is_named_in_the_system_prompt():
    text = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    missing = [cat for cat in SUPPORTED_CATEGORIES if cat not in text]
    assert not missing, f"categories.py declares categories absent from system_prompt.txt: {missing}"


def test_system_prompt_declares_exactly_eleven_categories():
    # The prompt's own text asserts "11 categorias" / "8 bugs formais e 3 smells".
    # If categories.py ever grows past 11, that claim silently goes stale.
    assert len(SUPPORTED_CATEGORIES) == 11
    assert len(FORMAL_CATEGORIES) == 8
    assert len(SMELL_CATEGORIES) == 3
