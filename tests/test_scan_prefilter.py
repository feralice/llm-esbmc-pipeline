from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest

from research_pipeline.preprocess import preprocess_file
from research_pipeline.scan.prefilter import assess_unit, filter_units


def _unit(tmp_path: Path, source: str):
    f = tmp_path / "m.py"
    f.write_text(source, encoding="utf-8")
    units = preprocess_file(f)
    assert len(units) == 1
    return units[0]


def test_division_is_risky(tmp_path: Path):
    unit = _unit(tmp_path, "def f(a: int, b: int) -> float:\n    return a / b\n")
    risk = assess_unit(unit)
    assert risk.is_risky
    assert "division_or_modulo" in risk.signals


def test_floor_div_and_modulo_are_risky(tmp_path: Path):
    unit = _unit(tmp_path, "def f(a: int, b: int) -> int:\n    return a // b + a % b\n")
    assert assess_unit(unit).is_risky


def test_subscript_is_risky(tmp_path: Path):
    unit = _unit(tmp_path, "def f(xs: list, i: int):\n    return xs[i]\n")
    risk = assess_unit(unit)
    assert risk.is_risky
    assert "subscript" in risk.signals


def test_divmod_call_is_risky(tmp_path: Path):
    unit = _unit(tmp_path, "def f(xs: list, n: int):\n    q, r = divmod(len(xs), n)\n    return q + r\n")
    risk = assess_unit(unit)
    assert risk.is_risky
    assert "call_divmod" in risk.signals or "divmod_call" in risk.signals


def test_pop_call_is_risky(tmp_path: Path):
    unit = _unit(tmp_path, "def f(xs: list, i: int):\n    return xs.pop(i)\n")
    assert "call_pop" in assess_unit(unit).signals


def test_range_over_literal_is_not_risky(tmp_path: Path):
    unit = _unit(tmp_path, "def f() -> int:\n    total = 0\n    for i in range(10):\n        total += i\n    return total\n")
    assert not assess_unit(unit).is_risky


def test_range_over_value_is_risky(tmp_path: Path):
    unit = _unit(tmp_path, "def f(n: int) -> int:\n    total = 0\n    for i in range(n):\n        total += i\n    return total\n")
    risk = assess_unit(unit)
    assert risk.is_risky
    assert "range_over_value" in risk.signals


def test_offset_index_is_risky(tmp_path: Path):
    unit = _unit(tmp_path, "def f(xs: list, i: int):\n    prev = xs[i - 1]\n    return prev\n")
    assert assess_unit(unit).is_risky


def test_plain_function_is_not_risky(tmp_path: Path):
    unit = _unit(tmp_path, "def greet(name: str) -> str:\n    msg = 'hi ' + name\n    return msg.upper()\n")
    risk = assess_unit(unit)
    assert not risk.is_risky
    assert risk.signals == []


def test_filter_units_risky_vs_all(tmp_path: Path):
    src = (
        "def risky(a: int, b: int) -> float:\n    return a / b\n\n"
        "def safe(name: str) -> str:\n    return name.strip()\n"
    )
    f = tmp_path / "two.py"
    f.write_text(src, encoding="utf-8")
    units = preprocess_file(f)
    assert len(units) == 2

    kept_risky = filter_units(units, mode="risky")
    assert [u.name for u, _ in kept_risky] == ["risky"]

    kept_all = filter_units(units, mode="all")
    assert [u.name for u, _ in kept_all] == ["risky", "safe"]


def test_filter_units_rejects_bad_mode(tmp_path: Path):
    with pytest.raises(ValueError):
        filter_units([], mode="nonsense")
