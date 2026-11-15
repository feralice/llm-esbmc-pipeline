import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from juiz_conserto import _STATUS, _spans  # noqa: E402


def test_spans_find_every_function_with_the_name():
    source = "def f(a):\n    return a\n\nclass C:\n    def f(self):\n        pass\n"
    assert _spans(source, "f") == ((1, 2), (5, 6))


def test_a_clean_run_of_the_fixed_version_is_the_only_fixed_ok():
    assert _STATUS["not_reproduced"] == "fixed_ok"
    assert _STATUS["reproduced"] == "fixed_breaks"
    assert "unavailable" not in _STATUS
