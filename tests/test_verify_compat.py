import ast

from research_pipeline.verify.compat import (
    NONE_GUARDS,
    cut_after_suspect,
    drop_project_decorators,
    none_guards,
    remove_unused,
    rename_builtin_named_methods,
    rewrite_compat,
    split_conditional_assignments,
)
from research_pipeline.verify.grounding import Grounded, ground
from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.rules import (
    ALL_RULES,
    METHOD_ALIAS,
    NONE_ATTRIBUTE,
    NONE_GUARD_KINDS,
    PERCENT_FORMAT,
)


def test_percent_s_with_tuple_literal_becomes_str_concatenation():
    source = 'def label(code, name):\n    return "id=%s:%s!" % (code, name)\n'
    rewritten, transforms = rewrite_compat(source, parameter_types={"label": {"code": "int", "name": "str"}})
    assert "    return ('id=' + str(code) + ':' + str(name) + '!')\n" in rewritten
    assert transforms == ["compat_percent_format:1"]


def test_equivalence_under_cpython_for_sample_values():
    source = 'def label(a, b):\n    return "%s-%s" % (a, b)\n'
    for a, b in [(1, "x"), (None, 2.5), ("", False), (b"a", 2)]:
        rewritten, transforms = rewrite_compat(source, parameter_types={"label": {
            "a": type(a).__name__ if a is not None else "none", "b": type(b).__name__,
        }})
        assert transforms == ["compat_percent_format:1"]
        original_ns, new_ns = {}, {}
        exec(source, original_ns)
        exec(rewritten, new_ns)
        assert original_ns["label"](a, b) == new_ns["label"](a, b)


def test_other_conversions_and_non_tuple_operands_are_left_alone():
    for body in ['"%d items" % (n,)', '"%s" % n', '"%s %s" % pair', '"%(k)s" % mapping', '"%s %s" % (a,)']:
        source = f"def f(n, pair, mapping, a):\n    return {body}\n"
        assert rewrite_compat(source) == (source, [])


def test_literal_percent_is_kept():
    source = 'def f(a):\n    return "%s is 100%%" % (a,)\n'
    rewritten, _ = rewrite_compat(source, parameter_types={"f": {"a": "str"}})
    assert "return (str(a) + ' is 100%')" in rewritten


def test_grounding_preserves_the_code_before_compatibility_rewrites():
    source = 'def label(code, name):\n    msg = "%s %s" % (code, name)\n    return 1 // len(msg)\n'
    grounded = ground(BugHypothesis("x.py", "label", "1 // len(msg)"), source)
    assert isinstance(grounded, Grounded)
    assert source in grounded.module
    assert "compat_percent_format:1" not in grounded.transforms
    assert ast.parse(grounded.module)


ALIAS_SOURCE = (
    "class R:\n"
    "    def __str__(self) -> str:\n"
    "        return 'r'\n"
    "\n"
    "    __repr__ = __str__\n"
    "\n"
    "    def scale(self, k, *, by=2):\n"
    "        return k * by\n"
    "\n"
    "    times = scale\n"
    "    LIMIT = 3\n"
    "    other = LIMIT\n"
)


def test_method_alias_becomes_one_line_delegating_def():
    rewritten, transforms = rewrite_compat(ALIAS_SOURCE)
    lines = rewritten.splitlines()
    assert lines[4] == "    def __repr__(self) -> str: return self.__str__()"
    assert lines[9] == "    def times(self, k, *, by=2): return self.scale(k, by=by)"
    assert "    other = LIMIT" in lines
    assert len(lines) == len(ALIAS_SOURCE.splitlines())
    assert "compat_method_alias:2" in transforms


def test_method_alias_rewrite_is_equivalent_under_cpython():
    original, rewritten = {}, {}
    exec(ALIAS_SOURCE, original)
    exec(rewrite_compat(ALIAS_SOURCE)[0], rewritten)
    for ns in (original, rewritten):
        r = ns["R"]()
        assert (repr(r), r.times(3), r.times(3, by=5)) == ("r", 6, 15)


