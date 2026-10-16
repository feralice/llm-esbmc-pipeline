# Linha da quebra no gabarito: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** dar a cada bug de exceção do gabarito todas as linhas da causa (`cause_expressions`, tiradas do patch por código) e as linhas onde a versão com bug quebra (`crash_expressions`, propostas por LLM e conferidas duas vezes), e medir antes/depois.

**Architecture:** um script (`scripts/propose_crash_lines.py`) com três subcomandos: `propose` (LLM lê função + patch e grava propostas validadas por AST em `crash_proposals.json`, retomável), `table` (gera a tabela de revisão em Markdown) e `apply` (grava as aceitas em `labels.json`, `ground_truths.json`, `manifest.json` e `manifest_full.json` de uma vez). A medição usa `at_bug_line` sobre os relatórios existentes, com o gabarito antigo (git) e o novo.

**Tech Stack:** Python 3 do `.venv`, `ast`, `research_pipeline.verify.llm_client.LLMClient` (backend `claude_cli`), `research_pipeline.v2_evaluator`, pytest.

**Spec:** `docs/superpowers/specs/2026-10-15-linha-da-quebra-design.md`

## Global Constraints

- Escopo: itens de `dataset/bugs_reais/ground_truths.json` com `failure_kind != "resultado_errado"` e sem `crash_expressions` (84 hoje).
- O LLM vê só função com bug, patch, `expression` e `failure_kind_note`; nunca hipóteses do pipeline.
- Backend padrão `claude_cli`, modelo `claude-sonnet-5-5`; escolhível por `--backend/--model`.
- `label_sources.crash_expressions = "llm_patch_revisado"` em todo item aplicado.
- Nunca mexer em `expression`; nunca aplicar item com `review` diferente de `aceita`.
- Sem travessão em texto; sem commit sem a Fernanda pedir (passos "commit" viram "ponto de parada").
- Suíte rápida: `timeout 10m .venv/bin/python -m pytest -q tests --ignore=tests/test_verify_esbmc_integration.py`.

## Review Focus

- Resposta do LLM com expressão que não existe na função: descartada e anotada, nunca aplicada (teste na Tarefa 1).
- Limite de uso do LLM no meio: o script para, salva o que tem, e a próxima execução continua sem refazer (teste na Tarefa 2).
- `same_as_expression: true` com lista não vazia: a lista é ignorada (teste na Tarefa 1).
- Item já com `crash_expressions` ou de resultado errado: nunca entra (teste na Tarefa 1).
- `apply` rodado duas vezes: não duplica expressões (teste na Tarefa 3).
- `causes` rodado antes de `propose`: o `propose` não pode pular o bug só porque já existe a chave da causa (teste na Tarefa 5).

---

### Tarefa 1: seleção, prompt e validação

**Files:**
- Create: `scripts/propose_crash_lines.py`
- Test: `tests/test_propose_crash_lines.py`

**Interfaces:**
- Produces: `pending_items(items: list[dict]) -> list[dict]`; `occurs_in(source: str, expression: str) -> bool`; `validate(reply: dict, source: str) -> dict` que devolve `{"same_as_expression": bool, "crash_expressions": [str], "discarded": [str], "exception": str, "reason": str}`; `build_prompt(item: dict, source: str, patch: str) -> str`; constante `SYSTEM`.

- [ ] **Passo 1: testes que falham**

