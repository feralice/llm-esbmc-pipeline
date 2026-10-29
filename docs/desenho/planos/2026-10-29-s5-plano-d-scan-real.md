# S5, plano D: o scan pronto para repo real (retomada, seleção, níveis, caminho)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** o `/verificar-repo` num repo real (AWS samples, boto3) retoma sem trocar resultados de hipótese, não gasta com exemplo e documentação, conta por nível o que o ESBMC decidiu e diz de qual arquivo é cada achado.

**Architecture:** tudo no caminho do scan (`scan/pipeline.py`, `verify/run_report.py`, `verify/levels.py`, `main.py`); o braço de agente e o motor não mudam. O checkpoint do scan passa a guardar os vereditos pelo `hypothesis_id` e o fingerprint inclui o hash dos prompts e a configuração do verify. A seleção filtra na escolha dos alvos, não no grafo, para os exemplos continuarem como contexto de chamador.

**Tech Stack:** Python 3.12, pytest.

**Spec:** itens 9a, 9b e 9c de `docs/projeto/PLANO_2026-10-19.md` (revisão do scan de 27/10) e o minor adiado do plano C (caminho no relatório), pedidos pela Fernanda em 29/10 antes do congelamento.

## Global Constraints

- Branch `master` (trabalho numa worktree destacada enquanto a rodada S6 lê o repo principal); sem commit até o ok da Fernanda; sem coautoria.
- Nenhuma chamada a LLM nos testes; nenhuma rodada paga.
- Textos do relatório em português, sem travessão.
- Suíte completa antes de declarar pronto.

## Review Focus

- Retomada depois que uma detecção que tinha falhado passa a dar hipóteses novas: os vereditos salvos continuam com a hipótese certa. Teste na Tarefa 1.
- Checkpoint do formato antigo (chaves por posição): o fingerprint muda e a retomada recusa, nunca lê errado. Teste na Tarefa 1.
- Repo cujo código inteiro está em `examples/`: a seleção sai vazia e a mensagem diz como incluir. Teste na Tarefa 2.
- Dois `__init__.py` com achado: o relatório mostra os dois caminhos. Teste na Tarefa 4.
- Resultado do agente com corpo alterado e veredito do ESBMC: nunca conta como nível `esbmc_agent`. Teste na Tarefa 3.

---

### Tarefa 1: Retomada pelo `hypothesis_id` e fingerprint com os prompts (9a)

**Files:** Modify `src/research_pipeline/scan/pipeline.py` (`_fingerprint`, `execute_scan`). Test `tests/test_scan_pipeline.py`.

**Interfaces:**
- Produces: `checkpoint["verify_results"]` com chave `hypothesis_id`; `_fingerprint(plan, model, verifier="engine", verify_config=None)` com `prompts` = sha256 do system prompt da detecção (com o foco) e dos user prompts dos alvos, e `verify_config` = os `verify_kwargs` serializados com `default=str`.
- Os verificadores continuam recebendo `completed` por índice: `execute_scan` traduz id para índice da lista atual.

- [ ] **Step 1: testes que falham**
  - `test_resume_keeps_each_verdict_with_its_hypothesis_when_a_new_one_appears`: primeira execução com a detecção de um alvo falhando; a retomada acerta esse alvo, que gera uma hipótese que entra antes das outras na lista; o verificador falso recebe em `completed` os vereditos antigos nos índices novos, e só a hipótese nova roda.
  - `test_resume_refuses_a_checkpoint_saved_by_position`: checkpoint com `verify_results` `{"0": ...}` e o fingerprint antigo recusa com `ValueError`.
  - `test_prompt_change_changes_the_scan_fingerprint` (monkeypatch em `load_system_prompt`) e `test_verify_config_changes_the_scan_fingerprint` (`bound` diferente).
- [ ] **Step 2:** rodar; esperado: FAIL.
- [ ] **Step 3:** implementar.
- [ ] **Step 4:** rodar; esperado: PASS.

### Tarefa 2: Seleção sem exemplo, documentação, `setup.py` e `async` (9b)

**Files:** Modify `src/research_pipeline/scan/callgraph.py` (`FunctionNode.is_async`), `src/research_pipeline/scan/pipeline.py` (`select_targets`, `plan_scan`), `src/main.py` (`--scan-include-examples`). Test `tests/test_scan_pipeline.py`.

