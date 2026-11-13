from research_pipeline.llm.prompt_routing import DEFAULT_VARIANTS, route_variants


def test_division_takes_the_arithmetic_row():
    assert route_variants("def f(a, b):\n    return a // b\n") == ("A2", "A16")


def test_subscript_takes_the_access_row():
    assert route_variants("def f(xs):\n    return xs[0]\n") == ("A2", "A12")


def test_assert_takes_the_state_row():
    assert route_variants("def f(x):\n    assert x > 0\n    return x\n") == ("A2", "A20")


def test_arithmetic_wins_over_access_when_both_match():
    assert route_variants("def f(xs, n):\n    return xs[0] // n\n") == ("A2", "A16")


def test_no_match_gets_the_frozen_default():
    assert route_variants("def f(x):\n    return x\n") == DEFAULT_VARIANTS


def test_unparseable_source_gets_the_default():
    assert route_variants("def f(:\n") == DEFAULT_VARIANTS


def test_auto_routes_each_function_on_its_own_source(tmp_path):
    from research_pipeline.llm.detection_cache import DetectionCache
    from research_pipeline.models import CodeUnit
    from pathlib import Path

    def unit(source):
        return CodeUnit(path=Path("m.py"), name="f", qualname="f", source=source, start_line=1, end_line=2,
                        parameters=[], type_hints={}, operations=[], loops=[], conditionals=[], guards=[],
                        metrics={})
    arithmetic = unit("def f(a, b):\n    return a // b\n")
    plain = unit("def f(x):\n    return x\n")
    assert route_variants(arithmetic.source) != route_variants(plain.source)
    cache = DetectionCache(tmp_path, "k")
    assert cache._path(arithmetic) != cache._path(plain)