```python
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("pcl", Path(__file__).parents[1] / "scripts/propose_crash_lines.py")
pcl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pcl)

SOURCE = "def f(xs, k):\n    window = get(k)\n    return xs[0] / window\n"


def test_pending_skips_wrong_results_and_already_labelled():
    items = [{"id": "a", "failure_kind": "excecao_local"},
             {"id": "b", "failure_kind": "resultado_errado"},
             {"id": "c", "failure_kind": "excecao_local", "crash_expressions": ["x"]}]
    assert [i["id"] for i in pcl.pending_items(items)] == ["a"]


def test_occurs_in_matches_spacing_and_return_prefix():
    assert pcl.occurs_in(SOURCE, "xs[0]/window")
    assert pcl.occurs_in(SOURCE, "return xs[0] / window")
    assert not pcl.occurs_in(SOURCE, "xs[1] / window")


def test_validate_discards_expressions_not_in_the_function():
    out = pcl.validate({"same_as_expression": False, "crash_expressions": ["xs[0] / window", "y / 0"],
                        "exception": "ZeroDivisionError", "reason": "r"}, SOURCE)
    assert out["crash_expressions"] == ["xs[0] / window"]
    assert out["discarded"] == ["y / 0"]


def test_validate_same_as_expression_ignores_the_list():
    out = pcl.validate({"same_as_expression": True, "crash_expressions": ["xs[0] / window"],
                        "exception": "E", "reason": "r"}, SOURCE)
    assert out["crash_expressions"] == [] and out["same_as_expression"]


def test_prompt_has_function_patch_and_cause_only():
    item = {"id": "a", "expression": "window = get(k)", "failure_kind_note": "divisão por zero"}
    prompt = pcl.build_prompt(item, SOURCE, "--- a\n+++ b\n")
    assert "window = get(k)" in prompt and "divisão por zero" in prompt and "+++ b" in prompt
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_propose_crash_lines.py -q`
Expected: FAIL (`FileNotFoundError` ou atributo ausente: o script ainda não existe).

- [ ] **Passo 3: implementação mínima**

```python
"""Propose, review and apply the line where each exception bug raises (crash_expressions).

The LLM sees only the buggy function, the fix patch and the labelled cause; never pipeline hypotheses."""

from __future__ import annotations

import ast
import textwrap

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


def _node(expression: str) -> ast.AST | None:
    from research_pipeline.v2_evaluator import _normalized
    return _normalized(expression)


def occurs_in(source: str, expression: str) -> bool:
    target = _node(expression)
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
```

No topo do script, antes dos imports do projeto, inserir `sys.path.insert(0, str(ROOT / "src"))` com `ROOT = Path(__file__).resolve().parents[1]`, como em `scripts/v2_orchestrate.py:18-19`, e trocar o import tardio de `_normalized` por import no topo.

- [ ] **Passo 4: rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_propose_crash_lines.py -q`
Expected: 5 passed.

- [ ] **Passo 5: ponto de parada** (sem commit; a Fernanda decide quando commitar)

### Tarefa 2: `propose` com retomada e falha de limite

**Files:**
- Modify: `scripts/propose_crash_lines.py`
- Test: `tests/test_propose_crash_lines.py`

**Interfaces:**
- Consumes: `pending_items`, `build_prompt`, `validate`, `SYSTEM` (Tarefa 1).
- Produces: `propose(items: list[dict], *, llm, dataset: Path, out: Path, retries: int = 2) -> dict` que grava e devolve `{id: entrada}`; entrada = saída de `validate` + `{"model": str, "status": "ok"|"failed"|"sem_patch", "raw": str}`. Para em `RuntimeError` do cliente (limite/CLI) depois de salvar.

- [ ] **Passo 1: testes que falham**

```python
import json

from research_pipeline.verify.llm_client import SynthResult


class _LLM:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), 0

    def complete(self, system, user, *, json_mode=False):
        self.calls += 1
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return SynthResult(reply, reply, "fake", {})


def _dataset(tmp_path, ids):
    for i in ids:
        (tmp_path / "funcao_com_bug").mkdir(exist_ok=True)
        (tmp_path / "patches").mkdir(exist_ok=True)
        (tmp_path / "funcao_com_bug" / f"{i}.py").write_text(SOURCE)
        (tmp_path / "patches" / f"{i}.diff").write_text("--- a\n+++ b\n")
    return [{"id": i, "file": f"{i}.py", "failure_kind": "excecao_local", "expression": "window = get(k)"} for i in ids]


OK = json.dumps({"same_as_expression": False, "crash_expressions": ["xs[0] / window"], "exception": "E", "reason": "r"})


