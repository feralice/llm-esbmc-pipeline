"""Propose, review and apply the line where each exception bug raises (crash_expressions).

The LLM sees only the buggy function, the fix patch and the labelled cause; never pipeline hypotheses."""

from __future__ import annotations

import argparse
import ast
import json
import sys
import textwrap
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.v2_evaluator import _normalized

DATASET = ROOT / "dataset/bugs_reais"
DOCUMENTS = {"labels": ROOT / "dataset/coleta_bugsinpy/labels.json",
             "ground_truths": DATASET / "ground_truths.json",
             "manifest": DATASET / "manifest.json",
             "manifest_full": DATASET / "manifest_full.json"}

SYSTEM = """You read a buggy Python function and the patch that fixes it. The bug makes the buggy
version raise an exception. Find the expression(s) in the BUGGY function where that exception is
raised. Copy each expression exactly as it appears in the buggy function. If the exception is raised
by the labelled cause line itself, set same_as_expression to true and leave crash_expressions empty.
Reply with one JSON object and nothing else:
{"same_as_expression": bool, "crash_expressions": [str], "exception": str, "reason": str}"""

_TASK = """Buggy function:
```python
{source}
```
Fix patch:
```diff
{patch}
```
Labelled cause (the line the fix changes): `{expression}`
Note: {note}"""


def pending_items(items: list[dict]) -> list[dict]:
    return [i for i in items if i.get("failure_kind") != "resultado_errado" and not i.get("crash_expressions")]


def occurs_in(source: str, expression: str) -> bool:
    target = _normalized(expression)
    if target is None:
        return False
    wanted = ast.dump(target)
    return any(ast.dump(n) == wanted for n in ast.walk(ast.parse(textwrap.dedent(source))))


def validate(reply: dict, source: str) -> dict:
    same = bool(reply.get("same_as_expression"))
    proposed = [] if same else [e for e in reply.get("crash_expressions") or [] if isinstance(e, str)]
    kept = [e for e in proposed if occurs_in(source, e)]
    return {"same_as_expression": same, "crash_expressions": kept,
            "discarded": [e for e in proposed if e not in kept],
            "exception": str(reply.get("exception", "")), "reason": str(reply.get("reason", ""))}


def build_prompt(item: dict, source: str, patch: str) -> str:
    return _TASK.format(source=source, patch=patch, expression=item.get("expression", ""),
                        note=item.get("failure_kind_note") or "none")


