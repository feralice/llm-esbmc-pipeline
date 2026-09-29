import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("v2_reverdict", ROOT / "scripts" / "v2_reverdict.py")
reverdict = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reverdict)

PROGRAM = '''def option(params, param):
    value = params.get(param)
    assert isinstance(value, bool)
    return value


def _esbmc_main() -> None:
    params: dict[str, bool] = {}
    param: str = nondet_str()
    option(params, param)


_esbmc_main()
'''


def _result(tmp_path, reading, reason, verdict="UNVALIDATED"):
    program = tmp_path / "p.py"
    program.write_text(PROGRAM, encoding="utf-8")
    return {
        "hypothesis": {"file": "x.py", "function": "option", "suspect_expression": "assert isinstance(value, bool)"},
        "verdict": verdict, "reason": reason, "program_path": str(program),
        "attempts": [{"reading": reading}], "replay": {"status": "reproduced", "exception_type": "AssertionError"},
    }


def test_assertion_violation_is_recomputed_as_confirmed(tmp_path):
    result = reverdict.reverdict_result(_result(tmp_path, "violation", "assertion ISINSTANCE(value, 0); unwinding assertion loop 4"))
    assert result["verdict"] == "CONFIRMED"
    assert result["reverdict"]["previous"] == "UNVALIDATED"


def test_results_without_an_esbmc_verdict_are_untouched(tmp_path):
    original = _result(tmp_path, "repairable", "ERROR: something", verdict="UNSUPPORTED")
    assert reverdict.reverdict_result(dict(original))["verdict"] == "UNSUPPORTED"
