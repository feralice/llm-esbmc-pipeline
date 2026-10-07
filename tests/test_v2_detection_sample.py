import importlib.util
from collections import Counter
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "v2_detection_sample", Path(__file__).resolve().parents[1] / "scripts" / "v2_detection_sample.py")
v2_detection_sample = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(v2_detection_sample)


def _items(kinds: dict[str, int]) -> list[dict]:
    return [{"id": f"{kind}_{i}", "failure_kind": kind} for kind, n in kinds.items() for i in range(n)]


def test_the_sample_keeps_the_dataset_proportions() -> None:
    picked = v2_detection_sample.sample(_items({"a": 60, "b": 30, "c": 10}), size=10, excluded=set())
    assert Counter(i["failure_kind"] for i in picked) == {"a": 6, "b": 3, "c": 1}


def test_rounding_still_gives_the_requested_size_and_every_kind() -> None:
    picked = v2_detection_sample.sample(_items({"a": 5, "b": 5, "c": 5}), size=7, excluded=set())
    assert len(picked) == 7 and set(Counter(i["failure_kind"] for i in picked)) == {"a", "b", "c"}


def test_excluded_items_never_enter_and_the_pick_is_stable() -> None:
    items = _items({"a": 20})
    first = v2_detection_sample.sample(items, size=5, excluded={"a_0", "a_1"})
    assert not {"a_0", "a_1"} & {i["id"] for i in first}
    assert first == v2_detection_sample.sample(list(reversed(items)), size=5, excluded={"a_0", "a_1"})
