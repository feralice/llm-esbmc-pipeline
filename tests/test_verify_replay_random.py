from research_pipeline.verify.render import Program
from research_pipeline.verify.replay import concrete_replay

NEEDS_BIG = (
    "def f(x: int) -> int:\n"
    "    if x > 50:\n"
    "        return 1 // 0\n"
    "    return x\n"
    "\n"
    "f(nondet_int())\n"
)
NEEDS_SPACE = (
    "def g(s: str) -> str:\n"
    "    if ' ' in s:\n"
    "        return [][0]\n"
    "    return s\n"
    "\n"
    "g(nondet_str())\n"
)
NEVER = (
    "def h(x: int) -> int:\n"
    "    return 1 // 0\n"
    "\n"
    "x = nondet_int()\n"
    "__ESBMC_assume(x != x)\n"
    "h(x)\n"
)


def test_the_exhaustive_pass_alone_misses_a_large_value() -> None:
    program = Program(NEEDS_BIG, 0, ((3, 3),), (), (1, 4))
    assert concrete_replay(program, "f").status == "not_reproduced"


def test_the_random_pass_reaches_a_large_int_and_a_string_with_a_space() -> None:
    big = concrete_replay(Program(NEEDS_BIG, 0, ((3, 3),), (), (1, 4)), "f", random_runs=300, seed=1)
    space = concrete_replay(Program(NEEDS_SPACE, 0, ((3, 3),), (), (1, 4)), "g", random_runs=300, seed=1)
    assert big.status == "reproduced" and big.line == 3
    assert space.status == "reproduced" and space.exception_type == "IndexError"


def test_an_assume_that_rejects_everything_ends_without_a_crash() -> None:
    verdict = concrete_replay(Program(NEVER, 0, ((2, 2),), (), (1, 2)), "h", random_runs=300, seed=1)
    assert verdict.status == "not_reproduced"
