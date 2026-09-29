import pytest

from research_pipeline.scan.rewrite import parse_rewrite_proposal
from research_pipeline.scan.rewrite_guard import validate_rewrite


def _proposal(source: str, driver: str, before: str, after: str, **overrides):
    data = {
        "rewritten_source": source,
        "driver_source": driver,
        "changes": [{"before": before, "after": after, "reason": "ESBMC compatibility"}],
        "input_cases": [],
        "assumptions": [],
        "oracle_ref": None,
    }
    data.update(overrides)
    return parse_rewrite_proposal(__import__("json").dumps(data))


def _faithful_case():
    original = "def ratio(a, b):\n    return a / b\n"
    rewritten = "def ratio(a: float, b: float):\n    return a / b\n"
    driver = "def main():\n    ratio(nondet_float(), nondet_float())\nmain()\n"
    proposal = _proposal(
        rewritten, driver, "def ratio(a, b):", "def ratio(a: float, b: float):"
    )
    return original, proposal


def test_faithful_normalization_passes():
    original, proposal = _faithful_case()
    report = validate_rewrite(
        original, proposal, function="ratio", expression="a / b",
        category="division_by_zero",
    )
    assert report.ok
    assert report.suspect_rewrite_line == 2
    assert report.risk == "structural"


def test_undeclared_change_is_rejected():
    original, proposal = _faithful_case()
    changed = proposal.rewritten_source.replace("a / b", "a // b")
    proposal = _proposal(
        changed, proposal.driver_source,
        "def ratio(a, b):", "def ratio(a: float, b: float):",
    )
    report = validate_rewrite(
        original, proposal, function="ratio", expression="a / b",
        category="division_by_zero",
    )
    assert not report.ok
    assert any("manifest" in reason for reason in report.reasons)


def test_removed_suspect_expression_is_rejected():
    original, proposal = _faithful_case()
    rewritten = "def ratio(a: float, b: float):\n    return a + b\n"
    proposal = _proposal(
        rewritten, proposal.driver_source,
        "def ratio(a, b):", "def ratio(a: float, b: float):",
    )
    report = validate_rewrite(
        original, proposal, function="ratio", expression="a / b",
        category="division_by_zero",
    )
    assert not report.ok
    assert any("suspect" in reason for reason in report.reasons)


def test_duplicate_suspect_is_ambiguous():
    original = "def ratio(a, b):\n    first = a / b\n    return a / b\n"
    rewritten = "def ratio(a: float, b: float):\n    first = a / b\n    return a / b\n"
    proposal = _proposal(
        rewritten, "def main():\n    ratio(1.0, 2.0)\nmain()\n",
        "def ratio(a, b):", "def ratio(a: float, b: float):",
    )
    report = validate_rewrite(
        original, proposal, function="ratio", expression="a / b",
        category="division_by_zero",
    )
    assert not report.ok
    assert any("ambiguous" in reason for reason in report.reasons)


def test_driver_assert_and_unbound_nondet_are_rejected():
    original, proposal = _faithful_case()
    unsafe_driver = (
        "def main():\n"
        "    choice = nondet_float()\n"
        "    assert choice != 0\n"
        "    ratio(1.0, 2.0)\n"
        "main()\n"
    )
    proposal = _proposal(
        proposal.rewritten_source, unsafe_driver,
        "def ratio(a, b):", "def ratio(a: float, b: float):",
    )
    report = validate_rewrite(
        original, proposal, function="ratio", expression="a / b",
        category="division_by_zero",
    )
    assert not report.ok
    assert any("assert" in reason or "nondet" in reason for reason in report.reasons)


def test_undefined_name_is_rejected():
    original, proposal = _faithful_case()
    rewritten = "def ratio(a: float, b: float):\n    return missing_helper(a) / b\n"
    proposal = _proposal(
        rewritten, proposal.driver_source,
        "def ratio(a, b):", "def ratio(a: float, b: float):",
    )
    report = validate_rewrite(
        original, proposal, function="ratio", expression="missing_helper(a) / b",
        category="division_by_zero",
    )
    assert not report.ok
    assert any("undefined" in reason for reason in report.reasons)