def test_alias_of_static_or_variadic_method_is_left_alone():
    source = (
        "class R:\n"
        "    @staticmethod\n"
        "    def make():\n"
        "        return 1\n"
        "    build = make\n"
        "    def many(self, *xs):\n"
        "        return xs\n"
        "    lots = many\n"
    )
    rewritten, transforms = rewrite_compat(source)
    assert rewritten == source and transforms == []


CUT = '''def helper(x):
    return x.missing_in_esbmc()


def f(xs, n):
    total = 0
    if n > 0:
        total = xs[n]
    other = helper(xs)
    return other


def _esbmc_main() -> None:
    f([1], 2)
'''


def test_code_after_the_suspect_statement_is_cut_and_its_helpers_go():
    cut, transforms = cut_after_suspect(CUT, "f", ((8, 8),))
    cut, removed = remove_unused(cut, "f")
    lines = cut.splitlines()
    assert lines[7] == "        total = xs[n]"
    assert lines[8] == "    pass" and lines[9] == "" and len(lines) == len(CUT.splitlines())
    assert "helper" not in cut
    assert transforms == ["cut_after_suspect:2"] and removed == ["unused_definitions_removed:helper"]


def test_an_annotated_return_ends_the_path_instead_of_falling_off():
    cut, _ = cut_after_suspect(CUT.replace("def f(xs, n):", "def f(xs, n) -> int:"), "f", ((8, 8),))
    lines = cut.splitlines()
    assert lines[8] == "    _esbmc_end_path()"
    assert lines[len(CUT.splitlines()):] == ["", "", "def _esbmc_end_path() -> None:", "    __ESBMC_assume(False)"]


def test_no_cut_for_a_recursive_function_a_generator_or_a_last_statement():
    recursive = CUT.replace("other = helper(xs)", "other = f(xs, n - 1)")
    generator = CUT.replace("other = helper(xs)", "other = yield xs")
    for source in (recursive, generator):
        assert cut_after_suspect(source, "f", ((8, 8),)) == (source, [])
    assert cut_after_suspect(CUT, "f", ((10, 10),)) == (CUT, [])


GUARDED = '''def f(node, key, table, count):
    node.next.prev = table[key] if key in table else count + 1
    return node
'''


def _raised(source, *args):
    namespace = {}
    exec(source, namespace)
    try:
        namespace["f"](*args)
    except Exception as exc:  # noqa: BLE001
        return type(exc).__name__
    return None


def test_none_guards_raise_what_cpython_raises_before_the_suspect():
    guarded, transforms = none_guards(GUARDED, "f", ((2, 2),))
    assert transforms == ["none_guards:3"]
    assert guarded.splitlines()[1] == ("    _esbmc_none_attribute(node is None); _esbmc_none_attribute(node.next is None); "
                                       "_esbmc_none_type(table is None); node.next.prev = "
                                       "table[key] if key in table else count + 1")
    assert "key is None" not in guarded and "count is None" not in guarded  # only one branch runs

    class Node:
        next = None

    linked = Node()
    linked.next = Node()
    guarded = "\n".join(NONE_GUARDS) + "\n" + guarded
    for args in [(None, 1, {}, 0), (Node(), 1, {}, 0), (linked, 1, None, 0), (linked, 1, {}, None),
                 (linked, 1, {1: 2}, None), (linked, 1, {}, 3)]:
        assert _raised(guarded, *args) == _raised(GUARDED, *args), args


def test_an_if_test_gets_its_guards_inside_and_keeps_its_line():
    source = "def f(x, n):\n    if '//' in x.url and\\\n            n > 0:\n        return 1\n    return 0\n"
    guarded, transforms = none_guards(source, "f", ((2, 2),))
    assert transforms == ["none_guards:2"] and len(guarded.splitlines()) == len(source.splitlines())
    assert guarded.splitlines()[1] == ("    if _esbmc_none_attribute(x is None) and _esbmc_none_type(x.url is None) and "
                                       "bool('//' in x.url and\\")
    assert guarded.splitlines()[2] == "            n > 0):"


def test_operands_that_short_circuit_may_skip_get_no_guard():
    source = "def f(x, y):\n    return x and x.a + len(y)\n"
    assert none_guards(source, "f", ((2, 2),)) == (source, [])


