# Harness genérico com reescrita validada — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** permitir reescrita de compatibilidade proposta pela LLM sem confundir uma violação na reescrita com um bug confirmado no código Python original.

**Architecture:** o código original continua sendo a primeira tentativa. Um diagnóstico de capacidade alimenta uma proposta estruturada de reescrita; portões AST/escopo, replay diferencial isolado e atribuição de propriedade decidem o tier de evidência. A orquestração e o avaliador mantêm `confirmed_original`, `rewrite_violation_empirical`, `rewrite_rejected` e `inconclusive` separados.

**Tech Stack:** Python 3.12, `ast`, pytest, ESBMC-Python 8.5.0; runtime de contêiner local configurável para replay (sem download automático); API LLM somente em testes/rodadas opt-in.

**Spec:** `DESENHO_HARNESS_GENERICO.md` (raiz do repositório).

## Estado e ponto de retomada

- Especificação genérica revisada e aprovada pela usuária; execução direta na
  `master` também foi aprovada.
- Branch atual: `master`. Existem alterações não commitadas do piloto anterior
  em `scan/pipeline.py`, `verification/esbmc_runner.py`,
  `tests/test_research_pipeline.py`, `scan/prepared_body.py` e
  `tests/test_prepared_real_body.py`. Existem também
  `scan/contract.py` e `tests/test_harness_contract.py` não rastreados;
  preservar ambos e confirmar sua autoria antes de editá-los.
- `PLANO_IMPLEMENTACAO_HARNESS.md` documenta o piloto específico e está
  marcado como histórico. Não retomar sua rodada dos 18 antes da Task 8.
- Task 1 concluída em código/testes (2026-09-28). O teste RED mostrou que o
  piloto era promovido automaticamente; o acoplamento foi retirado e o teste
  direto de `dz_real_02` foi preservado. Suíte focada: 43/43; completa: 435
  passaram, 2 live-LLM excluídos. Commit não feito: `.git` é read-only neste
  ambiente. Nenhuma API chamada.
- Task 2 concluída em código/testes (2026-09-28). Diagnóstico conservador por
  tipo de falha e captura de stdout/stderr/log parcial em timeout. Suíte focada:
  67 passed, 2 deselected. Commit não feito pela mesma restrição de `.git`.
- Task 3 concluída em código/testes (2026-09-28). O contrato JSON, prompt
  específico e método `synthesize_rewrite` foram implementados; backend foi
  simulado, sem API. Suíte focada: 20 passed; completa: 450 passed, 2
  deselected. Commit não feito pela restrição de `.git`.
- Task 4 concluída em código/testes (2026-09-28). Portão implementado para
  reconstrução pelo manifesto, expressão suspeita única, controle/precondição,
  nomes globais, asserts, nondet e oráculos. O `risk` distingue mudanças só de
  anotação de mudanças semânticas. Suíte focada: 36 passed; completa: 458
  passed, 2 deselected. Commit não feito pela restrição de `.git`.
- Revisão de 2026-09-29: a suíte encontrada tinha 470 passed, 2 failed e 2
  deselected. Os testes anteriores não validavam a integração runner/witness.
  Task 4 e Task 5 precisam de correções antes da integração E2E; os resultados
  históricos acima não significam validação semântica completa.
- Correção inicial de 2026-09-29: o runner preserva registros e entradas por
  propriedade sem alterar os campos legados. Witness reconhece os nomes reais
  ZeroDivisionError/IndexError e a categoria out_of_bounds. Replay distingue
  load/resolve/call e registra arquivo, função, linha e coluna da exceção.
  A confirmação exige coincidência com a operação original; resumo sem trace,
  localização ausente, inputs ambíguos e estado de objeto não reconstruído não
  confirmam. Métodos permanecem sem atribuição até existir contrato de estado.
