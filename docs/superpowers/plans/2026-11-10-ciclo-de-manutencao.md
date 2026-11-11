# Ciclo de manutenção do pipeline: plano de implementação

> **Para quem for executar:** usar superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans, tarefa por tarefa. Os passos usam caixas `- [ ]`.

**Objetivo:** depois de cada scan ou de cada ESBMC novo, um comando local mostra o que mudou nos limites conhecidos, agrupa as recusas novas, aprende tempos e guarda propostas de melhoria em quarentena até passarem num portão automático, sem gastar token de LLM e sem alterar o pipeline sozinho.

**Arquitetura:** pacote novo `src/research_pipeline/maintenance/` com um módulo por responsabilidade (limites, recusas, tempos, propostas, portão) e um comando `scripts/maintenance.py`. Tudo lê arquivos que o pipeline já grava (`scan_report.json`, `possiveis_problemas/*.py`, relatórios do motor verify) e reaproveita `scripts/v2_replay_specs.py`, que refaz uma rodada com as especificações já dadas pela LLM, sem chamada nova.

**Tecnologias:** Python 3.12, pytest, `gh` (busca de issues, injetável nos testes), ESBMC 8.6.0 do build em `~/esbmc-master/build-bw`.

**Desenho de origem:** conversa de 10/11/2026 com a Fernanda (auto-incrementável, sem perder tempo ajeitando, LLM ajuda mas com trava) e `docs/projeto/proposta_veredito_estado_alcancavel_2026-11-10.md`.

## Restrições globais

- Nenhuma chamada de LLM no comando de manutenção. A LLM só aparece como **autora de proposta** (Tarefa 4), e a proposta nunca é aplicada sem passar pelo portão.
- Mudança em **código do pipeline** nunca é aplicada sozinha: o portão só devolve ACEITA ou REJEITADA, quem aplica é a Fernanda.
- Sem commit sem pedido dela. Sem branch nova (padrão `master`; hoje o repositório está em `feat/harness-de-agente`).
- Flags do ESBMC dos limites, copiadas de `possiveis_problemas/README.md`: `--unwind 5 --multi-property --no-pointer-check --no-align-check`; o caso `12_*` usa `--incremental-bmc --max-k-step 5 --multi-property`. `--no-bounds-check` e `--no-unwinding-assertions` ficam proibidos.
- Textos de relatório em português simples, sem travessão, sem caminho de arquivo nos relatórios que irão ao orientador.
- Todo relatório grava a identidade do ESBMC (`esbmc_identity`) e a impressão digital do pipeline (Tarefa 6), para qualquer número ser reproduzível.

## Fora de escopo

- A trava nas lições automáticas (consulta de versão virando lição) já tem código e teste não commitados (`verify/lessons.py`, `tests/test_verify_auto_lesson_guard.py`). Este plano não o refaz: só pede revisão da Fernanda antes de commitar.
- Corrigir o harness (dict de `**kwargs`, objetos Spark e boto3). Isso é trabalho depois da entrega da matéria.

## Foco de revisão (falhas prováveis que o desenho implica)

- ESBMC ausente ou com versão que não responde: o comando deve dizer isso e parar, sem comparar contra a linha de base como se nada tivesse mudado.
- Linha de base inexistente (primeira execução): grava a base e diz que não há comparação.
- Limite que passou de recusa para "SUCCESSFUL": não declarar "corrigido" sozinho, porque o veredito pode estar errado. Listar como "mudou, conferir".
- `scan_report.json` de modelos diferentes misturados: o relatório de recusas separa por modelo.
- Mensagem de recusa com caminhos e números: a assinatura normalizada não pode tratar duas mensagens iguais como diferentes.
- Proposta de lição com a mesma chave de uma já aceita: não duplicar.

---

### Tarefa 0: Literatura antes de fechar o portão

**Arquivos:**
- Criar: `docs/projeto/literatura_auto_melhoria.md`

