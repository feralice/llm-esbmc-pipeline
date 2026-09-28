from __future__ import annotations

import pytest

from research_pipeline.scan.compat import (
    exclude_nan_inputs,
    EXPECTED_PROPERTY_MARKER,
    VERDICT_INVALID,
    VERDICT_OK,
    VERDICT_UNSUPPORTED,
    check_harness,
    check_outcome_grounding,
    undefined_names,
)

_GOOD = """\
def div_core(a: int, b: int) -> int:
    __ESBMC_assume(b >= 0)
    __ESBMC_assume(b <= 100)
    assert b != 0, "LLM_ESBMC_EXPECTED_PROPERTY"
    return a // b


def main() -> None:
    div_core(nondet_int(), nondet_int())


main()
"""


def test_good_harness_passes():
    r = check_harness(_GOOD)
    assert r.ok
    assert r.verdict == VERDICT_OK
    assert r.reasons == []


def test_syntax_error_is_invalid():
    r = check_harness("def f(:\n    return 1\n")
    assert not r.ok
    assert r.verdict == VERDICT_INVALID
    assert "does not parse" in r.reasons[0]


def test_any_import_is_invalid():
    r = check_harness("import math\n\ndef f(x: int) -> int:\n    return x\nf(nondet_int())\n")
    assert not r.ok
    assert r.verdict == VERDICT_INVALID
    assert "imports math" in r.reasons[0]


def test_from_import_is_invalid():
    src = "from collections import deque\n\ndef f(x: int) -> int:\n    return x\nf(1)\n"
    r = check_harness(src)
    assert r.verdict == VERDICT_INVALID


def test_numpy_reference_is_unsupported():
    src = (
        "def f(n: int) -> int:\n"
        "    a = np.zeros(n)\n"
        "    return len(a)\n"
        "f(nondet_int())\n"
    )
    r = check_harness(src)
    assert not r.ok
    assert r.verdict == VERDICT_UNSUPPORTED
    assert "np" in r.reasons[0]


def test_missing_module_level_driver_is_invalid():
    src = "def f(a: int, b: int) -> int:\n    return a // b\n"
    r = check_harness(src)
    assert not r.ok
    assert r.verdict == VERDICT_INVALID
    assert "module-level driver" in r.reasons[0]


def test_if_name_main_counts_as_driver():
    src = (
        "def f(a: int, b: int) -> int:\n"
        "    assert b != 0, 'LLM_ESBMC_EXPECTED_PROPERTY'\n"
        "    return a // b\n\n"
        "if __name__ == '__main__':\n    f(nondet_int(), nondet_int())\n"
    )
    assert check_harness(src).ok


def test_loop_is_invalid_before_builtin_compatibility():
    src = (
        "def f(xs: list, ys: list) -> int:\n"
        "    for a, b in zip(xs, ys):\n"
        "        pass\n"
        "    return 0\n"
        "f([1, 2], [3, 4])\n"
    )
    r = check_harness(src)
    assert not r.ok
    assert r.verdict == VERDICT_INVALID
    assert "loop" in r.reasons[0]


def test_enumerate_loop_is_invalid_for_scan_protocol():
    src = (
        "def f(xs: list) -> int:\n"
        "    for i, v in enumerate(xs):\n"
        "        pass\n"
        "    return 0\n"
        "f([1, 2])\n"
    )
    r = check_harness(src)
    assert not r.ok
    assert r.verdict == VERDICT_INVALID
    assert "loop" in r.reasons[0]


def test_loop_free_unsupported_builtin_is_reported():
    src = (
        "def f(xs: list, ys: list) -> object:\n"
        "    return zip(xs, ys)\n"
        "f([1, 2], [3, 4])\n"
    )
    r = check_harness(src)
    assert not r.ok
    assert r.verdict == VERDICT_UNSUPPORTED
    assert "zip" in r.reasons[0]


def test_hallucinated_nondet_name_is_invalid():
    src = (
        "def f(a: int, b: int) -> int:\n"
        "    assert b != 0\n"
        "    return a // b\n"
        "f(__ESBMC_nondet_int(), __ESBMC_nondet_int())\n"
    )
    r = check_harness(src)
    assert not r.ok
    assert r.verdict == VERDICT_INVALID
    assert "nondet" in r.reasons[0]


