"""Wrong-result hypotheses: ESBMC looks for an input that breaks the LLM's postcondition, the CPython
replay confirms the original breaks it, and (evaluation only) the fixed version, fed the same input,
must keep it. The fixed version is read only here, after the LLM is done."""

from __future__ import annotations

import ast
import copy
import textwrap
from dataclasses import replace

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
from .spec import parse_spec


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
    if reading.kind == "safe":
        return ESBMC_MISSED if replay.status == "property_violated" else NOT_CONFIRMED
    return final_verdict(reading, replay)


def value_outcome(reading: EsbmcReading, esbmc: ESBMCDirectResult, program: Program, function: str,
                  method_name: str, replay: ReplayVerdict, fixed_source: str | None,
                  original_source: str | None = None) -> tuple[str, str, ReplayVerdict | None]:
    """The verdict of a wrong-result hypothesis on ``program`` (the engine's or an agent's harness), the
    reason and the fixed-version control, when it ran."""
    verdict = value_verdict(reading, esbmc_hits_property(esbmc, program.property_line), replay)
    if verdict != VALUE_VIOLATION or fixed_source is None:
        return verdict, reading.message, None
    control = check_fixed(program, function, method_name, fixed_source, replay.inputs,
                          original_source=original_source, draws=replay.draws)
    verdict, why = apply_control(verdict, control)
    return verdict, why or reading.message, control


def engine_property(result: dict) -> tuple[str, str]:
    """``returns`` and ``postcondition`` of the last spec the engine accepted for this result, or empty
    strings when no attempt got that far (a rejected spec never reaches the harness)."""
    for attempt in reversed(result.get("attempts") or []):
        if "spec" not in attempt or attempt.get("problems"):
            continue
        try:
            spec = parse_spec(attempt["spec"])
        except ValueError:
            continue
        if spec.postcondition:
            return spec.returns, spec.postcondition
    return "", ""


def _first_line(node: ast.FunctionDef) -> int:
    return min([node.lineno, *(d.lineno for d in node.decorator_list)])


def _function_names(tree: ast.Module) -> list[str]:
    """Every name find_function looks up: module-level functions and methods of module-level classes."""
    names = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            names.append(node.name)
        elif isinstance(node, ast.ClassDef):
            names += [f"{node.name}.{m.name}" for m in node.body if isinstance(m, ast.FunctionDef)]
    return names


def changed_helpers(source: str, function: str, fixed_source: str, original_source: str | None) -> list[str]:
    """Functions of the program, other than the target, that the fix changed. Only a verbatim copy of the
    original's function counts: one the harness generated (a receiver's ``__init__``, a stub) differs
    from the original and stays."""
    if original_source is None:
        return []
    try:
        trees = [ast.parse(text) for text in (source, original_source, fixed_source)]
    except SyntaxError:
        return []
    changed = []
    for name in _function_names(trees[0]):
        program, original, fixed = (find_function(tree, name) for tree in trees)
        if name != function and program is not None and original is not None and fixed is not None \
                and _behaviour(program) == _behaviour(original) != _behaviour(fixed):
            changed.append(name)
    return changed


def _fixed_lines(fixed: ast.FunctionDef, fixed_lines: list[str], col_offset: int) -> list[str]:
    # Like grounding's _strip_decorators: wrapping decorators (and their definitions) are not in the program.
    kept = [line for d in fixed.decorator_list if ast.unparse(d) in _BINDING_DECORATORS
            for line in fixed_lines[d.lineno - 1:d.end_lineno]]
    text = "\n".join([*kept, *fixed_lines[fixed.lineno - 1:fixed.end_lineno]])
    return textwrap.indent(textwrap.dedent(text), " " * col_offset).splitlines()


def control_program(program: Program, function: str, fixed_source: str,
                    helpers: tuple[str, ...] = ()) -> Program | None:
    """The replay program with the target, and ``helpers`` (changed_helpers), swapped for their fixed
    versions; the property line moves by the change in length of the swaps above it (the driver follows
    the target). None when a function is missing from either side or the swap does not parse."""
    source = program.replay_source or program.source
    try:
        tree, fixed_tree = ast.parse(source), ast.parse(fixed_source)
    except SyntaxError:
        return None
    pairs = [(find_function(tree, name), find_function(fixed_tree, name)) for name in (function, *helpers)]
    if any(node is None or fixed is None for node, fixed in pairs):
        return None
    lines, fixed_lines = source.splitlines(), fixed_source.splitlines()
    line = program.property_line if program.replay_property_line is None else program.replay_property_line
    # Bottom up, so the swaps still to come keep their line numbers.
    for node, fixed in sorted(pairs, key=lambda pair: pair[0].lineno, reverse=True):
        first = _first_line(node)
        body = _fixed_lines(fixed, fixed_lines, node.col_offset)
        lines[first - 1:node.end_lineno] = body
        if first < line:
            line += len(body) - (node.end_lineno - first + 1)
    spliced = "\n".join(lines) + "\n"
    try:
        swapped = find_function(ast.parse(spliced), function)
    except SyntaxError:
        return None
    if swapped is None:
        return None
    span = (swapped.lineno, swapped.end_lineno)
    return Program(spliced, 0, (span,), (), span, property_line=line)


def _unchanged(program: Program, function: str, fixed_source: str) -> bool:
    """The fix leaves the target as it is: with no changed helper swapped either, the control would rerun
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
                inputs: list | None, *, original_source: str | None = None,
                draws: list | None = None) -> ReplayVerdict:
    """One run of the fixed version with the input that broke the original. With ``original_source`` (the
    buggy file) the helpers the fix changed are swapped too; with ``draws`` (where the original run drew
    each value) a control that draws them elsewhere is unavailable: each value would feed another input."""
    if inputs is None:
        return ReplayVerdict("unavailable", reason="the replay kept no input to give the fixed version")
    helpers = tuple(changed_helpers(program.replay_source or program.source, function, fixed_source,
                                    original_source))
    if not helpers and _unchanged(program, function, fixed_source):
        return ReplayVerdict("unavailable", reason="the fixed version leaves the target function unchanged")
    control = control_program(program, function, fixed_source, helpers)
    if control is None:
        return ReplayVerdict("unavailable", reason="the fixed function does not fit the replay program")
    verdict = concrete_replay(control, method_name, inputs=inputs)
    if draws is not None and verdict.draws is not None and verdict.draws != draws \
            and verdict.status in {"not_reproduced", "property_violated"}:
        verdict = ReplayVerdict("unavailable", inputs=inputs, draws=verdict.draws,
                                reason="the fixed version draws the nondet values in another order")
    return replace(verdict, reason=f"{verdict.reason} (helpers swapped: {', '.join(helpers)})".lstrip()
                   if helpers else verdict.reason)


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