- Verificação dessa correção: 23 testes novos/reformulados falharam antes da
  implementação; 89 passed, 2 deselected na suíte focada e 488 passed, 2
  deselected na suíte completa da cópia de validação. Após mudança de ambiente
  apagar /tmp, o patch foi reconstruído em
  `/mnt/c/users/ferna/esbmc/build/llm-esbmc-fix-EgYzsn` e a suíte completa voltou
  a passar (488 passed, 2 deselected, 18.32 s). Inclui ESBMC real e worker real
  sobre fixtures sintéticas controladas, sem API. Execução isolada de produção
  ainda não foi validada em contêiner.
- Fechamento de 2026-09-29 (Claude, sem API, sem commit):
  - Runner: cada propriedade violada guarda linha, coluna e atribuições com a
    função do estado (`assignments`). O estágio roda o ESBMC com `--no-slice`,
    senão entradas irrelevantes para a propriedade somem e teriam de ser
    adivinhadas.
  - Witness: entrada reconstruída pela chamada única do driver ao alvo
    (locais nondet do `main` ou literais); argumento calculado fica
    `rewrite_only`. Método com violação na linha suspeita vira `rewrite_only`
    (antes `unattributed`), pois a propriedade foi atribuída na reescrita.
  - Portão: expressão suspeita de qualquer tipo (subscrito, atributo); posição
    no controle comparada por caminho (if/while/IfExp/BoolOp/try/laço);
    chamada de método por instância (`C().m()` ou `obj = C(); obj.m()`);
    nondet pode passar por local atribuído uma vez; `raise` sem argumento não
    derruba mais o portão.
  - Replay: retorno com tipo (1, 1.0, True, lista e tupla diferem) e estado
    dos argumentos após a chamada; casos de borda derivados das anotações,
    somados aos casos da LLM; `UnavailableReplayExecutor` quando não há
    contêiner.
  - Prompt: recebe o "módulo de contexto" (`scan/context.py`: alvo e
    definições de topo alcançadas por nome, sem efeitos colaterais de topo),
    que também é o "original" do portão, do replay e da testemunha.
  - Task 7 e Task 8 implementadas (ver abaixo). Suíte: 550 passed,
    2 deselected. Docker não está integrado ao WSL nesta máquina, então o
    replay real ainda não foi exercitado em contêiner.
- Revisão (code-reviewer) do mesmo dia achou e foram corrigidos com teste:
  contexto que descartava escrita de topo em nome mantido (`D = 0; D += 4`
  fabricava `confirmed_original`), agora recusa o contexto; driver que
  redefinia nomes do módulo, agora só `def main()` + `main()`; tier empírico
  apoiado só em entradas da LLM, agora exige caso de borda independente;
  exceção de outro tipo no original vira `unattributed`, não `contradicted`;
  tokens de resposta malformada passam a contar. A baseline offline usa a
  localização do manifesto (`candidate_source: oracle_localized`).
- Próxima ação: habilitar integração WSL do Docker Desktop, construir imagem
  Python local, validar `ContainerReplayExecutor` com um caso trivial e só
  então aprovar teto de custo para a rodada live com `--rewrite-mode validated`.

## Global Constraints

- Trabalhar na branch `master`, como a usuária pediu; preservar alterações existentes e não incluir arquivos alheios em commits.
- Antes de cada commit, inspecionar `git diff --cached`; para arquivos já sujos no início, usar staging por hunk (`git add -p`) quando necessário. Se a sandbox bloquear escrita em `.git`, registrar a limitação e não solicitar permissão ampla para contorná-la.
- Nenhuma lógica de produção pode ler `dataset/*/bugs/` ou gabarito para gerar prompt, entradas ou contrato. `detection/` é a entrada da avaliação.
- Sem replay de Python de produção/LLM no processo do pipeline ou em subprocesso comum. Runtime isolado ausente ⇒ `inconclusive`, nunca aprovação implícita.
- Teste diferencial finito é filtro empírico, não prova de equivalência. Resultado na reescrita não herda tier de código original.
- Sem API no pytest padrão; rodada paga só após teto de custo/chamadas aprovado separadamente.
- Timeout, erro de frontend e zero VCCs não são segurança nem confirmação.
- O piloto `prepared_body.py` fica fora do caminho padrão; pode permanecer como fixture experimental sem acionar classificações E2E.

