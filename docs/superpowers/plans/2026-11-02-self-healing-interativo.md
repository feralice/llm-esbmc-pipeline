# Self-healing interativo e caderno compartilhado — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** comando `/self-healing` na extensão, dois scripts de apoio e o self-healing do lote lendo o caderno de lições.

**Architecture:** `src/research_pipeline/verify/lessons.py` lê, versiona e acrescenta regras ao caderno
(`verify/skills/reparos-aprendidos/SKILL.md`); `Healer` recebe as regras aprovadas no prompt de reparo; os scripts
`check_preserved.py` e `add_repair.py` são o que o comando chama.

**Tech Stack:** Python 3.12, pytest, comando Markdown do Claude Code.

**Spec:** `docs/superpowers/specs/2026-11-02-self-healing-interativo-design.md`

## Global Constraints

- Caderno só muda por `add_repair` (formato conferido) e só depois do "sim" da Fernanda.
- Regras aprovadas = seções `### ` antes de `## Format of an approved repair`.
- Sem chamada real a LLM nos testes; commits sem coautoria do Claude.

## Review Focus

- Título repetido no caderno: recusado. Teste na Task 1.
- Campo com quebra de linha (o formato é uma linha por campo): recusado. Teste na Task 1.
- Caderno sem a seção de formato: `add_repair` recusa em vez de acrescentar no lugar errado. Teste na Task 1.
- Caderno vazio de regras: o prompt do lote não ganha seção vazia. Teste na Task 2.
- Mudança no caderno muda o `config_label` (a retomada do scan não reaproveita resultado de outra versão). Teste na Task 2.

### Task 1: `lessons.py` e os dois scripts
**Produces:** `NOTEBOOK: Path`; `approved_repairs(path=NOTEBOOK) -> str`; `notebook_version(path=NOTEBOOK) -> str` (12 hex);
`add_repair(title, error, what, case, *, path=NOTEBOOK, today: date) -> None` (`ValueError` em formato inválido);
CLIs `scripts/add_repair.py --title --error --what --case [--notebook]` e
`scripts/check_preserved.py ORIGINAL HARNESS FUNCAO [EXPRESSAO]` (imprime `preservado`/`alterado`, sai 0/1).
- [ ] Testes → FAIL → implementar → PASS → commit `Read, version and extend the repair notebook from scripts`.

### Task 2: lote lê o caderno
**Consumes:** `approved_repairs`, `notebook_version`. **Produces:** `Healer(llm, knowledge, graph, lessons: str | None = None)`
(None = lê o caderno); `_repair` acrescenta `"Repairs the researcher approved for earlier cases:\n{lessons}"` quando
houver; `config_label` termina em `+notes:<versão>` quando houver regras.
- [ ] Testes → FAIL → implementar → PASS → commit `Give batch self-healing the approved repairs`.

### Task 3: comando `/self-healing`
**Files:** `extension/commands/self-healing.md`, `extension/README.md`. Passos: achar o caso, rodar o ESBMC, ler regras,
uma reescrita por vez com explicação, `check_preserved.py` (desfaz se alterado), ESBMC de novo, até 5 tentativas;
no veredito, propor a lição e só chamar `add_repair.py` com "sim".
- [ ] Revisar o texto contra a spec; suíte inteira; registro no README de experimentos; commit
  `Add the interactive /self-healing command`.
