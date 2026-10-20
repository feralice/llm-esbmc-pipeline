import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("v2_funnel", Path(__file__).resolve().parents[1] / "scripts/v2_funnel.py")
v2_funnel = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v2_funnel)


def test_the_furthest_verdict_at_the_bug_line_decides_the_stage():
    assert v2_funnel.stage(["UNSUPPORTED", "NOT_CONFIRMED"]) == "esbmc_rodou_sem_confirmar"
    assert v2_funnel.stage(["PIPELINE_ERROR", "CONFIRMED"]) == "confirmado"
    assert v2_funnel.stage(["GROUNDING_FAILED", "MISSING_DEPENDENCY"]) == "esbmc_recusou"


def test_a_bug_only_cut_by_the_llm_limit_never_reached_the_harness():
    assert v2_funnel.stage(["PIPELINE_ERROR", "PIPELINE_ERROR"]) == "cortado_pelo_limite_do_llm"


def test_value_verdicts_take_their_stage():
    assert v2_funnel.stage(["VALUE_CONFIRMED"]) == "confirmado"
    assert v2_funnel.stage(["PROPERTY_REJECTED"]) == "esbmc_rodou_sem_confirmar"


def test_bugs_before_the_harness_are_staged_by_detection():
    assert v2_funnel.bug_stage(in_run=False, verdicts=[], at_line=[]) == "fora_da_rodada"
    assert v2_funnel.bug_stage(in_run=True, verdicts=[], at_line=[]) == "sem_hipotese"
    assert v2_funnel.bug_stage(in_run=True, verdicts=["CONFIRMED"], at_line=[]) == "hipotese_fora_da_linha"
    assert v2_funnel.bug_stage(in_run=True, verdicts=["UNSUPPORTED"], at_line=["UNSUPPORTED"]) == "esbmc_recusou"


def test_llm_only_sits_between_refusal_and_a_checked_verdict():
    assert v2_funnel.stage(["UNSUPPORTED", "LLM_ONLY"]) == "so_llm"
    assert v2_funnel.stage(["LLM_ONLY", "NOT_CONFIRMED"]) == "esbmc_rodou_sem_confirmar"


def test_a_behaviour_change_leaves_the_denominator():
    assert v2_funnel.bug_stage(in_run=True, verdicts=["CONFIRMED"], at_line=["CONFIRMED"],
                               behaviour_change=True) == "mudanca_de_comportamento"
