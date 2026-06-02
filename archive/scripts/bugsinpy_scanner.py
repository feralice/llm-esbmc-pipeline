#!/usr/bin/env python3
"""
Scan BugsInPy for division_by_zero and out_of_bounds bugs and extract
them in the research pipeline format (minimal .py + ground_truth JSON entry).

Usage:
    # Clone BugsInPy then scan + extract:
    python scripts/bugsinpy_scanner.py --clone --extract

    # Use existing clone:
    python scripts/bugsinpy_scanner.py --bugsinpy-dir ./BugsInPy --extract

    # Save candidate report without writing files:
    python scripts/bugsinpy_scanner.py --bugsinpy-dir ./BugsInPy --report-json report.json
"""

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

# ── bug keyword patterns (applied only to removed "-" lines) ─────────────────

PATTERNS = {
    "division_by_zero": [
        r'[\w\)\]]\s*/\s*[\w\(]',  # actual division operator
    ],
    "out_of_bounds": [
        r'[\w\.]+\[(?!\s*["\']).*?\]',  # subscript access (exclude dict literals)
    ],
}

# Noise patterns: removed lines that match these are ignored
NOISE = [
    r'^\s*#',               # comment lines
    r'^\s*"""',             # docstring
    r"^\s*'''",
    r'^\s*from\s',          # import statements
    r'^\s*import\s',
    r'^\s*raise\s',         # raise statements
    r'^\s*except\s',        # except clauses
    r'^\s*-{3,}',           # diff markers
]

BUGSINPY_REPO = "https://github.com/soarsmu/BugsInPy.git"
DEFAULT_BUGSINPY_DIR = Path("./BugsInPy")
DEFAULT_OUTPUT_DIR = Path("examples/labeled/ok")
GROUND_TRUTH_DIR = Path("examples/labeled/ground_truths/bugs")


# ── helpers ──────────────────────────────────────────────────────────────────

def clone_bugsinpy(target: Path) -> None:
    if target.exists():
        print(f"[skip] BugsInPy already at {target}")
        return
    print(f"[clone] {BUGSINPY_REPO} → {target}")
    subprocess.run(
        ["git", "clone", "--depth=1", BUGSINPY_REPO, str(target)],
        check=True,
    )


def iter_bugs(bugsinpy_dir: Path):
    """Yield (project, bug_id, patch_path) for every bug in BugsInPy."""
    projects_dir = bugsinpy_dir / "projects"
    if not projects_dir.exists():
        sys.exit(f"[error] {projects_dir} not found — is --bugsinpy-dir correct?")
    for project_dir in sorted(projects_dir.iterdir()):
        if not project_dir.is_dir():
            continue
        bugs_dir = project_dir / "bugs"
        if not bugs_dir.exists():
            continue
        for bug_dir in sorted(bugs_dir.iterdir()):
            if not bug_dir.is_dir():
                continue
            patch = bug_dir / "bug_patch.txt"
            if patch.exists():
                yield project_dir.name, bug_dir.name, patch


def is_noise(line: str) -> bool:
    return any(re.match(pat, line) for pat in NOISE)


def get_removed_lines(patch_text: str) -> list[tuple[str, str]]:
    """Return list of (file_path, removed_line) from a patch."""
    result = []
    current_file = None
    for line in patch_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
        elif line.startswith("-") and not line.startswith("---") and current_file:
            result.append((current_file, line[1:]))
    return result


def classify_removed_lines(removed_lines: list[tuple[str, str]]) -> dict[str, list]:
    """Return {category: [(file, line)]} for matching removed lines."""
    matches: dict[str, list] = {}
    for file_path, line in removed_lines:
        if is_noise(line):
            continue
        for category, patterns in PATTERNS.items():
            if any(re.search(pat, line) for pat in patterns):
                # Extra guard: skip lines where "division" token looks safe
                if category == "division_by_zero":
                    # Skip lines that are obviously safe (dividing by constants > 0)
                    if re.search(r'/\s*[1-9]\d*\.?\d*\b', line):
                        continue
                    # Skip Python 2 integer division in print/comment context
                    if '"""' in line or "'''" in line:
                        continue
                matches.setdefault(category, []).append((file_path, line.strip()))
                break
    return matches


def parse_hunks(patch_text: str) -> list[dict]:
    """Parse unified-diff patch into hunks with context and removed lines."""
    hunks = []
    current_file = None
    current_hunk = None

    for line in patch_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
        elif line.startswith("@@ "):
            func_hint = ""
            m = re.search(r"@@ .+@@ (.+)", line)
            if m:
                func_hint = m.group(1).strip()
            current_hunk = {
                "file": current_file,
                "func_hint": func_hint,
                "context": [],
                "removed": [],
            }
            hunks.append(current_hunk)
        elif current_hunk is not None:
            if line.startswith("-") and not line.startswith("---"):
                current_hunk["removed"].append(line[1:])
            elif line.startswith("+") and not line.startswith("+++"):
                pass  # skip added lines
            else:
                current_hunk["context"].append(line.lstrip(" "))

    return hunks