## Review Focus

Os testes abaixo devem cobrir também estas entradas, que tendem a escapar em exemplos simples:

1. Arquivo com imports/efeitos no topo: replay não pode executar no host; Task 5 testa runtime ausente e isolamento.
2. Método que depende de `self`/construtor: entrada ou testemunha não concretizável fica inconclusiva; Tasks 5 e 6 testam.
3. Duas ocorrências idênticas da expressão suspeita: mapeamento ambíguo não pode confirmar; Task 4 testa.
4. Saída ESBMC com `TypeError` PASSED e outra propriedade FAILED: diagnóstico e atribuição usam a violação real; Tasks 2 e 6 testam.
5. Reescrita que passa em entradas finitas mas muda um ramo não amostrado: nunca recebe `confirmed_original` sem replay da testemunha; Tasks 6 e 7 testam.

---

### Task 1: Retirar o piloto específico do fluxo padrão e preservar a semântica dos relatórios existentes

**Files:** Modify `src/research_pipeline/scan/pipeline.py`; modify `tests/test_prepared_real_body.py`; test `tests/test_scan_pipeline.py`.

**Interfaces:** Consumes `run_pipeline_scan(...)`, `ScanCaseResult`; produces fluxo padrão sem `_try_prepared_real_body` e testes diretos do piloto preservados. Não alterar os valores históricos de `classification` nesta tarefa.

- [x] **Step 0: Medir baseline.** Observed: 436 passed, 2 deselected.
- [x] **Step 1: Escrever teste falhando.** `test_scan_does_not_promote_shape_specific_preparation` usa forma que satisfazia o piloto.
- [x] **Step 2: Verificar RED.** Falhou como esperado: o piloto era promovido sem chamar o sintetizador (`calls == 0`).
- [x] **Step 3: Implementar.** Removida a chamada e helpers de atribuição de `_try_prepared_real_body` do pipeline. Experimento e teste direto permanecem fora do fluxo padrão.
- [x] **Step 4: Verificar GREEN e regressão.** Suíte focada: 43 passed; completa: 435 passed, 2 deselected.
- [ ] **Step 5: Commit seletivo.** `git add src/research_pipeline/scan/pipeline.py tests/test_prepared_real_body.py tests/test_scan_pipeline.py`; `git commit -m "refactor: isolate shape-specific harness pilot"`.

### Task 2: Diagnóstico de capacidade do ESBMC, sem gabarito

**Files:** Create `src/research_pipeline/scan/capability.py`; modify `src/research_pipeline/verification/esbmc_runner.py`; test `tests/test_scan_capability.py`.

**Interfaces:** Produces `CapabilityDiagnostic(kind: str, message: str, source_line: int | None, raw_log_path: str)` e `diagnose_esbmc(status: str, stdout: str, stderr: str, raw_log_path: str = "") -> CapabilityDiagnostic`. Kinds: `method_entry`, `import`, `annotation`, `builtin`, `generator`, `container`, `timeout`, `unknown`. Task 3 consome o diagnóstico.

- [x] **Step 1: Escrever testes falhando.** Cobertos método de entrada, builtin, generator, timeout, TypeError listado como PASSED e erro desconhecido.
- [x] **Step 2: Verificar RED.** Import ausente observado; depois os testes detectaram TypeError PASSED escolhido como mensagem e uma asserção de teste defeituosa, corrigidos com evidência.
- [x] **Step 3: Implementar.** Diagnóstico conservador; preserva stdout/stderr/log parcial nos dois runners ao estourar timeout.
- [x] **Step 4: Verificar GREEN.** `tests/test_scan_capability.py tests/test_research_pipeline.py`: 67 passed, 2 deselected.
- [ ] **Step 5: Commit seletivo.** `git add src/research_pipeline/scan/capability.py src/research_pipeline/verification/esbmc_runner.py tests/test_scan_capability.py`; `git commit -m "feat: diagnose ESBMC Python compatibility failures"`.

