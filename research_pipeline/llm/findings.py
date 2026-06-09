from __future__ import annotations

import ast
import json

from .categories import SUPPORTED_CATEGORIES, VERIFIABLE_OPERATION_KIND
from ..ast_utils import expression_exists_in_executable_ast
from ..models import CodeUnit, Finding

"""Utilities for turning raw LLM JSON into normalized Finding objects.

The LLM response is not trusted directly. This module:

1. extracts the `findings` list from the JSON payload;
2. converts each dict into the project's Finding dataclass;
3. rejects categories outside the benchmark scope;
4. checks whether verifiable bug claims refer to executable code;
5. marks structural hallucinations as llm_false_positive.

It does not prove bugs. It only decides whether a finding is well-formed and
eligible for later ESBMC checking.
"""


def coerce_findings_payload(payload: dict) -> list[dict]:
    """Return payload["findings"] or fail if the LLM used the wrong shape."""
    findings = payload.get("findings")
    if not isinstance(findings, list):
        raise RuntimeError("JSON da LLM nao contem a chave 'findings' no formato esperado.")
    return findings


def finding_from_dict(data: dict) -> Finding:
    """Convert one raw finding dictionary from the LLM into a Finding object."""
    metadata_raw = data.get("metadata", {})
    if not isinstance(metadata_raw, dict):
        metadata_raw = {}

    return Finding(
        id=str(data.get("id") or "unknown"),
        stage=str(data.get("stage") or "llm_analysis"),
        finding_type=str(data.get("finding_type") or "smell_heuristic"),
        category=str(data.get("category") or "unknown"),
        title=str(data.get("title") or ""),
        explanation=str(data.get("explanation") or ""),
        evidence=_normalize_evidence(data.get("evidence", [])),
        verifiable=bool(data.get("verifiable", False)),
        confidence=str(data.get("confidence") or "low"),
        metadata={
            "expression": str(metadata_raw.get("expression", "")),
            "line": _metadata_int(metadata_raw.get("line")),
            "relative_line": _metadata_int(metadata_raw.get("relative_line")),
            "expected_exception": str(data.get("expected_exception", "")),
        },
    )


def normalize_findings(unit: CodeUnit, findings: list[Finding]) -> list[Finding]:
    """Normalize LLM findings for one CodeUnit.

    Supported categories are checked against the function source. Unsupported
    categories become out_of_scope_finding and are counted separately by the
    benchmark, not mixed into bug/smell precision and recall.
    """
    normalized: list[Finding] = []
    seen_ids: set[str] = set()
    for index, finding in enumerate(findings, start=1):
        finding_id = _unique_finding_id(
            preferred_id=finding.id,
            fallback_id=f"{unit.qualname}:llm:{index}",
            used_ids=seen_ids,
        )

        if finding.category not in SUPPORTED_CATEGORIES:
            normalized.append(_out_of_scope_finding(finding, finding_id))
            continue

        normalized.append(_normalize_supported_finding(unit, finding, finding_id))
    return normalized


def strip_markdown_json(text: str) -> str:
    """Strip markdown fences and trailing prose around a JSON response."""
    import re
    text = text.strip()

    # DeepSeek-R1 and other reasoning models wrap output in <think>...</think>.
    # Remove all such blocks before attempting JSON extraction.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    # Some models output Python literals instead of JSON booleans/null.
    text = re.sub(r'\bTrue\b', 'true', text)
    text = re.sub(r'\bFalse\b', 'false', text)
    text = re.sub(r'\bNone\b', 'null', text)

    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Some models append explanations after valid JSON. Keep only the first
    # complete JSON value when possible.
    try:
        _, end = json.JSONDecoder().raw_decode(text)
        text = text[:end]
    except json.JSONDecodeError:
        pass
    return text


def _normalize_evidence(evidence_raw) -> list[str]:
    """Normalize evidence to a list of strings."""
    if isinstance(evidence_raw, str):
        return [evidence_raw]
    if isinstance(evidence_raw, list):
        return [str(item) for item in evidence_raw]
    return [str(evidence_raw)]


