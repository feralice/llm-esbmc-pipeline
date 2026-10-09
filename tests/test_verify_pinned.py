import ast
import subprocess
from pathlib import Path

import pytest

from research_pipeline.verify.pinned import PINNED_SAFE, PINNED_UNAVAILABLE, pin_program, pinned_check

ESBMC = "/usr/local/bin/esbmc"
BUGGY = (
    "def f(x: str, n: int) -> str:\n"
    "    if n > 40:\n"
    "        return x[0]\n"
    "    return x\n"
    "\n"
    "f(nondet_str(), nondet_int())\n"
)


def _assume(condition):
    if not condition:
        raise SystemExit("assume failed")


def test_the_pinned_program_returns_the_values_in_call_order() -> None:
    code = pin_program("a = nondet_str()\nb = nondet_int()\nc = nondet_int()\n", ["", 41, 7])
    assert "nondet_" not in code
    namespace = {"__ESBMC_assume": _assume}
    exec(code, namespace)
    assert (namespace["a"], namespace["b"], namespace["c"]) == ("", 41, 7)


def test_a_call_past_the_sequence_is_assumed_away() -> None:
    code = pin_program("a = nondet_int()\nb = nondet_int()\n", [1])
    with pytest.raises(SystemExit, match="assume"):
        exec(code, {"__ESBMC_assume": _assume})


def test_lists_take_their_length_and_elements_from_the_sequence() -> None:
    source = "def f(xs: list) -> int:\n    return 1 // (len(xs) - 2)\n\nf(nondet_list(3, elem_type=nondet_str()))\n"
    code = pin_program(source, ["", 2, "a", "b"])
    ast.parse(code)
    # ESBMC types the element argument: a str list gets its own helper taking a str.
    assert "f(_pin_list_str(_pin_str()))" in code and "def _pin_list_str(elem_type: str) -> list[str]:" in code
    assert "['a', 'b']" in code
    namespace = {"__ESBMC_assume": _assume}
    exec(code.replace("f(_pin_list_str", "got = (_pin_list_str"), namespace)
    assert namespace["got"] == ["a", "b"]


@pytest.mark.parametrize("inputs", [[float("nan")], [float("inf")], [object()]])
def test_values_without_a_literal_cannot_be_pinned(inputs) -> None:
    assert pin_program("def f(x):\n    return x\n\nf(nondet_float())\n", inputs) is None


def _result(tmp_path: Path, source: str) -> dict:
    path = tmp_path / "h_a0.py"
    path.write_text(source)
    hypothesis = {"function": "f", "suspect_expression": "x[0]", "hypothesis_id": "h"}
    return {"hypothesis": hypothesis, "verdict": "ESBMC_TIMEOUT", "program_path": str(path), "attempts": [{}]}


def _dynamic(inputs):
    return [{"arm": "dynamic", "verdict": "FUZZ_FOUND", "replay": {"inputs": inputs}}]


@pytest.mark.skipif(not Path(ESBMC).exists(), reason="needs ESBMC")
def test_esbmc_confirms_the_pinned_crash(tmp_path: Path) -> None:
    outcome = pinned_check({**_result(tmp_path, BUGGY), "steps": _dynamic(["", 41])},
                           work_dir=tmp_path / "w", esbmc=ESBMC, bound=5, timeout_seconds=120)
    assert outcome["verdict"] == "CONFIRMED", outcome


@pytest.mark.skipif(not Path(ESBMC).exists(), reason="needs ESBMC")
def test_the_fixed_version_is_not_confirmed(tmp_path: Path) -> None:
    fixed = BUGGY.replace("        return x[0]\n", "        return x[:1]\n")
    result = _result(tmp_path, fixed)
    result["hypothesis"]["suspect_expression"] = "x[:1]"
    outcome = pinned_check({**result, "steps": _dynamic(["", 41])}, work_dir=tmp_path / "w", esbmc=ESBMC,
                           bound=5, timeout_seconds=120)
    assert outcome["verdict"] == PINNED_SAFE, outcome


def test_no_dynamic_input_is_unavailable(tmp_path: Path) -> None:
    outcome = pinned_check({**_result(tmp_path, BUGGY), "steps": []}, work_dir=tmp_path / "w", esbmc=ESBMC,
                           bound=5, timeout_seconds=10)
    assert outcome["verdict"] == PINNED_UNAVAILABLE
