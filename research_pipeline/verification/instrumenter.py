from __future__ import annotations

from pathlib import Path

from ..models import CodeUnit, FormalProperty, InstrumentationResult


_ESBMC_IMPORT_BLOCK = [
    "from esbmc import __ESBMC_assert, __ESBMC_assume, nondet_bool, nondet_int",
    "try:",
    "    from esbmc import nondet_float  # type: ignore[import-untyped]",
    "except ImportError:",
    "    # V1 fallback: some local ESBMC stubs do not expose symbolic floats.",
    "    def nondet_float() -> float:",
    "        return float(nondet_int())",
]


def instrument_unit(
    unit: CodeUnit,
    formal_property: FormalProperty,
    output_dir: str | Path,
) -> InstrumentationResult:
    source_lines = unit.path.read_text(encoding="utf-8").splitlines()
    source_lines = _strip_top_level_entrypoints(source_lines)
    insertion_index = _resolve_module_insertion_index(source_lines, formal_property, unit)
    indent = _detect_indent_for_line(source_lines, insertion_index)
    injected_lines = [
        f"{indent}assert {formal_property.assertion}, \"{formal_property.category}\""
    ]

    instrumented_lines = (
        source_lines[:insertion_index] + injected_lines + source_lines[insertion_index:]
    )
    driver_lines = _build_esbmc_driver(unit, formal_property.assumptions)
    instrumented_lines = _patch_import_lines(instrumented_lines)
    instrumented_source = "\n".join(
        ["# mypy: disable-error-code=name-defined", *_ESBMC_IMPORT_BLOCK, *instrumented_lines, "", *driver_lines]
    ) + "\n"

    output_path = Path(output_dir) / f"{_sanitize_filename(formal_property.finding_id)}.py"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(instrumented_source, encoding="utf-8")

    return InstrumentationResult(
        finding_id=formal_property.finding_id,
        category=formal_property.category,
        instrumented_source=instrumented_source,
        assertions=[formal_property.assertion],
        assumptions=formal_property.assumptions,
        esbmc_flags=formal_property.esbmc_flags,
        output_path=output_path,
    )


def _build_esbmc_driver(unit: CodeUnit, assumptions: list[str]) -> list[str]:
    call_args: list[str] = []
    param_setup: list[str] = []

    for parameter in unit.parameters:
        annotation = unit.type_hints.get(parameter, "")
        value_lines, argument_expr = _build_symbolic_value(parameter, annotation)
        param_setup.extend(value_lines)
        call_args.append(argument_expr)

    target_name = unit.name
    call_expr = f"{target_name}({', '.join(call_args)})"

    return [
        "def __esbmc_driver__() -> None:",
        *[f"    {line}" for line in param_setup],
        *[f"    __ESBMC_assume({assumption})" for assumption in assumptions],
        f"    {call_expr}",
        "",
        "__esbmc_driver__()",
    ]


def _build_symbolic_value(parameter: str, annotation: str) -> tuple[list[str], str]:
    normalized = annotation.replace(" ", "")

    if normalized in {"int", ""}:
        return [f"{parameter} = nondet_int()"], parameter

    if normalized in {"bool"}:
        return [f"{parameter} = nondet_bool()"], parameter

    if normalized in {"float"}:
        return [f"{parameter} = nondet_float()"], parameter

    if normalized in {"str"}:
        # LIMITAÇÃO CONHECIDA: parâmetros str recebem o valor concreto "abc".
        # O ESBMC não tem suporte a strings simbólicas; "abc" é usado como proxy.
        # Bugs que só se manifestam com strings específicas podem não ser detectados.
        return [f"{parameter} = \"abc\""], parameter

    if normalized in {"List[int]", "list[int]"}:
        return [
            f"{parameter} = [nondet_int(), nondet_int(), nondet_int()]",
        ], parameter

    if normalized in {"List[float]", "list[float]"}:
        return [
            f"{parameter} = [nondet_float(), nondet_float(), nondet_float()]",
        ], parameter

    return [f"{parameter} = nondet_int()"], parameter


def _detect_indent_for_line(lines: list[str], insertion_index: int) -> str:
    if 0 <= insertion_index < len(lines):
        stripped = lines[insertion_index].lstrip()
        if stripped:
            return lines[insertion_index][: len(lines[insertion_index]) - len(stripped)]

    for line in lines[1:]:
        stripped = line.lstrip()
        if stripped:
            return line[: len(line) - len(stripped)]
    return "    "


def _sanitize_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"_", "-", "."} else "_" for char in value)


def _patch_import_lines(source_lines: list[str]) -> list[str]:
    patched_lines: list[str] = []
    for line in source_lines:
        stripped = line.strip()
        if "from esbmc import" in stripped and "type: ignore" not in stripped:
            patched_lines.append(f"{line}  # type: ignore[import-untyped]")
        else:
            patched_lines.append(line)
    return patched_lines


def _strip_top_level_entrypoints(source_lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    skip_indented_block = False

    for line in source_lines:
        stripped = line.strip()
        current_indent = len(line) - len(line.lstrip())

        if skip_indented_block:
            if stripped and current_indent == 0:
                skip_indented_block = False
            else:
                continue

        if stripped == "main()":
            continue

        if stripped.startswith("if __name__ == "):
            skip_indented_block = True
            continue

        cleaned.append(line)

    return cleaned


def _resolve_module_insertion_index(
    source_lines: list[str],
    formal_property: FormalProperty,
    unit: CodeUnit,
) -> int:
    if formal_property.absolute_line is not None:
        return max(0, min(len(source_lines), formal_property.absolute_line - 1))
    if formal_property.insertion_line is not None:
        absolute_line = unit.start_line + formal_property.insertion_line - 1
        return max(0, min(len(source_lines), absolute_line - 1))
    return max(0, unit.start_line)
