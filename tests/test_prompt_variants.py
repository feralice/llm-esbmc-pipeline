import pytest

from research_pipeline.llm.prompt_variants import apply_variants
from research_pipeline.llm.prompts import load_system_prompt

BASE = load_system_prompt(include_smells=False, v2_detection=True)


def test_without_variants_the_prompt_is_the_baseline() -> None:
    assert apply_variants(BASE, ()) == BASE


def test_a1_asks_to_report_even_without_context() -> None:
    changed = apply_variants(BASE, ("A1",))
    assert "prefira não reportar" not in changed and "quando apropriado, não reporte" not in changed


def test_a2_adds_the_input_checklist_before_the_output_section() -> None:
    changed = apply_variants(BASE, ("A2",))
    assert changed.index("## PARTIÇÃO DE ENTRADAS") < changed.index("## SAÍDA")


def test_a3_asks_for_ranked_hypotheses() -> None:
    assert "da mais para a menos provável" in apply_variants(BASE, ("A3",))


def test_variants_compose() -> None:
    both = apply_variants(BASE, ("A1", "A2"))
    assert "## PARTIÇÃO DE ENTRADAS" in both and "prefira não reportar" not in both


def test_a_variant_whose_anchor_is_gone_fails_loudly() -> None:
    with pytest.raises(ValueError, match="A1"):
        apply_variants("prompt sem os trechos", ("A1",))


def test_an_unknown_variant_fails() -> None:
    with pytest.raises(ValueError, match="Z9"):
        apply_variants(BASE, ("Z9",))


def test_load_system_prompt_applies_variants() -> None:
    assert "## PARTIÇÃO DE ENTRADAS" in load_system_prompt(include_smells=False, v2_detection=True,
                                                           v2_variants=("A2",))
