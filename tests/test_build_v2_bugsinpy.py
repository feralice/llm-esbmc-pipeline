import ast
import importlib.util
from pathlib import Path

from research_pipeline.verify.astutil import find_function

SPEC = importlib.util.spec_from_file_location(
    "build_v2_bugsinpy", Path(__file__).resolve().parents[1] / "scripts" / "build_v2_bugsinpy.py")
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)

SOURCE = '''import os


class Index(
        os.PathLike,
        object):
    """Doc."""

    @property
    def size(self):
        return 1

    def ratio(self, n):
        if n:
            return 10 // n
        return 0


def top(x):
    return x[0]
'''


def test_excerpt_of_a_method_keeps_a_findable_class_and_the_exact_body():
    cut = build.excerpt(SOURCE, "Index.ratio")
    assert cut.startswith("class Index:\n    def ratio(self, n):\n")
    assert "return 10 // n" in cut and "def size" not in cut
    assert find_function(ast.parse(cut), "Index.ratio") is not None


def test_excerpt_of_a_function_and_of_a_missing_one():
    assert build.excerpt(SOURCE, "top") == "def top(x):\n    return x[0]\n"
    assert build.excerpt(SOURCE, "missing") is None