**Entrega:** notas de leitura (1 página) sobre agentes que se auto-aperfeiçoam com avaliação e sobre sobreajuste ao conjunto de avaliação, com fonte ao lado de cada ideia.

- [ ] **Passo 1:** buscar 5 a 8 trabalhos recentes sobre auto-aperfeiçoamento de agentes de código e de pipelines com LLM, e sobre vazamento ou sobreajuste ao conjunto usado para decidir mudanças.
- [ ] **Passo 2:** verificar cada citação com o agente `citation-verifier` (título, autores, ano, DOI, e se o resumo apoia a afirmação). Descartar o que vier AMBÍGUO, NÃO ENCONTRADO ou ARTIGO ERRADO.
- [ ] **Passo 3:** escrever as notas dizendo o que cada fonte sugere para o portão da Tarefa 5. A decisão final do desenho é da Fernanda; a Tarefa 5 só começa depois que ela ler.

---

### Tarefa 1: Regressão dos limites conhecidos

**Arquivos:**
- Criar: `src/research_pipeline/maintenance/__init__.py`, `src/research_pipeline/maintenance/limits.py`
- Criar: `docs/projeto/possiveis_problemas/baseline.json` (gerado na primeira execução)
- Testar: `tests/test_maintenance_limits.py`

**Interfaces:**
- Produz: `run_limits(esbmc_command: list[str], limits_dir: Path, *, runner: Runner | None = None, timeout_seconds: int = 300) -> dict[str, dict]`, uma entrada por `[0-9]*.py`, com `outcome` em `{"successful", "failed", "refused", "crash", "timeout"}` e `detail` (primeira mensagem de erro ou propriedade violada).
- Produz: `diff_outcomes(old: dict[str, dict], new: dict[str, dict]) -> dict[str, list[str]]` com as chaves `changed`, `unchanged`, `added`, `removed`.
- Consome: `Runner` e a execução de ESBMC de `verify/esbmc_run.py`; `esbmc_identity` de `verify/capabilities.py`.

- [ ] **Passo 1:** escrever o teste `test_crash_is_classified_apart_from_refusal`: saída com `ESBMC caught SIGSEGV` vira `crash`; `ERROR: ... not supported` vira `refused`; `VERIFICATION SUCCESSFUL` vira `successful`; estouro de tempo vira `timeout`.
- [ ] **Passo 2:** escrever `test_diff_reports_a_refusal_that_became_successful_as_changed_not_fixed` com um corpo fixo de dois casos; afirmar que o relatório diz "mudou, conferir" e nunca "corrigido".
- [ ] **Passo 3:** escrever `test_missing_baseline_writes_it_and_compares_nothing`.
- [ ] **Passo 4:** rodar `pytest tests/test_maintenance_limits.py -v`; esperado: FALHA (módulo não existe).
- [ ] **Passo 5:** implementar `limits.py`; a classificação usa as mesmas expressões de `verify/levels.py` (`_CRASH`, `_LANGUAGE`) em vez de duplicá-las; o caso `12_*` usa as flags próprias.
- [ ] **Passo 6:** rodar o teste; esperado: PASSA. Depois rodar uma vez de verdade contra o ESBMC do build local e conferir que a tabela bate com a do README (situação em `822227ff96`).

---

### Tarefa 2: Triagem das recusas novas

**Arquivos:**
- Criar: `src/research_pipeline/maintenance/refusals.py`
- Criar: `docs/projeto/possiveis_problemas/registro.json` (assinatura → issue, estado, arquivo reprodutor)
- Testar: `tests/test_maintenance_refusals.py`

**Interfaces:**
- Produz: `normalize_reason(reason: str) -> str` (tira caminhos, números de linha, identificadores de hipótese e nomes de variável do usuário; mantém o texto fixo do ESBMC).
- Produz: `triage(reports: list[Path], registry: dict[str, dict], search: Callable[[str], list[dict]] | None = None) -> dict` com `known`, `new` (cada um com assinatura, contagem, funções afetadas, modelo e caminho do programa) e `by_model`.
- Consome: `limit_group` de `verify/levels.py` para ignorar o que não é limite do ESBMC (`OTHER`, rede, localização).

