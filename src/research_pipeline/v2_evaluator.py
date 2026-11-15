"""Detection metrics for the V2 real-bug experiment.

The detector never reads these artifacts. Evaluation happens after the run, using the manifest
only to map detection sources to the known labels, which prevents oracle leakage into prompts.
"""

from __future__ import annotations

import ast
import json
import textwrap
from collections import Counter
from pathlib import Path


def _prf(tp: int, fp: int, fn: int) -> dict[str, float | None]:
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall
        else None
    )
    return {"precision": precision, "recall": recall, "f1": f1}


# Ground-truth failure kinds the ESBMC can confirm (dataset/README.md, campo failure_kind).
_REACHES_ESBMC = {"excecao_local": True, "excecao_modelavel": True,
                  "excecao_nao_modelavel": False, "resultado_errado": False, "incerto": None}


def should_reach_esbmc(item: dict) -> bool | None:
    """Whether the bug violates a property ESBMC checks on its own; None when unlabelled or uncertain."""
    if "failure_kind" not in item:
        return None
    kind = str(item["failure_kind"])
    if kind not in _REACHES_ESBMC:
        raise ValueError(f"unknown failure_kind {kind!r} in item {item.get('id')}")
    return _REACHES_ESBMC[kind]


_STATEMENT_PREFIXES = ("if ", "elif ", "while ", "return ", "assert ")


def _normalized(text: str) -> ast.AST | None:
    """One expression or statement, ignoring spacing, a leading keyword and a trailing colon; a
    compound statement may come with its body or as a bare header (``for x in y:``)."""
    block = textwrap.dedent(text).strip()
    text = block.removesuffix(":").strip()
    for prefix in _STATEMENT_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    try:
        return ast.parse(text, mode="eval").body
    except SyntaxError:
        pass
    for candidate in (block, block + "\n    pass"):
        try:
            body = ast.parse(candidate).body
        except SyntaxError:
            continue
        return body[0] if len(body) == 1 else None
    return None


def _is_reference(node: ast.expr) -> bool:
    while isinstance(node, ast.Attribute):
        node = node.value
    return isinstance(node, (ast.Name, ast.Constant))


def _subexpressions(node: ast.AST) -> set[str]:
    # A bare name, attribute chain or literal would match any expression that mentions it.
    return {ast.dump(n) for n in ast.walk(node)
            if isinstance(n, ast.stmt) or (isinstance(n, ast.expr) and not _is_reference(n))}


def expressions_equivalent(expected: str, found: str) -> bool:
    """Same expression up to spacing and ``if``/``return``-style wrapping, or one is a
    subexpression of the other (part of the buggy expression, or the statement around it)."""
    a, b = _normalized(expected), _normalized(found)
    if a is None or b is None:
        return False
    return ast.dump(a) == ast.dump(b) or ast.dump(a) in _subexpressions(b) or ast.dump(b) in _subexpressions(a)


def at_bug_line(hypothesis: dict, item: dict) -> bool:
    """The hypothesis names the bug's function and its cause or crash site (a labelled item only)."""
    if hypothesis["function"] not in {f.strip() for f in item["function"].split("/")}:
        return False
    expected = [e for e in [item.get("expression", ""), *item.get("cause_expressions", []),
                            *item.get("crash_expressions", [])] if e]
    return any(expressions_equivalent(e, hypothesis["suspect_expression"]) for e in expected)


def _points_at(item: dict, expression: str, *, equivalent: bool) -> bool:
    """An unlabelled item matches any expression; otherwise the cause or any crash site counts."""
    if not item["expressions"]:
        return True
    if equivalent:
        return any(expressions_equivalent(expected, expression) for expected in item["expressions"])
    return expression in item["expressions"]


def _ratio(part: int, whole: int) -> float | None:
    return part / whole if whole else None


