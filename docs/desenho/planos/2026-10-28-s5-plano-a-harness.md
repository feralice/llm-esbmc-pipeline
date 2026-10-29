# S5, plano A: harness e verificação antes do congelamento

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** fechar as falhas que a triagem da rodada S2 de 28/10 mostrou no braço de agente, para que S6 (refazer S2 e S3) meça uma versão que não perde bug por defeito do pipeline.

**Architecture:** tudo acontece em `verify/`. As regras vão para a skill `regras-harness`, que o agente lê. A rodada no CPython antes do ESBMC e o controle com a versão corrigida ficam em `evaluate_harness`. O limite dos laços da biblioteca fica em `esbmc_run.check`. O relatório lê o `agent_results.json` de uma rodada e não chama LLM nem ESBMC.

**Tech Stack:** Python 3.12, pytest, ESBMC master `4a356e33eb` (`~/esbmc-master/esbmc.sh`), `claude -p`.

**Spec:** linha S5 de `docs/projeto/PLANO_2026-10-19.md` (itens 1, 2, 3, 4, 11, 12 e 13) e a triagem de 28/10 (reprodutores 60 a 66 em `docs/projeto/possiveis_problemas/`).

## Global Constraints

- Branch `master`, sem branch por feature. Commit só com o ok da Fernanda, sem coautoria.
- Mensagem de commit com linha em branco entre o título e o corpo; escrever o corpo num arquivo e usar `git commit -F`.
- Nada de `--no-unwinding-assertions`.
- Textos para o agente e prompts em inglês; documentos dela em português, sem travessão.
- Suíte completa (`timeout 600 .venv/bin/python -m pytest -q`) antes de cada commit.
- O corpo da função alvo nunca muda: as regras novas valem só para stubs e driver.

## Review Focus

- Exceção do stub em uma só entrada do replay: a rodada no CPython antes do ESBMC não pode marcar o harness como quebrado quando a exceção nasce na linha suspeita (é o bug). Teste na Tarefa 2.
- Exceção dentro da função alvo, fora da linha suspeita: pode ser outro bug real; não volta ao agente como defeito do harness. Teste na Tarefa 2.
- Laço do próprio harness junto com laço da biblioteca: subir só a biblioteca não pode esconder o laço do harness; a leitura continua `artifact` e segue para a escalada normal. Teste na Tarefa 3.
- Caso sem arquivo corrigido no dataset: o script segue sem o controle e registra que ele não rodou. Teste na Tarefa 4.
- Confirmado sem pytest do ESBMC e sem entradas no replay: o relatório diz que não há teste, não inventa um. Teste na Tarefa 5.

---

### Tarefa 1: Regras de stub e driver tiradas da triagem (versão 4 da skill)

**Files:**
- Modify: `src/research_pipeline/verify/skills/regras-harness/SKILL.md`
- Test: `tests/test_verify_agent_arm.py`

**Interfaces:**
- Produces: `Version: 4` no SKILL.md; o hash muda e cada rodada já registra a versão.

- [ ] **Step 1: teste que falha** `test_harness_rules_cover_the_2026_10_28_workarounds`: lê o SKILL.md e verifica `"Version: 4"` e a presença de `"__ESBMC_"`, `"elif"`, `"lambda"`, `"dict.get"` e `"local variable"`.
- [ ] **Step 2:** rodar `.venv/bin/python -m pytest tests/test_verify_agent_arm.py -k 2026_10_28 -q`; esperado: FAIL.
- [ ] **Step 3:** acrescentar as regras 12 a 16, cada uma com o erro do ESBMC entre aspas, e trocar a versão para 4:
  - 12 (reprodutores 61 e 62): em stubs e driver, não usar atributo que pode faltar como operando de `or`/`and`; separar em `if`/`elif`.
  - 13 (63 e 66): para indexar ou desempacotar `obj.attr[k]` quando a classe de `attr` define `__getitem__`, ler `attr` numa variável local antes.
  - 14 (65): num stub, não reatribuir um parâmetro ao resultado de `dict.get()`; usar um nome novo.
  - 15 (64): callable de stub é `def` de módulo, não lambda dentro de método.
  - 16 (caso `gamma`): stubs usam o módulo `math`, nunca as funções `__ESBMC_*`.