def test_a_methods_receiver_gets_no_guard_but_its_attributes_do():
    source = "class K:\n    @classmethod\n    def m(cls, x):\n        return cls.a.b + x.c\n"
    guarded, _ = none_guards(source, "K.m", ((4, 4),))
    assert guarded.splitlines()[3] == (
        "        _esbmc_none_attribute(cls.a is None); _esbmc_none_type(cls.a.b is None); "
        "_esbmc_none_attribute(x is None); _esbmc_none_type(x.c is None); return cls.a.b + x.c")


def test_unreached_methods_and_display_dunders_leave_the_esbmc_copy():
    source = """class Offset:
    def __init__(self, n):
        self.n = n

    def __repr__(self):
        return '<%s>' % self.__class__.__name__

    def __eq__(self, other):
        return self.n == other.n

    def unused(self):
        return self.helper()

    def helper(self):
        return 1


def f(n):
    return Offset(n) == Offset(1)
"""
    pruned, transforms = remove_unused(source, "f")
    assert transforms == ["unused_definitions_removed:__repr__,helper,unused"]
    assert "__eq__" in pruned and "__init__" in pruned and "__class__" not in pruned
    assert len(pruned.splitlines()) == len(source.splitlines())


def test_a_removed_class_whose_methods_also_go_leaves_valid_code():
    source = "class Unused:\n    def m(self):\n        return 1\n\n\nclass Kept:\n    def m(self):\n        return 2\n\n\ndef f():\n    return Kept\n"
    pruned, _ = remove_unused(source, "f")
    ast.parse(pruned)
    assert "Unused" not in pruned and pruned.splitlines()[6] == "    pass"


def test_inside_a_loop_the_path_ends_after_the_suspect():
    source = ("def f(rows):\n    out = []\n    for row in rows:\n        out.append(1 / row)\n"
              "        best = min(enumerate(out))\n    return out\n")
    cut, transforms = cut_after_suspect(source, "f", ((4, 4),))
    lines = cut.splitlines()
    assert lines[4] == "        _esbmc_end_path()" and lines[5] == "    pass"
    assert transforms == ["cut_after_suspect:2"] and "enumerate" not in cut


def test_user_methods_named_like_container_methods_are_renamed_with_their_references():
    source = ("class Codes:\n    @staticmethod\n    def get(a: int) -> int:\n        return 10 // a\n\n\n"
              "class Bag:\n    def append(self, x: int) -> int:\n        return Codes.get(x)\n\n"
              "    def go(self, x: int) -> int:\n        self.items.append(x)\n        return self.append(x)\n\n\n"
              "def _esbmc_main() -> None:\n    _receiver = Bag()\n    _receiver.append(1)\n")
    renamed, target, transforms = rename_builtin_named_methods(source, "Bag.append")
    assert target == "Bag.esbmc_append"
    assert "    def esbmc_get(a: int) -> int:" in renamed and "return Codes.esbmc_get(x)" in renamed
    assert "    def esbmc_append(self, x: int) -> int:" in renamed and "return self.esbmc_append(x)" in renamed
    assert "        self.items.append(x)\n" in renamed
    assert "    _receiver.esbmc_append(1)\n" in renamed
    assert transforms == ["builtin_named_methods_renamed:append,get"]
    namespace = {}
    exec(renamed.split("def _esbmc_main")[0], namespace)
    assert namespace["Codes"].esbmc_get(5) == 2


def test_classes_without_builtin_named_methods_are_untouched():
    source = "class A:\n    def run(self) -> int:\n        return 1\n"
    assert rename_builtin_named_methods(source, "A.run") == (source, "A.run", [])


def test_a_computed_class_value_nothing_reads_leaves_the_esbmc_copy():
    source = ("import re\n\n\nclass P:\n    _unused = re.compile('x')\n    _used = re.compile('y')\n    LIMIT = 3\n\n"
              "    def go(self, n: int) -> int:\n        self._used.match('y')\n        return n // self.LIMIT\n")
    pruned, transforms = remove_unused(source, "P.go")
    assert "_unused" not in pruned and "_used = re.compile('y')" in pruned and "LIMIT = 3" in pruned
    assert transforms == ["unused_definitions_removed:_unused"]
    assert remove_unused(source, "P.go", display=False) == (source, [])


