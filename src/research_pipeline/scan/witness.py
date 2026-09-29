"""Conservative attribution of an ESBMC counterexample to original Python."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from research_pipeline.scan.replay import ReplayCase


@dataclass(frozen=True)
class WitnessAssessment:
    status: str
    case: ReplayCase | None
    reason: str
    exception: str = ""
    # Whether the native exception is a usual symptom of the hypothesized
    # category; recorded like category_evidence, never used to reject.
    category_match: bool | None = None


# Categories whose bug is a wrong value, not an exception: they need an oracle.
ORACLE_CATEGORIES = frozenset({"assertion_violation", "incorrect_result"})
_CATEGORY_EXCEPTIONS = {
    "division_by_zero": {"ZeroDivisionError"},
    "out_of_bounds": {"IndexError", "KeyError"},
    "none_misuse": {"AttributeError", "TypeError"},
    "type_mismatch": {"TypeError", "AttributeError", "ValueError"},
    "invalid_precondition": {"ValueError", "TypeError", "IndexError", "KeyError", "AssertionError"},
    "integer_overflow": {"OverflowError"},
}


def _native_exception(kind: str) -> str | None:
    match = re.match(r"uncaught exception: ([A-Za-z_]\w*)", kind.strip(), re.IGNORECASE)
    if match:
        return match.group(1)
    lowered = kind.lower()
    if "division by zero" in lowered:
        return "ZeroDivisionError"
    if "index out of bounds" in lowered or "array bounds" in lowered:
        return "IndexError"
    return None
_SCALAR_TYPES = (str, int, float, bool, type(None))


def _line(location: object) -> int | None:
    match = re.search(r"\blinha\s+(\d+)\b", str(location), re.IGNORECASE)
    return int(match.group(1)) if match else None


def _same_file(reported: str, expected: str) -> bool:
    # ESBMC echoes the path it was given, which the runner makes cwd-relative.
    return bool(reported) and Path(reported).resolve() == Path(expected).resolve()


def _scalar_assignments(raw: object) -> dict[str, object] | None:
    if not isinstance(raw, list) or not raw:
        return None
    values: dict[str, object] = {}
    for item in raw:
        match = re.fullmatch(r"\s*([A-Za-z_]\w*)\s*=\s*(.*?)\s*", str(item))
        if not match:
            continue
        name, rendered = match.groups()
        if name in values:
            return None
        try:
            value = ast.literal_eval(rendered)
        except (ValueError, SyntaxError):
            continue
        if isinstance(value, _SCALAR_TYPES):
            values[name] = value
    return values or None


def _entry_function(source: str, function: str) -> ast.FunctionDef | None:
    # Object state, decorators and variadic bindings need an explicit entry contract.
    if "." in function:
        return None
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    candidates = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == function]
    if len(candidates) != 1:
        return None
    fn = candidates[0]
    if fn.decorator_list or fn.args.vararg or fn.args.kwarg or fn.args.kwonlyargs:
        return None
    return fn


def _case_for(source: str, function: str, values: dict[str, object]) -> ReplayCase | None:
    fn = _entry_function(source, function)
    if fn is None:
        return None
    args = list(fn.args.posonlyargs) + list(fn.args.args)
    if any(arg.arg not in values for arg in args):
        return None
    return ReplayCase(tuple(values[arg.arg] for arg in args), {})


def _driver_values(record: dict) -> dict[str, object] | None:
    """Scalar values assigned in the driver's own frame; repeats are ambiguous."""
    frames = record.get("assignments")
    if not isinstance(frames, list):
        return None
    values: dict[str, object] = {}
    seen: set[str] = set()
    for frame in frames:
        if not isinstance(frame, dict) or frame.get("function") != "main":
            continue
        name = str(frame.get("name", ""))
        if name in seen:
            return None
        seen.add(name)
        try:
            value = ast.literal_eval(str(frame.get("value", "")))
        except (ValueError, SyntaxError):
            continue
        if isinstance(value, _SCALAR_TYPES):
            values[name] = value
    return values