def _save(out: Path, saved: dict) -> None:
    out.write_text(json.dumps(saved, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def propose(items: list[dict], *, llm, dataset: Path, out: Path, retries: int = 2) -> dict:
    """Stops after saving when the client raises (usage limit, CLI failure); a rerun resumes."""
    saved = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    for item in pending_items(items):
        if "status" in saved.get(item["id"], {}):
            continue
        source = (dataset / "funcao_com_bug" / item["file"]).read_text(encoding="utf-8")
        patch_path = dataset / "patches" / f"{item['id']}.diff"
        if not patch_path.exists():
            saved[item["id"]] = {**saved.get(item["id"], {}), "status": "sem_patch", "crash_expressions": [],
                                 "model": "", "raw": ""}
            _save(out, saved)
            continue
        prompt, entry = build_prompt(item, source, patch_path.read_text(encoding="utf-8")), None
        for _ in range(retries + 1):
            try:
                reply = llm.complete(SYSTEM, prompt, json_mode=True)
            except (RuntimeError, TimeoutError) as exc:
                print(f"parado em {item['id']}: {exc}", file=sys.stderr)
                _save(out, saved)
                return saved
            try:
                entry = {**validate(json.loads(reply.harness), source), "status": "ok"}
                break
            except (ValueError, AttributeError):
                prompt += "\n\nYour last reply was not the JSON object asked for."
        saved[item["id"]] = {**saved.get(item["id"], {}), **(entry or {"crash_expressions": [], "status": "failed"}),
                             "model": reply.model, "raw": reply.raw_response}
        _save(out, saved)
    return saved


def removed_lines(patch: str, source_file: str | None) -> list[str]:
    """Lines the fix deletes or rewrites in the bug's file (``-`` lines), stripped, in patch order."""
    lines, current = [], None
    for raw in patch.splitlines():
        if raw.startswith("--- "):
            current = raw[4:].removeprefix("a/").strip()
        elif raw.startswith("-") and not raw.startswith("---"):
            text = raw[1:].strip()
            if text and not text.startswith("#") and (source_file is None or (current or "").endswith(source_file)):
                lines.append(text)
    return lines


_HEADERS = {ast.If: "test", ast.While: "test", ast.For: "iter", ast.AsyncFor: "iter"}


def _expression_at(tree: ast.AST, source: str, lineno: int) -> str | None:
    """The innermost statement on ``lineno``; for if/while/for/with, only its header expression."""
    best = None
    for node in ast.walk(tree):
        inside = isinstance(node, ast.stmt) and node.lineno <= lineno <= node.end_lineno
        if inside and (best is None or (node.lineno >= best.lineno and node.end_lineno <= best.end_lineno)):
            best = node
    if best is None or _is_docstring(best):
        return None
    if not hasattr(best, "body"):
        return ast.get_source_segment(source, best)
    # A compound statement owns the line only through a header or clause (try:, else:, except ...:).
    if lineno < best.body[0].lineno and type(best) in _HEADERS:
        return ast.get_source_segment(source, getattr(best, _HEADERS[type(best)]))
    if lineno < best.body[0].lineno and isinstance(best, (ast.With, ast.AsyncWith)):
        return ast.get_source_segment(source, best.items[0].context_expr)
    return None


def _is_docstring(node: ast.stmt) -> bool:
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)


def cause_from_patch(source: str, patch: str, source_file: str | None) -> dict:
    """Every line of the function the fix changes (matched by text: curated patches carry the
    original repository's line numbers, not ours)."""
    removed = removed_lines(patch, source_file)
    if not removed:
        return {"status": "so_insercao", "expressions": []}
    with warnings.catch_warnings():  # invalid escapes in the project's own strings
        warnings.simplefilter("ignore", SyntaxWarning)
        tree = ast.parse(source)
    lines = source.splitlines()
    found, ambiguous = [], False
    for text in removed:
        hits = [n for n, line in enumerate(lines, 1) if line.strip() == text]
        ambiguous |= len(hits) > 1
        for lineno in hits:
            expression = _expression_at(tree, source, lineno)
            if expression and expression not in found:
                found.append(expression)
    if not found:
        return {"status": "sem_casamento", "expressions": []}
    return {"status": "ambigua" if ambiguous else "ok", "expressions": found}


def causes(items: list[dict], *, dataset: Path, out: Path) -> dict:
    saved = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    for item in items:
        patch_path = dataset / "patches" / f"{item['id']}.diff"
        source = (dataset / "funcao_com_bug" / item["file"]).read_text(encoding="utf-8")
        source_file = (item.get("provenance") or {}).get("source_file")
        cause = (cause_from_patch(source, patch_path.read_text(encoding="utf-8"), source_file)
                 if patch_path.exists() else {"status": "sem_patch", "expressions": []})
        saved.setdefault(item["id"], {})["cause"] = cause
    _save(out, saved)
    return saved


def _items(document) -> list[dict]:
    return document if isinstance(document, list) else document["items"]


def _reviewed_cause(entry: dict) -> tuple[list[str], str]:
    cause = entry.get("cause") or {}
    if entry.get("cause_review") == "corrigida":
        return entry.get("cause_expressions_review") or [], "patch_revisado"
    if cause.get("status") == "ok" or entry.get("cause_review") == "aceita":
        return cause.get("expressions") or [], "patch"
    return [], ""


def _reviewed_crash(entry: dict) -> list[str]:
    if entry.get("review") == "corrigida":
        return entry.get("crash_expressions_review") or []
    return entry.get("crash_expressions") or [] if entry.get("review") == "aceita" else []


def _extend(item: dict, field: str, expressions: list[str], source: str) -> bool:
    current = item.get(field) or []
    new = current + [e for e in expressions if e not in current]
    if new == current:
        return False
    item[field] = new
    item.setdefault("label_sources", {})[field] = source
    return True


def apply(proposals: dict, documents: dict) -> int:
    """Patch causes go in unless ambiguous and unreviewed; crash lines only when accepted or corrected
    in review. Reapplying adds nothing."""
    changed = set()
    for document in documents.values():
        for item in _items(document):
            entry = proposals.get(item["id"]) or {}
            causes_, origin = _reviewed_cause(entry)
            if _extend(item, "cause_expressions", causes_, origin):
                changed.add(item["id"])
            if _extend(item, "crash_expressions", _reviewed_crash(entry), "llm_patch_revisado"):
                changed.add(item["id"])
    return len(changed)


def merge_reviews(proposals: dict, reviews: list[dict], sources: dict[str, str]) -> None:
    """Fold reviewer decisions in; every expression a reviewer wrote must exist in the function."""
    for review in reviews:
        entry = proposals.setdefault(review["id"], {})
        source = sources[review["id"]]
        for field, verdict_key in (("crash_expressions_review", "review"), ("cause_expressions_review", "cause_review")):
            written = review.get(field) or []
            kept = [e for e in written if occurs_in(source, e)]
            note_key = "review_note" if verdict_key == "review" else "cause_note"
            note = review.get(note_key, "")
            if len(kept) < len(written):
                note += f" (descartado, não existe na função: {', '.join(e for e in written if e not in kept)})"
            verdict = review.get(verdict_key)
            if verdict in ("rejeitada", "corrigida") and kept:
                verdict = "corrigida"
            elif verdict == "corrigida":
                verdict = "duvida"
            entry.update({verdict_key: verdict, field: kept, note_key: note.strip()})


def dump_like(original: str, data) -> str:
    """Same layout as the file being rewritten, so the diff shows only the new labels."""
    return json.dumps(data, indent=2, ensure_ascii=False) + ("\n" if original.endswith("\n") else "")


def _code(expressions: list[str]) -> str:
    return "; ".join(f"`{' '.join(e.split())}`" for e in expressions)


def review_table(proposals: dict, items: dict[str, dict]) -> str:
    """One row per bug with the lines that will enter the ground truth after review."""
    lines = ["| Bug | Tipo | Causa atual | Causa (patch) | Nota causa | Quebra | Exceção | Nota quebra |",
             "|---|---|---|---|---|---|---|---|"]
    for key, entry in sorted(proposals.items()):
        item = items.get(key, {})
        status = (entry.get("cause") or {}).get("status", "")
        cause_review = entry.get("cause_review")
        cause = f"{status} → {cause_review}" if cause_review else status
        cause += f": {_code(_reviewed_cause(entry)[0])}" if _reviewed_cause(entry)[0] else ""
        if "status" not in entry:
            crash = ""
        elif entry.get("same_as_expression") and entry.get("review") == "aceita":
            crash = "aceita: a própria causa"
        else:
            crash = f"{entry.get('review', 'pendente')}: {_code(_reviewed_crash(entry) or entry.get('crash_expressions') or [])}"
        lines.append(f"| {key} | {item.get('failure_kind', '')} | `{' '.join(item.get('expression', '').split())}` | "
                     f"{cause} | {entry.get('cause_note', '')} | {crash} | {entry.get('exception', '')} | "
                     f"{entry.get('review_note', '')} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["causes", "propose", "merge", "table", "apply"])
    parser.add_argument("--proposals", type=Path, default=DATASET / "crash_proposals.json")
    parser.add_argument("--backend", default="claude_cli")
    parser.add_argument("--model", default="claude-sonnet-5-5")
    parser.add_argument("--llm-timeout", type=int, default=300)
    parser.add_argument("--reviews", type=Path, nargs="*", default=[])
    parser.add_argument("--out", type=Path, default=ROOT / "docs/historico/revisao_linha_da_quebra_2026-10-15.md")
    args = parser.parse_args(argv)
    truths = json.loads(DOCUMENTS["ground_truths"].read_text(encoding="utf-8"))["items"]
    if args.command == "causes":
        causes(truths, dataset=DATASET, out=args.proposals)
        return 0
    if args.command == "propose":
        from research_pipeline.verify.llm_client import (
            LLMClient,  # only this command needs a client
        )
        propose(truths, llm=LLMClient(backend=args.backend, model=args.model, timeout_seconds=args.llm_timeout), dataset=DATASET, out=args.proposals)
        return 0
    proposals = json.loads(args.proposals.read_text(encoding="utf-8"))
    if args.command == "merge":
        sources = {i["id"]: (DATASET / "funcao_com_bug" / i["file"]).read_text(encoding="utf-8") for i in truths}
        reviews = [json.loads(line) for path in args.reviews for line in path.read_text(encoding="utf-8").splitlines()
                   if line.strip()]
        merge_reviews(proposals, reviews, sources)
        _save(args.proposals, proposals)
        return 0
    if args.command == "table":
        args.out.write_text(review_table(proposals, {i["id"]: i for i in truths}), encoding="utf-8")
        return 0
    raw = {k: p.read_text(encoding="utf-8") for k, p in DOCUMENTS.items()}
    documents = {k: json.loads(text) for k, text in raw.items()}
    print(f"{apply(proposals, documents)} itens alterados")
    for key, path in DOCUMENTS.items():
        path.write_text(dump_like(raw[key], documents[key]), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