def _triage_metrics(expected: list[dict], generated: list[dict]) -> dict:
    """Did detection send to ESBMC exactly the found bugs that ESBMC can confirm?

    Only bugs found as in ``expression_equivalent`` count, so a finding about another line of the same
    function says nothing about the bug. A bug is "sent" when any matching finding was sent.
    """
    counts = {"should_send": {"sent": 0, "held": 0}, "should_hold": {"sent": 0, "held": 0}, "uncertain_label": 0}
    for item in expected:
        found = [c for c in generated if c["file"] == item["file"] and c["function"] in item["functions"]
                 and _points_at(item, c["expression"], equivalent=True)]
        if not found:
            continue
        if item["reaches_esbmc"] is None:
            counts["uncertain_label"] += 1
            continue
        group = counts["should_send" if item["reaches_esbmc"] else "should_hold"]
        group["sent" if any(c["sent"] for c in found) else "held"] += 1
    send, hold = counts["should_send"], counts["should_hold"]
    return {
        **counts,
        "sent_when_should": _ratio(send["sent"], send["sent"] + send["held"]),
        "held_when_should": _ratio(hold["held"], hold["sent"] + hold["held"]),
    }


def _bug_detection_metrics(
    expected_items: list[dict], candidates: list, base: Path,
    rejected_findings: list[dict] | None = None,
) -> dict:
    """Measure case localization and the triage decision."""
    expected = [
        {
            "file": str((base / item["detection_file"]).resolve()),
            # "gamma / lgamma": the same bug appears in each listed function.
            "functions": {part.strip() for part in str(item.get("function", "")).split("/") if part.strip()},
            # Every line the patch changes, then where the buggy version raises (exception bugs only).
            "expressions": [e for e in [str(item.get("expression", "")), *item.get("cause_expressions", []),
                                         *item.get("crash_expressions", [])] if e],
            "reaches_esbmc": should_reach_esbmc(item),
        }
        for item in expected_items
        if item.get("categories")
    ]
    generated = [
        {
            "file": str(Path(candidate["file"]).resolve())
            if isinstance(candidate, dict)
            else str(Path(candidate.file).resolve()),
            "function": str(candidate.get("function", ""))
            if isinstance(candidate, dict)
            else str(candidate.function),
            "expression": str(candidate.get("expression", ""))
            if isinstance(candidate, dict)
            else str(candidate.expression),
            # Candidates are what detection sent to ESBMC; rejected findings were held back.
            "sent": not isinstance(candidate, dict) or bool(candidate.get("sent", True)),
        }
        for candidate in [*candidates, *({**r, "sent": False} for r in (rejected_findings or []))]
    ]

    def count_matches(predicate) -> dict[str, float | None | int]:
        matched = sum(
            any(predicate(item, candidate) for candidate in generated)
            for item in expected
        )
        false_positives = sum(
            not any(predicate(item, candidate) for item in expected)
            for candidate in generated
        )
        false_negatives = len(expected) - matched
        return {
            "tp": matched,
            "fp": false_positives,
            "fn": false_negatives,
            **_prf(matched, false_positives, false_negatives),
        }

    def matches_primary_location(item: dict, candidate: dict) -> bool:
        """Match the strongest location fields available in the manifest."""
        if candidate["file"] != item["file"]:
            return False
        if item["functions"] and candidate["function"] not in item["functions"]:
            return False
        return _points_at(item, candidate["expression"], equivalent=False)

    file_metrics = count_matches(lambda item, candidate: candidate["file"] == item["file"])
    location_metrics = count_matches(
        lambda item, candidate: (
            candidate["file"] == item["file"]
            and candidate["function"] in item["functions"]
        )
    )
    expression_metrics = count_matches(
        lambda item, candidate: (
            candidate["file"] == item["file"]
            and candidate["function"] in item["functions"]
            and bool(item["expressions"]) and _points_at(item, candidate["expression"], equivalent=False)
        )
    )
    equivalent_metrics = count_matches(
        lambda item, candidate: (
            candidate["file"] == item["file"]
            and candidate["function"] in item["functions"]
            and bool(item["expressions"]) and _points_at(item, candidate["expression"], equivalent=True)
        )
    )
    detection_metrics = count_matches(matches_primary_location)
    triage = _triage_metrics(expected, generated)
    return {
        "detection": detection_metrics,
        "file": file_metrics,
        "location": location_metrics,
        "expression": expression_metrics,
        "expression_equivalent": equivalent_metrics,
        "triage": triage,
    }