def _case_from_driver(source: str, function: str, driver_source: str, values: dict[str, object]) -> ReplayCase | None:
    """Rebuild entry arguments from the driver's single call to the target.

    Each argument must be a literal or a bare driver local with a concrete
    counterexample value; anything computed is left unattributed.
    """
    fn = _entry_function(source, function)
    if fn is None:
        return None
    try:
        driver = ast.parse(driver_source)
    except SyntaxError:
        return None
    calls = [node for node in ast.walk(driver)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == function]
    if len(calls) != 1 or calls[0].keywords:
        return None
    params = list(fn.args.posonlyargs) + list(fn.args.args)
    if len(calls[0].args) != len(params):
        return None
    resolved: list[object] = []
    for arg in calls[0].args:
        if isinstance(arg, ast.Name) and arg.id in values:
            resolved.append(values[arg.id])
            continue
        try:
            value = ast.literal_eval(arg)
        except ValueError:
            return None
        if not isinstance(value, _SCALAR_TYPES):
            return None
        resolved.append(value)
    return ReplayCase(tuple(resolved), {})


def assess_witness(
    details: dict,
    *,
    expected_category: str,
    rewritten_file: str,
    rewritten_line: int,
    original_source: str,
    function: str,
    executor,
    original_line: int | None = None,
    original_column: int | None = None,
    driver_source: str = "",
    rewritten_end_line: int | None = None,
    original_end_line: int | None = None,
) -> WitnessAssessment:
    """A statement anchor (``*_end_line`` given) matches any operation inside its lines;
    an expression anchor must match line and column exactly."""
    if original_line is None or (original_column is None and original_end_line is None):
        return WitnessAssessment("unattributed", None, "original suspect location is required")
    if expected_category in ORACLE_CATEGORIES:
        return WitnessAssessment("unattributed", None, "category needs an independent oracle, not a native property")

    properties = details.get("violated_property_records")
    if not isinstance(properties, list):
        return WitnessAssessment("unattributed", None, "per-property evidence is missing")
    targets = [
        prop for prop in properties
        if isinstance(prop, dict)
        and _same_file(str(prop.get("file", "")), rewritten_file)
        and _line(prop.get("location")) is not None
        and rewritten_line <= _line(prop.get("location")) <= (rewritten_end_line or rewritten_line)
        and _native_exception(str(prop.get("kind", "")))
    ]
    raised = {_native_exception(str(prop.get("kind", ""))) for prop in targets}
    if len(raised) != 1:
        return WitnessAssessment("unattributed", None, "native violation is missing or ambiguous at the suspect line")
    exception = raised.pop()
    exception_matches = {exception}
    category_match = exception in _CATEGORY_EXCEPTIONS.get(expected_category, set())
    targets = targets[-1:]

    def assessment(status: str, case: ReplayCase | None, reason: str) -> WitnessAssessment:
        return WitnessAssessment(status, case, reason, exception, category_match)

    if "." in function:
        return assessment("rewrite_only", None, "object entry state cannot be reconstructed")

    if driver_source:
        driver_values = _driver_values(targets[0])
        case = None if driver_values is None else _case_from_driver(
            original_source, function, driver_source, driver_values
        )
        if case is None:
            return assessment("rewrite_only", None, "driver arguments have no concrete counterexample values")
    else:
        values = _scalar_assignments(targets[0].get("counterexample"))
        if values is None:
            return assessment("rewrite_only", None, "counterexample has no concrete scalar assignments")
        case = _case_for(original_source, function, values)
        if case is None:
            return assessment("unattributed", None, "counterexample cannot reconstruct the original entry arguments")

    outcome = executor.run(original_source, function, case)
    if outcome.kind in {"unavailable", "timeout"}:
        return assessment("rewrite_only", case, f"original replay {outcome.kind}: {outcome.exception_message}")
    if outcome.phase != "call":
        return assessment("rewrite_only", case, "original replay has no target-call provenance")
    if outcome.kind == "exception" and outcome.exception_type not in exception_matches:
        # A different failure means the input never reached the operation; it neither confirms nor refutes.
        return assessment("unattributed", case, f"original raised {outcome.exception_type} instead")
    if outcome.kind == "exception":
        location = outcome.exception_location
        scope = str(location.get("function", ""))
        if (location.get("file") == "<candidate>"
                and (scope == function or scope.startswith(f"{function}.<locals>."))
                and (original_line <= int(location.get("line") or 0) <= original_end_line
                     if original_end_line is not None
                     else location.get("line") == original_line and location.get("column") == original_column)):
            return assessment("reproduced_original", case, "native exception reproduced at the original suspect operation")
        if not outcome.exception_location:
            return assessment("rewrite_only", case, "original exception location is unavailable")
    return assessment("contradicted", case, "original replay did not reproduce the expected native exception")
