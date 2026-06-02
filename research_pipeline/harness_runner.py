from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .esbmc_runner import run_esbmc_direct
from .models import CodeUnit, ESBMCDirectResult
from .preprocess import preprocess_file

HARNESS_MODE_DIVISION = "division"
HARNESS_MODE_BOUNDS = "bounds"
DIVISION_TRIGGER = "division_by_zero_candidate"
BOUNDS_TRIGGER = "out_of_bounds_candidate"


@dataclass
class HarnessRunResult:
    source_file: str
    function: str
    harness_file: str
    trigger: str
    esbmc_result: ESBMCDirectResult

    def to_dict(self) -> dict:
        return {
            "source_file": self.source_file,
            "function": self.function,
            "harness_file": self.harness_file,
            "trigger": self.trigger,
            "esbmc_result": self.esbmc_result.to_dict(),
        }


def run_esbmc_harness_pipeline(
    input_paths: list[str | Path],
    output_dir: str | Path = "artifacts/esbmc-harness",
    esbmc_command: list[str] | None = None,
    bound: int = 5,
    timeout_seconds: int = 30,
) -> list[HarnessRunResult]:
    output_path = Path(output_dir)
    harness_dir = output_path / "generated"
    harness_dir.mkdir(parents=True, exist_ok=True)

    results: list[HarnessRunResult] = []
    for input_path in input_paths:
        file_path = Path(input_path)
        for unit in preprocess_file(file_path):
            if _has_division_candidate(unit):
                result = _run_generated_harness(
                    file_path=file_path,
                    function_name=unit.name,
                    harness_dir=harness_dir,
                    output_path=output_path,
                    trigger=DIVISION_TRIGGER,
                    suffix=HARNESS_MODE_DIVISION,
                    harness_source=build_harness(
                        file_path,
                        unit.name,
                        harness_mode=HARNESS_MODE_DIVISION,
                    ),
                    esbmc_command=esbmc_command,
                    bound=bound,
                    timeout_seconds=timeout_seconds,
                )
                if result is not None:
                    results.append(result)

            if _has_bounds_candidate(unit):
                result = _run_generated_harness(
                    file_path=file_path,
                    function_name=unit.name,
                    harness_dir=harness_dir,
                    output_path=output_path,
                    trigger=BOUNDS_TRIGGER,
                    suffix=HARNESS_MODE_BOUNDS,
                    harness_source=build_harness(
                        file_path,
                        unit.name,
                        harness_mode=HARNESS_MODE_BOUNDS,
                    ),
                    esbmc_command=esbmc_command,
                    bound=bound,
                    timeout_seconds=timeout_seconds,
                )
                if result is not None:
                    results.append(result)

    summary_path = output_path / "esbmc_harness_results.json"
    summary_path.write_text(
        json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return results


def _has_division_candidate(unit: CodeUnit) -> bool:
    return any(operation.kind == "division" for operation in unit.operations)


def _has_bounds_candidate(unit: CodeUnit) -> bool:
    return any(
        operation.kind == "subscript" or ".pop(" in operation.expression
        for operation in unit.operations
    )


def _run_generated_harness(
    file_path: Path,
    function_name: str,
    harness_dir: Path,
    output_path: Path,
    trigger: str,
    suffix: str,
    harness_source: str | None,
    esbmc_command: list[str] | None,
    bound: int,
    timeout_seconds: int,
) -> HarnessRunResult | None:
    if harness_source is None:
        return None

    harness_file = harness_dir / f"{file_path.stem}_{function_name}_{suffix}_harness.py"
    harness_file.write_text(harness_source, encoding="utf-8")
    esbmc_result = run_esbmc_direct(
        harness_file,
        esbmc_command=esbmc_command,
        bound=bound,
        timeout_seconds=timeout_seconds,
        output_dir=output_path,
    )
    return HarnessRunResult(
        source_file=str(file_path.resolve()),
        function=function_name,
        harness_file=str(harness_file.resolve()),
        trigger=trigger,
        esbmc_result=esbmc_result,
    )


def build_harness(
    file_path: str | Path,
    function_name: str,
    harness_mode: str,
) -> str | None:
    file_path = Path(file_path)
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: list[str] = []
    target: ast.FunctionDef | ast.AsyncFunctionDef | None = None

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(ast.get_source_segment(source, node) or ast.unparse(node))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            target = node

    if target is None:
        return None

    function_source = ast.get_source_segment(source, target) or ast.unparse(target)
    arguments = _build_arguments(target, harness_mode=harness_mode)
    if arguments is None:
        return None

    header = "\n".join(_filter_imports(imports))
    if header:
        header += "\n\n"

    return (
        f"{header}"
        f"{function_source}\n\n\n"
        "def main():\n"
        f"    result = {function_name}({', '.join(arguments)})\n"
        "    return result\n\n\n"
        "main()\n"
    )


def _filter_imports(imports: list[str]) -> list[str]:
    # Keep ordinary imports that ESBMC can usually model. Drop heavy external packages.
    blocked = ("numpy", "torch", "neuronxcc")
    return [
        item
        for item in imports
        if not any(re.search(rf"\b{name}\b", item) for name in blocked)
    ]


def _build_arguments(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    harness_mode: str,
) -> list[str] | None:
    denominators = _division_denominators(node)
    args: list[str] = []
    for arg in node.args.args:
        name = arg.arg
        hint = ast.unparse(arg.annotation) if arg.annotation is not None else ""
        args.append(_value_for_parameter(name, hint, denominators, harness_mode))
    return args


def _division_denominators(node: ast.AST) -> set[str]:
    denominators: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.BinOp) and isinstance(child.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            denominators.add(ast.unparse(child.right))
    return denominators


def _value_for_parameter(
    name: str,
    hint: str,
    denominators: set[str],
    harness_mode: str,
) -> str:
    lowered = name.lower()
    hint_lower = hint.lower()

    if harness_mode == HARNESS_MODE_BOUNDS:
        if _looks_like_sequence_parameter(lowered, hint_lower):
            return "[]"
        if "str" in hint_lower or lowered in {"content_disposition", "text", "name", "s"}:
            return "\"x\""
        if "index" in lowered or lowered in {"i", "idx", "pos"}:
            return "5"

    if name in denominators or lowered in {"divisor", "denom", "denominator", "step_size"}:
        return "0.0" if "float" in hint_lower else "0"

    # Common host-side arithmetic edge case: step_size = chunk_size - 1.
    if "chunk" in lowered or lowered in {"wdw_size", "window_size", "pool_size"}:
        return "1"

    if "list" in hint_lower or hint_lower.startswith("list"):
        return "[1, 2, 3]"
    if "float" in hint_lower:
        return "5.0"
    if "str" in hint_lower:
        return "\"a\""
    if "bool" in hint_lower:
        return "True"

    return "5"


def _looks_like_sequence_parameter(parameter_name: str, type_hint: str) -> bool:
    sequence_names = {"items", "values", "script_parts", "parts"}
    return (
        "list" in type_hint
        or type_hint.startswith("list")
        or parameter_name in sequence_names
    )
