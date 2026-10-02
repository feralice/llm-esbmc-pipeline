import filecmp
import json
from pathlib import Path

import pytest

from research_pipeline.evaluator import load_ground_truth_cases
from research_pipeline.llm.categories import FORMAL_CATEGORIES
from research_pipeline.v2_eligibility import (
    EligibilityError,
    build_eligible,
    detection_shows_buggy_code,
)

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "dataset" / "v2_real_world"
ELIGIBLE = ROOT / "dataset" / "historico" / "v2_real_world_eligible"

DIFF = """# source: https://github.com/example/proj/commit/abc
diff --git a/proj/mod.py b/proj/mod.py
--- a/proj/mod.py
+++ b/proj/mod.py
@@ -1,3 +1,5 @@ def first(items):
 def first(items):
+    if not items:
+        return None
     return items[0]
"""
BUGGY_SOURCE = "def first(items):\n    return items[0]\n"
FIXED_SOURCE = "def first(items):\n    if not items:\n        return None\n    return items[0]\n"
SYMPTOMS = {"out_of_bounds": ["IndexError"], "invalid_precondition": ["IndexError"]}


def _audit(buggy="failed", prop="IndexError", fixed="successful"):
    return {
        "buggy": {"verdict": buggy, "esbmc_property": prop},
        "fixed": {"verdict": fixed, "esbmc_property": ""},
    }


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _dataset(tmp_path: Path, *, decisions: dict, audits: dict, detection=BUGGY_SOURCE,
             provenance=None) -> Path:
    root = tmp_path / "v2"
    for folder in ("bugs", "detection", "patches"):
        (root / folder).mkdir(parents=True)
    provenance = provenance if provenance is not None else {
        "repo_url": "https://github.com/example/proj", "fixed_commit": "abc"}
    items, manifest_items = [], []
    for key, categories in (("a", ["out_of_bounds", "invalid_precondition"]),
                            ("b", ["incorrect_result"])):
        (root / "bugs" / f"{key}.py").write_text("x = [][0]\n", encoding="utf-8")
        (root / "bugs" / f"{key}_fixed.py").write_text("x = 0\n", encoding="utf-8")
        (root / "detection" / f"{key}.py").write_text(detection, encoding="utf-8")
        (root / "patches" / f"{key}.diff").write_text(DIFF, encoding="utf-8")
        items.append({"id": key, "harness_file": f"{key}.py", "categories": categories,
                      "function": "first", "expression": "items[0]", "provenance": provenance})
        manifest_items.append({"id": key, "detection_file": f"detection/{key}.py",
                               "harness_file": f"bugs/{key}.py", "categories": categories,
                               "function": "first", "expression": "items[0]"})
    _write_json(root / "ground_truths.json", {"evaluation_policy": {}, "items": items})
    _write_json(root / "manifest.json", {"evaluation_policy": {}, "items": manifest_items})
    _write_json(root / "eligibility.json", {"symptoms_for_category": SYMPTOMS, "items": decisions})
    _write_json(root / "esbmc_audit.json", {"results": audits})
    return root


def _eligible(categories=("out_of_bounds", "invalid_precondition"), prop="IndexError"):
    return {"status": "eligible", "categories": list(categories), "esbmc_property": prop, "reason": "r"}


REJECTED = {"status": "rejected", "reason": "non-formal"}


def test_build_preserves_every_justified_category(tmp_path) -> None:
    root = _dataset(tmp_path, decisions={"a": _eligible(), "b": REJECTED}, audits={"a": _audit()})
    out = tmp_path / "eligible"
    build_eligible(root, out)

    cases = load_ground_truth_cases(out / "ground_truths.json")
    assert [entry["category"] for _, entries in cases for entry in entries] == [
        "out_of_bounds", "invalid_precondition"]


def test_build_excludes_non_eligible_items_explicitly(tmp_path) -> None:
    root = _dataset(tmp_path, decisions={"a": _eligible(), "b": REJECTED}, audits={"a": _audit()})
    out = tmp_path / "eligible"
    build_eligible(root, out)

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert [item["id"] for item in manifest["items"]] == ["a"]
    assert not (out / "bugs" / "b.py").exists()
    assert not (out / "detection" / "b.py").exists()


def test_non_formal_category_is_never_eligible(tmp_path) -> None:
    root = _dataset(tmp_path, decisions={"a": _eligible(), "b": _eligible(["incorrect_result"])},
                    audits={"a": _audit(), "b": _audit()})
    with pytest.raises(EligibilityError, match="non-formal category incorrect_result"):
        build_eligible(root, tmp_path / "eligible")