def evaluate_detection(
    *,
    candidates: list,
    ground_truth_path: str | Path,
    manifest_path: str | Path | None = None,
    evaluated_sources: list[str | Path] | None = None,
    rejected_findings: list[dict] | None = None,
    evaluate_by_function: bool = False,
    results: list[dict] | None = None,
    additional_findings: list[dict] | None = None,
) -> dict:
    """Detection by location (file, function, expression) and the triage of what goes to ESBMC."""
    gt_path = Path(ground_truth_path)
    manifest_file = Path(manifest_path) if manifest_path else gt_path.parent / "manifest.json"
    gt_items = json.loads(gt_path.read_text(encoding="utf-8")).get("items", [])
    manifest_payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    manifest_items = manifest_payload.get("items", [])
    patch_context_ids = {
        str(item) for item in manifest_payload.get("evaluation_policy", {}).get("patch_context_items", [])
    }
    if {str(i.get("id")) for i in gt_items} != {str(i.get("id")) for i in manifest_items}:
        raise ValueError("ground truth and V2 manifest contain different case IDs")

    base = manifest_file.parent
    allowed = {str(Path(p).resolve()) for p in evaluated_sources} if evaluated_sources is not None else None
    evaluated_items = [
        item for item in manifest_items
        if str(item.get("id")) not in patch_context_ids
        and (allowed is None or str((base / item["detection_file"]).resolve()) in allowed)
    ]
    location = _bug_detection_metrics(evaluated_items, candidates, base, rejected_findings)
    return {
        "detection_scope": "items without patch context",
        "excluded_patch_context_items": len(patch_context_ids),
        # Primary location match (file, function and, when labelled, the exact expression).
        "detection": location["detection"],
        # Whether detection sent to ESBMC the found bugs ESBMC can confirm, and held back the rest.
        "triage": location["triage"],
        "bug_detection": location,
        **({"by_function": evaluate_functions(
            evaluated_items, [*candidates, *(rejected_findings or []), *(additional_findings or [])], base, results=results,
            sibling_labels=json.loads((base / "gabarito_funcoes.json").read_text(encoding="utf-8"))
            if (base / "gabarito_funcoes.json").exists() else None)} if evaluate_by_function else {}),
    }


_SIBLING_REVIEW_PENDING = frozenset({'pymodbus_2977', 'pycomm3_331', 'gps_127'})


def _function_names(label: str) -> set[str]:
    return {part.strip() for part in label.split('/') if part.strip()}


def _replayed_exception(result: dict, expected_type: str) -> bool:
    replay = result.get('replay') or {}
    if not expected_type or replay.get('exception_type') != expected_type:
        return False
    if replay.get('status') == 'reproduced':
        return True
    line, span = replay.get('line'), replay.get('target_range')
    return (replay.get('status') == 'other_failure' and isinstance(line, int)
            and isinstance(span, (list, tuple)) and len(span) == 2
            and all(isinstance(value, int) for value in span) and span[0] <= line <= span[1])


def evaluate_functions(expected_items: list[dict], candidates: list, base: Path, *,
                       results: list[dict] | None = None, sibling_labels: list[dict] | None = None) -> dict:
    """Count labelled cases once, independently of expression, and keep patch siblings separate.

    Replay exception names must match exactly. A bare ``error`` cannot establish ``struct.error``.
    None for ``results`` means replay and ESBMC were not evaluated (detection-only).
    """
    generated = [c if isinstance(c, dict) else c.to_dict() for c in candidates]
    sisters = {str(row['id']): set(row['tocadas_pelo_patch']) for row in (sibling_labels or [])}
    cases, sibling_rows = [], []
    for item in expected_items:
        if not item.get('categories'):
            continue
        case_id = str(item['id'])
        file = (base / item['detection_file']).resolve()
        labelled = _function_names(item.get('function', ''))

        def matches(hypothesis: dict, functions: set[str]) -> bool:
            return Path(hypothesis['file']).resolve() == file and hypothesis.get('function') in functions

        pointed = any(matches(c, labelled) for c in generated)
        matching = [r for r in (results or []) if matches(r['hypothesis'], labelled)]
        reproduced = [r for r in matching if _replayed_exception(r, item.get('expected_type', ''))]
        cases.append({'id': case_id, 'functions': sorted(labelled), 'expected_type': item.get('expected_type'),
                      'apontado': pointed,
                      'apontado_e_reproduzido': pointed and bool(reproduced) if results is not None else None,
                      'confirmado_esbmc': pointed and any(r['verdict'] == 'CONFIRMED' for r in reproduced)
                      if results is not None else None})
        if case_id.removeprefix('cps_') in _SIBLING_REVIEW_PENDING:
            continue
        sibling_functions = sisters.get(case_id, set()) - labelled
        found_sisters = sorted({c['function'] for c in generated if matches(c, sibling_functions)})
        if found_sisters:
            sibling_rows.append({'id': case_id, 'functions': found_sisters,
                                 'file': str(file), 'source': 'gabarito_funcoes.json'})
    return {'total': len(cases), 'apontado': sum(row['apontado'] for row in cases),
            'apontado_e_reproduzido': sum(row['apontado_e_reproduzido'] for row in cases)
            if results is not None else None,
            'confirmado_esbmc': sum(row['confirmado_esbmc'] for row in cases) if results is not None else None,
            'cases': cases, 'mesmo_padrao_em_outra_funcao': sibling_rows,
            'sibling_labels_available': sibling_labels is not None,
            'excluded_sibling_cases': sorted(_SIBLING_REVIEW_PENDING),
            'input_layout': _function_input_layout(expected_items, base)}