def extract_function_from_hunk(hunk: dict) -> tuple[str | None, str | None, int | None]:
    """
    Reconstruct the buggy function from a patch hunk.
    Returns (func_name, func_source, bug_line_in_func).
    """
    # Interleave: context lines keep position; removed lines are inserted
    # where they were relative to context (simplified: append both)
    all_lines = hunk["context"] + hunk["removed"]

    func_lines: list[str] = []
    func_name: str | None = None
    bug_line: int | None = None

    for line in all_lines:
        stripped = line.strip()
        if stripped.startswith("def "):
            m = re.match(r"def (\w+)", stripped)
            func_name = m.group(1) if m else None
            func_lines = [line]
        elif func_lines:
            func_lines.append(line)

    if not func_lines:
        # Fall back to func_hint from hunk header
        m = re.match(r"def (\w+)", hunk.get("func_hint", ""))
        if m:
            func_name = m.group(1)
        return func_name, None, None

    source = dedent("\n".join(func_lines))

    # Validate syntax
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_name = node.name
                break
    except SyntaxError:
        pass

    # Find line number of buggy expression in the function
    for removed_line in hunk["removed"]:
        rs = removed_line.strip()
        if not rs or is_noise(removed_line):
            continue
        for i, fl in enumerate(func_lines):
            if rs and rs in fl:
                bug_line = i + 1
                break
        if bug_line:
            break

    return func_name, source, bug_line


def find_buggy_expression(hunk: dict, category: str) -> str | None:
    """Extract key buggy expression, searching removed lines then context."""
    search_order = hunk["removed"] + hunk["context"]
    for line in search_order:
        stripped = line.strip()
        if not stripped or is_noise(line):
            continue
        if category == "division_by_zero" and re.search(r'[\w\)\]]\s*/\s*[\w\(]', stripped):
            m = re.search(r'[\w\.\[\]()]+\s*/\s*[\w\.\[\]()]+', stripped)
            if m:
                return m.group(0)
        if category == "out_of_bounds":
            m = re.search(r'[\w\.]+\[.+?\]', stripped)
            if m:
                return m.group(0)
    # Fallback: first non-trivial removed line
    for line in hunk["removed"]:
        stripped = line.strip()
        if stripped and not is_noise(line):
            return stripped[:80]
    return None


def make_minimal_py(func_name: str, func_source: str) -> str:
    """Return a minimal Python file containing only the target function."""
    try:
        tree = ast.parse(func_source)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                lines = func_source.splitlines()
                return "\n".join(lines[node.lineno - 1 : node.end_lineno]) + "\n"
    except Exception:
        pass
    return func_source


def make_stub(project: str, bug_id: str, category: str, expression: str | None) -> str:
    """Fallback stub when function cannot be auto-extracted."""
    if category == "division_by_zero":
        expr = expression or "numerator / denominator"
        return (
            f"# TODO: fill in real body from {project} bug #{bug_id}\n"
            f"def {project}_div_zero(numerator, denominator):\n"
            f"    return {expr}\n"
        )
    expr = expression or "items[index]"
    return (
        f"# TODO: fill in real body from {project} bug #{bug_id}\n"
        f"def {project}_oob(items, index):\n"
        f"    return {expr}\n"
    )


# ── scanning ─────────────────────────────────────────────────────────────────

def scan(bugsinpy_dir: Path) -> list[dict]:
    candidates = []
    seen: set[tuple] = set()

    for project, bug_id, patch_path in iter_bugs(bugsinpy_dir):
        patch_text = patch_path.read_text(errors="replace")
        removed_lines = get_removed_lines(patch_text)
        category_matches = classify_removed_lines(removed_lines)
        if not category_matches:
            continue

        hunks = parse_hunks(patch_text)

        for category, matched_lines in category_matches.items():
            key = (project, bug_id, category)
            if key in seen:
                continue
            seen.add(key)

            # Find best hunk for this category
            best_hunk = None
            for hunk in hunks:
                for _, ml in matched_lines:
                    hunk_text = " ".join(hunk["removed"])
                    if ml[:40] in hunk_text:
                        best_hunk = hunk
                        break
                if best_hunk:
                    break
            if best_hunk is None and hunks:
                best_hunk = hunks[0]

            func_name, func_source, bug_line = (None, None, None)
            expression = None
            if best_hunk:
                func_name, func_source, bug_line = extract_function_from_hunk(best_hunk)
                expression = find_buggy_expression(best_hunk, category)
            if expression is None and matched_lines:
                # Use the matched line as expression fallback
                expression = matched_lines[0][1][:80]

            candidates.append({
                "project": project,
                "bug_id": bug_id,
                "category": category,
                "file_in_project": matched_lines[0][0] if matched_lines else "",
                "func_name": func_name,
                "func_source": func_source,
                "expression": expression,
                "bug_line": bug_line,
                "auto_extractable": func_name is not None and func_source is not None,
            })

    return candidates


