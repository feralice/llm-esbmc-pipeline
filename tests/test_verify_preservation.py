import ast

import pytest

from research_pipeline.verify.differential import _key
from research_pipeline.verify.round_warnings import round_warnings
from research_pipeline.verify.validation import target_preserved

ORIGINAL = '''def f(xs, n):
    """Doc."""
    total = 0
    for i in range(n):
        if xs[i] > 0:
            total += xs[i]
    if total == 0:
        raise ValueError("empty")
    assert total > 0
    return 10 // total
'''


def _harness(body: str) -> str:
    return body + "\n\ndef driver():\n    f(nondet_list(), nondet_int())\n"


@pytest.mark.parametrize("harness", [
    pytest.param(ORIGINAL.replace("def f(xs, n):", "def f(xs: list[int], n: int) -> int:")
                 .replace("total = 0", "total: int = 0"), id="annotations"),
    pytest.param(ORIGINAL.replace('    """Doc."""\n', ""), id="docstring"),
    pytest.param(ORIGINAL.replace("    total = 0\n", "    total = 0\n    pass\n"), id="pass"),
    pytest.param(ORIGINAL.replace("total", "acc").replace("for i in", "for k in").replace("xs[i]", "xs[k]"),
                 id="consistent_rename"),
])
def test_what_never_runs_or_only_respells_a_local_is_preserved(harness: str) -> None:
    assert target_preserved(ORIGINAL, _harness(harness), "f", "10 // total")


@pytest.mark.parametrize("harness", [
    pytest.param(ORIGINAL.replace("xs[i] > 0", "xs[i] >= 0"), id="comparison_operator"),
    pytest.param(ORIGINAL.replace('        raise ValueError("empty")\n', "        pass\n"), id="raise_removed"),
    pytest.param(ORIGINAL.replace("    assert total > 0\n", ""), id="assert_removed"),
    pytest.param(ORIGINAL.replace("range(n)", "range(n - 1)"), id="loop_bound"),
    pytest.param(ORIGINAL.replace("10 // total", "11 // total"), id="constant"),
    pytest.param(ORIGINAL.replace("total += xs[i]", "total += 1"), id="value_for_expression"),
    pytest.param(ORIGINAL.replace("    total = 0\n", "    total = 0\n    __ESBMC_assume(n > 0)\n"),
                 id="assume_inserted"),
    pytest.param(ORIGINAL.replace("    return 10 // total", "    if total:\n        return 10 // total"),
                 id="guard_added"),
    pytest.param(ORIGINAL.replace("    assert total > 0\n", "").replace(
        "    if total == 0:", "    assert total > 0\n    if total == 0:"), id="statements_reordered"),
    pytest.param(ORIGINAL.replace("total", "n"), id="local_renamed_onto_a_parameter"),
])
def test_a_change_on_the_bug_path_is_not_preserved(harness: str) -> None:
    assert not target_preserved(ORIGINAL, _harness(harness), "f", "10 // total")


def test_two_locals_merged_into_one_name_is_not_a_renaming() -> None:
    original = "def f(a):\n    x = a\n    y = a + 1\n    return x // y\n"
    assert target_preserved(original, original.replace("y", "z"), "f")
    assert not target_preserved(original, original.replace("y", "x"), "f")


def test_a_local_renamed_to_a_global_the_body_reads_is_not_a_renaming() -> None:
    original = "def f(a):\n    x = a\n    return len(x)\n"
    assert not target_preserved(original, original.replace("x", "len"), "f")


def test_no_renaming_when_the_body_reaches_names_by_text() -> None:
    original = "def f(a):\n    x = a\n    return locals()\n"
    assert not target_preserved(original, original.replace("x = a", "y = a"), "f")


def test_a_renamed_parameter_is_not_a_local_renaming() -> None:
    original = "def f(count):\n    return 10 // count\n"
    assert not target_preserved(original, original.replace("count", "total"), "f")


def test_a_comprehension_variable_is_renamed_in_its_own_scope() -> None:
    original = "def f(xs):\n    x = 0\n    ys = [x * 2 for x in xs]\n    return x + len(ys)\n"
    assert target_preserved(original, original.replace("[x * 2 for x in xs]", "[v * 2 for v in xs]"), "f")
    assert not target_preserved(original, original.replace("x * 2 for x", "x * 2 for v"), "f")


def test_a_closure_follows_the_renaming_of_the_outer_local() -> None:
    original = "def f(a):\n    k = a\n    def g(b):\n        return b // k\n    return g(1)\n"
    assert target_preserved(original, original.replace("k", "q"), "f")


