#!/usr/bin/env python3
"""Testa ESBMC com --assign-param-nondet em todos os arquivos out_of_bounds.

Uso:
    python scripts/test_oob_assign_nondet.py
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OOB_DIR = ROOT / "dataset/labeled/ok/bugs/out_of_bounds"
UNWIND = 5
TIMEOUT = 30


def get_function_names(file_path: Path) -> list[str]:
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    return [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("test_")
    ]


def run_esbmc(file_path: Path, function_name: str) -> tuple[str, str]:
    cmd = [
        "esbmc", "--python", "python3",
        str(file_path),
        "--function", function_name,
        "--assign-param-nondet",
        "--unwind", str(UNWIND),
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
            status = "VIOLATION FOUND"
        elif "VERIFICATION SUCCESSFUL" in combined:
            status = "no violation"
        else:
            status = "inconclusive"
        return status, combined
    except subprocess.TimeoutExpired:
        return "timeout", ""


def main() -> None:
    files = sorted(OOB_DIR.glob("*.py"))
    if not files:
        print(f"Nenhum arquivo encontrado em {OOB_DIR}", file=sys.stderr)
        sys.exit(1)

    print(f"{'Arquivo':<15} {'Função':<25} {'Status':<20} {'Keyword encontrada'}")
    print("-" * 90)

    found = 0
    for file_path in files:
        functions = get_function_names(file_path)
        if not functions:
            print(f"{file_path.name:<15} {'(sem função)':<25} {'SKIP':<20}")
            continue

        func = functions[0]
        status, output = run_esbmc(file_path, func)

        keywords = []
        if "dereference failure" in output.lower():
            keywords.append("dereference failure")
        if "BMC_list_size" in output or "bmc_list_size" in output.lower():
            keywords.append("BMC_list_size")
        if "array" in output.lower() and "bound" in output.lower():
            keywords.append("array bounds")
        if "out-of-bounds" in output.lower() or "out of bounds" in output.lower():
            keywords.append("out-of-bounds")

        kw_str = ", ".join(keywords) if keywords else "-"
        print(f"{file_path.name:<15} {func:<25} {status:<20} {kw_str}")

        if status == "VIOLATION FOUND":
            found += 1

    print("-" * 90)
    print(f"\nViolação encontrada: {found}/{len(files)} arquivos")


if __name__ == "__main__":
    main()