def test_real_intrinsic_names_pass():
    assert check_harness(_GOOD).ok


def test_assume_alias_is_allowed():
    src = _GOOD.replace("__ESBMC_assume", "assume")
    assert check_harness(src).ok


@pytest.mark.parametrize(
    "snippet, expected",
    [
        ("x = lambda y: y\n", "lambda"),
        ("x = (y := 1)\n", "walrus"),
        ("__ESBMC_assert(True, 'x')\n", "outside the scalar harness property profile"),
        ("values.add(1)\n", "unsupported ESBMC-Python method"),
    ],
)
def test_known_esbmc_incompatibilities_are_rejected(snippet: str, expected: str):
    src = (
        "def f(x: int) -> int:\n"
        f"    {snippet}"
        "    assert x != 0, 'LLM_ESBMC_EXPECTED_PROPERTY'\n"
        "    return x\n"
        "f(nondet_int())\n"
    )
    result = check_harness(src)
    assert not result.ok
    assert expected in " ".join(result.reasons)


def test_esbmc_cover_is_allowed_alongside_marked_assert():
    """__ESBMC_cover compiles to assert(!cond), a Call node distinct from the
    ast.Assert the marker check counts, and --multi-property (esbmc_runner.py)
    reports it as a separate property from the marked assert - confirmed with
    real ESBMC 8.5.0, 2026-09-12. See docs EXP-01 (commit b18f5de) for the
    --multi-property side of this guarantee."""
    src = (
        "def f(x: int) -> int:\n"
        "    __ESBMC_cover(x == 0)\n"
        "    assert x != 0, 'LLM_ESBMC_EXPECTED_PROPERTY'\n"
        "    return x\n"
        "f(nondet_int())\n"
    )
    result = check_harness(src)
    assert result.ok, result.reasons


def test_esbmc_cover_is_still_rejected_for_loop_style():
    """allow_bounded_loop=True is the loop harness style. synth_prompt_loop.txt
    rule 9 forbids __ESBMC_cover there (the bounded loop already forces every
    iteration), and unlike the scalar style, cover-in-a-loop was never proven
    safe against --multi-property's cover/marker separation - only the scalar
    case was (see test_esbmc_cover_is_allowed_alongside_marked_assert)."""
    src = (
        "def f(xs: list) -> int:\n"
        "    total: int = 0\n"
        "    for i in range(3):\n"
        "        __ESBMC_cover(total == 0)\n"
        "        total = total + xs[i]\n"
        "    assert total != 0, 'LLM_ESBMC_EXPECTED_PROPERTY'\n"
        "    return total\n"
        "f([nondet_int(), nondet_int(), nondet_int()])\n"
    )
    result = check_harness(src, allow_bounded_loop=True)
    assert not result.ok
    assert "outside the scalar harness property profile" in " ".join(result.reasons)


def test_unsupported_esbmc_assigns_is_not_whitelisted():
    src = (
        "def f(x: int) -> int:\n"
        "    __ESBMC_assigns(x)\n"
        "    assert x != 0, 'LLM_ESBMC_EXPECTED_PROPERTY'\n"
        "    return x\n"
        "f(nondet_int())\n"
    )
    result = check_harness(src)
    assert not result.ok
    assert result.verdict == VERDICT_UNSUPPORTED
    assert "__ESBMC_assigns" in " ".join(result.reasons)


def test_undefined_names_ignores_intrinsics_and_builtins():
    assert undefined_names(_GOOD) == set()


def test_undefined_names_flags_unknown_symbol():
    src = "def f(x: int) -> int:\n    return x + MYSTERY_CONST\nf(nondet_int())\n"
    assert "MYSTERY_CONST" in undefined_names(src)


