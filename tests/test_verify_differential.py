from pathlib import Path

from research_pipeline.verify import differential as differential_module
from research_pipeline.verify.differential import differential
from research_pipeline.verify.hypothesis import BugHypothesis

ORIGINAL = "def divide(a, b):\n    return a // b\n"

HARNESS = '''from esbmc import nondet_int


def divide(a: int, b: int) -> int:
    return a // b


def main() -> None:
    a: int = nondet_int()
    b: int = nondet_int()
    divide(a, b)


main()
'''

SEEDS = {"int": [7, 0], "float": []}


def _hypothesis(tmp_path: Path, source: str = ORIGINAL) -> BugHypothesis:
    path = tmp_path / "orig.py"
    path.write_text(source, encoding="utf-8")
    return BugHypothesis(str(path), "divide", "a // b", category="division_by_zero")


def test_same_body_agrees_on_every_input(tmp_path):
    result = differential(HARNESS, ORIGINAL, _hypothesis(tmp_path), SEEDS, runs=5)
    assert result.total >= 1 and result.agreed == result.total
    assert result.level == "stubs" and result.preservation == "nao_medida"
    assert result.divergences == []


def test_simplified_body_that_hides_the_bug_diverges(tmp_path):
    simplified = HARNESS.replace("return a // b", "return a // 1")
    result = differential(simplified, ORIGINAL, _hypothesis(tmp_path), SEEDS, runs=5)
    assert result.divergences and result.agreed < result.total
    assert result.preservation == "alterada"
    divergence = result.divergences[0]
    assert divergence["harness"]["status"] == "not_reproduced"
    assert divergence["original"]["exception_type"] == "ZeroDivisionError"


def test_counterexample_comes_first(tmp_path, monkeypatch):
    compared = []
    real = differential_module.concrete_replay

    def spy(*args, **kwargs):
        if kwargs.get("inputs") is not None:
            compared.append(kwargs["inputs"])
        return real(*args, **kwargs)
    monkeypatch.setattr(differential_module, "concrete_replay", spy)
    differential(HARNESS, ORIGINAL, _hypothesis(tmp_path), SEEDS, runs=3)
    assert compared[0] == [7, 0]


def test_importable_free_function_runs_for_real(tmp_path):
    h = _hypothesis(tmp_path, "import math\n\n\ndef divide(a, b):\n    return a // b\n")
    result = differential(HARNESS, ORIGINAL, h, SEEDS, runs=3, original_path=Path(h.file))
    assert result.level == "real", result
    assert result.total >= 1 and result.agreed == result.total
    assert result.preservation == "preservada"


CHECKED = """def check(b):
    if b == 0:
        raise ValueError("b must not be zero")


def divide(a, b):
    check(b)
    return a // b
"""


def test_real_level_sees_a_dependency_the_stubs_hide(tmp_path):
    h = _hypothesis(tmp_path, CHECKED)
    stubbed = HARNESS.replace("def divide(a: int, b: int) -> int:\n",
                              "def check(b: int) -> None:\n    return None\n\n\n"
                              "def divide(a: int, b: int) -> int:\n    check(b)\n")
    result = differential(stubbed, CHECKED, h, SEEDS, runs=3, original_path=Path(h.file))
    assert result.level == "real" and result.preservation == "alterada", result
    divergence = result.divergences[0]
    assert divergence["harness"]["exception_type"] == "ZeroDivisionError"
    assert divergence["real"]["exception_type"] == "ValueError"


def test_unimportable_original_falls_back_to_stubs(tmp_path):
    h = _hypothesis(tmp_path, "import pacote_que_nao_existe\n\n\ndef divide(a, b):\n    return a // b\n")
    result = differential(HARNESS, ORIGINAL, h, SEEDS, runs=3, original_path=Path(h.file))
    assert result.level == "stubs" and result.preservation == "nao_medida"
    assert "pacote_que_nao_existe" in result.reason