### Task 3: Contrato estruturado para reescrita LLM

**Files:** Create `src/research_pipeline/scan/rewrite.py`; modify `src/research_pipeline/scan/synth.py`; create `src/research_pipeline/prompts/rewrite_prompt.txt`; test `tests/test_scan_rewrite_proposal.py`.

**Interfaces:** Consumes `CapabilityDiagnostic`. Produces `RewriteChange(before: str, after: str, reason: str)`, `RewriteProposal(rewritten_source: str, driver_source: str, changes: tuple[RewriteChange, ...], input_cases: tuple[dict, ...], assumptions: tuple[str, ...], oracle_ref: str | None)`, `parse_rewrite_proposal(raw: str) -> RewriteProposal`, e `HarnessSynthesizer.synthesize_rewrite(unit, finding, diagnostic, *, repair_feedback="") -> tuple[RewriteProposal, SynthResult]`. Proposta malformada lança `ValueError` categorizável; não vira harness vazio.

- [x] **Step 1: Escrever testes falhando.** JSON fiel/incompleto/inválido, prompt com diagnóstico/código e sem `fixed_behaviour`, truncamento explícito e backend falso com telemetria.
- [x] **Step 2: Verificar RED.** Import ausente observado antes da implementação.
- [x] **Step 3: Implementar.** Contrato estrito, prompt próprio, `synthesize_rewrite` e parser JSON usando os mesmos limites de contexto/telemetria.
- [x] **Step 4: Verificar GREEN.** Suíte focada: 20 passed; completa: 450 passed, 2 deselected.
- [ ] **Step 5: Commit seletivo.** `git add src/research_pipeline/scan/rewrite.py src/research_pipeline/scan/synth.py src/research_pipeline/prompts/rewrite_prompt.txt tests/test_scan_rewrite_proposal.py`; `git commit -m "feat: add structured compatibility rewrite proposal"`.

### Task 4: Portão estático de proveniência e propriedade

**Files:** Create `src/research_pipeline/scan/rewrite_guard.py`; test `tests/test_scan_rewrite_guard.py`; modify `src/research_pipeline/scan/compat.py` e `src/research_pipeline/scan/driver_check.py` apenas para reutilizar validadores puros existentes, sem enfraquecer os tiers antigos.

**Interfaces:** Consumes `RewriteProposal`. Produces `GuardReport(ok: bool, reasons: tuple[str, ...], suspect_rewrite_line: int | None)` e `validate_rewrite(original_source: str, proposal: RewriteProposal, *, function: str, expression: str, category: str, trusted_oracle: str | None = None) -> GuardReport`. `trusted_oracle` vem de configuração explícita do usuário, nunca da LLM.

- [x] **Step 1: Escrever testes falhando.** Oito casos cobrindo normalização fiel, mudança não declarada, expressão removida/duplicada, nondet/assert, nome indefinido, precondição e oracle claim.
- [x] **Step 2: Verificar RED.** Import ausente observado antes da implementação.
- [x] **Step 3: Implementar.** Reconstrução AST via manifesto, preservação da expressão e controle, validação de nomes/driver/assert/nondet/oracle; risk distingue anotação de mudança semântica.
- [x] **Step 4: Verificar GREEN.** Focada: 36 passed; completa: 458 passed, 2 deselected.
- [ ] **Step 5: Commit seletivo.** `git add src/research_pipeline/scan/rewrite_guard.py tests/test_scan_rewrite_guard.py src/research_pipeline/scan/compat.py src/research_pipeline/scan/driver_check.py`; `git commit -m "feat: validate rewrite provenance and bug grounding"`.

### Task 5: Replay diferencial isolado e seguro

**Files:** Create `src/research_pipeline/scan/replay.py`; create `src/research_pipeline/scan/replay_worker.py`; test `tests/test_scan_replay.py`.