- [ ] **Step 4:** rodar o teste; esperado: PASS.
- [ ] **Step 5:** commit.

### Tarefa 2: Rodar o harness no CPython antes do ESBMC

**Files:**
- Modify: `src/research_pipeline/verify/agent_arm.py` (`evaluate_harness`, `retry_reason`)
- Test: `tests/test_verify_agent_arm.py`

**Interfaces:**
- Consumes: `concrete_replay(program, function, *, seeds: dict[str, list] | None = None) -> ReplayVerdict` (`replay.py`), com `status`, `exception_type`, `raised_at`.
- Produces: veredito `HARNESS_BROKEN = "HARNESS_BROKEN"` em `agent_arm.py`; `retry_reason` devolve o motivo dele.

- [ ] **Step 1: testes que falham**
  - `test_stub_that_raises_outside_the_target_is_harness_broken`: harness cujo stub faz `[][0]` antes de chamar o alvo; `evaluate_harness` devolve `HARNESS_BROKEN`, o motivo cita a linha do stub e o ESBMC não é chamado (runner falso que falha se for chamado).
  - `test_exception_at_the_suspect_line_still_goes_to_esbmc`: harness do `DIV` de `tests/test_verify_replay.py`; o ESBMC falso é chamado.
  - `test_exception_inside_the_target_off_the_suspect_line_is_not_harness_broken`.
  - `test_harness_broken_goes_back_to_the_agent`: `retry_reason(HARNESS_BROKEN, "x", {}, False) == "x"`.
- [ ] **Step 2:** rodar; esperado: FAIL.
- [ ] **Step 3:** em `evaluate_harness`, logo depois de calcular `target`, rodar `concrete_replay` sem sementes sobre o harness inteiro. Se `status == "other_failure"` e `raised_at` estiver fora de `target.lineno..target.end_lineno`, devolver `HARNESS_BROKEN` com o motivo `"under CPython, harness.py raises {exception_type} at line {raised_at}, outside {function}: fix the stub or the driver"`. Gravar o replay em `result["smoke"]`.
- [ ] **Step 4:** rodar; esperado: PASS.
- [ ] **Step 5:** commit.

### Tarefa 3: Limite próprio para os laços da biblioteca de strings do ESBMC

**Files:**
- Modify: `src/research_pipeline/verify/esbmc_run.py` (`check`)
- Test: `tests/test_verify_esbmc_run.py`

**Interfaces:**
- Produces: `LIBRARY_UNWIND = 64`; `library_loops(show_loops: str, program: Path) -> list[str]`, que devolve `"função:índice"` para cada laço cujo arquivo não é `program`; `how["library_unwind"] = 64` quando usado.

- [ ] **Step 1: testes que falham**
  - `test_library_loops_parses_show_loops`: com o trecho de `--show-loops` medido em 28/10 (`goto-loop Loop 3 (strlen:0):` seguido de ` file /esbmc-vfs/libc/library/string.c ...`, e um laço do próprio programa), devolve só os da biblioteca.
  - `test_unwinding_only_in_library_raises_only_library_loops`: runner falso cuja 1a leitura é `artifact` com `violated_files` só de biblioteca; a 2a chamada recebe `--unwindsetname` com `:64` em cada laço e mantém `--unwind` no limite original.
  - `test_unwinding_in_the_program_keeps_the_global_escalation`: um arquivo de `violated_files` é o programa; o fluxo dobra o limite como hoje.
- [ ] **Step 2:** rodar; esperado: FAIL.
- [ ] **Step 3:** em `check`, antes da escalada `bound * 2`, quando `only_unwinding(reading)` e todo arquivo de `violated_files` difere de `path`, rodar `--show-loops` uma vez, montar `--unwindsetname` e repetir com o limite original. A leitura nova só substitui a anterior se for um veredito, como no resto de `check`.
- [ ] **Step 4:** rodar; esperado: PASS. Conferir à mão no harness `artifacts/v2/tarefa10-passo4-2026-10-28/cases/9aa2441c21d5/harness.py`; em 28/10 os laços da biblioteca passaram e sobrou o laço 17 do harness (linha 7).
- [ ] **Step 5:** commit.