- [ ] **Passo 1:** escrever `test_same_refusal_with_different_paths_and_lines_has_one_signature` usando as duas mensagens `ERROR: TypeError at ...programs/232b413943df_a2.py 227: list indices must be integers...` e a variante com outro hash e linha.
- [ ] **Passo 2:** escrever `test_known_signature_is_not_new` e `test_new_signature_keeps_the_program_and_runs_the_search_once`.
- [ ] **Passo 3:** escrever `test_reports_from_different_models_are_not_merged`.
- [ ] **Passo 4:** rodar o arquivo de teste; esperado: FALHA.
- [ ] **Passo 5:** implementar `refusals.py`; a busca em issues é a função injetada `search` (o comando de verdade passa uma que chama `gh issue list --repo esbmc/esbmc --state all --search ...`; nos testes é um objeto falso). Resultado de busca é sugestão: o relatório diz "possível issue existente", nunca "duplicata".
- [ ] **Passo 6:** rodar o teste; esperado: PASSA. Rodar sobre `scan_report.json` do pyserial e do cost-explorer e conferir que os 5 `from_url` caem numa assinatura só.

---

### Tarefa 3: Tempos por função (só medir)

**Arquivos:**
- Criar: `src/research_pipeline/maintenance/timing.py`
- Testar: `tests/test_maintenance_timing.py`

**Interfaces:**
- Produz: `collect_timings(reports: list[Path]) -> list[dict]` com `function`, `bound`, `seconds`, `verdict`, `model`; e `summarize(rows) -> dict` com a taxa de estouro de tempo por faixa de bound.
- Não aplica nada: o relatório só diz se vale a pena aprender o bound inicial.

- [ ] **Passo 1:** conferir antes onde o `scan_report.json` guarda o bound e o tempo por tentativa (`results[].attempts[]` e `results[].seconds`). Se faltar o bound, registrar a lacuna no relatório em vez de inventar.
- [ ] **Passo 2:** escrever `test_rows_without_a_bound_are_counted_as_missing_not_zero`.
- [ ] **Passo 3:** rodar; esperado: FALHA. Implementar; rodar; esperado: PASSA.

---

### Tarefa 4: Quarentena de propostas

**Arquivos:**
- Criar: `src/research_pipeline/maintenance/proposals.py`
- Criar: pasta `docs/projeto/quarentena/` (uma subpasta por proposta)
- Testar: `tests/test_maintenance_proposals.py`

**Interfaces:**
- Produz: `add_proposal(kind: str, title: str, evidence: dict, root: Path, *, author: str) -> str` (devolve o id); `kind` em `{"licao", "regra_compat", "issue", "codigo"}`; `evidence` exige `program` e `origin` (rodada e caso).
- Produz: `list_proposals(root: Path) -> list[dict]` e `set_status(root, proposal_id, status)` com `status` em `{"quarentena", "aceita", "rejeitada"}`.
- Regra: `kind == "codigo"` nunca chega a `aceita` sem campo `aprovada_por`.

- [ ] **Passo 1:** escrever `test_proposal_without_program_or_origin_is_refused`.
- [ ] **Passo 2:** escrever `test_code_proposal_cannot_be_accepted_without_a_human_approval`.
- [ ] **Passo 3:** escrever `test_duplicate_proposal_by_evidence_hash_is_not_added_twice`.
- [ ] **Passo 4:** rodar; esperado: FALHA. Implementar; rodar; esperado: PASSA.

---

### Tarefa 5: Portão automático

**Arquivos:**
- Criar: `src/research_pipeline/maintenance/gate.py`
- Testar: `tests/test_maintenance_gate.py`