**Interfaces:** Produces `ReplayCase(args: tuple, kwargs: dict)`, `ReplayOutcome(kind: str, value: object | None, exception_type: str, exception_message: str, effects: dict)`, `ReplayReport(status: str, compared: int, divergences: tuple[str, ...])`, `ContainerReplayExecutor.run(source: str, function: str, case: ReplayCase) -> ReplayOutcome`, `compare_rewrite(original: str, rewritten: str, function: str, cases: tuple[ReplayCase, ...], executor) -> ReplayReport`. Status: `matched`, `diverged`, `unavailable`, `timeout`. Task 6 consome `ReplayCase` e `ReplayOutcome`.

- [x] **Step 1: Escrever testes falhando.** `test_equal_return_and_exception_match`, `test_changed_exception_diverges`, `test_runtime_missing_is_unavailable`, `test_import_side_effect_never_runs_on_host`, `test_constructor_without_json_entry_is_unavailable`, `test_container_command_has_no_network_and_read_only_mounts`, `test_timeout_is_not_match`, `test_independent_boundary_cases_are_added_to_llm_cases`. Testar comparação com executor em memória; testar construção do comando sem executar código não confiável no host.
- [x] **Step 2: Verificar RED.** Run: `PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/test_scan_replay.py`. Expected: FAIL por módulo ausente.
- [x] **Step 3: Implementar.** Runtime local configurado explicitamente (por exemplo Podman/Docker) e imagem Python já presente; nunca fazer pull automático. Comando em lista de argumentos, `--network none`, usuário não root, rootfs read-only, capacidades descartadas, `no-new-privileges`, limites de PID/memória/CPU/tempo, montagem mínima sem segredos. Worker serializa retorno/exceção/efeitos declarados; módulos/imports ou entradas não serializáveis ⇒ `unavailable`. Mesclar entradas da LLM com casos de borda/controle derivados deterministicamente da assinatura/AST, para que a LLM não escolha sozinha um conjunto que mascare divergência. Sem runtime isolado ⇒ não executar.
- [x] **Step 4: Verificar GREEN.** Run: `PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/test_scan_replay.py`. Expected: 0 falhas e nenhum código de produção executado no host.
- [ ] **Step 5: Commit seletivo.** `git add src/research_pipeline/scan/replay.py src/research_pipeline/scan/replay_worker.py tests/test_scan_replay.py`; `git commit -m "feat: add isolated differential replay gate"`.

### Task 6: Atribuir propriedade e testemunha ao original

**Files:** Create `src/research_pipeline/scan/witness.py`; modify `src/research_pipeline/verification/esbmc_runner.py`; test `tests/test_scan_witness.py`.

**Interfaces:** Consumes `GuardReport`, `ReplayCase`, `ReplayOutcome`, `ESBMCDirectResult.details`. Produces `WitnessAssessment(status: str, case: ReplayCase | None, reason: str)` e `assess_witness(details: dict, *, expected_category: str, rewritten_file: str, rewritten_line: int, original_source: str, function: str, executor, original_line: int | None = None, original_column: int | None = None) -> WitnessAssessment`. Status: `reproduced_original`, `rewrite_only`, `contradicted`, `unattributed`. Linha/coluna original ausentes impedem confirmação. Usar `details["violated_property_records"]`, com contraexemplo próprio por propriedade; os campos antigos continuam como resumo. `ReplayOutcome.phase` separa preparação de chamada, e `exception_location` guarda a origem da exceção (não participa da comparação diferencial de resultados). O parser de contraexemplo retorna `None` se faltar valor necessário ou houver atribuições repetidas; nunca escolhe um valor nondet por conta própria. Neste incremento, só entradas escalares de funções livres são reconstruídas; objetos exigem contrato próprio.

