from dataclasses import replace

import pytest

from research_pipeline.models import ESBMCDirectResult
from research_pipeline.verify.outcome import (
    CHECKED,
    ESBMC_MISSED,
    ESBMC_TIMEOUT,
    NOT_CONFIRMED,
    OTHER_FAILURE,
    PROPERTY_REJECTED,
    UNVALIDATED,
    VALUE_CONFIRMED,
    VALUE_VIOLATION,
    VERDICTS,
    EsbmcReading,
)
from research_pipeline.verify.render import Program
from research_pipeline.verify.replay import ReplayVerdict, concrete_replay
from research_pipeline.verify.value_oracle import (
    apply_control,
    check_fixed,
    control_program,
    esbmc_hits_property,
    value_verdict,
)

VALUE = '''def magnitude(x):
    return x if x > 0 else x


def _esbmc_main() -> None:
    x: int = nondet_int()
    _esbmc_result: int = magnitude(x)
    assert _esbmc_result >= 0


_esbmc_main()
'''
FIXED = "def magnitude(x):\n    # the fix\n    return x if x > 0 else -x\n"
PROPERTY_LINE = 8


def _program():
    return Program(VALUE, 5, ((2, 2),), (), (1, 2), property_line=PROPERTY_LINE)


VIOLATION, SAFE, TIMEOUT = EsbmcReading("violation", "assertion"), EsbmcReading("safe", ""), EsbmcReading("timeout", "")


@pytest.mark.parametrize(("reading", "hit", "status", "expected"), [
    (VIOLATION, True, "property_violated", VALUE_VIOLATION),
    (VIOLATION, False, "property_violated", UNVALIDATED),
    (VIOLATION, True, "other_failure", OTHER_FAILURE),
    (VIOLATION, True, "reproduced", OTHER_FAILURE),
    (VIOLATION, True, "not_reproduced", UNVALIDATED),
    (SAFE, False, "property_violated", ESBMC_MISSED),
    (SAFE, False, "not_reproduced", NOT_CONFIRMED),
    (TIMEOUT, False, "unavailable", ESBMC_TIMEOUT),
])
def test_value_verdict(reading, hit, status, expected):
    assert value_verdict(reading, hit, ReplayVerdict(status)) == expected


@pytest.mark.parametrize(("verdict", "control", "expected"), [
    (VALUE_VIOLATION, ReplayVerdict("property_violated"), PROPERTY_REJECTED),
    (VALUE_VIOLATION, ReplayVerdict("not_reproduced"), VALUE_CONFIRMED),
    (VALUE_VIOLATION, ReplayVerdict("reproduced", "ValueError"), VALUE_VIOLATION),
    (VALUE_VIOLATION, ReplayVerdict("unavailable", reason="discarded"), VALUE_VIOLATION),
    (VALUE_VIOLATION, None, VALUE_VIOLATION),
    (NOT_CONFIRMED, ReplayVerdict("not_reproduced"), NOT_CONFIRMED),
])
def test_control_needs_a_clean_run_of_the_fixed_version(verdict, control, expected):
    assert apply_control(verdict, control)[0] == expected


def _esbmc(records):
    return ESBMCDirectResult(source_file="p.py", status="violation_found", command=["esbmc"], returncode=1,
                             summary="", details={"violated_property_records": records})


def test_esbmc_hits_only_the_assert_at_the_property_line():
    assert esbmc_hits_property(_esbmc([{"kind": "assertion", "line": 8}]), 8)
    assert not esbmc_hits_property(_esbmc([{"kind": "assertion", "line": 2}]), 8)
    assert not esbmc_hits_property(_esbmc([{"kind": "division by zero", "line": 8}]), 8)
    assert not esbmc_hits_property(_esbmc([{"kind": "unwinding assertion loop 1", "line": 8}]), 8)
    assert not esbmc_hits_property(_esbmc([]), 8)


def test_the_fixed_function_replaces_the_target_and_moves_the_property_line():
    control = control_program(_program(), "magnitude", FIXED)
    assert control.property_line == PROPERTY_LINE + 1
    assert control.source.splitlines()[control.property_line - 1] == "    assert _esbmc_result >= 0"
    assert "else -x" in control.source and "else x\n" not in control.source
    assert concrete_replay(control, "magnitude", inputs=[-1]).status == "not_reproduced"
    # The swap works on the replay copy, so it starts from the replay's property line.
    grown = replace(_program(), property_line=PROPERTY_LINE + 2, replay_property_line=PROPERTY_LINE)
    assert control_program(grown, "magnitude", FIXED).property_line == PROPERTY_LINE + 1


