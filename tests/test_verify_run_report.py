import subprocess
import sys

from research_pipeline.verify.pytest_gen import replay_pytest
from research_pipeline.verify.run_report import render_run_report

DIV = '''def ratio(total, count):
    return total // count


def main() -> None:
    total: int = nondet_int()
    count: int = nondet_int()
    ratio(total, count)


main()
'''


def _result(verdict, reason="", function="f", **extra):
    return {"verdict": verdict, "reason": reason,
            "hypothesis": {"file": "dataset/x.py", "function": function, "suspect_expression": "a // b", "line": 3},
            **extra}


def _passes(tmp_path, harness, replay, spans=((2, 2),), target=(1, 2)):
    test = replay_pytest(harness, "ratio", replay, spans=spans, target=target)
    (tmp_path / "test_replay.py").write_text(test, encoding="utf-8")
    done = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "test_replay.py"],
                          cwd=tmp_path, capture_output=True, text=True, check=False)
    return done.returncode == 0


def test_replay_pytest_fails_on_the_buggy_harness(tmp_path):
    assert _passes(tmp_path, DIV, {"status": "reproduced", "exception_type": "ZeroDivisionError", "inputs": [1, 0]})


def test_replay_pytest_rebuilds_nondet_lists(tmp_path):
    harness = DIV.replace("    total: int = nondet_int()", "    xs: list = nondet_list(3, 0)\n    total: int = len(xs)") \
        .replace("main() -> None:", "main() -> None:")
    replay = {"status": "reproduced", "exception_type": "ZeroDivisionError", "inputs": [2, 5, 6, 0]}
    assert _passes(tmp_path, harness, replay)


def test_replay_pytest_keeps_nan_inputs(tmp_path):
    harness = DIV.replace("total: int = nondet_int()", "total: float = nondet_float()")
    replay = {"status": "reproduced", "exception_type": "ZeroDivisionError", "inputs": [float("nan"), 0]}
    assert _passes(tmp_path, harness, replay)


def test_replay_pytest_fails_when_the_exception_moves(tmp_path):
    replay = {"status": "reproduced", "exception_type": "ZeroDivisionError", "inputs": [1, 1]}
    assert not _passes(tmp_path, DIV, replay)


def test_replay_pytest_is_none_without_inputs():
    assert replay_pytest(DIV, "ratio", {}, spans=((2, 2),), target=(1, 2)) is None


def test_report_lists_confirmed_first_with_their_test():
    report = render_run_report([_result("UNSUPPORTED", "ERROR: x"),
                                _result("CONFIRMED", "uncaught exception: TypeError", function="g",
                                        pytest={"status": "reproduces", "path": "cases/a/test_replay.py"},
                                        replay={"exception_type": "TypeError", "inputs": [""]})])
    sections = [line for line in report.splitlines() if line.startswith("## ")]
    assert sections[0].startswith("## Confirmados isolados (1)")
    assert "cases/a/test_replay.py" in report.split(sections[1])[0]


def test_report_counts_false_positives():
    report = render_run_report([_result("FIXED_ALSO_FAILS"), _result("BEHAVIOUR_CHANGED"), _result("CONFIRMED")])
    sections = [line for line in report.splitlines() if line.startswith("## ")]
    assert "## Falsos positivos barrados pelos controles (2)" in sections


def test_report_groups_llm_suspicions_by_limit():
    report = render_run_report([_result("UNSUPPORTED", "ERROR: unsupported: calling method"),
                                _result("BOUND_INCONCLUSIVE", "unwinding assertion loop 3")])
    suspicions = report.split("## Suspeitas do LLM")[1]
    assert "esbmc_language" in suspicions and "esbmc_bound" in suspicions
    assert "unwinding assertion loop 3" in suspicions


def test_report_keeps_harness_defects_apart_from_esbmc_limits():
    report = render_run_report([_result("HARNESS_BROKEN", "under CPython, harness.py raises NameError at line 3")])
    assert "### harness_broken (1)" in report and "esbmc_" not in report


def test_report_lists_held_findings_apart_and_never_as_confirmed():
    held = [{"file": "dataset/x.py", "function": "g", "expression": "round(x)", "explanation": "wrong rounding"}]
    report = render_run_report([_result("CONFIRMED")], held=held)
    section = report.split("## Suspeitas do LLM que o ESBMC não verifica (1)")[1]
    assert "`x.py::g`" in section and "round(x)" in section and "wrong rounding" in section
    assert report.index("## Confirmados isolados (1)") < report.index("## Suspeitas do LLM que o ESBMC não verifica")


def test_simplified_confirmations_are_not_counted_as_confirmed():
    report = render_run_report([_result("CONFIRMED"), _result("CONFIRMED_SIMPLIFIED", "body changed")])
    assert "## Confirmados isolados (1)" in report and "1 confirmadas pelo ESBMC (isoladas)" in report
    section = report.split("## Confirmados em código simplificado (1)")[1].split("## ")[0]
    assert "body changed" in section


def test_confirmed_are_listed_by_evidence_with_the_audit_note():
    weak = _result("CONFIRMED", function="weak", replay={"exception_type": "KeyError", "inputs": []})
    strong = _result("CONFIRMED", function="strong", replay={"exception_type": "ZeroDivisionError", "inputs": [0]},
                     pytest={"status": "reproduces", "path": "t.py"}, control={"status": "not_reproduced"},
                     differential={"level": "real", "preservation": "preservada"})
    text = render_run_report([weak, strong])
    assert text.index("strong") < text.index("weak")
    assert "evidência: teste, versão corrigida passa, diferencial real" in text
    assert "auditoria manual" in text


def test_report_names_files_relative_to_the_scanned_root():
    def at(path):
        r = _result("CONFIRMED", replay={"exception_type": "KeyError", "inputs": []})
        r["hypothesis"]["file"] = path
        return r

    held = [{"file": "/repo/pkg/b/__init__.py", "function": "g", "expression": "x", "explanation": "y"}]
    text = render_run_report([at("/repo/pkg/a/__init__.py")], held=held, root="/repo")
    assert "`pkg/a/__init__.py::f`" in text and "`pkg/b/__init__.py::g`" in text
    assert "`__init__.py::f`" in render_run_report([at("/repo/pkg/a/__init__.py")])


def test_an_unavailable_or_failing_control_is_not_evidence():
    from research_pipeline.verify.run_report import evidence
    for status in ("unavailable", "other_failure", "property_violated", "reproduced"):
        assert evidence(_result("CONFIRMED", control={"status": status})) == []
    assert evidence(_result("CONFIRMED", control={"status": "not_reproduced"})) == ["versão corrigida passa"]


def test_cpython_only_reproductions_are_listed_below_esbmc_confirmations():
    cpython = _result("REPRODUCED_CPYTHON", "ESBMC reached no decision", function="g",
                      replay={"exception_type": "KeyError", "inputs": ["k"]}, pytest={"status": "reproduces", "path": "t.py"})
    report = render_run_report([_result("CONFIRMED"), cpython])
    assert "1 confirmadas pelo ESBMC (isoladas)" in report and "1 reproduzidas só no CPython" in report
    section = report.split("## Reproduzidos só no CPython (1)")[1].split("## ")[0]
    assert "x.py::g" in section and "KeyError" in section and "t.py" in section
    assert report.index("## Confirmados isolados (1)") < report.index("## Reproduzidos só no CPython")
    assert "x.py::g" not in report.split("## Suspeitas do LLM")[1]