### Tarefa 4: Controle com a versão corrigida no script do braço de agente

**Files:**
- Modify: `scripts/v2_agent_arm.py`
- Test: `tests/test_v2_agent_arm_script.py`

**Interfaces:**
- Consumes: `run_agent_arm(..., fixed_path: Path | None)` (já existe; dá `FIXED_ALSO_FAILS`).
- Produces: flag `--fixed-sources` (padrão `dataset/bugs_reais/arquivo_corrigido`); `"fixed_sources"` em `variant` e em `COMPARED_FIELDS`.

- [ ] **Step 1: testes que falham**
  - `test_fixed_source_reaches_the_arm`: com um arquivo de mesmo nome em `--fixed-sources`, a chamada gravada pela fixture `calls` recebe `fixed_path` apontando para ele.
  - `test_missing_fixed_source_runs_without_control`: sem o arquivo, `fixed_path` é `None` e o resultado tem `"fixed_control": "missing"`.
- [ ] **Step 2:** rodar; esperado: FAIL.
- [ ] **Step 3:** passar `fixed_path = Path(args.fixed_sources) / Path(h.file).name` quando existir, como `scripts/v2_orchestrate.py:85` já faz.
- [ ] **Step 4:** rodar; esperado: PASS.
- [ ] **Step 5:** commit.

### Tarefa 5: Pytest a partir do replay e relatório da rodada

**Files:**
- Create: `src/research_pipeline/verify/run_report.py`
- Create: `scripts/v2_run_report.py`
- Modify: `src/research_pipeline/verify/agent_arm.py` (fallback do pytest)
- Test: `tests/test_verify_run_report.py`

**Interfaces:**
- Consumes: `result["pytest"]` (`status`, `path`, `reason`), `result["replay"]` (`inputs`, `exception_type`, `line`), `levels.limit_group(verdict, reason)`.
- Produces: `replay_pytest(harness: str, function: str, replay: dict) -> str | None`, que escreve um teste que injeta as entradas do replay no lugar dos `nondet_*` e espera `pytest.raises(<exception_type>)`; `render_run_report(results: list[dict]) -> str`.

- [ ] **Step 1: testes que falham**
  - `test_replay_pytest_fails_on_the_buggy_harness`: para o harness `DIV` com entradas `[1, 0]`, o teste gerado passa (o `ZeroDivisionError` acontece).
  - `test_replay_pytest_is_none_without_inputs`.
  - `test_report_lists_confirmed_first_with_their_test`: a 1a seção é "Confirmados" e mostra o caminho do pytest.
  - `test_report_counts_false_positives`: `FIXED_ALSO_FAILS` e `BEHAVIOUR_CHANGED` entram em "Falsos positivos", logo depois dos confirmados.
  - `test_report_groups_llm_suspicions_by_limit`: `UNSUPPORTED` e `BOUND_INCONCLUSIVE` aparecem em "Suspeitas do LLM", agrupados pelo grupo de `limit_group`, com o motivo.
- [ ] **Step 2:** rodar; esperado: FAIL.
- [ ] **Step 3:** implementar. Em `evaluate_harness`, quando o veredito é `CONFIRMED` e o pytest do ESBMC sai `not_generated`, gravar o de `replay_pytest` em `case_dir/test_replay.py`, rodá-lo e registrar em `result["pytest"]` com `"route": "replay"`. `scripts/v2_run_report.py <pasta>` escreve `<pasta>/relatorio.md`.
- [ ] **Step 4:** rodar; esperado: PASS. Gerar o relatório da rodada de 28/10 e conferir à mão o caso `nm_real_23`.
- [ ] **Step 5:** commit.

### Tarefa 6: Registro

**Files:**
- Modify: `docs/experimentos/README.md`

- [ ] **Step 1:** registrar a rodada S2 de 28/10 (1a medição, sem controle da versão corrigida, com a mistura de código no meio da rodada) e a taxa de JSON inválido medida em 28/10: 0 em 1.080 chamadas de detecção do `claude_cli`, pela `llm_telemetry.json` das pastas `artifacts/v2/det-*`.
- [ ] **Step 2:** commit.
