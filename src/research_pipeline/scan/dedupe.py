"""Group exact function ASTs and normalized expressions without changing hypothesis identities."""

from __future__ import annotations

import ast
import textwrap
from collections.abc import Callable

from ..verify.hypothesis import BugHypothesis


def function_ast(source: str, qualname: str) -> str | None:
    """Return an exact structural key; unknown or ambiguous functions stay separate."""
    try:
        node = ast.parse(textwrap.dedent(source))
        for name in qualname.split('.'):
            matches = [child for child in node.body
                       if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                       and child.name == name]
            if len(matches) != 1:
                return None
            node = matches[0]
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return None
        if (node.body and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)):
            node.body.pop(0)
        return ast.dump(node, include_attributes=False)
    except (SyntaxError, ValueError, RecursionError):
        return None


def expression_ast(expression: str) -> str:
    try:
        return ast.dump(ast.parse(expression.strip()), include_attributes=False)
    except (SyntaxError, ValueError, RecursionError):
        return expression.strip()


def deduplicate(hypotheses: list[BugHypothesis], source_of: Callable[[BugHypothesis], str | None]) -> tuple[list, list]:
    representatives, groups, by_key = [], [], {}
    for hypothesis in sorted(hypotheses, key=lambda h: (h.file, h.line, h.function, h.suspect_expression)):
        body = source_of(hypothesis)
        key = (body, expression_ast(hypothesis.suspect_expression), hypothesis.oracle)
        if body is None or key not in by_key:
            representatives.append(hypothesis)
            if body is not None:
                by_key[key] = {'representante': hypothesis.to_dict(), 'duplicatas': []}
            continue
        group = by_key[key]
        if not group['duplicatas']:
            groups.append(group)
        group['duplicatas'].append(hypothesis.to_dict())
    return representatives, groups


def duplicates_markdown(groups: list[dict], results: list[dict]) -> str:
    if not groups:
        return ''
    verdicts = {r['hypothesis']['hypothesis_id']: r['verdict'] for r in results}
    lines = ['', '## Hipóteses duplicadas', '']
    for group in groups:
        representative = group['representante']
        entries = [representative, *group['duplicatas']]
        functions = len({(h['file'], h['function']) for h in entries})
        verdict = verdicts.get(representative['hypothesis_id'], 'sem veredito')
        lines += [f'{len(entries)} hipóteses em {functions} funções idênticas, verificadas 1 vez. '
                  f'Veredito do representante aplicado ao grupo: {verdict}.',
                  f"Representante: `{representative['file']}::{representative['function']}` "
                  f"`{representative['suspect_expression']}`."]
        lines.extend(f"- Duplicata: `{h['file']}::{h['function']}` `{h['suspect_expression']}`."
                     for h in group['duplicatas'])
        lines.append('')
    return '\n'.join(lines) + '\n'