def test_changed_precondition_is_rejected():
    original = "def ratio(a, b):\n    if b != 0:\n        return a / b\n    return 0\n"
    rewritten = "def ratio(a: float, b: float):\n    if b > 0:\n        return a / b\n    return 0\n"
    proposal = _proposal(
        rewritten, "def main():\n    ratio(1.0, 2.0)\nmain()\n",
        "def ratio(a, b):", "def ratio(a: float, b: float):",
    )
    report = validate_rewrite(
        original, proposal, function="ratio", expression="a / b",
        category="division_by_zero",
    )
    assert not report.ok
    assert any("control" in reason for reason in report.reasons)


def test_untrusted_llm_oracle_is_rejected():
    original, proposal = _faithful_case()
    proposal = _proposal(
        proposal.rewritten_source, proposal.driver_source,
        "def ratio(a, b):", "def ratio(a: float, b: float):",
        oracle_ref="the-model-says-this-is-correct",
    )
    report = validate_rewrite(
        original, proposal, function="ratio", expression="a / b",
        category="division_by_zero",
    )
    assert not report.ok
    assert any("oracle" in reason for reason in report.reasons)


def _annotated(original: str, before: str, after: str, driver: str, **kwargs):
    rewritten = original.replace(before, after, 1)
    return validate_rewrite(original, _proposal(rewritten, driver, before, after), **kwargs)


RATIO_DRIVER = "def main():\n    ratio(nondet_float(), nondet_float())\nmain()\n"


def test_suspect_moved_into_guarded_branch_is_rejected():
    original = "def ratio(a, b):\n    if b != 0:\n        return 0\n    return a / b\n"
    rewritten = "def ratio(a, b):\n    if b != 0:\n        return a / b\n    return 0\n"
    proposal = _proposal(
        rewritten, RATIO_DRIVER,
        "        return 0\n    return a / b", "        return a / b\n    return 0",
    )
    report = validate_rewrite(
        original, proposal, function="ratio", expression="a / b", category="division_by_zero",
    )
    assert not report.ok
    assert any("control" in reason for reason in report.reasons)


def test_suspect_moved_out_of_loop_is_rejected():
    original = "def ratio(a, b):\n    for _ in range(a):\n        a / b\n    return 0\n"
    rewritten = "def ratio(a, b):\n    for _ in range(a):\n        pass\n    a / b\n    return 0\n"
    proposal = _proposal(
        rewritten, RATIO_DRIVER,
        "        a / b\n    return 0", "        pass\n    a / b\n    return 0",
    )
    report = validate_rewrite(
        original, proposal, function="ratio", expression="a / b", category="division_by_zero",
    )
    assert not report.ok
    assert any("control" in reason for reason in report.reasons)


def test_subscript_suspect_is_recognized():
    report = _annotated(
        "def pick(items, i):\n    return items[i]\n",
        "def pick(items, i):", "def pick(items: list[int], i: int):",
        "def main():\n    pick([1, 2], nondet_int())\nmain()\n",
        function="pick", expression="items[i]", category="out_of_bounds",
    )
    assert report.ok, report.reasons
    assert report.suspect_rewrite_line == 2


def test_attribute_call_suspect_is_recognized():
    report = _annotated(
        "def first(items):\n    return items.pop(0)\n",
        "def first(items):", "def first(items: list[int]):",
        "def main():\n    first([nondet_int()])\nmain()\n",
        function="first", expression="items.pop(0)", category="out_of_bounds",
    )
    assert report.ok, report.reasons


METHOD_SOURCE = "class C:\n    def f(self, x):\n        return 10 // x\n"


