from pathlib import Path

from research_pipeline.preprocess import preprocess_file
from research_pipeline.smell_policy import (
    load_smell_thresholds,
    smell_measurements,
    smells_from_policy,
)


def _unit(tmp_path: Path, source: str):
    path = tmp_path / "sample.py"
    path.write_text(source, encoding="utf-8")
    return preprocess_file(path)[0]


def test_smell_threshold_config_is_explicit_and_valid() -> None:
    policy = load_smell_thresholds()
    assert policy["long_method_min_executable_lines"] == 16
    assert policy["many_parameters_min"] == 5
    assert policy["complex_conditional_min_boolean_operators"] == 3


def test_smell_policy_counts_parameters_and_boolean_operators(tmp_path: Path) -> None:
    unit = _unit(
        tmp_path,
        """def sample(self, a: int, b: int, c: int, d: int, e: int) -> bool:
    return (a > 0 and b > 0) or (c > 0 and d > 0)
""",
    )
    measures = smell_measurements(unit)
    assert measures["parameters"] == 5
    assert measures["max_boolean_operators"] == 3
    assert {"many_parameters", "complex_conditional"} <= smells_from_policy(unit)


def test_all_v1_smell_controls_meet_their_versioned_policy() -> None:
    root = Path("dataset/labeled/ok/smells")
    for category_dir in sorted(root.iterdir()):
        for source in sorted(category_dir.glob("*.py")):
            unit = preprocess_file(source)[0]
            assert category_dir.name in smells_from_policy(unit), source