def test_a_call_on_a_variable_annotated_with_the_class_is_renamed_too():
    source = ("class _Obj_params:\n    def get(self, a0=None) -> bool:\n        return True\n\n\n"
              "def f(params: _Obj_params, key: str):\n    return params.get(key)\n\n\n"
              "def _esbmc_main() -> None:\n    params: _Obj_params = _Obj_params()\n    f(params, 'k')\n")
    renamed, _, _ = rename_builtin_named_methods(source, "f")
    assert "    return params.esbmc_get(key)\n" in renamed
    assert remove_unused(renamed, "f")[0].count("def esbmc_get") == 1


def test_project_decorators_are_blanked_and_builtin_ones_stay():
    source = ("def deprecated(func):\n    return func\n\n\n"
              "class C:\n    @deprecated\n    def f(self):\n        return 1\n\n"
              "    @staticmethod\n    def g():\n        return 2\n")
    rewritten, transforms = drop_project_decorators(source)
    assert "@deprecated" not in rewritten and "@staticmethod" in rewritten
    assert len(rewritten.splitlines()) == len(source.splitlines())
    assert transforms == ["project_decorators_removed:deprecated"]


def test_conditional_assignment_of_functions_becomes_if_else():
    source = "def f(a, w):\n    g = w if a == 1 else lambda c: w(c, 2)\n    return g\n"
    rewritten, transforms = split_conditional_assignments(source)
    assert "    if a == 1: g = w\n    else: g = lambda c: w(c, 2)\n" in rewritten
    assert transforms == ["conditional_assignments_split:1"]
    plain = "def f(a):\n    x = 3 if a else 0\n    return x\n"
    assert split_conditional_assignments(plain) == (plain, [])


def test_a_definition_named_only_by_itself_is_unused():
    source = ("def deprecated(func=None):\n    if func is None:\n        return deprecated\n    return func\n\n\n"
              "def f(x):\n    return x\n")
    pruned, transforms = remove_unused(source, "f")
    assert "def deprecated" not in pruned
    assert transforms == ["unused_definitions_removed:deprecated"]


def test_rule_names_cover_every_none_guard_kind():
    assert NONE_GUARD_KINDS < ALL_RULES and len(ALL_RULES) == 12


def test_rewrite_compat_skips_a_disabled_percent_rule():
    source = 'def label(code, name):\n    return "id=%s:%s!" % (code, name)\n'
    types = {"label": {"code": "int", "name": "str"}}
    assert rewrite_compat(source, parameter_types=types, rules=ALL_RULES - {PERCENT_FORMAT}) == (source, [])
    assert rewrite_compat(source, parameter_types=types)[1] == ["compat_percent_format:1"]


def test_rewrite_compat_skips_a_disabled_alias_rule():
    source = "class C:\n    def __str__(self):\n        return 'c'\n    __repr__ = __str__\n"
    assert rewrite_compat(source, rules=ALL_RULES - {METHOD_ALIAS}) == (source, [])
    assert rewrite_compat(source)[1] == ["compat_method_alias:1"]


def test_none_guards_keep_only_the_enabled_kinds():
    source = "def f(a, xs):\n    y = a.size, 'k' in xs\n    return y\n"
    both, transforms = none_guards(source, "f", ((2, 2),))
    assert "_esbmc_none_attribute(a is None)" in both and "_esbmc_none_type(xs is None)" in both
    assert transforms == ["none_guards:2"]
    only_in, transforms = none_guards(source, "f", ((2, 2),), kinds=NONE_GUARD_KINDS - {NONE_ATTRIBUTE})
    assert "_esbmc_none_attribute" not in only_in and "_esbmc_none_type(xs is None)" in only_in
    assert transforms == ["none_guards:1"]
    assert none_guards(source, "f", ((2, 2),), kinds=frozenset()) == (source, [])


def test_guards_of_a_for_header_go_inside_its_iterable():
    source = "def f(total, size, step):\n    for h in range((total - size) // step):\n        pass\n"
    guarded, transforms = none_guards(source, "f", ((2, 2),))
    ast.parse(guarded)
    assert transforms and guarded.splitlines()[1].lstrip().startswith("for h in _esbmc_none_type(")