def test_undefined_helper_call_is_invalid():
    """Regression: gpt-4o-mini synth run (2026-09-02) called an unimported project
    helper (safe_url_string) instead of reconstructing the expression with nondet
    scalars; ESBMC then errored internally (tool_error) instead of a clean verdict.
    check_harness() must reject this before it reaches ESBMC.
    """
    src = (
        "def model():\n"
        "    url: str = nondet_str()\n"
        "    encoding: str = nondet_str()\n"
        "    s = safe_url_string(url, encoding)\n"
        "    assert isinstance(s, str), 'LLM_ESBMC_EXPECTED_PROPERTY'\n"
        "def main():\n"
        "    model()\n"
        "main()\n"
    )
    r = check_harness(src)
    assert not r.ok
    assert r.verdict == VERDICT_INVALID
    assert "safe_url_string" in r.reasons[0]


def test_abs_of_symbolic_string_is_invalid():
    src = (
        "def f(x: str) -> int:\n"
        "    y: int = abs(x)\n"
        f"    assert y >= 0, {EXPECTED_PROPERTY_MARKER!r}\n"
        "    return y\n"
        "f(nondet_str())\n"
    )
    r = check_harness(src)
    assert not r.ok
    assert "abs() receives str" in r.reasons[0]


def test_symbolic_integer_subscript_is_invalid():
    src = (
        "def f(x: int) -> int:\n"
        "    y: int = x[0]\n"
        f"    assert y != 0, {EXPECTED_PROPERTY_MARKER!r}\n"
        "    return y\n"
        "f(nondet_int())\n"
    )
    r = check_harness(src)
    assert not r.ok
    assert "subscript non-container" in r.reasons[0]


def test_scalar_attribute_method_is_allowed():
    """Regression: 106-candidate run on 2026-09-03 showed a blanket ban on any
    .method() call rejected cheap, well-modeled string/dict methods (.isdigit,
    .startswith, .get, .join...), not just expensive ones (.split, .replace,
    .partition - documented as costly in dataset/v2_real_world/README.md).
    check_harness() no longer rejects on attribute calls alone; a genuinely
    unsupported method still fails at the ESBMC stage, not here.
    """
    src = (
        "def f(x: str) -> bool:\n"
        "    y: bool = x.isdigit()\n"
        f"    assert y != 0, {EXPECTED_PROPERTY_MARKER!r}\n"
        "    return y\n"
        "f(nondet_str())\n"
    )
    assert check_harness(src).ok


def test_tautological_isinstance_against_own_nondet_type_is_invalid():
    """Regression (EXP-02, empirical probe, 2026-09-04): a parameter
    declared `bool` and fed nondet_bool() can only ever hold True/False in
    ESBMC-Python's static type model, so `isinstance(param, bool)` is always
    True by construction. 6 of 12 safe_on_abstraction results in the
    2026-09-03 diagnosis had this exact shape - a vacuous proof, not a real
    safety result.
    """
    src = (
        "def f() -> None:\n"
        "    param: bool = nondet_bool()\n"
        f"    assert isinstance(param, bool), {EXPECTED_PROPERTY_MARKER!r}\n"
        "f()\n"
    )
    r = check_harness(src)
    assert not r.ok
    assert "always True" in r.reasons[0]


def test_isinstance_against_a_different_type_is_not_flagged():
    """isinstance checking a type OTHER than the target's own declared type is
    a real (if maybe always-false) check, not the always-True tautology this
    rule targets - do not over-reject.
    """
    src = (
        "def f() -> None:\n"
        "    x: int = nondet_int()\n"
        "    y: bool = isinstance(x, str)\n"
        f"    assert y != 0, {EXPECTED_PROPERTY_MARKER!r}\n"
        "f()\n"
    )
    assert check_harness(src).ok


def test_unconstrained_outcome_assertion_is_invalid():
    """Regression (EXP-03, empirical probe, 2026-09-04): a bare boolean
    asserted over a fully unconstrained nondet_str() "confirms" on a fabricated
    input unrelated to the real bug (av_real_12/thefuck#7: `assert "php -s" in
    script` fails on the empty string, which has nothing to do with the actual
    bug about flags separated by other arguments).
    """
    src = (
        "def f() -> bool:\n"
        "    script: str = nondet_str()\n"
        "    matches: bool = \"php -s\" in script\n"
        f"    assert matches, {EXPECTED_PROPERTY_MARKER!r}\n"
        "    return matches\n"
        "f()\n"
    )
    r = check_harness(src, category="assertion_violation")
    assert not r.ok
    assert "unconstrained" in r.reasons[0]


