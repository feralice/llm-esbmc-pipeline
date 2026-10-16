"""Wrong-result hypotheses: ESBMC looks for an input that breaks the LLM's postcondition, the CPython
replay confirms the original breaks it, and (evaluation only) the fixed version, fed the same input,
must keep it. The fixed version is read only here, after the LLM is done."""

from __future__ import annotations

import ast
import copy
import textwrap

from research_pipeline.models import ESBMCDirectResult
from research_pipeline.verification.esbmc_runner import _ESBMC_LIBRARY_PATHS

from .astutil import find_function
from .grounding import _BINDING_DECORATORS
from .outcome import (
    ESBMC_MISSED,
    NOT_CONFIRMED,
    OTHER_FAILURE,
    PROPERTY_REJECTED,
    UNVALIDATED,
    VALUE_CONFIRMED,
    VALUE_VIOLATION,
    EsbmcReading,
    final_verdict,
)
from .render import Program
from .replay import ReplayVerdict, concrete_replay


def esbmc_hits_property(esbmc: ESBMCDirectResult, property_line: int) -> bool:
    """By line, not by message: the text ESBMC prints for an assert is not part of the contract. An
    assertion inside ESBMC's own models may share the line number, so its file must not be a model's."""
    records = esbmc.details.get("violated_property_records") or []
    return any(str(r.get("kind", "")).lower().startswith("assertion") and r.get("line") == property_line
               and not any(path in str(r.get("file", "")) for path in _ESBMC_LIBRARY_PATHS)
               for r in records)


def value_verdict(reading: EsbmcReading, property_hit: bool, replay: ReplayVerdict) -> str:
    if reading.kind == "violation":
        if replay.status == "property_violated":
            return VALUE_VIOLATION if property_hit else UNVALIDATED
        return OTHER_FAILURE if replay.status in {"reproduced", "other_failure"} else UNVALIDATED
    if reading.kind in {"safe", "artifact"}:
        return ESBMC_MISSED if replay.status == "property_violated" else NOT_CONFIRMED
    return final_verdict(reading, replay)


def _first_line(node: ast.FunctionDef) -> int:
    return min([node.lineno, *(d.lineno for d in node.decorator_list)])


def control_program(program: Program, function: str, fixed_source: str) -> Program | None:
    """The replay program with the target swapped for its fixed version; the property line moves by the
    difference in length (the driver follows the target). None when either function is missing or the
    swap does not parse. Only the target is swapped: helpers stay as in the buggy version."""
    source = program.replay_source or program.source
    try:
        target = find_function(ast.parse(source), function)
        fixed = find_function(ast.parse(fixed_source), function)
    except SyntaxError:
        return None
    if target is None or fixed is None:
        return None
    first = _first_line(target)
    # Like grounding's _strip_decorators: wrapping decorators (and their definitions) are not in the program.
    fixed_lines = fixed_source.splitlines()
    kept = [line for d in fixed.decorator_list if ast.unparse(d) in _BINDING_DECORATORS
            for line in fixed_lines[d.lineno - 1:d.end_lineno]]
    text = "\n".join([*kept, *fixed_lines[fixed.lineno - 1:fixed.end_lineno]])
    body = textwrap.indent(textwrap.dedent(text), " " * target.col_offset).splitlines()
    lines = source.splitlines()
    spliced = "\n".join([*lines[:first - 1], *body, *lines[target.end_lineno:]]) + "\n"
    try:
        swapped = find_function(ast.parse(spliced), function)
    except SyntaxError:
        return None
    if swapped is None:
        return None
    delta = len(body) - (target.end_lineno - first + 1)
    line = program.property_line if program.replay_property_line is None else program.replay_property_line
    span = (swapped.lineno, swapped.end_lineno)
    return Program(spliced, 0, (span,), (), span, property_line=line + delta)


def _unchanged(program: Program, function: str, fixed_source: str) -> bool:
    """The fix lies elsewhere (e.g. a helper): only the target is swapped, so the control would rerun
    the same code and read as a wrong property."""
    try:
        original = find_function(ast.parse(program.replay_source or program.source), function)
        fixed = find_function(ast.parse(fixed_source), function)
    except SyntaxError:
        return False
    return original is not None and fixed is not None and _behaviour(original) == _behaviour(fixed)


def _behaviour(function: ast.FunctionDef) -> str:
    """The function as the control would run it: no annotations (render adds some to the buggy copy)
    and only binding decorators (grounding blanks the wrapping ones)."""
    function = copy.deepcopy(function)
    function.decorator_list = [d for d in function.decorator_list if ast.unparse(d) in _BINDING_DECORATORS]
    function.returns = None
    for node in ast.walk(function):
        if isinstance(node, ast.arg):
            node.annotation = None
    return ast.dump(function)


def check_fixed(program: Program, function: str, method_name: str, fixed_source: str,
                inputs: list | None) -> ReplayVerdict:
    """One run of the fixed version with the input that broke the original."""
    if inputs is None:
        return ReplayVerdict("unavailable", reason="the replay kept no input to give the fixed version")
    if _unchanged(program, function, fixed_source):
        return ReplayVerdict("unavailable", reason="the fixed version leaves the target function unchanged")
    control = control_program(program, function, fixed_source)
    if control is None:
        return ReplayVerdict("unavailable", reason="the fixed function does not fit the replay program")
    return concrete_replay(control, method_name, inputs=inputs)


def apply_control(verdict: str, control: ReplayVerdict | None) -> tuple[str, str]:
    """Only a clean run of the fixed version (it ends and keeps the property) confirms; an exception or
    an unavailable run says nothing about the property."""
    if verdict != VALUE_VIOLATION or control is None:
        return verdict, ""
    if control.status == "property_violated":
        return PROPERTY_REJECTED, "the fixed version breaks the property with the same input"
    if control.status == "not_reproduced":
        return VALUE_CONFIRMED, ""
    detail = control.exception_type or control.reason
    return VALUE_VIOLATION, f"control inconclusive: {control.status} {detail}".strip()
