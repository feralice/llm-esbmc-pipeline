#!/usr/bin/env python3
"""Roda ESBMC em todos os arquivos do dataset exceto code smells.

Usa os flags corretos por categoria:
  - assertion_violation : --unwind 5
  - division_by_zero    : --no-bounds-check --unwind 5
  - out_of_bounds       : --no-div-by-zero-check --assign-param-nondet --unwind 5
  - clean               : --unwind 5 (espera VERIFICATION SUCCESSFUL)

Uso:
    python scripts/run_esbmc_dataset.py
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "dataset/labeled/ok"
UNWIND = 5
TIMEOUT = 30

CATEGORY_FLAGS: dict[str, list[str]] = {
    "assertion_violation": [],
    "division_by_zero":    ["--no-bounds-check"],
    "out_of_bounds":       ["--no-div-by-zero-check", "--assign-param-nondet"],
    "clean":               [],
}

# Categorias que devem encontrar violação
BUG_CATEGORIES = {"assertion_violation", "division_by_zero", "out_of_bounds"}


def get_first_function(file_path: Path) -> str | None:
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("test_"):
            return node.name
    return None


def run_esbmc(file_path: Path, function_name: str, extra_flags: list[str]) -> tuple[str, str]:
    cmd = [
        "esbmc", "--python", "python3",
        str(file_path),
        "--function", function_name,
        "--unwind", str(UNWIND),
        *extra_flags,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
        combined = result.stdout + result.stderr
        if "VERIFICATION FAILED" in combined:
            return "FAILED", combined
        if "VERIFICATION SUCCESSFUL" in combined:
            return "SUCCESSFUL", combined
        return "inconclusive", combined
    except subprocess.TimeoutExpired:
        return "timeout", ""


def main() -> None:
    summary: dict[str, dict[str, int]] = {}

    print(f"{'Arquivo':<22} {'Categoria':<22} {'Função':<28} {'ESBMC':<14} {'OK?'}")
    print("-" * 100)

    for category, extra_flags in CATEGORY_FLAGS.items():
        if category == "clean":
            cat_dir = DATASET / "clean"
        else:
            cat_dir = DATASET / "bugs" / category

        files = sorted(cat_dir.glob("*.py"))
        counts = {"ok": 0, "fail": 0, "skip": 0}

        for file_path in files:
            func = get_first_function(file_path)
            if not func:
                print(f"{file_path.name:<22} {category:<22} {'(sem função)':<28} {'SKIP':<14} -")
                counts["skip"] += 1
                continue

            status, output = run_esbmc(file_path, func, extra_flags)

            if category in BUG_CATEGORIES:
                # bug: espera FAILED
                ok = "✓" if status == "FAILED" else "✗"
                if status == "FAILED":
                    counts["ok"] += 1
                else:
                    counts["fail"] += 1
            else:
                # clean: espera SUCCESSFUL
                ok = "✓" if status == "SUCCESSFUL" else "✗"
                if status == "SUCCESSFUL":
                    counts["ok"] += 1
                else:
                    counts["fail"] += 1

            # Extrai keyword da saída
            kw = ""
            if "dereference failure" in output.lower():
                kw = "dereference"
            elif "division by zero" in output.lower():
                kw = "div-by-zero"
            elif "assertion" in output.lower() and "FAILED" in status:
                kw = "assertion"
            elif status == "inconclusive":
                # pega primeira linha de erro se houver
                for line in (output.splitlines()):
                    if "error" in line.lower() or "crash" in line.lower():
                        kw = line.strip()[:30]
                        break

            print(f"{file_path.name:<22} {category:<22} {func:<28} {status:<14} {ok}  {kw}")

        summary[category] = counts
        total = counts["ok"] + counts["fail"] + counts["skip"]
        print(f"  → {category}: {counts['ok']}/{total} {'violations' if category in BUG_CATEGORIES else 'safe'}\n")

    print("=" * 100)
    print("RESUMO FINAL")
    print("=" * 100)
    grand_ok = grand_total = 0
    for cat, counts in summary.items():
        total = counts["ok"] + counts["fail"] + counts["skip"]
        grand_ok += counts["ok"]
        grand_total += total
        label = "violation found" if cat in BUG_CATEGORIES else "verified safe"
        print(f"  {cat:<25} {counts['ok']:>2}/{total}  ({label})")
    print(f"\n  TOTAL: {grand_ok}/{grand_total} arquivos com resultado esperado")


if __name__ == "__main__":
    main()
