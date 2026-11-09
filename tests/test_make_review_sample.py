from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import make_review_sample as sample


def _items(projects: list[str], per_project: int) -> list[dict]:
    return [{"id": f"{p}_{i}", "file": f"{p}_{i}.py", "provenance": {"project": p}}
            for p in projects for i in range(per_project)]


def test_sample_has_no_project_from_the_excluded_set() -> None:
    chosen = sample.choose(_items(["a", "b", "c"], 5), excluded_projects={"b"}, size=8, seed=0)
    assert chosen and all(not i.startswith("b_") for i in chosen)


def test_sample_spreads_over_projects_before_repeating_one() -> None:
    chosen = sample.choose(_items(["a", "b", "c", "d"], 10), excluded_projects=set(), size=8, seed=0)
    assert {c.split("_")[0] for c in chosen} == {"a", "b", "c", "d"}
    assert len(chosen) == 8


def test_sample_is_reproducible_with_seed_and_capped_by_availability() -> None:
    items = _items(["a", "b"], 3)
    assert sample.choose(items, set(), 4, seed=7) == sample.choose(items, set(), 4, seed=7)
    assert len(sample.choose(items, set(), 100, seed=7)) == 6
