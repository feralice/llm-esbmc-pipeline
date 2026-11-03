# Smells: ferramenta gera, LLM filtra — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** um filtro por LLM sobre candidatos de smell vindos de ferramenta, medido no PySmell rotulado e ligado ao scan com o ruff.

**Architecture:** módulo `src/research_pipeline/smells/filter.py` (candidato, chamada em lote por trecho de código, pontuação); prompt `src/research_pipeline/prompts/smell_filter.txt`; script de medição `scripts/smell_filter_pysmell.py`; no scan, `ruff_candidates` alimenta `scan_smells.json` e o `judge_smells` existente.

**Tech Stack:** Python 3.12, `ast`, `ruff` (CLI, saída JSON), pytest, `LLMClient` existente.

**Spec:** `docs/superpowers/specs/2026-11-02-smells-ferramenta-llm-design.md`

## Global Constraints

- Prompt em inglês; o código entre marcadores `<UNTRUSTED_PYTHON_CODE>` (como no prompt de Feature Envy).
- O filtro só tira: candidato sem resposta válida mantém a decisão da ferramenta e é contado em `llm_errors`.
- Candidato sem código não vai ao LLM e é contado em `no_code`.
- Nenhuma chamada real a LLM nos testes nem sem `--yes`.
- Branch `feat/harness-de-agente`; commits sem coautoria do Claude.

## Review Focus

- Resposta com id que não foi pedido, ou id repetido: ignorar o extra, usar a primeira resposta. Teste na Task 1.
- `smell` vindo como string `"false"`: só `True` booleano conta como smell. Teste na Task 1.
- Retomada: candidato já respondido não é perguntado de novo. Teste na Task 2.
- Arquivo que o ruff não consegue ler: não derruba o scan. Teste na Task 3.
- Pontuação com zero candidatos de um smell: precisão `None`, não divisão por zero. Teste na Task 1.

---

### Task 1: candidato, filtro em lote e pontuação

**Files:** Create `src/research_pipeline/smells/__init__.py`, `src/research_pipeline/smells/filter.py`, `src/research_pipeline/prompts/smell_filter.txt`; Test `tests/test_smell_filter.py`.

**Interfaces (Produces):**
- `SmellCandidate(id: str, smell: str, path: str, line: int, tool: str, metrics: dict, code: str)` (frozen dataclass).
- `filter_candidates(candidates: list[SmellCandidate], llm, *, done: dict | None = None, on_answer=None) -> dict[str, dict]`: agrupa por `(path, code)`, uma chamada por grupo; resultado por id: `{"smell": bool, "reason": str}`, `{"error": str}` ou `{"skipped": "no code"}`. `done` traz respostas anteriores (não repergunta id com resposta sem erro); `on_answer(results)` é chamado depois de cada grupo.
- `score(candidates, labels: dict[str, int], results: dict[str, dict]) -> dict`: `{"tool": {...}, "tool_llm": {...}, "per_smell": {smell: {"tool": {...}, "tool_llm": {...}}}, "llm_errors": int, "no_code": int}`, cada bloco `{"tp", "fp", "fn", "precision", "recall", "f1"}`; o LLM só tira candidatos com `smell is False`; `fn` inclui os rótulos positivos que a ferramenta não apontou (passados em `labels` com id fora de `candidates`).

- [ ] Testes (LLM falso, `SimpleNamespace(raw_response=...)`): dois candidatos no mesmo trecho → uma chamada; resposta sem um id → `error` só nele; JSON inválido → `error` em todo o grupo; id extra/repetido; `"false"` string não tira; `done` evita chamada; `score` com zero candidatos dá `precision` `None`; `score` em exemplo de 4 itens com números exatos.
- [ ] Rodar → FAIL; implementar; rodar → PASS; commit `Filter tool-reported smell candidates with an LLM`.

### Task 2: medição no PySmell

**Files:** Create `scripts/smell_filter_pysmell.py`; Test `tests/test_smell_filter.py`.

**Interfaces:** `pysmell_candidates(rows: list[dict]) -> tuple[list[SmellCandidate], dict[str, int]]` (candidatos = união das heurísticas; labels de todos os itens); CLI `python scripts/smell_filter_pysmell.py --out DIR [--sample 200] [--seed 42] [--backend claude_cli] [--model M] [--yes]`: sem `--yes` imprime candidatos, chamadas e sai; com `--yes` grava `DIR/results.json` a cada grupo (retomável) e `DIR/score.json`.

- [ ] Teste de `pysmell_candidates` com 3 linhas falsas; teste do caminho sem `--yes` (nenhuma chamada). FAIL → implementar → PASS → commit `Measure the smell filter on PySmell's hand labels`.

### Task 3: ruff no scan

**Files:** Modify `src/research_pipeline/smells/filter.py` (`ruff_candidates`), `src/research_pipeline/scan/pipeline.py` (`plan_scan` com `smells=True` grava `tool_candidates`; `judge_smells` filtra eles), `src/main.py` (mensagem da simulação conta as chamadas); Test `tests/test_scan_pipeline.py`.

**Interfaces:** `RUFF_SMELLS = {"PLR0913": "LongParameterList", "PLR0915": "LongMethod", "C901": "LongMethod", "PLR0904": "LargeClass"}`; `ruff_candidates(root: Path, ruff: str = "ruff") -> list[SmellCandidate]` (roda `ruff check --isolated --select <regras> --output-format json`, código = função ou classe que contém a linha); `scan_smells.json` ganha `"tool_candidates": [{"id", "smell", "path", "line", "rule", "llm"?}]`.

- [ ] Teste: repo com função de 7 parâmetros → um candidato `LongParameterList`; `judge_smells` com LLM falso grava `llm` no candidato; arquivo com erro de sintaxe não derruba. FAIL → implementar → PASS; suíte inteira; registro no `docs/experimentos/README.md` (sem rodada); commit `Feed ruff smell candidates to the scan's LLM filter`.
