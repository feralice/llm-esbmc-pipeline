from pathlib import Path

import pytest

from research_pipeline.verify import pytest_gen
from research_pipeline.verify.pytest_gen import esbmc_pytest, pytest_seeds

ESBMC = Path.home() / "esbmc-master/esbmc.sh"
needs_esbmc = pytest.mark.skipif(not ESBMC.exists(), reason="ESBMC v8.6 wrapper not installed")

DIVISION = '''from esbmc import nondet_int


def ratio(a: int, b: int) -> int:
    return a // b


def main() -> None:
    x: int = nondet_int()
    y: int = nondet_int()
    ratio(x, y)


main()
'''

METHOD = '''from esbmc import nondet_int


class Conta:
    def __init__(self, total: int) -> None:
        self.total = total

    def media(self, n: int) -> int:
        return self.total // n


def main() -> None:
    n: int = nondet_int()
    Conta(10).media(n)


main()
'''


def _harness(tmp_path: Path, source: str) -> Path:
    path = tmp_path / "harness.py"
    path.write_text(source, encoding="utf-8")
    return path


def _run(tmp_path: Path, source: str, exception: str = "ZeroDivisionError") -> dict:
    return esbmc_pytest(_harness(tmp_path, source), esbmc_command=[str(ESBMC)], bound=5,
                        out_dir=tmp_path / "out", exception=exception)


@needs_esbmc
def test_direct_route_reproduces_a_free_function_bug(tmp_path):
    result = _run(tmp_path, DIVISION)
    assert (result["status"], result["route"]) == ("reproduces", "direct"), result
    assert Path(result["path"]).exists()


@needs_esbmc
def test_falls_back_when_direct_generation_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(pytest_gen, "_direct_test",
                        lambda *a, **k: {"status": "not_generated", "path": "", "reason": "forced"})
    result = _run(tmp_path, DIVISION)
    assert (result["status"], result["route"]) == ("reproduces", "free_function"), result


@needs_esbmc
def test_a_method_goes_to_the_free_function_route_and_is_not_generated(tmp_path):
    result = _run(tmp_path, METHOD)
    assert (result["status"], result["route"]) == ("not_generated", "free_function"), result


@needs_esbmc
def test_a_test_that_fails_with_another_exception_does_not_reproduce(tmp_path):
    result = _run(tmp_path, DIVISION, exception="KeyError")
    assert result["status"] == "does_not_reproduce", result


def test_an_unrecognised_harness_shape_is_not_generated(tmp_path):
    result = _run(tmp_path, "def f(a: int) -> int:\n    return a\n")
    assert (result["status"], result["route"]) == ("not_generated", "free_function")


def test_a_missing_esbmc_is_not_generated(tmp_path):
    result = esbmc_pytest(_harness(tmp_path, DIVISION), esbmc_command=[str(tmp_path / "nope")], bound=5,
                          out_dir=tmp_path / "out", exception="ZeroDivisionError")
    assert result["status"] == "not_generated"


def test_pytest_seeds_read_the_generated_values(tmp_path):
    test = tmp_path / "test_x.py"
    test.write_text('@pytest.mark.parametrize("a,b", [\n    (7, 0),\n    (2.5, -1),\n])\ndef test_f(a,b):\n    f(a,b)\n')
    assert pytest_seeds(str(test)) == {"int": [7, 0, -1], "float": [2.5]}
    assert pytest_seeds(str(tmp_path / "missing.py")) == {}


ESBMC_TEST = '''from bug import *
import pytest

@pytest.mark.parametrize("a,b", [
    (0, 2),
])
def test_ratio(a,b):
    """Auto-generated test cases for ratio"""
    ratio(a,b)
'''


def test_awaited_test_runs_each_call_of_the_coroutine_with_asyncio():
    test = pytest_gen.awaited_test(ESBMC_TEST, "ratio")
    assert test.startswith("import asyncio\n")
    assert "    asyncio.run(ratio(a, b))" in test and "\n    ratio(a, b)" not in test


COROUTINE_PROGRAM = '''async def scale(b: int) -> int:
    return b * b + 1


async def ratio(a: int, b: int) -> int:
    d = await scale(b)
    return a // (d - 5)


import asyncio


def _esbmc_main() -> None:
    a: int = nondet_int()
    b: int = nondet_int()
    asyncio.run(ratio(a, b))


_esbmc_main()
'''


@needs_esbmc
def test_a_coroutine_reproducer_awaits_the_target(tmp_path):
    from research_pipeline.verify.render import Program

    result = pytest_gen.pytest_reproducer(Program(COROUTINE_PROGRAM, 13, ((7, 7),), ()), function="ratio",
                                          params={"a": "int", "b": "int"}, exception="ZeroDivisionError",
                                          esbmc_command=[str(ESBMC)], bound=5, out_dir=tmp_path, name="bug",
                                          coroutine=True)
    assert result["status"] == "reproduces", result
    assert "asyncio.run(ratio(" in Path(result["path"]).read_text(encoding="utf-8")