def _metadata_int(value) -> int:
    """Convert optional metadata line values to an int, using 0 when absent."""
    if value in (None, ""):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _unique_finding_id(preferred_id: str, fallback_id: str, used_ids: set[str]) -> str:
    """Return a stable unique id for one finding within a CodeUnit."""
    candidate_id = preferred_id.strip() or fallback_id
    if candidate_id in used_ids:
        candidate_id = f"{candidate_id}:{len(used_ids) + 1}"
    used_ids.add(candidate_id)
    return candidate_id


def _out_of_scope_finding(finding: Finding, finding_id: str) -> Finding:
    """Mark a supported-shape finding whose category is outside benchmark scope."""
    metadata = dict(finding.metadata)
    metadata["original_category"] = finding.category
    metadata["has_guard"] = "false"
    return Finding(
        id=finding_id,
        stage=finding.stage or "llm_analysis",
        finding_type="out_of_scope_finding",
        category=finding.category,
        title=finding.title,
        explanation=finding.explanation,
        evidence=finding.evidence,
        verifiable=False,
        confidence=finding.confidence,
        metadata=metadata,
    )


def _normalize_supported_finding(unit: CodeUnit, finding: Finding, finding_id: str) -> Finding:
    """Normalize a finding whose category is inside the benchmark scope."""
    metadata = dict(finding.metadata)
    finding_type = finding.finding_type
    verifiable = finding.verifiable

    # assertion_violation is checked by matching assert-like source syntax.
    if verifiable and finding.category == "assertion_violation":
        finding_type, verifiable = _normalize_assertion_violation(unit, metadata)
    # division_by_zero and out_of_bounds are checked against operations from preprocessing.
    elif verifiable:
        finding_type, verifiable = _normalize_operation_finding(unit, finding.category, metadata)

    return Finding(
        id=finding_id,
        stage=finding.stage or "llm_analysis",
        finding_type=finding_type,
        category=finding.category,
        title=finding.title,
        explanation=finding.explanation,
        evidence=finding.evidence,
        verifiable=verifiable,
        confidence=finding.confidence,
        metadata=metadata,
    )


def _normalize_assertion_violation(unit: CodeUnit, metadata: dict[str, object]) -> tuple[str, bool]:
    """Accept assertion_violation only when the reported assert exists in source."""
    metadata["has_guard"] = "false"
    if _assertion_violation_matches_source(unit, str(metadata.get("expression", ""))):
        return "suspected_bug", True
    return "llm_false_positive", False


def _normalize_operation_finding(
    unit: CodeUnit,
    category: str,
    metadata: dict[str, object],
) -> tuple[str, bool]:
    """Normalize verifiable operation-based bug claims.

    This handles division_by_zero and out_of_bounds. The goal is structural
    validation: does the LLM's expression correspond to executable code?
    """
    expected_operation_kind = VERIFIABLE_OPERATION_KIND.get(category)
    if expected_operation_kind is None:
        return "smell_heuristic", False

    expression = str(metadata.get("expression", ""))

    # Phase 1: exact match against operations extracted by preprocess.py.
    # This is the preferred path because it also gives us line metadata.
    matched_operation = _find_matching_operation(unit, expected_operation_kind, expression)
    if matched_operation is not None:
        metadata["line"] = matched_operation.line
        metadata["relative_line"] = matched_operation.relative_line
        if _denominator_is_nonzero_constant(category, expression):
            metadata["has_guard"] = "false"
            return "llm_false_positive", False
        has_guard = _guard_covers_operation(unit, expression, category)
        metadata["has_guard"] = "true" if has_guard else "false"
        return "suspected_bug", True

    # Phase 2: the expression exists in the AST, but preprocess.py did not
    # classify it as the expected operation kind. Keep it verifiable instead
    # of treating it as hallucination.
    if expression_exists_in_executable_ast(expression, unit.source):
        if _denominator_is_nonzero_constant(category, expression):
            metadata["has_guard"] = "false"
            return "llm_false_positive", False
        metadata["has_guard"] = "false"
        metadata["ast_unrecognized"] = "true"
        return "suspected_bug", True

    # Phase 3: the expression genuinely does not occur in executable code.
    metadata["has_guard"] = "false"
    return "llm_false_positive", False