# ── output ───────────────────────────────────────────────────────────────────

def write_extracted_files(candidates: list[dict], output_dir: Path, gt_dir: Path) -> None:
    by_category: dict[str, list[dict]] = {}
    for c in candidates:
        by_category.setdefault(c["category"], []).append(c)

    for category, items in by_category.items():
        py_dir = output_dir / "bugs" / category
        py_dir.mkdir(parents=True, exist_ok=True)

        gt_path = gt_dir / f"{category}.json"
        if gt_path.exists():
            gt = json.loads(gt_path.read_text())
        else:
            gt = {
                "dataset_name": f"python-bugs-{category}",
                "category": category,
                "total_items": 0,
                "items": [],
            }

        existing_ids = {item["id"] for item in gt["items"]}
        added = 0

        for c in items:
            entry_id = f"bugsinpy_{c['project']}_{c['bug_id']}_{category}"
            if entry_id in existing_ids:
                print(f"[skip] {entry_id} already in ground truth")
                continue

            func_name = c["func_name"] or f"{c['project']}_bug_{c['bug_id']}"
            py_filename = f"{c['project']}_{c['bug_id']}_{category}.py"
            py_path = py_dir / py_filename

            if c["auto_extractable"] and c["func_source"]:
                content = make_minimal_py(func_name, c["func_source"])
                confidence = "medium"
            else:
                content = make_stub(c["project"], c["bug_id"], category, c["expression"])
                confidence = "low"
                print(f"[stub]  {entry_id}: auto-extract failed — stub written, needs manual review")

            py_path.write_text(content)
            print(f"[write] {py_path}")

            gt["items"].append({
                "id": entry_id,
                "source_dataset": "BugsInPy",
                "source_project": c["project"],
                "source_bug_id": c["bug_id"],
                "file": py_filename,
                "function": func_name,
                "expected_label": "bug",
                "expected_category": category,
                "expected_type": "suspected_bug",
                "line": c["bug_line"],
                "expression": c["expression"],
                "verifiable": True,
                "should_go_to_esbmc": True,
                "confidence": confidence,
                "source_file_in_project": c["file_in_project"],
                "needs_manual_review": not c["auto_extractable"],
            })
            existing_ids.add(entry_id)
            added += 1

        gt["total_items"] = len(gt["items"])
        gt_path.write_text(json.dumps(gt, indent=2, ensure_ascii=False))
        print(f"[gt]    {gt_path}  (+{added} new)")


def print_report(candidates: list[dict]) -> None:
    auto = sum(1 for c in candidates if c["auto_extractable"])
    print(f"\n{'='*65}")
    print(f"  BugsInPy Scan — {len(candidates)} candidates  "
          f"(auto: {auto}, stub: {len(candidates)-auto})")
    print(f"{'='*65}")
    by_cat: dict[str, list] = {}
    for c in candidates:
        by_cat.setdefault(c["category"], []).append(c)
    for cat, items in sorted(by_cat.items()):
        print(f"\n  [{cat.upper()}]  {len(items)} bugs")
        for c in items:
            flag = "✓" if c["auto_extractable"] else "?"
            fn = (c["func_name"] or c.get("func_hint", "") or "(unknown)")[:28]
            expr = (c["expression"] or "")[:50]
            print(f"  {flag} {c['project']:15s} #{c['bug_id']:5s}  fn={fn:30s}  {expr}")
    print()


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--bugsinpy-dir", type=Path, default=DEFAULT_BUGSINPY_DIR)
    parser.add_argument("--clone", action="store_true",
                        help="Clone BugsInPy before scanning")
    parser.add_argument("--extract", action="store_true",
                        help="Write .py files and update ground_truth JSONs")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--gt-dir", type=Path, default=GROUND_TRUTH_DIR)
    parser.add_argument("--report-json", type=Path,
                        help="Save full candidate list as JSON")
    args = parser.parse_args()

    if args.clone:
        clone_bugsinpy(args.bugsinpy_dir)

    if not args.bugsinpy_dir.exists():
        sys.exit(
            f"[error] {args.bugsinpy_dir} not found.\n"
            "Run with --clone or pass --bugsinpy-dir <path>."
        )

    print(f"[scan]  {args.bugsinpy_dir} ...")
    candidates = scan(args.bugsinpy_dir)
    print_report(candidates)

    if args.report_json:
        serializable = [{k: v for k, v in c.items() if k != "func_source"} for c in candidates]
        args.report_json.write_text(json.dumps(serializable, indent=2, ensure_ascii=False))
        print(f"[json]  {args.report_json}")

    if args.extract:
        print("[extract] writing files ...")
        write_extracted_files(candidates, args.output_dir, args.gt_dir)
    else:
        print("Tip: add --extract to write .py files and update ground_truth JSONs.")


if __name__ == "__main__":
    main()
