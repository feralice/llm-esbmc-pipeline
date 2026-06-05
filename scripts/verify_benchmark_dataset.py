from __future__ import annotations

import ast
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_pipeline.evaluator import load_ground_truth_cases

EXTERNAL_IMPORTS = {
    "numpy", "pandas", "requests", "flask", "django", "scipy", "sklearn",
    "torch", "tensorflow", "pytest", "hypothesis",
}
BUG_CATEGORIES = {"division_by_zero", "out_of_bounds", "assertion_violation"}
SMELL_CATEGORIES = {"long_method", "many_parameters", "complex_conditional"}


def parse_file(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return None


def functions(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    return {node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}


def no_top_level_execution(tree: ast.Module) -> list[str]:
    issues: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            issues.append(f"top-level call at line {node.lineno}")
        if isinstance(node, ast.If):
            issues.append(f"top-level if at line {node.lineno}")
    return issues


def no_external_imports(tree: ast.Module) -> list[str]:
    issues: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        for name in names:
            base = name.split(".")[0]
            if base in EXTERNAL_IMPORTS:
                issues.append(f"external import: {name}")
    return issues


def type_hint_issues(func: ast.FunctionDef) -> list[str]:
    issues: list[str] = []
    for arg in func.args.args:
        if arg.annotation is None:
            issues.append(f"parameter without type hint: {arg.arg}")
    if func.returns is None:
        issues.append("return without type hint")
    return issues


def category_shape_issues(expected: dict) -> list[str]:
    category = expected.get("category", "")
    verifiable = expected.get("verifiable")
    should_go = expected.get("should_go_to_esbmc")
    issues: list[str] = []

    if category in BUG_CATEGORIES:
        if verifiable is not True:
            issues.append("bug category must be verifiable=true")
        if should_go is not True:
            issues.append("bug category must go to ESBMC")
        if not expected.get("expression"):
            issues.append("bug category must have expression")
    elif category == "clean":
        if verifiable is not False:
            issues.append("clean must be verifiable=false")
        if should_go is not False:
            issues.append("clean must not go to ESBMC")
    elif category in SMELL_CATEGORIES:
        if verifiable is not False:
            issues.append("smell must be verifiable=false")
        if should_go is not False:
            issues.append("smell must not go to ESBMC")
        if expected.get("expected_type") != "smell":
            issues.append("smell must have expected_type=smell")
    else:
        issues.append(f"unknown category: {category}")
    return issues


def verify_case(path: Path, expected: dict) -> list[str]:
    issues: list[str] = []
    issues.extend(category_shape_issues(expected))

    if not path.exists():
        return issues + [f"missing file: {path}"]

    tree = parse_file(path)
    if tree is None:
        return issues + ["syntax error"]

    func_name = expected.get("function", "")
    funcs = functions(tree)
    if func_name not in funcs:
        issues.append(f"function not found: {func_name}")
    else:
        issues.extend(type_hint_issues(funcs[func_name]))

    issues.extend(no_top_level_execution(tree))
    issues.extend(no_external_imports(tree))
    return issues


def main() -> int:
    gt = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dataset/labeled/ground_truths"
    cases = load_ground_truth_cases(gt)
    failures: list[tuple[Path, str, list[str]]] = []
    counts: Counter[str] = Counter()

    for path, expected_list in cases:
        for expected in expected_list:
            category = str(expected.get("category", ""))
            counts[category] += 1
            issues = verify_case(path, expected)
            if issues:
                failures.append((path, str(expected.get("id", "")), issues))

    print(f"ground_truth: {gt}")
    print(f"cases: {len(cases)}")
    print("categories:")
    for category, total in sorted(counts.items()):
        print(f"  {category}: {total}")

    if failures:
        print("\nFAILURES:")
        for path, item_id, issues in failures:
            print(f"  {item_id} :: {path}")
            for issue in issues:
                print(f"    - {issue}")
        return 1

    print("\nDATASET OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())