def _find_matching_operation(unit: CodeUnit, expected_kind: str, expression: str):
    """Find an AST-extracted operation matching kind and optional expression."""
    return next(
        (
            operation
            for operation in unit.operations
            if operation.kind == expected_kind
            and (not expression or operation.expression == expression)
        ),
        None,
    )


def _guard_covers_operation(unit: CodeUnit, expression: str, category: str) -> bool:
    """Return whether a guard mentions the risky operand/index.

    This is metadata only. It does not prove safety and does not block ESBMC.
    """
    if not unit.guards or not expression:
        return False
    if category == "division_by_zero":
        return _division_guard_covers_expression(unit, expression)
    if category == "out_of_bounds":
        return _bounds_guard_covers_expression(unit, expression)
    return False


def _division_guard_covers_expression(unit: CodeUnit, expression: str) -> bool:
    """Heuristically check whether a guard mentions the division denominator."""
    for operator in ("//", "/", "%"):
        if operator in expression:
            denominator = expression.split(operator, 1)[-1].strip()
            return bool(denominator and any(denominator in guard for guard in unit.guards))
    return False


def _bounds_guard_covers_expression(unit: CodeUnit, expression: str) -> bool:
    """Heuristically check whether a guard mentions the subscript index."""
    start = expression.find("[")
    end = expression.rfind("]")
    if not 0 <= start < end:
        return False
    index = expression[start + 1 : end].strip()
    return bool(index and any(index in guard for guard in unit.guards))


def _assertion_violation_matches_source(unit: CodeUnit, expression: str) -> bool:
    """Return True when an assertion expression is present in the function."""
    expression = expression.strip()
    if not expression:
        # Model identified the category but didn't provide the expression.
        # Accept if the function contains any assert at all.
        return bool(_assertion_tests(unit.source))

    source = unit.source
    if expression in source:
        return True

    expected = _parse_assertion_expression(expression)
    if expected is None:
        return False

    expected_dump = ast.dump(expected)
    return any(ast.dump(actual) == expected_dump for actual in _assertion_tests(unit.source))


def _parse_assertion_expression(expression: str) -> ast.AST | None:
    """Parse either `assert condition` or bare `condition` into an AST node."""
    try:
        module = ast.parse(expression)
    except SyntaxError:
        try:
            return ast.parse(expression, mode="eval").body
        except SyntaxError:
            return None

    if len(module.body) != 1:
        return None

    statement = module.body[0]
    if isinstance(statement, ast.Assert):
        return statement.test
    if isinstance(statement, ast.Expr):
        return statement.value
    return None


def _assertion_tests(source: str) -> list[ast.AST]:
    """Extract assert test expressions from source."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    return [node.test for node in ast.walk(tree) if isinstance(node, ast.Assert)]


def _denominator_is_nonzero_constant(category: str, expression: str) -> bool:
    """Return True if the division denominator is a non-zero literal constant.

    Catches cases like `x // 100` where ZeroDivisionError is impossible.
    Only applies to division_by_zero; other categories are unaffected.
    """
    if category != "division_by_zero":
        return False
    try:
        body = ast.parse(expression, mode="eval").body
    except SyntaxError:
        return False
    if not isinstance(body, ast.BinOp):
        return False
    if not isinstance(body.op, (ast.Div, ast.FloorDiv, ast.Mod)):
        return False
    right = body.right
    if not isinstance(right, ast.Constant):
        return False
    return right.value != 0
