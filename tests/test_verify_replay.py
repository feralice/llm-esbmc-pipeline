from research_pipeline.verify.render import Program
from research_pipeline.verify.replay import concrete_replay


def _program(source: str, target_line: int) -> Program:
    lines = source.splitlines()
    return Program(source, lines.index("def main() -> None:") + 1, ((target_line, target_line),), ())


DIV = '''def ratio(total, count):
    if count > 5:
        return 0
    return total // count


def main() -> None:
    total: int = nondet_int()
    count: int = nondet_int()
    ratio(total, count)


main()
'''


def test_reachable_division_by_zero_is_reproduced_at_the_suspect_line():
    verdict = concrete_replay(_program(DIV, 4), "ratio")
    assert (verdict.status, verdict.exception_type, verdict.line) == ("reproduced", "ZeroDivisionError", 4)
    assert verdict.runs >= 1


def test_guard_that_blocks_the_crash_gives_not_reproduced():
    source = DIV.replace("if count > 5:", "if count == 0:")
    verdict = concrete_replay(_program(source, 4), "ratio")
    assert verdict.status == "not_reproduced"
    assert verdict.runs > 1


def test_assume_discards_runs():
    source = DIV.replace("    ratio(total, count)", "    __ESBMC_assume(count != 0)\n    ratio(total, count)")
    assert concrete_replay(_program(source, 4), "ratio").status == "not_reproduced"


def test_exception_on_another_line_is_other_failure():
    source = DIV.replace("        return 0", "        return [][0]").replace("if count > 5:", "if count > 0:") \
        .replace("    return total // count", "    return 1")
    verdict = concrete_replay(_program(source, 4), "ratio")
    assert (verdict.status, verdict.exception_type, verdict.line) == ("other_failure", "IndexError", 3)


def test_optional_none_first_reaches_attribute_error():
    source = '''from typing import Optional


class User:
    def __init__(self) -> None:
        _attr_name: Optional[str] = None
        if nondet_bool():
            _attr_name = nondet_str()
        self.name = _attr_name

    def greet(self):
        return self.name.upper()


def main() -> None:
    _receiver = User()
    _receiver.greet()


main()
'''
    verdict = concrete_replay(_program(source, 12), "greet")
    assert (verdict.status, verdict.exception_type) == ("reproduced", "AttributeError")


def test_lists_are_enumerated_including_empty():
    source = '''def last(xs):
    return xs.pop()


def main() -> None:
    xs: list[int] = nondet_list(3, elem_type=nondet_int())
    last(xs)


main()
'''
    verdict = concrete_replay(_program(source, 2), "last")
    assert (verdict.status, verdict.exception_type) == ("reproduced", "IndexError")


def test_host_unsafe_program_is_not_executed():
    source = "import os\n\n\ndef main() -> None:\n    os.remove('x')\n\n\nmain()\n"
    verdict = concrete_replay(_program(source, 5), "main")
    assert verdict.status == "unavailable"


def test_infinite_loop_runs_are_discarded():
    source = '''def spin(n):
    while n >= 0:
        pass
    return 1 // n


def main() -> None:
    n: int = nondet_int()
    spin(n)


main()
'''
    verdict = concrete_replay(_program(source, 4), "spin", timeout_seconds=30)
    assert verdict.status == "not_reproduced"


COUNTEREXAMPLE = """[Counterexample]

State 1 file p.py line 9 column 4 function _esbmc_main thread 0
----------------------------------------------------
  n = 8 (00000000 00000000 00000000 00000000 00000000 00000000 00000000 00001000)

State 2 file p.py line 3 column 4 function deep thread 0
----------------------------------------------------
  i = 3 (00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000011)

State 3 file p.py line 35 column 0 thread 0
----------------------------------------------------
  t = 0.000000 (00111011 01100011 11010110 00100000 10010101 00000000 00000000 00000000)
"""


def test_counterexample_seeds_read_driver_values_and_exact_floats():
    from research_pipeline.verify.replay import counterexample_seeds
    assert counterexample_seeds(COUNTEREXAMPLE, "_esbmc_main") == {"int": [8], "float": []}
    seeds = counterexample_seeds(COUNTEREXAMPLE, None)
    assert seeds["int"] == [8, 3]
    assert seeds["float"] == [1.312665133989138e-22]


def test_replay_reproduces_a_bug_only_the_counterexample_reaches():
    from research_pipeline.verify.render import Program
    from research_pipeline.verify.replay import concrete_replay
    source = ("def deep(n: int):\n    return 10 // (n - 8)\n\n\n"
              "def _esbmc_main() -> None:\n    n: int = nondet_int()\n    deep(n)\n\n\n_esbmc_main()\n")
    program = Program(source, 5, ((2, 2),), (), (1, 2))
    assert concrete_replay(program, "deep").status == "not_reproduced"
    seeded = concrete_replay(program, "deep", seeds={"int": [8], "float": []})
    assert (seeded.status, seeded.exception_type) == ("reproduced", "ZeroDivisionError")