**Interfaces:**
- Consome: `resolve_rules` de `verify/capabilities.py` (sondas), `scripts/v2_replay_specs.py` (reaplicar as especificações já gravadas), a rodada de referência `artifacts/pgene601/rodada-final-2026-11-09`.
- Produz: `run_gate(reference_report: Path, *, esbmc_command: list[str], runner=None, replay=None, suite=None) -> dict` com `verdict` em `{"ACEITA", "REJEITADA"}` e os três números lado a lado (antes e depois): **bugs confirmados pela função** (métrica principal, vem primeiro), sondas aceitas, testes aprovados.
- Critério: `REJEITADA` se os confirmados com gabarito caírem, ou se alguma sonda piorar, ou se a suíte tiver falha nova. Empate ou ganho: `ACEITA`.
- Para evitar sobreajuste, o portão também recebe `holdout`: um conjunto de bugs que **não** foi usado para escrever a proposta; sem `holdout` o relatório diz que o resultado está dentro da amostra.

- [ ] **Passo 1:** escrever `test_gate_rejects_when_confirmed_bugs_drop_even_if_probes_improve` com resultados injetados (`replay` e `suite` falsos).
- [ ] **Passo 2:** escrever `test_gate_reports_the_main_metric_before_the_intermediate_ones`.
- [ ] **Passo 3:** escrever `test_gate_says_in_sample_when_no_holdout_is_given`.
- [ ] **Passo 4:** rodar; esperado: FALHA. Implementar (as chamadas reais ficam atrás dos parâmetros injetáveis); rodar; esperado: PASSA.
- [ ] **Passo 5:** rodar o portão uma vez de verdade, sem mudança nenhuma, e conferir que devolve ACEITA com os mesmos 14 confirmados pela função da rodada de 09/11. Se não reproduzir 14, parar e investigar antes de seguir (a impressão digital ou o ESBMC mudou).

---

### Tarefa 6: Comando único e impressão digital

**Arquivos:**
- Criar: `scripts/maintenance.py`, `src/research_pipeline/maintenance/fingerprint.py`
- Modificar: `docs/experimentos/README.md` (entrada de como rodar e o que cada subcomando grava)
- Testar: `tests/test_maintenance_cli.py`

**Interfaces:**
- Produz: `pipeline_fingerprint(root: Path) -> dict` com `git_commit`, `dirty` (true se há alteração não commitada), `notebook_version` (de `verify/lessons.notebook_version`), `rules` (conjunto ativo, de `resolve_rules`), `esbmc_identity`.
- Subcomandos: `limits`, `refusals <scan_report...>`, `timing <report...>`, `proposals {add,list,status}`, `gate <relatório_de_referência>`.
- Cada subcomando grava `manutencao_AAAA-MM-DD/<subcomando>.json` e `.md` com a impressão digital no topo.

- [ ] **Passo 1:** escrever `test_every_report_starts_with_the_fingerprint_and_says_when_the_tree_is_dirty`.
- [ ] **Passo 2:** escrever `test_missing_esbmc_stops_with_a_clear_message_and_exit_code_1`.
- [ ] **Passo 3:** rodar; esperado: FALHA. Implementar; rodar; esperado: PASSA.
- [ ] **Passo 4:** rodar `python scripts/maintenance.py limits` e `python scripts/maintenance.py refusals /mnt/e/scan_amazon/*/scan_report.json` e anexar a saída ao README de experimentos como primeira rodada registrada.

---

## Conferência do plano

- **Cobertura do pedido:** limites que o ESBMC corrige (T1), triagem do trabalho manual das recusas (T2), timeout (T3, só medição), LLM sugere e não aplica (T4 e T5), reprodutibilidade (T6). A trava das lições está fora, já feita.
- **Sem token:** nenhuma tarefa chama LLM. O replay das especificações já gravadas é local.
- **Dado que falta:** a Tarefa 3 depende de o relatório guardar o bound por tentativa; o Passo 1 dela confere isso antes de qualquer código.
- **Decisões que são da Fernanda:** ler a Tarefa 0 antes da 5; aprovar toda proposta do tipo `codigo`; decidir se a manutenção entra antes ou depois da entrega da matéria.