- [x] **Step 1: Escrever testes falhando.** `test_exact_native_property_and_line_replays_on_original`, `test_other_line_is_unattributed`, `test_passed_typeerror_does_not_hide_zero_division`, `test_incomplete_counterexample_is_rewrite_only`, `test_concrete_counterexample_contradicts_original`, `test_self_state_not_reconstructible_is_unattributed`, `test_wrong_category_is_unattributed`.
- [x] **Step 2: Verificar RED.** Run: `PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/test_scan_witness.py`. Expected: FAIL por módulo ausente.
- [x] **Step 3: Implementar.** Usar propriedade violada e seu arquivo/linha reais, não qualquer `VERIFICATION FAILED`; extrair valores concretos apenas de campos parseáveis; executar o mesmo caso no original pelo executor isolado. Para `incorrect_result`, aceitar somente `trusted_oracle` explicitamente configurado; caso contrário `unattributed`.
- [x] **Step 4: Verificar GREEN.** Run: `PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/test_scan_witness.py tests/test_research_pipeline.py`. Expected: 0 falhas.
- [ ] **Step 5: Commit seletivo.** `git add src/research_pipeline/scan/witness.py src/research_pipeline/verification/esbmc_runner.py tests/test_scan_witness.py`; `git commit -m "feat: replay verified witnesses on original Python"`.

### Task 7: Orquestração opt-in, artefatos e métricas honestas

**Files:** Create `src/research_pipeline/scan/rewrite_stage.py`; modify `src/research_pipeline/scan/pipeline.py`, `src/research_pipeline/v2_evaluator.py`, `src/main.py`; test `tests/test_scan_rewrite_e2e.py`, `tests/test_v2_evaluator.py`, `tests/test_main_v2.py`.

**Interfaces:** Consumes Tasks 2–6. Produces `run_rewrite_stage(candidate, unit, diagnostic, synthesizer, executor, esbmc_command, bound, timeout_seconds, output_dir) -> ScanCaseResult` e opção CLI `--rewrite-mode {off,validated}` (default `off`). `_try_native` e `_try_real_body_driver` mantêm retorno atual, mas aceitam `diagnostics: list[CapabilityDiagnostic] | None = None` para registrar falhas não conclusivas com stdout/stderr/log; o estágio recebe o diagnóstico mais informativo sem repetir chamada ESBMC. Adicionar classificações exatas `confirmed_original`, `rewrite_violation_empirical`, `rewrite_rejected`, `inconclusive`; `ScanCaseResult.to_dict/from_dict` preserva campos novos em checkpoint. Nunca mapear `rewrite_violation_empirical` para `is_real_body_confirmation`.

- [x] **Step 1: Escrever testes falhando.** `test_original_is_attempted_before_rewrite`, `test_rewrite_default_off_makes_no_new_api_call`, `test_guard_rejection_skips_esbmc`, `test_missing_replay_runtime_is_inconclusive`, `test_rewrite_only_counted_separately`, `test_concrete_original_replay_counts_as_confirmed_original`, `test_timeout_stays_inconclusive`, `test_checkpoint_roundtrip_keeps_evidence_and_artifacts`. Usar sintetizador determinístico fake, ESBMC real nos testes de integração pequenos quando cabível; sem credenciais.
- [x] **Step 2: Verificar RED.** Run: `PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/test_scan_rewrite_e2e.py tests/test_v2_evaluator.py tests/test_main_v2.py`. Expected: falhas nos novos testes por estágio/labels ausentes; testes antigos não são ignorados.
- [x] **Step 3: Implementar.** Inserir estágio após tentativas reais e antes do scalar fallback; converter `RewriteProposal.input_cases` validados em `ReplayCase`; limitar tentativas de reparo e preservar telemetria; salvar original, reescrita, diff, manifesto, replay e log ESBMC com hash e caminhos por candidato. Atualizar serializer/checkpoint, resumo CLI e avaliador sem reinterpretar relatórios legados. Definir retorno `rewrite_rejected`/`inconclusive` quando não houver evidência suficiente; não cair silenciosamente para `SAFE_DRIVER`.
- [x] **Step 4: Verificar GREEN e suíte completa.** Run: `PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider`. Expected: 0 falhas, testes live-LLM permanecem deselected; Run: `git diff --check`. Expected: exit 0.
- [ ] **Step 5: Commit seletivo.** `git add src/research_pipeline/scan/rewrite_stage.py src/research_pipeline/scan/pipeline.py src/research_pipeline/v2_evaluator.py src/main.py tests/test_scan_rewrite_e2e.py tests/test_v2_evaluator.py tests/test_main_v2.py`; `git commit -m "feat: integrate evidence-tiered compatibility rewrite"`.