def test_unconstrained_outcome_assertion_passes_with_assume():
    """An __ESBMC_assume restricting the domain to what the real caller
    guarantees makes the same shape of assertion meaningful again."""
    src = (
        "def f() -> bool:\n"
        "    script: str = nondet_str()\n"
        "    __ESBMC_assume(len(script) > 0)\n"
        "    matches: bool = \"php -s\" in script\n"
        f"    assert matches, {EXPECTED_PROPERTY_MARKER!r}\n"
        "    return matches\n"
        "f()\n"
    )
    assert check_harness(src, category="assertion_violation").ok


def test_unconstrained_outcome_assertion_passes_with_oracle_comparison():
    """Comparing the buggy expression against an explicit expected value (the
    pattern used in dataset/v2_real_world/bugs/*.py) is the other accepted way
    to ground the assertion, with no assume required."""
    src = (
        "def f() -> None:\n"
        "    script: str = nondet_str()\n"
        "    buggy: bool = \"php -s\" in script\n"
        "    correct: bool = \" -s \" in script\n"
        f"    assert buggy == correct, {EXPECTED_PROPERTY_MARKER!r}\n"
        "f()\n"
    )
    assert check_harness(src, category="assertion_violation").ok


def test_unconstrained_outcome_assertion_rejects_hardcoded_comparison():
    """Regression (EXP-03 re-run, empirical probe, 2026-09-04): codex's
    retry after the first version of this rule wrapped the same vacuous
    assertion in `expected: bool = True; assert matched == expected` - passes
    a naive "is it a Compare" check but is exactly as vacuous as the bare
    assert it replaced, since `expected` is a hardcoded constant, not a real
    correct-value computation.
    """
    src = (
        "def f() -> bool:\n"
        "    script: str = nondet_str()\n"
        "    expected: bool = True\n"
        "    matched: bool = \"php -s\" in script\n"
        f"    assert matched == expected, {EXPECTED_PROPERTY_MARKER!r}\n"
        "    return matched\n"
        "f()\n"
    )
    r = check_harness(src, category="assertion_violation")
    assert not r.ok
    assert "hardcoded constant" in r.reasons[0]


def test_outcome_grounding_accepts_separately_computed_expected_value():
    src = (
        "def f() -> None:\n"
        "    value: int = nondet_int()\n"
        "    result: int = value + 1\n"
        "    expected: int = value - 1\n"
        f"    assert result == expected, {EXPECTED_PROPERTY_MARKER!r}\n"
        "f()\n"
    )
    assert check_outcome_grounding(src).ok


def test_outcome_grounding_rejects_raw_nondet_expected_value():
    src = (
        "def f() -> None:\n"
        "    result: bool = nondet_bool()\n"
        "    expected: bool = nondet_bool()\n"
        f"    assert result == expected, {EXPECTED_PROPERTY_MARKER!r}\n"
        "f()\n"
    )
    r = check_outcome_grounding(src)
    assert not r.ok
    assert "differential assertion" in r.reasons[0]


def test_outcome_grounding_rejects_expected_value_derived_from_result():
    src = (
        "def f() -> None:\n"
        "    value: int = nondet_int()\n"
        "    result: int = value + 1\n"
        "    expected: int = result + 1\n"
        f"    assert result == expected, {EXPECTED_PROPERTY_MARKER!r}\n"
        "f()\n"
    )
    assert not check_outcome_grounding(src).ok


def test_unconstrained_outcome_check_does_not_apply_to_precondition_categories():
    """invalid_precondition (and none_misuse/variable_misuse/type_mismatch) bugs
    are, by design, "an unchecked precondition lets a bad value through" - a
    bare boolean over unconstrained input IS the correct shape there, not the
    defect this rule targets."""
    src = (
        "def f() -> None:\n"
        "    current_is_none: bool = nondet_bool()\n"
        f"    assert not current_is_none, {EXPECTED_PROPERTY_MARKER!r}\n"
        "f()\n"
    )
    assert check_harness(src, category="invalid_precondition").ok
    assert check_harness(src, category=None).ok