def _function_input_layout(items: list[dict], base: Path) -> dict:
    from .preprocess import preprocess_file
    labelled = [item for item in items if item.get("categories")]
    paths = sorted({(base / item["detection_file"]).resolve() for item in labelled})
    functions, missing = {}, []
    for path in paths:
        try:
            functions[path] = {u.qualname for u in preprocess_file(path) if u.kind == "function"}
        except (OSError, SyntaxError, ValueError, UnicodeError, RecursionError):
            missing.append(str(path))
    counts = [len(names) for names in functions.values()]
    complete = bool(paths) and not missing
    return {"files": len(paths), "available_files": len(functions), "missing_sources": missing,
            "functions": sum(counts) if complete else None,
            "min_functions": min(counts) if complete else None,
            "max_functions": max(counts) if complete else None,
            "mean_functions": sum(counts) / len(counts) if complete else None,
            "distribution": dict(sorted(Counter(counts).items())),
            "all_functions_labelled": complete and all(
                bool(functions[(base / item["detection_file"]).resolve()])
                and functions[(base / item["detection_file"]).resolve()] <= _function_names(item.get("function", ""))
                for item in labelled)}


def render_function_evaluation(metrics: dict, *, fix_judge: dict | None = None) -> str:
    """Present the measured levels before the function-localization support metric."""
    total = metrics["total"]

    def count(value):
        return "não medido" if value is None else f"{value} de {total}"

    lines = ["# Avaliação por função", "",
             f"**Apontado e reproduzido: {count(metrics['apontado_e_reproduzido'])}.**", "",
             f"**Confirmado pelo ESBMC: {count(metrics['confirmado_esbmc'])}.**", ""]
    if fix_judge is not None and fix_judge.get("fixed_ok") is not None:
        lines += [f"**Juiz do conserto: {fix_judge['fixed_ok']} entradas deixam de falhar na versão corrigida.**",
                  f"Fonte: {fix_judge.get('source', 'não informada')}. Controle separado, sem somar aos outros níveis.", ""]
    else:
        lines += ["Juiz do conserto: não medido neste relatório.", ""]
    lines += [f"Apontado (apoio): {count(metrics['apontado'])}.", ""]
    layout = metrics.get("input_layout", {})
    if layout.get("functions") is not None:
        lines += [(f"Entrada: {layout['files']} arquivos, {layout['functions']} funções; "
                   f"de {layout['min_functions']} a {layout['max_functions']} funções por arquivo, "
                   f"média {layout['mean_functions']:.2f}."), ""]
        if layout.get("all_functions_labelled"):
            lines += ["Aviso: o nível apontado não tem poder de discriminação da localização neste desenho. "
                      "Todas as funções oferecidas estão nos rótulos; quando a LLM apresenta uma hipótese, "
                      "não há outra função disponível para escolher. Esse nível não mede distinguir código "
                      "com bug de código sem bug.", ""]
    else:
        lines += ["Entrada: não foi possível conferir a quantidade de funções em todos os arquivos.", ""]
    lines += ["A reprodução ocorre no harness; não prova alcance pelo código real. "
              "Os números de confirmação acima são o subconjunto reproduzido com a exceção esperada.", "",
              "## Mesmo padrão em outra função", "", "| Caso | Funções |", "|---|---|"]
    for row in metrics.get("mesmo_padrao_em_outra_funcao", []):
        lines.append(f"| {row['id']} | {', '.join(row['functions'])} |")
    if not metrics.get("mesmo_padrao_em_outra_funcao"):
        lines += ["", "Nenhum caso listado nesta tabela."]
    return "\n".join(lines) + "\n"