### Task 8: Avaliação offline e portão de custo para rodada live

**Files:** Create `src/research_pipeline/scan/rewrite_eval.py`; create `tests/test_scan_rewrite_eval.py`; modify `PLANO_IMPLEMENTACAO_GENERICO.md` somente para registrar resultados, não para mudar critérios após vê-los.

**Interfaces:** Produces `evaluate_offline(candidates_path: str, detection_root: str, output_dir: str, *, per_case_timeout: int) -> dict` que não instancia backend LLM; registra por caso diagnóstico, tier, tempo, causa de recusa e log. A rodada live é comando separado e exige teto de chamadas/custo confirmado pela usuária.

- [x] **Step 1: Escrever testes falhando.** `test_offline_evaluation_never_reads_bug_harness`, `test_offline_evaluation_never_calls_llm`, `test_per_case_timeout_recorded_as_inconclusive`, `test_aggregate_keeps_original_and_rewrite_counts_separate`.
- [x] **Step 2: Verificar RED.** Run: `PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/test_scan_rewrite_eval.py`. Expected: FAIL por função ausente.
- [x] **Step 3: Implementar.** Ler somente manifesto/candidatos e arquivos `detection/`; produzir JSON por caso e resumo com configuração e hashes. Chamar apenas probes originais e diagnóstico, não o fallback de síntese (um fake que lança erro não é baseline sem LLM). Rodar os 18 elegíveis com limite explícito; se o sandbox impedir escrever na raiz, usar `/tmp` e registrar caminho. Não rodar 104 nem API nesta tarefa.
- [x] **Step 4: Verificar GREEN e resultados.** Run: `PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider`; Expected: 0 falhas. Run: `git diff --check`; Expected: exit 0. Conferir manualmente que os 18 registros existem e que nenhum item entrou por `bugs/`.
- [ ] **Step 5: Commit seletivo.** `git add src/research_pipeline/scan/rewrite_eval.py tests/test_scan_rewrite_eval.py PLANO_IMPLEMENTACAO_GENERICO.md`; `git commit -m "test: record offline compatibility baseline"`.

### Resultado da Task 8 (2026-09-29)

`outputs/rewrite_offline_2026-09-29/` (timeout 20 s, bound 5, ESBMC 8.5.0,
sem LLM). Nos 18 elegíveis, nenhuma tentativa no código original foi
conclusiva: 10 `method_entry`, 4 `dependency` (objeto/função de topo ausente),
1 `builtin` (formatação `%` não constante) e 3 `unknown`. Onze casos são
elegíveis para o estágio de reescrita (categoria com propriedade nativa e
expressão suspeita). O estágio não roda offline: exige LLM.

Desvios de interface em relação ao texto das tasks: `run_rewrite_stage`
devolve `RewriteStageResult` e o pipeline converte; `evaluate_offline` recebe
o manifesto (lê só `detection_file`, `function`, `categories`, `expression`).
Reescrita inconclusiva ou rejeitada não encerra o caso: segue para o fallback
escalar com `rewrite_status`/`rewrite_evidence` gravados no resultado.
`confirmed_original` conta como confirmação no corpo real no avaliador;
`rewrite_violation_empirical` aparece à parte (`rewrite_only` nas perdas).

## Handoff

Não iniciar a rodada paga sem aprovação separada do teto de custo. Após as Tasks 1–8, revisar o diff inteiro, classificar achados por risco e corrigir os importantes com teste RED→GREEN. O relatório final deve dizer quantos casos tiveram evidência no original, só na reescrita, rejeição ou inconclusão; nunca apresentar a soma como prova de equivalência.
