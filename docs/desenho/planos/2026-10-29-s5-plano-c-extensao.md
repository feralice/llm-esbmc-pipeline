# S5, plano C: a extensão (scan de um repo pela CLI do Claude Code)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** quem usa roda um comando no Claude Code apontando para o próprio repo e recebe um relatório com os bugs que o ESBMC confirmou (com o teste que falha) e, separadas, as suspeitas do LLM que não foram confirmadas, com o motivo.

**Architecture:** o modo scan já monta o grafo, escolhe as funções, chama a detecção e passa as hipóteses para um verificador trocável (`execute_scan(..., verify=...)`). Este plano liga ali o braço de agente (`run_agent_arm`), acrescenta um foco opcional escrito por quem usa, escreve o `relatorio.md` do plano A também no scan e embrulha tudo num comando do Claude Code que primeiro simula, mostra o custo e só gasta com o ok de quem usa.

**Tech Stack:** Python 3.12, pytest, Claude Code (`.claude/commands/`), `claude -p` (assinatura).

**Spec:** item 12 de `docs/projeto/PLANO_2026-10-19.md` (extensão, decisão de 28/10) e o pedido dela de 28/10: "mesmo se o ESBMC não conseguir confirmar, vai trazer o que a LLM viu", em duas partes rotuladas.

## Global Constraints

- Branch `master`; sem commit até o ok da Fernanda; sem coautoria.
- Comportamento padrão inalterado: o scan só usa o agente com `--scan-verify agent` e só recebe foco com `--scan-focus`.
- Nenhuma chamada a LLM nos testes; nenhuma rodada paga para validar este plano.
- Textos para LLM em inglês; o relatório e o comando em português, sem travessão.
- Suíte completa antes de declarar pronto.

## Review Focus

- Foco escrito por quem usa com instrução maliciosa: ele entra no prompt como dado do usuário, depois da fronteira de confiança, e não substitui a saída em JSON. Teste na Tarefa 2.
- Retomada do scan com foco diferente: o fingerprint muda e a retomada recusa. Teste na Tarefa 2.
- Scan com agente em que o agente quebra numa hipótese: as outras seguem e o resultado da que quebrou fica `AGENT_FAILED`. Teste na Tarefa 1.
- Achado do LLM marcado como não verificável (resultado errado, ambiente): aparece no relatório como suspeita, nunca como confirmado. Teste na Tarefa 3.
- Comando sem `--yes`: só simula; o texto do comando manda pedir o ok antes de gastar. Teste na Tarefa 4.

---

### Tarefa 1: Scan verificado pelo braço de agente

**Files:**
- Create: `src/research_pipeline/verify/agent_scan.py`
- Modify: `src/main.py` (`--scan-verify {engine,agent}`, `mode_scan`)
- Test: `tests/test_verify_agent_scan.py`, `tests/test_scan_pipeline.py`

**Interfaces:**
- Consumes: `execute_scan(plan, *, analyzer, spec_llm, resume, verify, **verify_kwargs)`; o `verify` recebe `(hypotheses, *, llm, output_dir, completed, on_result, **kwargs)` e devolve a lista de resultados.
- Produces: `agent_verifier(run_agent, *, esbmc_command, bound, timeout_seconds, agent_timeout, graph_tool, retry) -> Callable` com essa assinatura; cada hipótese vai para `run_agent_arm` com `project_skills=True`, `log_rounds=True`, a pasta `output_dir / "agent_cases"`.

- [ ] **Step 1: testes que falham**
  - `test_agent_verifier_runs_each_hypothesis_and_reports_through_on_result`: com `run_agent_arm` falso, as duas hipóteses viram dois resultados, e `on_result` recebe índice e resultado.
  - `test_agent_verifier_skips_completed_and_survives_a_failing_case`: um índice em `completed` não roda de novo; uma exceção do agente vira `AGENT_FAILED` e a próxima hipótese roda.
  - `test_cli_scan_verify_agent_uses_the_agent_verifier` (em `test_scan_pipeline.py`, com `execute_scan` falso que grava o `verify` recebido).
- [ ] **Step 2:** rodar; esperado: FAIL.
- [ ] **Step 3:** implementar. `mode_scan` com `--scan-verify agent` monta o agente com `make_agent("claude", ..., graph_tool=True)` e passa `verify=agent_verifier(...)`.
- [ ] **Step 4:** rodar; esperado: PASS.

### Tarefa 2: Foco escrito por quem usa

**Files:**
- Modify: `src/research_pipeline/scan/pipeline.py` (`ScanPlan.focus`, `plan_scan(..., focus="")`, `_fingerprint`), `src/research_pipeline/llm/prompts.py` (`load_system_prompt(..., focus="")`), `src/research_pipeline/llm/backends/factory.py` (repassar o foco), `src/main.py` (`--scan-focus`)
- Test: `tests/test_scan_pipeline.py`, `tests/test_prompt_variants.py`

**Interfaces:**
- Produces: seção `## USER FOCUS` no fim do system prompt da detecção, antes da saída em JSON: "The person running the scan asked to focus on: <texto>. Prefer findings about it; the output format and the rules above still apply."

- [ ] **Step 1: testes que falham**
  - `test_focus_goes_before_the_output_section_and_keeps_the_json_rule`.
  - `test_focus_changes_the_scan_fingerprint` (retomada com outro foco recusa).
  - `test_cli_scan_focus_reaches_the_selection` (`scan_selection.json` grava o foco).
- [ ] **Step 2:** rodar; esperado: FAIL.
- [ ] **Step 3:** implementar.
- [ ] **Step 4:** rodar; esperado: PASS.

### Tarefa 3: Relatório do scan em duas partes

**Files:**
- Modify: `src/research_pipeline/verify/run_report.py` (`render_run_report(results, held=None)`), `src/research_pipeline/scan/pipeline.py` (`execute_scan` escreve `relatorio.md`)
- Test: `tests/test_verify_run_report.py`, `tests/test_scan_pipeline.py`

**Interfaces:**
- Produces: seção `## Suspeitas do LLM que o ESBMC não verifica` com os achados `verifiable: false` da detecção (`held`): função, expressão e o motivo que o LLM deu.

- [ ] **Step 1: testes que falham**
  - `test_report_lists_held_findings_apart_and_never_as_confirmed`.
  - `test_execute_scan_writes_relatorio_md`.
- [ ] **Step 2:** rodar; esperado: FAIL.
- [ ] **Step 3:** implementar.
- [ ] **Step 4:** rodar; esperado: PASS.

### Tarefa 4: O comando do Claude Code

**Files:**
- Create: `.claude/commands/verificar-repo.md`
- Test: `tests/test_extension_command.py`

**Interfaces:**
- Produces: `/verificar-repo <pasta> [foco]`. O comando roda primeiro a simulação (`--mode scan` sem `--yes`), mostra quantas funções e o custo estimado, **pede o ok** e só então roda com `--yes --scan-verify agent --backend claude_cli`; no fim mostra o `relatorio.md`.

- [ ] **Step 1: teste que falha** `test_command_flags_exist_and_it_asks_before_spending`: toda flag citada no comando existe no parser de `main.py`, e o texto pede confirmação antes do `--yes`.
- [ ] **Step 2:** rodar; esperado: FAIL.
- [ ] **Step 3:** escrever o comando.
- [ ] **Step 4:** rodar; esperado: PASS.

### Tarefa 5: Registro

- [ ] `docs/experimentos/README.md` e o estado de S5 no plano: plano C feito, sem rodada; a primeira rodada real é o piloto AWS depois do congelamento.