**Interfaces:**
- Produces: `NON_PRODUCT_DIRS = frozenset({"examples", "example", "docs", "doc"})`; `select_targets(..., include_examples=False)` pula funções em arquivo com uma dessas pastas no caminho relativo, o `setup.py` da raiz (um `pkg/setup.py` é código do produto), e funções `async def` (o ESBMC-Python não modela `async`); `plan_scan(..., include_examples=False)` e `ScanPlan.to_dict()["excluded"]` com a contagem por motivo (`examples`, `setup`, `async`).
- O grafo continua com tudo: os exemplos seguem como chamadores no contexto.

- [ ] **Step 1: testes que falham**
  - `test_selection_skips_examples_docs_setup_and_async_but_keeps_them_as_callers`.
  - `test_selection_with_only_examples_is_empty_and_says_how_to_include` (a mensagem cita `--scan-include-examples`).
  - `test_cli_scan_include_examples_reaches_the_selection`.
- [ ] **Step 2:** rodar; esperado: FAIL.
- [ ] **Step 3:** implementar; o filtro de async não muda com a flag.
- [ ] **Step 4:** rodar; esperado: PASS.

### Tarefa 3: Níveis no scan e confirmados por força da evidência (9c)

**Files:** Modify `src/research_pipeline/verify/levels.py` (`agent_levels`), `src/research_pipeline/scan/pipeline.py` (`_report`, `summary_markdown`), `src/research_pipeline/verify/run_report.py` (ordem dos confirmados). Test `tests/test_verify_levels.py`, `tests/test_verify_run_report.py`, `tests/test_scan_pipeline.py`.

**Interfaces:**
- Produces: `agent_levels(agent: list[dict]) -> list[dict]`, mesmas linhas de `consolidate` quando o agente é o único nível (ESBMC no corpo intacto: `esbmc_agent`; simplificado: `esbmc_agent_simplified`; o resto `llm_only` com o grupo do motivo, `agent_rewrote_function` quando o corpo mudou). `scan_report.json` ganha `levels = {"summary": level_summary(rows), "rows": rows}`: `consolidate(results)` com o motor, `agent_levels(results)` com o agente.
- `evidence(result) -> list[str]`, em `run_report.py`: `"teste"` quando `pytest.status == "reproduces"`, `"versão corrigida passa"` quando há `control` e ele não reproduziu, `"diferencial real"` quando `differential.level == "real"` e a preservação não é `mudou`. Os confirmados saem do mais forte para o mais fraco, cada um com a lista; a seção diz que todo confirmado passa por auditoria manual antes de virar issue (9e).
- O S1 (alcançabilidade) já está dentro do `run_agent_arm`, que o `--scan-verify agent` usa: nada a ligar; o teste fixa isso.

- [ ] **Step 1: testes que falham**
  - `test_agent_levels_never_counts_a_rewritten_body_as_an_agent_verdict`.
  - `test_confirmed_are_listed_by_evidence_with_the_audit_note`.
  - `test_scan_report_has_levels_for_the_engine_and_for_the_agent`.
- [ ] **Step 2:** rodar; esperado: FAIL.
- [ ] **Step 3:** implementar.
- [ ] **Step 4:** rodar; esperado: PASS.

### Tarefa 4: Caminho relativo no relatório

**Files:** Modify `src/research_pipeline/verify/run_report.py` (`render_run_report(..., root=None)`), `src/research_pipeline/scan/pipeline.py` (passa `plan.root`). Test `tests/test_verify_run_report.py`.

**Interfaces:**
- Produces: com `root`, cada entrada mostra o caminho relativo a ele (`pkg/a/__init__.py::f`); sem `root` (braço de agente) continua o nome do arquivo.

- [ ] **Step 1: teste que falha** `test_report_names_files_relative_to_the_scanned_root`.
- [ ] **Step 2:** rodar; esperado: FAIL.
- [ ] **Step 3:** implementar; também nas suspeitas `held`.
- [ ] **Step 4:** rodar; esperado: PASS.

### Tarefa 5: Registro

- [ ] `docs/experimentos/README.md` e o estado de S5 no plano: plano D feito, sem rodada; o 9d (piloto barato) e o item 14 (bug semeado) vêm depois.