def test_eligible_requires_provenance(tmp_path) -> None:
    root = _dataset(tmp_path, decisions={"a": _eligible(), "b": REJECTED}, audits={"a": _audit()},
                    provenance={"repo_url": "", "fixed_commit": ""})
    with pytest.raises(EligibilityError, match="missing repo_url"):
        build_eligible(root, tmp_path / "eligible")


def test_eligible_requires_patch_evidence(tmp_path) -> None:
    root = _dataset(tmp_path, decisions={"a": _eligible(), "b": REJECTED}, audits={"a": _audit()})
    (root / "patches" / "a.diff").unlink()
    with pytest.raises(EligibilityError, match="missing patches"):
        build_eligible(root, tmp_path / "eligible")


@pytest.mark.parametrize(
    ("audit", "message"),
    [
        (_audit(fixed="failed"), "fixed harness: failed"),
        (_audit(buggy="successful"), "buggy harness: successful"),
        (_audit(prop="unwinding_assertion"), "expected failed 'IndexError'"),
    ],
)
def test_eligible_requires_buggy_fail_and_fixed_pass(tmp_path, audit, message) -> None:
    root = _dataset(tmp_path, decisions={"a": _eligible(), "b": REJECTED}, audits={"a": audit})
    with pytest.raises(EligibilityError, match=message):
        build_eligible(root, tmp_path / "eligible")


def test_symptom_must_match_every_category(tmp_path) -> None:
    root = _dataset(tmp_path, decisions={"a": _eligible(prop="KeyError"), "b": REJECTED},
                    audits={"a": _audit(prop="KeyError")})
    with pytest.raises(EligibilityError, match="symptom KeyError incompatible with out_of_bounds"):
        build_eligible(root, tmp_path / "eligible")


def test_detection_showing_fixed_code_is_rejected(tmp_path) -> None:
    root = _dataset(tmp_path, decisions={"a": _eligible(), "b": REJECTED}, audits={"a": _audit()},
                    detection=FIXED_SOURCE)
    with pytest.raises(EligibilityError, match="detection does not show the pre-fix code"):
        build_eligible(root, tmp_path / "eligible")


def test_detection_check_distinguishes_buggy_from_fixed_source() -> None:
    assert detection_shows_buggy_code(BUGGY_SOURCE, DIFF)
    assert not detection_shows_buggy_code(FIXED_SOURCE, DIFF)
    assert not detection_shows_buggy_code(FIXED_SOURCE + "\n" + BUGGY_SOURCE, DIFF)


def test_every_real_item_has_a_decision_with_a_valid_status() -> None:
    # Only bugs with a hand-written harness in bugs/ go through eligibility.
    gt_ids = {item["id"] for item in json.loads((DATASET / "ground_truths.json").read_text())["items"]
              if "harness_file" in item}
    decisions = json.loads((DATASET / "eligibility.json").read_text(encoding="utf-8"))["items"]
    assert set(decisions) == gt_ids
    assert {d["status"] for d in decisions.values()} <= {
        "eligible", "needs_review", "unsupported_by_esbmc", "rejected"}
    assert all(d["reason"] for d in decisions.values())


def test_real_eligible_items_use_only_formal_categories() -> None:
    decisions = json.loads((DATASET / "eligibility.json").read_text(encoding="utf-8"))["items"]
    for key, decision in decisions.items():
        if decision["status"] == "eligible":
            assert set(decision["categories"]) <= FORMAL_CATEGORIES, key


def test_committed_eligible_subset_matches_a_fresh_build(tmp_path) -> None:
    fresh = tmp_path / "eligible"
    build_eligible(DATASET, fresh)

    for name in ("ground_truths.json", "manifest.json"):
        assert json.loads((ELIGIBLE / name).read_text(encoding="utf-8")) == json.loads(
            (fresh / name).read_text(encoding="utf-8")), name
    for folder in ("bugs", "detection"):
        comparison = filecmp.dircmp(ELIGIBLE / folder, fresh / folder)
        assert not (comparison.left_only or comparison.right_only or comparison.diff_files), folder
        for name in comparison.common_files:
            assert (ELIGIBLE / folder / name).read_bytes() == (DATASET / folder / name).read_bytes()


def test_every_fixed_harness_pairs_with_a_dataset_item() -> None:
    ids = {item["id"] for item in json.loads((DATASET / "ground_truths.json").read_text())["items"]}
    fixed = {path.name.removesuffix("_fixed.py") for path in (DATASET / "bugs").glob("*_fixed.py")}
    assert fixed <= ids