def test_propose_resumes_without_calling_again(tmp_path):
    items, out = _dataset(tmp_path, ["a"]), tmp_path / "p.json"
    pcl.propose(items, llm=_LLM(OK), dataset=tmp_path, out=out)
    llm = _LLM()
    pcl.propose(items, llm=llm, dataset=tmp_path, out=out)
    assert llm.calls == 0 and json.loads(out.read_text())["a"]["crash_expressions"] == ["xs[0] / window"]


def test_propose_stops_and_saves_on_usage_limit(tmp_path):
    items, out = _dataset(tmp_path, ["a", "b"]), tmp_path / "p.json"
    pcl.propose(items, llm=_LLM(OK, RuntimeError("claude -p saiu com código 1")), dataset=tmp_path, out=out)
    assert list(json.loads(out.read_text())) == ["a"]


def test_propose_retries_non_json_then_fails(tmp_path):
    items, out = _dataset(tmp_path, ["a"]), tmp_path / "p.json"
    saved = pcl.propose(items, llm=_LLM("x", "y", "z"), dataset=tmp_path, out=out)
    assert saved["a"]["status"] == "failed"


def test_missing_patch_is_marked(tmp_path):
    items, out = _dataset(tmp_path, ["a"]), tmp_path / "p.json"
    (tmp_path / "patches" / "a.diff").unlink()
    assert pcl.propose(items, llm=_LLM(), dataset=tmp_path, out=out)["a"]["status"] == "sem_patch"
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_propose_crash_lines.py -q`
Expected: os 4 testes novos falham (`propose` não existe).

- [ ] **Passo 3: implementação**

```python
def _save(out: Path, saved: dict) -> None:
    out.write_text(json.dumps(saved, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def propose(items: list[dict], *, llm, dataset: Path, out: Path, retries: int = 2) -> dict:
    saved = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    for item in pending_items(items):
        if item["id"] in saved:
            continue
        source = (dataset / "funcao_com_bug" / item["file"]).read_text(encoding="utf-8")
        patch_path = dataset / "patches" / f"{item['id']}.diff"
        if not patch_path.exists():
            saved[item["id"]] = {"status": "sem_patch", "crash_expressions": [], "model": "", "raw": ""}
            _save(out, saved)
            continue
        prompt, entry = build_prompt(item, source, patch_path.read_text(encoding="utf-8")), None
        for _ in range(retries + 1):
            try:
                reply = llm.complete(SYSTEM, prompt, json_mode=True)
            except RuntimeError as exc:
                print(f"parado em {item['id']}: {exc}", file=sys.stderr)
                _save(out, saved)
                return saved
            try:
                entry = {**validate(json.loads(reply.harness), source), "status": "ok"}
                break
            except (ValueError, AttributeError):
                prompt += "\n\nYour last reply was not the JSON object asked for."
        saved[item["id"]] = {**(entry or {"crash_expressions": [], "status": "failed"}),
                             "model": reply.model, "raw": reply.raw_response}
        _save(out, saved)
    return saved
```

Acrescentar `import json`, `import sys` e `from pathlib import Path` no topo.

- [ ] **Passo 4: rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_propose_crash_lines.py -q`
Expected: 9 passed.

- [ ] **Passo 5: ponto de parada**

### Tarefa 3: `apply` nos quatro arquivos do gabarito

**Files:**
- Modify: `scripts/propose_crash_lines.py`
- Test: `tests/test_propose_crash_lines.py`

**Interfaces:**
- Produces: `apply(proposals: dict, documents: dict[str, dict | list]) -> int` que altera em memória `labels` (lista) e `ground_truths`/`manifest`/`manifest_full` (dicts com `items`) e devolve quantos itens mudaram; só aplica `review == "aceita"` com `crash_expressions` não vazio; `label_sources.crash_expressions = "llm_patch_revisado"`; não duplica.

- [ ] **Passo 1: testes que falham**

```python
def _docs():
    item = lambda: {"id": "a", "label_sources": {"expression": "changed_line"}}
    return {"labels": [item()], "ground_truths": {"items": [item()]},
            "manifest": {"items": [item()]}, "manifest_full": {"items": [item()]}}


def test_apply_writes_accepted_into_all_documents_once():
    docs, props = _docs(), {"a": {"review": "aceita", "crash_expressions": ["xs[0] / window"]}}
    assert pcl.apply(props, docs) == 1
    assert pcl.apply(props, docs) == 0
    for doc in (docs["labels"], docs["ground_truths"]["items"], docs["manifest_full"]["items"]):
        assert doc[0]["crash_expressions"] == ["xs[0] / window"]
        assert doc[0]["label_sources"]["crash_expressions"] == "llm_patch_revisado"


def test_apply_skips_rejected_and_doubtful():
    docs = _docs()
    props = {"a": {"review": "rejeitada", "crash_expressions": ["x"]}}
    assert pcl.apply(props, docs) == 0 and "crash_expressions" not in docs["ground_truths"]["items"][0]
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_propose_crash_lines.py -q`
Expected: 2 falhas (`apply` não existe).

- [ ] **Passo 3: implementação**

```python
def _items(document) -> list[dict]:
    return document if isinstance(document, list) else document["items"]


def apply(proposals: dict, documents: dict) -> int:
    changed = set()
    for document in documents.values():
        for item in _items(document):
            entry = proposals.get(item["id"])
            if not entry or entry.get("review") != "aceita" or not entry.get("crash_expressions"):
                continue
            current = item.get("crash_expressions") or []
            new = current + [e for e in entry["crash_expressions"] if e not in current]
            if new != current:
                item["crash_expressions"] = new
                item.setdefault("label_sources", {})["crash_expressions"] = "llm_patch_revisado"
                changed.add(item["id"])
    return len(changed)
```

- [ ] **Passo 4: rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_propose_crash_lines.py -q`
Expected: 11 passed.

- [ ] **Passo 5: ponto de parada**

### Tarefa 4: CLI (`propose`, `table`, `apply`) e tabela de revisão

**Files:**
- Modify: `scripts/propose_crash_lines.py`
- Test: `tests/test_propose_crash_lines.py`

**Interfaces:**
- Consumes: `propose`, `apply` (Tarefas 2 e 3).
- Produces: `review_table(proposals: dict, items: dict[str, dict]) -> str` (Markdown com colunas Bug, Causa, Quebra proposta, Exceção, Parecer, Nota) e `main(argv=None) -> int`.

- [ ] **Passo 1: teste que falha**

```python
def test_review_table_lists_each_proposal():
    props = {"a": {"crash_expressions": ["xs[0] / window"], "exception": "ZeroDivisionError",
                   "review": "aceita", "review_note": "divisão logo abaixo", "same_as_expression": False}}
    table = pcl.review_table(props, {"a": {"expression": "window = get(k)"}})
    assert "| a | `window = get(k)` | `xs[0] / window` | ZeroDivisionError | aceita | divisão logo abaixo |" in table
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_propose_crash_lines.py -q`
Expected: 1 falha.

- [ ] **Passo 3: implementação**

```python
DATASET = ROOT / "dataset/bugs_reais"
DOCUMENTS = {"labels": ROOT / "dataset/coleta_bugsinpy/labels.json",
             "ground_truths": DATASET / "ground_truths.json",
             "manifest": DATASET / "manifest.json",
             "manifest_full": DATASET / "manifest_full.json"}


def review_table(proposals: dict, items: dict[str, dict]) -> str:
    lines = ["| Bug | Causa | Quebra proposta | Exceção | Parecer | Nota |", "|---|---|---|---|---|---|"]
    for key, entry in sorted(proposals.items()):
        crash = "a própria causa" if entry.get("same_as_expression") else \
            "; ".join(f"`{e}`" for e in entry.get("crash_expressions") or []) or entry.get("status", "")
        cause = " ".join(items.get(key, {}).get("expression", "").split())
        lines.append(f"| {key} | `{cause}` | {crash} | {entry.get('exception', '')} | "
                     f"{entry.get('review', 'pendente')} | {entry.get('review_note', '')} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["propose", "table", "apply"])
    parser.add_argument("--proposals", type=Path, default=DATASET / "crash_proposals.json")
    parser.add_argument("--backend", default="claude_cli")
    parser.add_argument("--model", default="claude-sonnet-5-5")
    parser.add_argument("--out", type=Path, default=ROOT / "docs/projeto/revisao_linha_da_quebra_2026-10-15.md")
    args = parser.parse_args(argv)
    truths = json.loads(DOCUMENTS["ground_truths"].read_text(encoding="utf-8"))["items"]
    if args.command == "propose":
        from research_pipeline.verify.llm_client import LLMClient
        propose(truths, llm=LLMClient(backend=args.backend, model=args.model), dataset=DATASET, out=args.proposals)
        return 0
    proposals = json.loads(args.proposals.read_text(encoding="utf-8"))
    if args.command == "table":
        args.out.write_text(review_table(proposals, {i["id"]: i for i in truths}), encoding="utf-8")
        return 0
    documents = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in DOCUMENTS.items()}
    print(f"{apply(proposals, documents)} itens alterados")
    for key, path in DOCUMENTS.items():
        path.write_text(json.dumps(documents[key], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Acrescentar `import argparse` no topo.

- [ ] **Passo 4: rodar teste, suíte e lint**

Run: `.venv/bin/python -m pytest tests/test_propose_crash_lines.py -q` → 12 passed.
Run: `timeout 10m .venv/bin/python -m pytest -q tests --ignore=tests/test_verify_esbmc_integration.py` → tudo passa.
Run: `pylint scripts/propose_crash_lines.py --disable=C0114,C0116` → sem erros.
Mutação: trocar `if not entry or entry.get("review") != "aceita"` por `if not entry` e confirmar que `test_apply_skips_rejected_and_doubtful` falha; desfazer.

- [ ] **Passo 5: ponto de parada**

### Tarefa 5: causa a partir do patch (sem LLM)

**Files:**
- Modify: `scripts/propose_crash_lines.py`
- Test: `tests/test_propose_crash_lines.py`

**Interfaces:**
- Consumes: `_save`, `propose` (Tarefa 2).
- Produces: `removed_lines(patch: str, source_file: str | None) -> list[str]`; `cause_from_patch(source: str, patch: str, source_file: str | None) -> dict` que devolve `{"status": "ok"|"ambigua"|"so_insercao"|"sem_casamento", "expressions": [str]}`; `causes(items: list[dict], *, dataset: Path, out: Path) -> dict` que grava `saved[id]["cause"]` para todo bug de exceção (inclusive os que já têm quebra). `propose` passa a pular só bugs cuja entrada já tem `status`.

- [ ] **Passo 1: testes que falham**

```python
PATCH = """--- a/pkg/m.py
+++ b/pkg/m.py
@@ -1,4 +1,4 @@
 def f(xs, k):
-    window = get(k)
+    window = get(k) or 1
     if window > 0:
-    return xs[0] / window
+    return xs[0] / window
--- a/pkg/other.py
+++ b/pkg/other.py
@@ -1,2 +1,2 @@
-    window = get(k)
+    pass
"""

SOURCE_IF = "def f(xs, k):\n    window = get(k)\n    if window > 0:\n        return xs[0] / window\n"


def test_removed_lines_only_from_the_target_file():
    assert pcl.removed_lines(PATCH, "pkg/m.py") == ["window = get(k)", "return xs[0] / window"]


def test_cause_matches_statements_by_text():
    out = pcl.cause_from_patch(SOURCE_IF, PATCH, "pkg/m.py")
    assert out == {"status": "ok", "expressions": ["window = get(k)", "return xs[0] / window"]}


def test_cause_uses_the_header_of_a_compound_statement():
    patch = "--- a/m.py\n+++ b/m.py\n@@ -1 +1 @@\n-    if window > 0:\n+    if window:\n"
    assert pcl.cause_from_patch(SOURCE_IF, patch, "m.py")["expressions"] == ["window > 0"]


def test_insertion_only_patch():
    patch = "--- a/m.py\n+++ b/m.py\n@@ -1 +1,2 @@\n+    check(k)\n     window = get(k)\n"
    assert pcl.cause_from_patch(SOURCE_IF, patch, "m.py") == {"status": "so_insercao", "expressions": []}


def test_repeated_text_is_ambiguous():
    source = "def f(a):\n    a.pop()\n    a.pop()\n"
    patch = "--- a/m.py\n+++ b/m.py\n@@ -1 +1 @@\n-    a.pop()\n+    a.clear()\n"
    out = pcl.cause_from_patch(source, patch, "m.py")
    assert out["status"] == "ambigua" and out["expressions"] == ["a.pop()"]


def test_no_match_in_the_function():
    patch = "--- a/m.py\n+++ b/m.py\n@@ -1 +1 @@\n-    other()\n+    pass\n"
    assert pcl.cause_from_patch(SOURCE_IF, patch, "m.py")["status"] == "sem_casamento"


def test_propose_does_not_skip_a_bug_that_only_has_its_cause(tmp_path):
    items, out = _dataset(tmp_path, ["a"]), tmp_path / "p.json"
    out.write_text(json.dumps({"a": {"cause": {"status": "ok", "expressions": []}}}))
    saved = pcl.propose(items, llm=_LLM(OK), dataset=tmp_path, out=out)
    assert saved["a"]["status"] == "ok" and saved["a"]["cause"]["status"] == "ok"
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_propose_crash_lines.py -q`
Expected: os 7 testes novos falham (funções ausentes; o de `propose` falha porque a entrada já existe e é pulada).

- [ ] **Passo 3: implementação**

```python
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
    """The innermost statement on ``lineno``; for if/while/for, only its header expression."""
    best = None
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt) and node.lineno <= lineno <= node.end_lineno:
            if best is None or node.lineno >= best.lineno and node.end_lineno <= best.end_lineno:
                best = node
    if best is None or isinstance(best, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return None
    header = _HEADERS.get(type(best))
    if header and lineno < best.body[0].lineno:
        return ast.get_source_segment(source, getattr(best, header))
    if isinstance(best, (ast.With, ast.AsyncWith)) and lineno < best.body[0].lineno:
        return ast.get_source_segment(source, best.items[0].context_expr)
    return ast.get_source_segment(source, best)


def cause_from_patch(source: str, patch: str, source_file: str | None) -> dict:
    removed = removed_lines(patch, source_file)
    if not removed:
        return {"status": "so_insercao", "expressions": []}
    tree, lines = ast.parse(source), source.splitlines()
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
        if item.get("failure_kind") == "resultado_errado":
            continue
        patch_path = dataset / "patches" / f"{item['id']}.diff"
        source = (dataset / "funcao_com_bug" / item["file"]).read_text(encoding="utf-8")
        source_file = (item.get("provenance") or {}).get("source_file")
        cause = cause_from_patch(source, patch_path.read_text(encoding="utf-8"), source_file) \
            if patch_path.exists() else {"status": "sem_patch", "expressions": []}
        saved.setdefault(item["id"], {})["cause"] = cause
    _save(out, saved)
    return saved
```

Em `propose`, trocar `if item["id"] in saved: continue` por `if "status" in saved.get(item["id"], {}): continue` e gravar com `saved[item["id"]] = {**saved.get(item["id"], {}), ...}` nas duas atribuições (preserva `cause`). Em `main`, acrescentar `"causes"` ao `choices` e o ramo `if args.command == "causes": causes(truths, dataset=DATASET, out=args.proposals); return 0`. Em `review_table`, acrescentar a coluna "Causa (patch)" com `entry.get("cause", {}).get("status")` e as expressões.

- [ ] **Passo 4: rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_propose_crash_lines.py -q` → 21 passed (o teste de `review_table` é ajustado à coluna nova).

- [ ] **Passo 5: ponto de parada**

### Tarefa 6: `apply` grava a causa e a avaliação aceita as três listas

**Files:**
- Modify: `scripts/propose_crash_lines.py` (`apply`)
- Modify: `src/research_pipeline/v2_evaluator.py:83` e `:136`
- Test: `tests/test_propose_crash_lines.py`, `tests/test_v2_evaluator.py`

**Interfaces:**
- Consumes: entradas com `cause` (Tarefa 5).
- Produces: itens do gabarito com `cause_expressions` e `label_sources.cause_expressions = "patch"`; `at_bug_line` e a localização aceitam `expression`, `cause_expressions` e `crash_expressions`.

- [ ] **Passo 1: testes que falham**

```python
# tests/test_propose_crash_lines.py
def test_apply_writes_deterministic_causes_and_reviewed_ambiguous_ones():
    docs = _docs()
    props = {"a": {"cause": {"status": "ok", "expressions": ["window = get(k)", "xs[0] / window"]}}}
    assert pcl.apply(props, docs) == 1
    item = docs["ground_truths"]["items"][0]
    assert item["cause_expressions"] == ["window = get(k)", "xs[0] / window"]
    assert item["label_sources"]["cause_expressions"] == "patch"
    docs = _docs()
    assert pcl.apply({"a": {"cause": {"status": "ambigua", "expressions": ["a.pop()"]}}}, docs) == 0
    assert pcl.apply({"a": {"cause": {"status": "ambigua", "expressions": ["a.pop()"]},
                            "cause_review": "aceita"}}, docs) == 1
```

```python
# tests/test_v2_evaluator.py
from research_pipeline.v2_evaluator import at_bug_line


def test_at_bug_line_accepts_any_cause_line_from_the_patch():
    item = {"function": "f", "expression": "window = get(k)", "cause_expressions": ["k = k or 1"]}
    assert at_bug_line({"function": "f", "suspect_expression": "k = k or 1"}, item)
    assert not at_bug_line({"function": "f", "suspect_expression": "other()"}, item)
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_propose_crash_lines.py tests/test_v2_evaluator.py -q`
Expected: os 2 testes novos falham.

- [ ] **Passo 3: implementação**

Em `apply`, antes do bloco da quebra, dentro do laço por item:

```python
            cause = (entry or {}).get("cause") or {}
            if cause.get("expressions") and (cause.get("status") == "ok" or entry.get("cause_review") == "aceita"):
                current = item.get("cause_expressions") or []
                new = current + [e for e in cause["expressions"] if e not in current]
                if new != current:
                    item["cause_expressions"] = new
                    item.setdefault("label_sources", {})["cause_expressions"] = "patch"
                    changed.add(item["id"])
```

e trocar a guarda da quebra para `if not entry or entry.get("review") != "aceita" or not entry.get("crash_expressions"): continue` depois desse bloco (mesma regra de antes).

Em `src/research_pipeline/v2_evaluator.py`, nas linhas 83 e 136, incluir `*item.get("cause_expressions", [])` entre `expression` e `crash_expressions`, e atualizar o comentário da linha 135 para "Where the patch changes the code (every changed line), then where the buggy version raises".

- [ ] **Passo 4: rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_propose_crash_lines.py tests/test_v2_evaluator.py -q` → tudo passa.
Run: `timeout 10m .venv/bin/python -m pytest -q tests --ignore=tests/test_verify_esbmc_integration.py` → tudo passa.
Run: `.venv/bin/python -m ruff check scripts/propose_crash_lines.py src/research_pipeline/v2_evaluator.py tests/test_propose_crash_lines.py` → limpo.
Mutação: tirar `*item.get("cause_expressions", [])` da linha 83 e confirmar que `test_at_bug_line_accepts_any_cause_line_from_the_patch` falha; desfazer.

- [ ] **Passo 5: ponto de parada**

### Tarefa 7: rodada real, conferência e revisão (operacional)

**Files:**
- Create: `dataset/bugs_reais/crash_proposals.json` (gerado), `docs/projeto/revisao_linha_da_quebra_2026-10-15.md` (gerado)

- [ ] **Passo 0:** `PYTHONPATH=src .venv/bin/python scripts/propose_crash_lines.py causes` (sem LLM) e conferir os `ambigua`, `so_insercao` e `sem_casamento` na revisão.
- [ ] **Passo 1:** rodar `PYTHONPATH=src .venv/bin/python scripts/propose_crash_lines.py propose` (84 chamadas ao `claude_cli`). Se parar por limite, rodar de novo depois; a retomada não refaz.
- [ ] **Passo 2:** conferência do Claude Code: para cada entrada `ok`, ler `funcao_com_bug/<id>.py` e `patches/<id>.diff`, e preencher no JSON `review` (`aceita`, `rejeitada` ou `duvida`) e `review_note` (uma frase com o motivo). `sem_patch` e `failed` ficam `duvida`.
- [ ] **Passo 3:** `PYTHONPATH=src .venv/bin/python scripts/propose_crash_lines.py table` e entregar a tabela à Fernanda. Esperar ela marcar discordâncias e ajustar o JSON.

### Tarefa 8: aplicar (medição adiada para o item 6 do PLANO_GERAL, a pedido da Fernanda)

**Files:**
- Modify: `dataset/coleta_bugsinpy/labels.json`, `dataset/bugs_reais/{ground_truths,manifest,manifest_full}.json`, `docs/experimentos/README.md`

- [ ] **Passo 1:** `PYTHONPATH=src .venv/bin/python scripts/propose_crash_lines.py apply` e conferir com `git diff --stat dataset/` que só `crash_expressions`/`label_sources` mudaram (`git diff dataset/ | grep '^[-+] ' | grep -v crash_expressions | grep -v label_sources | grep -v '^\+ *"' ` deve listar só linhas das listas novas).
- [ ] **Passo 2:** medir antes e depois nos relatórios existentes:

```bash
git show HEAD:dataset/bugs_reais/ground_truths.json > /tmp/claude-1000/gt_antes.json
PYTHONPATH=src .venv/bin/python - <<'EOF'
import json
from pathlib import Path
from research_pipeline.v2_evaluator import at_bug_line
def load(p): return {i["id"]: i for i in json.load(open(p))["items"]}
before, after = load("/tmp/claude-1000/gt_antes.json"), load("dataset/bugs_reais/ground_truths.json")
for rep in ["artifacts/v2/final-2026-10-15-codex/v2_verify_report.json",
            "artifacts/v2/esbmc-master-lote5full-2026-10-14/merged_report.json"]:
    res = json.load(open(rep))["results"]
    for name, gt in (("antes", before), ("depois", after)):
        hit = {Path(r["hypothesis"]["file"]).stem for r in res
               if (it := gt.get(Path(r["hypothesis"]["file"]).stem)) and it.get("failure_kind") != "resultado_errado"
               and at_bug_line(r["hypothesis"], it)}
        conf = {Path(r["hypothesis"]["file"]).stem for r in res if r["verdict"] == "CONFIRMED"
                and (it := gt.get(Path(r["hypothesis"]["file"]).stem)) and it.get("failure_kind") != "resultado_errado"
                and at_bug_line(r["hypothesis"], it)}
        print(rep.split("/")[2], name, "linha certa:", len(hit), "confirmados na linha:", len(conf))
EOF
```

Uma confirmação nova só conta para a métrica depois de conferir que a exceção do replay é a esperada (como foi feito com bip_scrapy_15).
- [ ] **Passo 3:** registrar em `docs/experimentos/README.md` (Fase 15): data, comando, modelo, quantas aceitas/rejeitadas/dúvidas, antes e depois por relatório, e a nota de que a mesma família de modelo faz detecção e rótulo, com dupla revisão como controle.
- [ ] **Passo 4:** suíte rápida de novo e ponto de parada para a Fernanda decidir o commit.
