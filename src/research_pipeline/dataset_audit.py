from __future__ import annotations

import ast
import json
import re
import warnings
from collections import Counter
from pathlib import Path

from .ast_utils import expression_exists_as_statement
from .evaluator import load_ground_truth_cases
from .preprocess import preprocess_file

_LEAKY_NAME = re.compile(r"(^|_)(buggy|correct|fixed|broken|unsafe)($|_)", re.IGNORECASE)
_LEAKY_COMMENT = re.compile(
    r"\b(real bug|before the fix|pre-fix|buggy|the fix|correct behavior|crash trigger)\b",
    re.IGNORECASE,
)


def _match_unit(units, declared_function: str, expression: str):
    """Resolve a ground-truth function label to the real unit in the source.

    Mirrors main.py:_load_v2_oracle_candidates -- v2 dataset labels can name
    the bugs/ oracle function (e.g. buggy_match), which differs from the
    plain name shown to the detection LLM (match). Falls back to matching
    the suspect expression's text when the declared name isn't a unit here.
    """
    alternatives = [part.strip() for part in declared_function.split("/")]
    matched = next(
        (
            unit
            for unit in units
            if any(
                alt and (unit.qualname == alt or unit.name == alt.split(".")[-1])
                for alt in alternatives
            )
        ),
        None,
    )
    if matched is None and expression:
        matched = next((unit for unit in units if expression in unit.source), None)
    return matched


def _load_v2_manifest_cases(ground_truth_path: Path):
    """Audit the v2 flat-multilabel dataset against manifest.json,
    not ground_truths.json.

    main.py:_load_v2_oracle_candidates builds real candidates from the
    manifest's function/expression/detection_file fields. ground_truths.json
    carries different function/expression values for buggy-vs-correct cases
    (e.g. function="buggy_match", expression="buggy_match(s) ==
    correct_match(s)") describing the bugs/ oracle harness, not the code the
    detection LLM actually reads -- auditing against it false-flags every
    such case as unlabeled/ungrounded. Returns None when there's no sibling
    manifest (legacy/test datasets keep using load_ground_truth_cases).
    """
    manifest_path = ground_truth_path.parent / "manifest.json"
    if not manifest_path.is_file():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    grouped: dict[Path, list[dict]] = {}
    for item in manifest.get("items", []):
        if not isinstance(item, dict) or not item.get("detection_file"):
            continue
        source = manifest_path.parent / str(item["detection_file"])
        expected = grouped.setdefault(source, [])
        for category in item.get("categories", []):
            expected.append({
                "function": str(item.get("function", "")),
                "category": str(category),
                "verifiable": True,
                "expression": str(item.get("expression", "")),
                "line": item.get("line"),
            })
    return sorted(grouped.items(), key=lambda case: str(case[0]))


def _prefer_detection_source(source_path: Path) -> Path:
    """Resolve to the file the detection LLM actually reads.

    load_ground_truth_cases() points v2 flat-multilabel datasets at bugs/
    (the synthesized oracle harness, e.g. buggy_match/correct_match), which
    other callers need but is never shown to the detection LLM. When a
    sibling detection/ file exists, audit against that instead.
    """
    if source_path.parent.name != "bugs":
        return source_path
    candidate = source_path.parent.parent / "detection" / source_path.name
    return candidate if candidate.exists() else source_path


def audit_dataset(ground_truth_path: str | Path) -> dict:
    """Audit whether a dataset is suitable for function-level LLM detection."""
    path = Path(ground_truth_path)
    raw = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    raw_items = raw.get("items", []) if isinstance(raw, dict) else []
    ids = [str(item.get("id", "")) for item in raw_items]
    files = [str(item.get("harness_file", item.get("file", ""))) for item in raw_items]

    issues: list[dict] = []
    for value, count in Counter(ids).items():
        if value and count > 1:
            issues.append({"code": "duplicate_id", "id": value, "count": count})
    for value, count in Counter(files).items():
        if value and count > 1:
            issues.append({"code": "duplicate_file", "file": value, "count": count})

    checked_labels = 0
    accepted_labels = 0
    cases = _load_v2_manifest_cases(path) or load_ground_truth_cases(path)
    for raw_source_path, expected in cases:
        source_path = _prefer_detection_source(raw_source_path)
        source = source_path.read_text(encoding="utf-8") if source_path.exists() else ""
        units = preprocess_file(source_path) if source else []
        for entry in expected:
            if not entry.get("verifiable", False):
                continue
            checked_labels += 1
            function = str(entry.get("function", ""))
            category = str(entry.get("category", ""))
            expression = str(entry.get("expression", ""))
            unit = _match_unit(units, function, expression)
            prefix = {"file": source_path.name, "function": function, "category": category}
            if unit is None:
                issues.append({**prefix, "code": "missing_target_function"})
                continue
            if _LEAKY_NAME.search(unit.name) or _LEAKY_NAME.search(unit.qualname):
                issues.append({**prefix, "code": "label_leak_in_function_name"})
            if _has_leaky_comment(unit.source):
                issues.append({**prefix, "code": "label_leak_in_comments"})

            if expression_exists_as_statement(expression, unit.source):
                accepted_labels += 1
            else:
                issues.append({
                    **prefix,
                    "code": "ground_truth_not_grounded_in_target",
                    "expression": expression,
                    "reason": "expression_not_found",
                })

        if _has_hidden_oracle(source):
            issues.append({"file": source_path.name, "code": "oracle_hidden_in_skipped_main"})

    counts = Counter(issue["code"] for issue in issues)
    return {
        "ground_truth": str(path),
        "labels_checked": checked_labels,
        "labels_grounded_in_target": accepted_labels,
        "labels_not_grounded_in_target": checked_labels - accepted_labels,
        "issue_counts": dict(sorted(counts.items())),
        "issues": issues,
    }


def write_dataset_audit(report: dict, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _has_leaky_comment(source: str) -> bool:
    comments = [line for line in source.splitlines() if line.lstrip().startswith("#")]
    return bool(_LEAKY_COMMENT.search("\n".join(comments)))


def _has_hidden_oracle(source: str) -> bool:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in tree.body:
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "main"
            and any(isinstance(child, ast.Assert) for child in ast.walk(node))
        ):
            return True
    return False