def test_str_coercion_tautology_is_invalid():
    """Regression (real external code, 2026-09-05): synthesized harness for
    tqdm's `_is_utf` (category type_mismatch, not one of the two outcome
    categories) modeled `encoding_is_text: bool = str(encoding) == encoding`
    for `encoding: int` -- always False in real Python regardless of value,
    proving nothing about the hypothesized bug. Not scoped to assertion_
    violation/incorrect_result: this is a general AST-shape defect.
    """
    src = (
        "def f() -> bool:\n"
        "    encoding: int = nondet_int()\n"
        "    encoding_is_text: bool = str(encoding) == encoding\n"
        f"    assert encoding_is_text, {EXPECTED_PROPERTY_MARKER!r}\n"
        "    return encoding_is_text\n"
        "f()\n"
    )
    r = check_harness(src, category="type_mismatch")
    assert not r.ok
    assert "always False" in r.reasons[0]


def test_str_coercion_of_str_typed_value_is_not_flagged():
    """`str(x) == x` is a legitimate (if odd) check when x is already a str --
    only cross-type str-vs-number coercion is the always-False tautology."""
    src = (
        "def f() -> bool:\n"
        "    name: str = nondet_str()\n"
        "    y: bool = str(name) == name\n"
        f"    assert y, {EXPECTED_PROPERTY_MARKER!r}\n"
        "    return y\n"
        "f()\n"
    )
    assert check_harness(src, category="type_mismatch").ok


def test_expected_assertion_marker_is_required():
    src = "def f(x: int) -> None:\n    assert x != 0\nf(nondet_int())\n"
    r = check_harness(src)
    assert not r.ok
    assert "exactly one expected assertion" in r.reasons[0]


_LOOP_HARNESS = """\
def model() -> None:
    a: int = nondet_int()
    b: int = nondet_int()
    c: int = nondet_int()
    __ESBMC_assume(-1000 <= a and a <= 1000)
    __ESBMC_assume(-1000 <= b and b <= 1000)
    __ESBMC_assume(-1000 <= c and c <= 1000)
    __ESBMC_assume(a <= b and b <= c)
    xs: list[int] = [a, b, c]
    for i in range(1, 3):
        gap: int = xs[i] - xs[i - 1]
        assert gap >= 0, "LLM_ESBMC_EXPECTED_PROPERTY"

model()
"""


def test_loop_harness_rejected_without_opt_in():
    r = check_harness(_LOOP_HARNESS, category="incorrect_result")
    assert not r.ok
    assert "loop" in r.reasons[0]


def test_loop_harness_accepted_with_opt_in():
    assert check_harness(
        _LOOP_HARNESS, category="incorrect_result", allow_bounded_loop=True
    ).ok


def test_loop_harness_rejects_while():
    src = _LOOP_HARNESS.replace("for i in range(1, 3):", "while a < b:")
    r = check_harness(src, allow_bounded_loop=True)
    assert not r.ok
    assert "while" in r.reasons[0]


def test_loop_harness_rejects_symbolic_range_bound():
    src = _LOOP_HARNESS.replace("range(1, 3)", "range(1, len(xs))")
    r = check_harness(src, allow_bounded_loop=True)
    assert not r.ok
    assert "int literal" in r.reasons[0]


def test_loop_harness_rejects_second_loop():
    src = _LOOP_HARNESS.replace(
        "model()\n",
        "def other() -> None:\n    for j in range(2):\n        pass\n\nother()\nmodel()\n",
    )
    r = check_harness(src, allow_bounded_loop=True)
    assert not r.ok
    assert "more than one loop" in r.reasons[0]