@pytest.mark.parametrize("driver", [
    "def main():\n    C().f(nondet_int())\nmain()\n",
    "def main():\n    obj = C()\n    obj.f(nondet_int())\nmain()\n",
])
def test_method_driver_on_instance_is_accepted(driver):
    report = _annotated(
        METHOD_SOURCE, "def f(self, x):", "def f(self, x: int):", driver,
        function="C.f", expression="10 // x", category="division_by_zero",
    )
    assert report.ok, report.reasons


def test_method_driver_on_unrelated_object_is_rejected():
    driver = "class D:\n    def f(self, x):\n        return x\n\ndef main():\n    D().f(nondet_int())\nmain()\n"
    report = _annotated(
        METHOD_SOURCE, "def f(self, x):", "def f(self, x: int):", driver,
        function="C.f", expression="10 // x", category="division_by_zero",
    )
    assert not report.ok
    assert any("exactly once" in reason for reason in report.reasons)


@pytest.mark.parametrize("guarded", [
    "a / b if b else 0.0",
    "b and a / b",
])
def test_suspect_wrapped_in_expression_guard_is_rejected(guarded):
    original = "def ratio(a, b):\n    return a / b\n"
    rewritten = f"def ratio(a, b):\n    return {guarded}\n"
    proposal = _proposal(rewritten, RATIO_DRIVER, "    return a / b", f"    return {guarded}")
    report = validate_rewrite(
        original, proposal, function="ratio", expression="a / b", category="division_by_zero",
    )
    assert not report.ok
    assert any("control" in reason for reason in report.reasons)


def test_bare_reraise_does_not_crash_guard():
    original = "def ratio(a, b):\n    try:\n        return a / b\n    except ValueError:\n        raise\n"
    report = _annotated(
        original, "def ratio(a, b):", "def ratio(a: float, b: float):", RATIO_DRIVER,
        function="ratio", expression="a / b", category="division_by_zero",
    )
    assert report.ok, report.reasons


def test_nondet_bound_to_local_passed_to_target_is_connected():
    driver = "def main():\n    a: float = nondet_float()\n    b = nondet_float()\n    ratio(a, b)\nmain()\n"
    report = _annotated(
        "def ratio(a, b):\n    return a / b\n", "def ratio(a, b):", "def ratio(a: float, b: float):", driver,
        function="ratio", expression="a / b", category="division_by_zero",
    )
    assert report.ok, report.reasons


@pytest.mark.parametrize("driver", [
    "def main():\n    a = nondet_float()\n    ratio(1.0, 2.0)\nmain()\n",
    "def main():\n    a = nondet_float()\n    a = nondet_float()\n    ratio(a, 2.0)\nmain()\n",
    "def main():\n    a = nondet_float()\n    ratio(a + 1.0, 2.0)\nmain()\n",
])
def test_nondet_local_not_passed_directly_is_disconnected(driver):
    report = _annotated(
        "def ratio(a, b):\n    return a / b\n", "def ratio(a, b):", "def ratio(a: float, b: float):", driver,
        function="ratio", expression="a / b", category="division_by_zero",
    )
    assert not report.ok
    assert any("disconnected" in reason for reason in report.reasons)


@pytest.mark.parametrize("driver", [
    "SCALE = 0\ndef main():\n    ratio(nondet_float(), nondet_float())\nmain()\n",
    "def ratio(a, b):\n    return a / 0\ndef main():\n    ratio(nondet_float(), nondet_float())\nmain()\n",
    "def main():\n    global SCALE\n    SCALE = 0\n    ratio(nondet_float(), nondet_float())\nmain()\n",
    "def main():\n    def ratio(a, b):\n        return a / 0\n    ratio(nondet_float(), nondet_float())\nmain()\n",
])
def test_driver_cannot_shadow_or_rebind_module_names(driver):
    report = _annotated(
        "SCALE = 1.0\n\n\ndef ratio(a, b):\n    return a / b\n",
        "def ratio(a, b):", "def ratio(a: float, b: float):", driver,
        function="ratio", expression="a / b", category="division_by_zero",
    )
    assert not report.ok
    assert any("driver" in reason for reason in report.reasons)