def test_a_fixed_file_without_the_function_gives_no_control():
    assert control_program(_program(), "magnitude", "def other():\n    pass\n") is None
    assert check_fixed(_program(), "magnitude", "magnitude", "def other():\n    pass\n", [-1]).status == "unavailable"


def test_no_inputs_means_no_control():
    assert check_fixed(_program(), "magnitude", "magnitude", FIXED, None).status == "unavailable"


def test_new_verdict_names_do_not_collide():
    existing = {"CONFIRMED", "ESBMC_MISSED", "UNVALIDATED", "OTHER_FAILURE", "NOT_CONFIRMED", "GROUNDING_FAILED",
                "MISSING_DEPENDENCY", "UNSUPPORTED", "SPEC_FAILED", "ESBMC_TIMEOUT", "ESBMC_ERROR",
                "PIPELINE_ERROR", "NO_SOURCE", "AGENT_FAILED", "CONFIRMED_SIMPLIFIED", "STUB_INDUCED",
                "FIXED_ALSO_FAILS", "FUZZ_FOUND", "FUZZ_OTHER", "FUZZ_NOTHING", "FUZZ_UNAVAILABLE", "PINNED_SAFE",
                "PINNED_UNAVAILABLE", "LLM_INPUT_NOTHING", "LLM_INPUT_UNAVAILABLE", "ARM_FAILED", "TARGET_ALTERED"}
    new = {VALUE_VIOLATION, VALUE_CONFIRMED, PROPERTY_REJECTED}
    assert len(new) == 3 and new.isdisjoint(existing)
    assert new <= set(VERDICTS) and new <= CHECKED


def test_an_assertion_of_an_esbmc_model_at_the_same_line_is_not_the_property():
    model = {"kind": "assertion", "line": 8, "file": "/esbmc-vfs/models/builtins.py"}
    assert not esbmc_hits_property(_esbmc([model]), 8)
    assert esbmc_hits_property(_esbmc([{**model, "file": "/tmp/work/program.py"}]), 8)


def test_a_fixed_file_that_leaves_the_target_unchanged_gives_no_control():
    # The fix is elsewhere (a helper): rerunning the same function says nothing about the property.
    same = "def helper():\n    return 1\n\n\n" + VALUE.split("\n\n\n")[0] + "\n"
    verdict = check_fixed(_program(), "magnitude", "magnitude", same, [-1])
    assert verdict.status == "unavailable" and "unchanged" in verdict.reason
    assert apply_control(VALUE_VIOLATION, verdict)[0] == VALUE_VIOLATION


def test_a_wrapping_decorator_of_the_fixed_function_stays_out_of_the_control():
    # Grounding blanked the decorator in the buggy copy; its definition is not in the program.
    fixed = "@memoize\ndef magnitude(x):\n    return x if x > 0 else -x\n"
    control = control_program(_program(), "magnitude", fixed)
    assert "@memoize" not in control.source
    assert control.source.splitlines()[control.property_line - 1] == "    assert _esbmc_result >= 0"
    assert check_fixed(_program(), "magnitude", "magnitude", fixed, [-1]).status == "not_reproduced"


BOX = '''class Box:
    def __init__(self):
        self.v = 0

    def size(self):
        return self.v - 1


def _esbmc_main() -> None:
    _receiver = Box()
    _esbmc_result: int = _receiver.size()
    assert _esbmc_result >= 0


_esbmc_main()
'''
BOX_FIXED = '''class Box:
    def __init__(self):
        self.v = 0

    @staticmethod
    def unit():
        return 1

    @property
    def size(self):
        return self.v
'''


def test_a_property_decorator_is_dropped_but_binding_decorators_stay():
    program = Program(BOX, 9, ((6, 6),), (), (5, 6), property_line=12)
    assert check_fixed(program, "Box.size", "size", BOX_FIXED, []).status == "not_reproduced"
    static = BOX_FIXED.replace("    @property\n    def size(self):\n        return self.v\n",
                               "    @staticmethod\n    def size():\n        return 0\n")
    assert "    @staticmethod\n    def size():" in control_program(program, "Box.size", static).source


def test_annotations_the_harness_added_do_not_hide_an_unchanged_target():
    annotated = replace(_program(), source=VALUE.replace("def magnitude(x):", "def magnitude(x: int):"))
    fixed = "def helper():\n    return 2\n\n\n@memoize\ndef magnitude(x):\n    return x if x > 0 else x\n"
    verdict = check_fixed(annotated, "magnitude", "magnitude", fixed, [-1])
    assert verdict.status == "unavailable" and "unchanged" in verdict.reason
    assert apply_control(VALUE_VIOLATION, verdict)[0] == VALUE_VIOLATION