def test_loop_harness_still_rejects_esbmc_cover():
    """__ESBMC_cover is allowed for scalar style (see
    test_esbmc_cover_is_allowed_alongside_marked_assert). Confirmed with real
    ESBMC 8.5.0 (2026-09-12) that the same cover/marked-assert separation
    also holds inside a bounded for-loop body -- the validator still rejects
    it there because synth_prompt_loop.txt rule 9 calls it redundant once the
    loop is fully unwound, not because it is unsafe."""
    src = _LOOP_HARNESS.replace(
        "gap: int = xs[i] - xs[i - 1]\n",
        "gap: int = xs[i] - xs[i - 1]\n        __ESBMC_cover(gap == 0)\n",
    )
    r = check_harness(src, allow_bounded_loop=True)
    assert not r.ok
    assert "outside the scalar harness property profile" in r.reasons[0]


@pytest.mark.parametrize(
    "container_expr, expected",
    [
        ("[nondet_int() for _ in range(3)]", "comprehension"),
        ("{1: a, 2: b, 3: c}", "dicts or sets"),
        ("{a, b, c}", "dicts or sets"),
        ("[[a], [b], [c]]", "nested list"),
    ],
)
def test_loop_harness_rejects_bad_container_shapes(container_expr: str, expected: str):
    """synth_prompt_loop.txt rule 2 says the container must be a flat list
    literal of fresh nondet_*() values -- nothing enforced this before, so a
    harness violating it would have passed check_harness() and spent a real
    ESBMC call on an undocumented model shape."""
    src = _LOOP_HARNESS.replace("xs: list[int] = [a, b, c]\n", f"xs = {container_expr}\n")
    r = check_harness(src, allow_bounded_loop=True)
    assert not r.ok
    assert expected in " ".join(r.reasons)


_IDENTICAL_SIDES = '''def model():
    vmax: float = nondet_float()
    expander: float = nondet_float()
    buggy: float = vmax + expander * abs(vmax)
    correct: float = vmax + expander * abs(vmax)
    assert buggy == correct, "LLM_ESBMC_EXPECTED_PROPERTY"

def main():
    model()

main()
'''

_CONSTANT_ASSERT = '''def model():
    make_current: bool = nondet_bool()
    __ESBMC_cover(make_current)
    assert False, "LLM_ESBMC_EXPECTED_PROPERTY"

def main():
    model()

main()
'''

_DIFFERENTIAL = '''def model():
    x: int = nondet_int()
    buggy: int = x // 2
    correct: int = (x + 1) // 2
    assert buggy == correct, "LLM_ESBMC_EXPECTED_PROPERTY"

def main():
    model()

main()
'''


@pytest.mark.parametrize(
    ("harness", "reason"),
    [(_IDENTICAL_SIDES, "identical expressions"), (_CONSTANT_ASSERT, "constant False")],
)
def test_vacuous_expected_assertion_is_rejected(harness: str, reason: str) -> None:
    result = check_harness(harness)
    assert not result.ok
    assert reason in result.reasons[0]


def test_differential_expected_assertion_is_accepted() -> None:
    assert check_harness(_DIFFERENTIAL).ok


def test_assumptions_after_expected_assertion_are_rejected() -> None:
    source = '''def model():
    x: int = nondet_int()
    assert x != 0, "LLM_ESBMC_EXPECTED_PROPERTY"
    __ESBMC_assume(x >= 0)

def main():
    model()

main()
'''
    result = check_harness(source)
    assert not result.ok
    assert "after the expected assertion" in " ".join(result.reasons)


def test_unreachable_cover_condition_is_rejected() -> None:
    source = '''def model():
    index: int = 1
    __ESBMC_cover(index < 0)
    assert index >= 0, "LLM_ESBMC_EXPECTED_PROPERTY"

def main():
    model()

main()
'''
    result = check_harness(source)
    assert not result.ok
    assert "cover condition" in " ".join(result.reasons)


def test_exclude_nan_inputs_guards_every_nondet_float() -> None:
    patched = exclude_nan_inputs(_IDENTICAL_SIDES)
    lines = patched.splitlines()
    assert lines[2] == "    __ESBMC_assume(vmax - vmax == 0)"
    assert lines[4] == "    __ESBMC_assume(expander - expander == 0)"
    assert exclude_nan_inputs(_DIFFERENTIAL) == _DIFFERENTIAL
