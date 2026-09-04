from __future__ import annotations

import ast
import json
import re
from collections import Counter
from pathlib import Path

from .evaluator import load_ground_truth_cases
from .llm.findings import normalize_findings
from .models import Finding
from .preprocess import preprocess_file

_LEAKY_NAME = re.compile(r"(^|_)(buggy|correct|fixed|broken|unsafe)($|_)", re.IGNORECASE)
_LEAKY_COMMENT = re.compile(
    r"\b(real bug|before the fix|pre-fix|buggy|the fix|correct behavior|crash trigger)\b",
    re.IGNORECASE,
)


def audit_dataset(ground_truth_path: str | Path) -> dict:
    """Audit whether a dataset is suitable for function-level LLM detection."""
    path = Path(ground_truth_path)
    raw = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    raw_items = raw.get("items", []) if isinstance(raw, dict) else []
    ids = [str(item.get("id", "")) for item in raw_items]
    files = [str(item.get("file", "")) for item in raw_items]

    issues: list[dict] = []
    for value, count in Counter(ids).items():
        if value and count > 1:
            issues.append({"code": "duplicate_id", "id": value, "count": count})
    for value, count in Counter(files).items():
        if value and count > 1:
            issues.append({"code": "duplicate_file", "file": value, "count": count})

    checked_labels = 0
    accepted_labels = 0
    for source_path, expected in load_ground_truth_cases(path):
        source = source_path.read_text(encoding="utf-8") if source_path.exists() else ""
        units = {unit.name: unit for unit in preprocess_file(source_path)} if source else {}
        for entry in expected:
            if not entry.get("verifiable", False):
                continue
            checked_labels += 1
            function = str(entry.get("function", ""))
            category = str(entry.get("category", ""))
            expression = str(entry.get("expression", ""))
            unit = units.get(function)
            prefix = {"file": source_path.name, "function": function, "category": category}
            if unit is None:
                issues.append({**prefix, "code": "missing_target_function"})
                continue
            if _LEAKY_NAME.search(function):
                issues.append({**prefix, "code": "label_leak_in_function_name"})
            if _has_leaky_comment(unit.source):
                issues.append({**prefix, "code": "label_leak_in_comments"})

            finding = Finding(
                id="dataset-audit", stage="audit", finding_type="suspected_bug",
                category=category, title="", explanation="", evidence=[],
                verifiable=True, confidence="high",
                metadata={"expression": expression, "line": entry.get("line", 0)},
            )
            normalized = normalize_findings(unit, [finding])[0]
            if normalized.verifiable:
                accepted_labels += 1
            else:
                issues.append({
                    **prefix,
                    "code": "ground_truth_not_grounded_in_target",
                    "expression": expression,
                    "reason": normalized.metadata.get("ast_rejection_reason", "unknown"),
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