def test_a_bare_annotation_goes_only_where_the_name_is_bound_anyway() -> None:
    original = "def f(a):\n    x = a\n    return x\n"
    assert target_preserved(original, original.replace("    x = a\n", "    x: int\n    x = a\n"), "f")
    reads_global = "def f(a):\n    return a + g\n"
    assert not target_preserved(reads_global, reads_global.replace("    return", "    g: int\n    return"), "f")


def test_nested_definitions_drop_their_docstring_and_undecorated_annotations() -> None:
    original = 'def f(a):\n    def g(b):\n        """Doc."""\n        return b // a\n    return g(1)\n'
    harness = "def f(a: int) -> int:\n    def g(b: int) -> int:\n        return b // a\n    return g(1)\n"
    assert target_preserved(original, harness, "f")


def test_a_decorated_nested_function_keeps_its_annotations() -> None:
    original = "def f(a):\n    @register\n    def g(b):\n        return b // a\n    return g(1)\n"
    assert not target_preserved(original, original.replace("def g(b):", "def g(b: int):"), "f")


def test_a_dataclass_field_annotation_in_a_nested_class_is_kept() -> None:
    original = "def f(a):\n    class P:\n        x: int = 0\n    return P()\n"
    assert not target_preserved(original, original.replace("x: int = 0", "x = 0"), "f")


def test_a_function_level_import_may_become_a_module_level_stub() -> None:
    original = "def f(a):\n    from lib import parse\n    return parse(a)[0]\n"
    harness = "def parse(a):\n    return nondet_list()\n\ndef f(a):\n    return parse(a)[0]\n"
    assert target_preserved(original, harness, "f")
    assert not target_preserved(original, harness.replace("def parse(a):\n    return nondet_list()\n\n", ""), "f")


def test_an_import_inside_try_is_kept() -> None:
    original = ("def f(a):\n    try:\n        from lib import parse\n    except ImportError:\n        return 0\n"
                "    return parse(a)\n")
    harness = "def parse(a):\n    return a\n\n" + original.replace("        from lib import parse\n", "        pass\n")
    assert not target_preserved(original, harness, "f")


def test_the_catalogue_rename_of_a_rebound_parameter_is_mapped_back() -> None:
    original = "def f(params, key):\n    key = params.get(key)\n    assert isinstance(key, bool)\n    return key\n"
    harness = "def f(params, key):\n    value = params.get(key)\n    assert isinstance(value, bool)\n    return value\n"
    assert target_preserved(original, harness, "f")
    assert not target_preserved(original, harness.replace("isinstance(value, bool)", "isinstance(value, int)"), "f")


def test_the_slicer_result_member_and_spread_renames_are_mapped_back() -> None:
    original = "import np\ndef f(x, parts):\n    return x < np.finfo(float).tiny * len(lib.make(*parts))\n"
    sliced = "def f(x, parts):\n    return x < np.finfo__tiny(float) * len(lib.make(_star0=parts))\n"
    assert target_preserved(original, sliced, "f")
    assert not target_preserved(original, sliced.replace("float", "int"), "f")


def test_compat_str_is_str_only_where_the_module_imports_it() -> None:
    imported = "from .compat import compat_str\ndef f(s):\n    assert type(s) == compat_str\n    return s\n"
    harness = "def f(s):\n    assert type(s) == str\n    return s\n"
    assert target_preserved(imported, harness, "f")
    fallback = imported.replace("from .compat import compat_str\n",
                                "try:\n    compat_str = unicode\nexcept NameError:\n    compat_str = str\n")
    assert not target_preserved(fallback, harness, "f")


NESTED = "def f(a):\n    k = a - 1\n    def g(b):\n        return b // k\n    return g(1)\n"


def test_the_entry_function_of_a_nested_target_gets_the_same_normalisation() -> None:
    annotated = NESTED.replace("def f(a):", "def f(a: int) -> int:").replace("k = a - 1", "k: int = a - 1")
    assert target_preserved(NESTED, annotated, "f.g", "b // k")
    assert not target_preserved(NESTED, NESTED.replace("a - 1", "a + 1"), "f.g", "b // k")


def test_differential_keys_ignore_annotations_like_the_preservation_check() -> None:
    plain, typed = ast.parse("x = f(a)").body[0], ast.parse("x: int = f(a)").body[0]
    assert _key(plain) == _key(typed)
    assert _key(plain) != _key(ast.parse("x = f(b)").body[0])


def test_round_warnings_do_not_call_an_annotated_copy_a_changed_body() -> None:
    original = "def f(n):\n    return 10 // n\n"
    annotated = "def f(n: int) -> int:\n    return 10 // n\n"
    assert "body_changed" not in round_warnings(annotated, original, "f", mypy_timeout=1)
    assert "body_changed" in round_warnings(annotated.replace("10", "11"), original, "f", mypy_timeout=1)
