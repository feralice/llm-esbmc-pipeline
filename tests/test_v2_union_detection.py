import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("union", Path(__file__).parents[1] / "scripts" / "v2_union_detection.py")
union_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(union_module)


def _report(sent, held):
    return {"detection": {"candidates": [{"file": "a.py", "function": "f", "expression": e} for e in sent],
                          "rejected_findings": [{"file": "a.py", "function": "f", "expression": e} for e in held]}}


def test_union_keeps_each_finding_once_and_prefers_sent() -> None:
    sent, held = union_module.union([_report(["x[0]"], ["y.z"]), _report(["y.z", "x[0]"], ["w"])])
    assert sorted(c.expression for c in sent) == ["x[0]", "y.z"]
    assert [h["expression"] for h in held] == ["w"]
