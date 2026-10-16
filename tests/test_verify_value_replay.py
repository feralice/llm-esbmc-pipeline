from research_pipeline.verify.render import Program
from research_pipeline.verify.replay import concrete_replay

VALUE = '''def magnitude(x):
    return x if x > 0 else x


def _esbmc_main() -> None:
    x: int = nondet_int()
    _esbmc_result: int = magnitude(x)
    assert _esbmc_result >= 0


_esbmc_main()
'''
ASSERT = "    assert _esbmc_result >= 0"


def _program(source, spans=((2, 2),), with_property=True):
    lines = source.splitlines()
    end = lines.index("def _esbmc_main() -> None:") - 2
    return Program(source, lines.index("def _esbmc_main() -> None:") + 1, spans, (), (1, end),
                   property_line=lines.index(ASSERT) + 1 if with_property else 0)


def test_the_search_finds_an_input_that_violates_the_property():
    program = _program(VALUE)
    verdict = concrete_replay(program, "magnitude")
    assert (verdict.status, verdict.line, verdict.inputs) == ("property_violated", program.property_line, [-1])
    assert verdict.exception_type == "AssertionError"


def test_the_fixed_function_keeps_the_property():
    fixed = VALUE.replace("else x\n", "else -x\n")
    assert concrete_replay(_program(fixed), "magnitude").status == "not_reproduced"


def test_fixed_inputs_run_once():
    assert concrete_replay(_program(VALUE), "magnitude", inputs=[-1]).status == "property_violated"
    assert concrete_replay(_program(VALUE), "magnitude", inputs=[2]).status == "not_reproduced"


def test_an_assert_inside_the_target_is_not_the_property():
    inner = VALUE.replace("    return x if x > 0 else x", "    assert x >= 0\n    return x if x > 0 else x")
    verdict = concrete_replay(_program(inner, spans=((3, 3),)), "magnitude")
    assert verdict.status == "other_failure" and verdict.line == 2


def test_without_a_property_line_a_driver_assert_stays_other_failure():
    assert concrete_replay(_program(VALUE, with_property=False), "magnitude").status == "other_failure"


def test_a_discarded_fixed_run_is_unavailable_with_a_property():
    assumed = VALUE.replace("    x: int = nondet_int()\n", "    x: int = nondet_int()\n    __ESBMC_assume(x != -1)\n")
    assert concrete_replay(_program(assumed), "magnitude", inputs=[-1]).status == "unavailable"


def test_a_property_violation_claimed_at_another_line_is_not_trusted(monkeypatch):
    import json
    import subprocess

    from research_pipeline.verify import replay

    def fake_run(command, cwd, **_):
        (cwd / command[-1]).write_text(json.dumps({"status": "property_violated", "line": 2, "inputs": [-1]}))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(replay.subprocess, "run", fake_run)
    monkeypatch.setattr(replay, "_no_network_prefix", lambda: ())
    assert concrete_replay(_program(VALUE), "magnitude").status == "unavailable"
