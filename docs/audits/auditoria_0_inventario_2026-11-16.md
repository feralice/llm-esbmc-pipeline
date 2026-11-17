# Auditoria 0: inventário científico do repositório (16/11/2026)

Documento de trabalho da Fernanda. Complementa `auditoria_pipeline_2026-11-16.md`, que tem a auditoria metodológica e estatística. Aqui o foco é **o que existe, onde está e em que estado**.

**Como foi feito.**
- Feito pelo Claude Code (Opus 5.5), só com leitura de arquivos, `git log` e contagens em memória com Python.
- Nenhum experimento, chamada de LLM ou alteração de código.
- Os testes **não foram executados**: o estado "testado" abaixo quer dizer "existe arquivo de teste", não "o teste passa agora". A última execução registrada é `CONGELAMENTO_2026-11-14.md`, com 2073 testes passando e 1 pulado em 14/11.
- A arquitetura do motor verify foi lida no código nesta sessão (em parte por um subagente, com conferência minha). Os módulos `grounding.py`, `spec.py`, `caller_facts.py`, `slicing.py` e `value_oracle.py` **não foram lidos inteiros**.

**Rótulos:** [F] fato verificado; [I] inferência; [H] hipótese; [NV] não verificado.

---

## 1. Mapa dos diretórios e arquivos relevantes

| Caminho | Conteúdo | Observação |
|---|---|---|
| `src/main.py` | ponto de entrada: `mode_v2` (l. 663), `_mode_v2_verify` (l. 403), `mode_scan` (l. 568), `mode_benchmark` (l. 332), `main` (l. 1100) | [F] |
| `src/research_pipeline/cli_args.py` | argumentos; perfis `rapido`, `padrao`, `medicao`, `congelado` (l. 34-40); modos `hybrid`, `benchmark`, `scan` (l. 82-83) | [F] |
| `src/research_pipeline/cli.py` | subcomando `llm-esbmc scan` | [F] |
| `src/research_pipeline/llm/` (16 arquivos) | prompts, variantes, roteamento, backends (7), telemetria, cache de detecção, política de falha, preço | [F] |
| `src/research_pipeline/prompts/` | `system_prompt_v2.txt`, `v2_variants/A*.txt`, `input_spec_prompt.txt`, `healing_prompt.txt` | [F] |
| `src/research_pipeline/verify/` (55 arquivos + `probes/` com 52) | motor de verificação: loop, render, compat, grounding, spec, ESBMC, replay, healing, níveis, relatório, agente | [F] |
| `src/research_pipeline/verification/` | `esbmc_runner.py` (leitura da saída do ESBMC) | [F] |
| `src/research_pipeline/scan/` (9 arquivos) | grafo de chamadas, contexto do repositório, pré-filtro, deduplicação, métricas do grafo | [F] |
| `src/research_pipeline/maintenance/` (10 arquivos) | lições automáticas, propostas, recusas, limites | [F] |
| `src/research_pipeline/v2_evaluator.py` | avaliação por expressão e por função (`evaluate_functions`, l. 292) | [F] |
| `src/research_pipeline/smells/`, `smell_policy.py` | métricas de code smell (V1) | [F] |
| `tests/` | 164 arquivos, 1653 funções `test_` (contagem por grep) | [F] |
| `scripts/` (79 arquivos) | construção de datasets, rodadas, agregação, tabelas | [F]; detalhe na seção 7 |
| `dataset/` | 6 conjuntos | seção 3 |
| `artifacts/` | saídas: `v2/` (240 entradas), `pgene601/` (29 rodadas), `cps/`, `scan*`, `esbmc_capabilities`, `flag_ablation_logs*` | [F] |
| `docs/experimentos/` | registro das rodadas (`README.md`, 1823 linhas), pastas `fase-1` a `fase-11`, versões do ESBMC, modelos e tokens | [F] |
| `docs/projeto/` | planos, regra de acerto, origem dos 47, handoffs, `possiveis_problemas/`, trabalhos relacionados | [F] |
| `docs/pgene601/` | candidatos e pré-seleção dos 47, sondas e mypy, proposta, `artigo/` | [F] |
| `docs/pgene601/artigo/` | `artigo.tex` (63 linhas, esqueleto), `mapa_dados.md`, `tabela_experimentos.md`, `tabela_scans.md` | [F] |
| `docs/desenho/`, `docs/esbmc/`, `docs/historico/`, `docs/escrita/` | desenho do motor, referência do frontend Python, histórico, diretrizes de escrita | [F] |
| `docs/audits/` | auditorias anteriores e estas | [F] |
| `extension/` | plugin do Claude Code, `/verify-repo` | [F] |
| `artigos_estudo/` | artigos convertidos para Markdown (ESBMC-Python, EVA, self-healing etc.) | [F] |
| `archive/` | V1, relatórios antigos, issues antigas | [F] |
| `kbs2026.pdf`, `UFAM-2026-Cordeiro.pdf`, diretrizes de LLM (PDF) | material de referência na raiz | [F] |
| `teste.py`, `teste_agente_3bugs/`, `pyrightconfig.json`, `scripts/relatorio_bugs.py` | arquivos soltos ou não commitados | [F] `git status` |

---

## 2. Fluxograma da arquitetura implementada (modo `hybrid`, etapa `end-to-end`)

```
dataset/<conjunto>/funcao_com_bug/*.py
        |
        v
[preprocess_file] ---> 1 unidade por função (main.py:865-887)
        |
        v
[DETECÇÃO: LLM]  system_prompt_v2 + variantes (padrão A1,A2)
        |   função renomeada target_function, sem docstring/comentários (prompts.py:116-191)
        v
achados (JSON) --> campo "verifiable" escolhido pela LLM
        |                     \
        | verificáveis          `--> retidos (rejected_findings): só contam no nível "apontado"
        v
[GROUNDING por AST] localiza função e expressão suspeita no arquivo_com_bug
        |
        v
[ESPECIFICAÇÃO: LLM] JSON {params, attributes, stubs, assumptions}; até 2 reparos (loop.py:202,242-293)
        |
        v
[RENDER + COMPAT, sem LLM] cut_after_suspect, none_guards, stubs de import, remoção de código não usado,
        |                   regras ligadas por sondas de capacidade (render.py:550-568, compat.py)
        v
[ESBMC] --unwind 5 --multi-property; escala unwind 10/20, incremental-bmc, k-induction,
        |   troca de solver e timeout 300 s (esbmc_run.py:91-200)
        |
        +--> recusa (UNSUPPORTED, MISSING_DEPENDENCY, GROUNDING_FAILED)
        |        --> [SELF-HEALING: LLM] edita código fora do corpo, stubs, corpo simplificado;
        |            até 3 rodadas por obstáculo, 9 no total (healing.py:468-480)
        |            --> volta ao ESBMC; se esgotar --> LLM_ONLY
        |
        +--> violação --> [REPLAY CPython] busca determinística no harness pré-reescrita
                 |         (sementes do contraexemplo + domínio pequeno; replay_worker.py:285-330)
                 |
                 +--> falha antes da suspeita --> [REFINAMENTO: LLM] nova assunção (até 2; loop.py:327-373)
                 |
                 v
        [VEREDITO] CONFIRMED / UNVALIDATED / OTHER_FAILURE / NOT_CONFIRMED / ESBMC_MISSED /
                   BOUND_INCONCLUSIVE / ESBMC_TIMEOUT / HANDLED_BY_CALLER / DEPENDS_ON_LIBRARY ...
                   (outcome.py:126-143)
        |
        v
[NÍVEIS + AVALIAÇÃO] levels.py; v2_evaluator.py (por expressão e, com --evaluate-by-function, por função)
        |
        v
v2_verify_report.json, v2_checkpoint.json, llm_telemetry.json, programs/, avaliacao_funcoes.md
```

**Modo `scan`** (`scan/pipeline.py`, docstring l. 1-5) [F]:

```
repositório --> plan_scan (sem LLM): grafo de chamadas, ranking (callers ou pagerank), estimativa de custo
            --> execute_scan: detecção por função, com chamadores como contexto
            --> motor verify (engine) ou agente (--scan-verify agent)
            --> scan_report.json, scan_summary.md (checkpoint por função)
```

O perfil `congelado` recusa o modo scan (`main.py:569`, segundo subagente) [F].

---

## 3. Inventário dos datasets (contagens verificadas)

| Conjunto | Itens | Composição verificada | Usado em | Fonte |
|---|---:|---|---|---|
| `bugs_reais/` | 289 | 115 rotulados à mão (85 BugsInPy + 30 de commits de correção) e 174 `rotulo_automatico` (BugsInPy); prefixos `bip` 174, `ip` 29, `nm` 25, `av` 17, `oob` 14, `tm` 13, `vm` 8, `dz` 4, `ir` 4, `io` 1 | fases 7 a 27 (setembro a outubro) | `manifest.json` (289), `ground_truths.json` (289) [F] |
| `bugs_reais/funcao_com_bug/` | 289 | um arquivo por bug | detecção | [F] |
| `bugs_reais/arquivo_com_bug/`, `arquivo_corrigido/` | 281 entradas cada (280 arquivos + `fetch_report.json`) | 9 bugs sem arquivo, porque o trecho foi editado à mão | harness e controle | [F]; o README diz 280 |
| `bugs_reais/patches/` | 289 | | auditoria | [F] |
| `bugs_reais/amostra_deteccao.json` | 50 | estratificada por hash; depois revisada para 48 casos válidos | seleção de prompts (F9 a F27) | [F] |
| `bugs_reais/conjunto_dificil.json` | 20 | tirado de `full-2026-10-05-regrounded` | F10 | [F] |
| `bugs_reais/amostra_harness.json` | 30 hipóteses | semente 20261022, tirada de `final-2026-10-17` | F30, S6 | [F] |
| `bugs_reais/eligibility.json`, `manifest_full.json` | 115 | elegibilidade dos harnesses manuais de 09/09 | legado | [F] |
| **BugsInPy no total** | 259 em `bugs_reais` | 85 à mão + 174 automáticos. A coleta tinha 199 candidatos e 219 rejeitados; 23 saíram por expressão não encontrada e 2 por função aninhada reescrita | | `coleta_bugsinpy/*.json`, `dataset/README.md` [F] |
| `failure_kind` em `bugs_reais` | 289 | `resultado_errado` 178, `excecao_local` 59, `excecao_nao_modelavel` 24, `excecao_modelavel` 23, `incerto` 5; só 82 alcançáveis pelo ESBMC | métrica de triagem | `dataset/README.md` [F nas contagens do README; NV recontagem] |
| `disciplina_pgene601/` | 47 | 21 projetos; 47 PRs integrados distintos; 53 funções, todas rotuladas; 39 `excecao_local` e 8 `excecao_modelavel` | rodadas de 02 a 16/11 | `manifest.json` [F] |
| `disciplina_pgene601/arquivo_corrigido/` | 47 | versões corrigidas | só o controle VALUE_ORACLE (inativo); detecção nas corrigidas preparada mas não executada | [F] |
| `disciplina_pgene601/gabarito_funcoes.json` | 47 | funções tocadas por cada patch | tabela das funções irmãs | [F] |
| `disciplina_pgene601/adafruit_valor/` | 4 | bugs de valor errado, separados | não usado nas rodadas principais [I] | [F] |
| `disciplina_pgene601/geral/` | 1 arquivo (README da triagem inicial) | | | [F] |
| `harness_bugs_reais/` | 115 harnesses manuais (mais `_fixed`) e 18 elegíveis | legado de 09/09 | avaliador, pelos nomes | [F] |
| `v1_sintetico/` | 70 funções `.py` | bugs, limpas e smells | só benchmark V1 | [F] |
| `code_smell/` | 379 arquivos em 24 smells; rótulos: PySmell 2570 (150 positivos), mlflow 410 (214), CodeSmile 376 (240), Smelly Code 132 | fora do pipeline | `README.md` [F] |

**Inconsistências do dataset [F]:**
- `dataset/README.md` diz que `disciplina_pgene601` não tem bug validado ("ainda não") e que o pipeline não o usa. As duas afirmações estão desatualizadas.
- A ressalva do `cps_pymodbus_2980` cita `ReadFileRecordResponse.decode`, mas o patch toca `WriteFileRecordRequest.decode` (hunk `@@ -169`, def na linha 170).
- A chave `crash_expressions` falta em 29 dos 47 itens, em vez de aparecer como lista vazia.
- O manifesto dos 47 não tem datas de merge.

---

## 4. Implementações por etapa

| Etapa | Onde está | O que faz | Estado no perfil `congelado` |
|---|---|---|---|
| Detecção | `llm/prompts.py:94-191`, `llm/prompt_variants.py:17-28`, `prompts/system_prompt_v2.txt`, `v2_variants/A1*`, `A2_checklist.txt` | 1 chamada por função; A1 ("report anyway") e A2 (partição de entradas) | ativa [F] |
| Variantes A3 a A22 | `prompts/v2_variants/` | contexto de arquivo (A11, A12), docstring (A10), oráculo de valor (A15), decoradores (A22) etc. | inativas [F] |
| Roteamento de prompt | `llm/prompt_routing.py` | escolhe variantes por característica | inativo (`routing: null`) [F] |
| Triagem | `main.py:927-937` | campo `verifiable` da LLM | ativa [F] |
| AST grounding | `verify/grounding.py`, `verify/astutil.py` | localiza a hipótese no arquivo real | ativo [F]; código não lido inteiro |
| Especificação do harness | `verify/spec.py`, `prompts/input_spec_prompt.txt`, `verify/loop.py` | JSON de tipos, stubs e assunções | ativa [F] |
| Contexto dos chamadores | `verify/caller_facts.py`, `attempts.py:15` | guards dos chamadores viram assunções | ativo (`spec_context=callers`) [F, subagente] |
| Render e compatibilidade | `verify/render.py`, `verify/compat.py`, `verify/rules.py`, `verify/probes/` | reescritas e sondas de capacidade | ativo [F] |
| ESBMC | `verify/esbmc_run.py`, `verification/esbmc_runner.py`, `verify/esbmc_provenance.py` | escalonamento de bound, solver e timeout; procedência | ativo [F] |
| Replay | `verify/replay.py`, `verify/replay_worker.py`, `verify/sandbox.py` | busca determinística isolada | ativo, sem modo aleatório [F] |
| Healing | `verify/healing.py`, `prompts/healing_prompt.txt`, `verify/skills/reparos-aprendidos/SKILL.md`, `verify/esbmc_knowledge.py` | reparo guiado pelo erro e pela base de conhecimento | ativo (`error+kb`) [F] |
| Refinamento | `verify/loop.py:327-373` | nova assunção quando o replay falha antes da suspeita | ativo [F] |
| Veredito e níveis | `verify/outcome.py`, `verify/levels.py` | combina ESBMC e replay | ativo [F] |
| pytest dos confirmados | `verify/pytest_gen.py` | gera teste a partir do CONFIRMED | ativo, não muda o veredito [F, subagente] |
| Oráculo de valor | `verify/value_oracle.py` | bugs de resultado errado, com controle nas corrigidas | inativo [F] |
| Agente | `verify/agent_arm.py`, `agent_scan.py`, `agent_validation.py` | o agente escreve o harness | inativo no congelado; usado no scan com `--scan-verify agent` e na extensão [F] |
| Lições automáticas | `maintenance/`, `verify/lessons.py` | grava reparos novos no caderno | desligadas no congelado; o caderno é lido mesmo assim [F] |
| Modo scan | `scan/`, `main.py:568`, `cli.py` | repositório inteiro | separado do congelado [F] |
| Extensão | `extension/` | `/verify-repo` no Claude Code | separada [F] |

---

## 5. Gabarito, patches e rótulos

| Estrutura | Campos | Onde | Observação |
|---|---|---|---|
| Manifesto dos 47 | `id`, `cohort`, `function`, `expression`, `categories`, `line`, `label_sources`, `review`, `provenance`, `expected_type`, `failure_kind`, `failure_kind_source`, `failure_kind_note`, `crash_expressions`, `ressalva`, `detection_file` | `dataset/disciplina_pgene601/manifest.json` | `function` aceita duas funções separadas por `/` (6 casos) [F] |
| Manifesto de `bugs_reais` | `id`, `detection_file`, `harness_file`, `function`, `categories`, `harness_strategies`, `expression`, `provenance`, `oracle`, `abstraction`, `failure_kind`, `cause_expressions`, `label_sources` | `dataset/bugs_reais/manifest.json` | não tem `expected_type` [F] |
| Gabarito | igual ao manifesto, lido pela avaliação | `ground_truths.json` | a avaliação por função lê o `manifest.json` vizinho (`report.py:57-58`) [F, subagente] |
| Funções tocadas pelo patch | `id`, `tocadas_pelo_patch` | `gabarito_funcoes.json`, gerado por `scripts/gabarito_funcoes.py` | 3 patches largos excluídos até revisão [F] |
| Origem dos rótulos | `label_sources.expression`: `changed_line` 34, `statement_after_insertion` 10, `statement_before_insertion` 3 | manifesto | os 13 de inserção são rótulos ambíguos [F] |
| Patches | `.diff` por bug | `patches/` | [F] |

---

## 6. Experimentos, resultados, custos e logs

O histórico completo está na Parte 4 de `auditoria_pipeline_2026-11-16.md`. Aqui ficam só as rodadas e os artefatos que importam.

| Grupo | Artefatos | Resultado registrado | Custo | Status |
|---|---|---|---|---|
| V1 sintética | `archive/v1_*`, `docs/historico/v1*` | não auditado aqui | | [NV] |
| Fases 1 a 6 (setembro) | `docs/experimentos/fase-1` a `fase-6`, `artifacts/v2/*` | métricas antigas (confirmed_driver etc.) | | não comparáveis [F] |
| Fase 7 a 14 (outubro, `bugs_reais`) | `artifacts/v2/triage-*`, `full-*`, `final-2026-10-15*` | por exemplo, 5 CONFIRMED em 4 bugs (F7 full) | `REGISTRO_MODELOS_TOKENS.md` | [F, subagente] |
| Seleção de prompt (50/48) | `artifacts/v2/det-2026-10-06-*` a `det-2026-10-31-*` | A5 de 22 a 26 na linha; três repetições 22, 23, 24 | | [F] |
| 47, detecção (02 e 03/11) | `artifacts/pgene601/e2e-2026-11-02`, `codex-2026-11-03` | 36/47 e 39/47 na linha | | [F, subagente] |
| 47, rodadas completas (06 a 11/11) | `congelado-c-2026-11-06`, `ajustes-2026-11-07`, `rodada-final-2026-11-08`, `-09`, `rodada-2026-11-11` | pela regra atual, recalculada nesta auditoria: 6, 5, 8 (09/11), 9 confirmados | `llm_telemetry.json` em cada pasta | exploratórias [F] |
| 47, ruído (14/11) | `ruido-2026-11-14-r1` | 89 de 128 verificações; não vale | 28,4 M tokens | [F] |
| 47, congelada (16/11) | `congelado-2026-11-16-r1` | 13 reproduzidos, 8 confirmados | 560 chamadas, 11,45 M tokens, US$ 42,04 estimado | completa, pré-registrada [F] |
| 47, agente (16/11 à noite) | `agente-teste-2026-11-16`, `teste_agente_3bugs/` | 3 bugs, código não commitado | | não registrada [F] |
| Baselines dos 47 | `mypy-2026-10-18`, `mypy-2026-11-03`, `pytest-2026-11-03` | mypy 2/47 (5/47 com `--check-untyped-defs`); pytest 10 (36 sem teste) | sem LLM | [F nos documentos] |
| Scans | `artifacts/cps/*`, `artifacts/scan_*`, `/mnt/e/scan_amazon/*` (fora do repositório) | 0 bugs novos confirmados pelo ESBMC; 1 bug novo por leitura da LLM (GSA, issue #132); issue pymodbus #3085 | | registros em `docs/experimentos/indice_scans_2026-11-12.md` [F nos documentos] |
| Capacidades do ESBMC | `artifacts/esbmc_capabilities`, `flag_ablation_logs*`, `docs/projeto/possiveis_problemas/` | recusas catalogadas; issues abertas no ESBMC | | [F nos documentos] |

**Logs [F]:** cada rodada guarda `run.log`, `status.log`, `commit.txt` (só nas recentes), `v2_checkpoint.json`, `v2_verify_report.json`, `llm_telemetry.json` e `programs/` com os harnesses gerados.

---

## 7. Scripts de avaliação e de tabelas

| Script | Função | Lido? |
|---|---|---|
| `scripts/rodar_47_ruido.sh` | roda r1 (detecção e verificação) e r2 (só verificação) no perfil congelado | sim [F] |
| `scripts/relatorio_bugs.py` | `RELATORIO_BUGS.md`, um estágio por bug | sim; **não commitado** [F] |
| `scripts/pgene601_tabela.py` | tabela de baselines (pytest) | não |
| `scripts/pgene601_mypy_baseline.py` | baseline mypy | não |
| `scripts/juiz_conserto.py` | juiz do conserto: a entrada deixa de falhar na versão corrigida? | não |
| `scripts/deteccao_corrigidas.sh`, `preparar_deteccao_corrigidas.py` | detecção nas versões corrigidas (pago) | não; nunca executado [F] |
| `scripts/gabarito_funcoes.py` | funções tocadas pelo patch | não |
| `scripts/compare_runs.py`, `pareado.py` | comparação de rodadas; comparação pareada | não |
| `scripts/funil.py`, `v2_funnel.py`, `v2_levels.py`, `v2_run_report.py` | funil e níveis | não |
| `scripts/telemetry_summary.py` | resumo de tokens e custo | não |
| `scripts/registro_rodadas.py` | registro das rodadas | não |
| `scripts/v2_self_consistency.py`, `v2_union_detection.py`, `v2_judge.py`, `v2_hallucination.py` | análises da fase de seleção de prompt | não |
| `scripts/relatorio_scans.py`, `scan_com_retomada.sh`, `scan_noite.sh` | scans | não |
| `scripts/atualizar_esbmc.sh` | atualiza e recompila o ESBMC | não |
| `scripts/build_*`, `fetch_v2_*`, `collect_validated_bugs.py` | construção dos datasets | não |

---

## 8. Documentação acadêmica, artigos e planos

| Documento | Estado |
|---|---|
| `docs/pgene601/artigo/artigo.tex` | **esqueleto**: só os títulos das seções e comentários com o que vai em cada uma, sem texto, sem tabelas, sem figuras e sem bibliografia. Último commit em 10/11 (`89ac2b5`) [F] |
| `docs/pgene601/artigo/mapa_dados.md` | de onde sai cada número; ainda descreve a rodada congelada como "em andamento" e chama a de 06/11 de "única fora da amostra" [F] |
| `docs/pgene601/artigo/tabela_experimentos.md` | tipo de cada rodada; tem alterações não commitadas [F] |
| `docs/pgene601/artigo/tabela_scans.md` | scans com ressalvas detalhadas [F] |
| `docs/pgene601/proposta_projeto_cps_2026-09-22.md` | proposta da disciplina | não lida |
| `docs/projeto/trabalhos_relacionados_2026-10-16.md`, `fichamento.md`, `leituras_recomendadas.md`, `literatura_auto_melhoria.md` | material de revisão bibliográfica | não lidos; as citações **não foram verificadas** |
| `artigos_estudo/*.md` | conversões de artigos | não lidos |
| `docs/projeto/PLANO_2026-11-12.md`, `PLANO_CODEX*_2026-11-14.md`, `EXECUCAO_CODEX*` | planos e execuções recentes | lidos pelo subagente |
| Figuras | não encontrei figuras do artigo (`.png`, `.pdf`, `.svg`) em `docs/pgene601/artigo/` [F] | |

**Comentários do `artigo.tex` que já estão desatualizados [F]:**
- "47 bugs reais de 20 projetos": são 21.
- "Gabarito pela linha do patch; níveis expressão, função, arquivo": desde 14/11 o critério é por função, em dois níveis.

---

## 9. Matriz de funcionalidades

"Testado" = existe arquivo de teste com o nome correspondente (não executado agora). "Documentado" = descrito em documento atual (D), só em documento desatualizado (Dd) ou não documentado (-).

| Funcionalidade | Implementada | Testada | Ativa no congelado | Documentada |
|---|---|---|---|---|
| Detecção A1+A2 | sim | `test_prompt_variants`, `test_prompt_surface_consistency` | sim | D |
| Variantes A3 a A22 | sim | `test_prompt_variants`, `test_prompt_decorators` | não | D (README de experimentos) |
| Roteamento de prompts | sim | `test_prompt_routing`, `test_routing_cli` | não | D (`tabela_roteamento_prompts_v1.md`) |
| Cache de detecção | sim | `test_detection_cache*` | não | - |
| Isolamento do Claude CLI | sim | `test_claude_cli_command`, `test_claude_cli_backend` | sim | D (help da flag) |
| Triagem pela LLM | sim | `test_v2_triage` | sim | Dd |
| Limite de hipóteses por função | sim | `test_hypothesis_cap` | não | - |
| Revisão de hipóteses | sim | `test_hypothesis_review*` | não | D (memória do projeto) |
| AST grounding | sim | `test_verify_grounding`, `test_verify_nested` | sim | Dd |
| Especificação em JSON | sim | `test_verify_spec`, `test_llm_client_json_mode` | sim | Dd |
| Contexto dos chamadores | sim | `test_verify_caller_facts`, `test_caller_exception_context` | sim | - |
| Compatibilidade e sondas | sim | `test_verify_compat*`, `test_verify_capabilities` | sim | D (`possiveis_problemas/`) |
| `cut_after_suspect`, `none_guards` | sim | `test_verify_compat`, `test_verify_dead_guards` [I] | sim | - |
| Escalonamento do ESBMC | sim | `test_verify_esbmc_run`, `test_verify_rounds` | sim | Dd (doc diz unwind fixo) |
| Procedência do ESBMC | sim | `test_esbmc_provenance`, `test_atualizar_esbmc` | sim | D (`ESBMC_VERSOES.md`) |
| Replay determinístico | sim | `test_verify_replay*` | sim | Dd (doc diz "mesmo contraexemplo") |
| Replay aleatório | sim | `test_verify_replay_random` | não | - |
| Self-healing | sim | `test_healing*` | sim | D (memória, README de experimentos); Dd (`entendendo_o_pipeline.md` não traz) |
| Parada do reparo sem mudança de erro | sim (`f55cc5a`) | `test_healing_loop` | sim | D (README de experimentos) |
| Refinamento por assunção | sim | `test_verify_loop` [I] | sim | - |
| Base de conhecimento do ESBMC | sim | `test_esbmc_knowledge` | sim | - |
| Lições automáticas | sim | `test_verify_auto_lessons`, `test_verify_auto_lesson_guard` | não | D |
| Avaliação por função | sim | `test_function_evaluation_report`, `test_v2_evaluator` | sim | D (`REGRA_DE_ACERTO`) |
| Níveis (esbmc_engine, llm_only) | sim | `test_verify_levels` | sim | - |
| pytest dos confirmados | sim | `test_verify_pytest_gen` | sim | - |
| Oráculo de valor e controle nas corrigidas | sim | `test_verify_value_*`, `test_v2_audit_control` | não | D, mas a doc diz que o controle roda |
| Juiz do conserto | sim (script) | `test_juiz_conserto` | não (pós-rodada) | D (`CONGELAMENTO`) |
| Detecção nas corrigidas | sim (script) | `test_deteccao_corrigidas` | nunca executada | D |
| Agente que escreve o harness | sim | `test_verify_agent_*`, `test_v2_agent_*` | não | D (`HANDOFF_harness_de_agente.md`) |
| Modo scan | sim | `test_scan_*` (10 arquivos) | não (separado) | D (`modo_scan_2026-10-14.md`) |
| Extensão `/verify-repo` | sim | `test_extension_command` | separado | D (`extension/README.md`) |
| Manutenção automática | sim | `test_maintenance_*` (9 arquivos) | não | D (`manutencao.md`) |
| Smells (V1) | sim | `test_smell_*`, `test_smells_metricas` | não | D |

---

## 10. Inconsistências entre documentação e código

| # | Documento | Diz | Código ou artefato mostra |
|---|---|---|---|
| 1 | `entendendo_o_pipeline.md:95`, `README.md:55` | a LLM "nunca escreve código" | o healing escreve stubs e edições (`healing.py:414-438`) [F] |
| 2 | `entendendo_o_pipeline.md:12,87`; `README.md:60,68` | "mesma exceção na mesma linha" | ESBMC comparado só pelo tipo da exceção; replay por busca (`outcome.py:131-137`, `replay_worker.py:285-330`) [F] |
| 3 | `entendendo_o_pipeline.md:75` | `--unwind 5` fixo | escalonamento (`esbmc_run.py:91-200`) [F] |
| 4 | `entendendo_o_pipeline.md:220-233` | lista de vereditos | faltam LLM_ONLY, BOUND_INCONCLUSIVE, HANDLED_BY_CALLER, DEPENDS_ON_LIBRARY [F] |
| 5 | `entendendo_o_pipeline.md:378-383`; `README.md:63` | "retry removido", "só reparo de JSON" | refinamento por assunção (`loop.py:327-373`) e healing [F] |
| 6 | `README.md:343` | `--bound` vira `--max-k-step` | o motor verify usa `--unwind` (`esbmc_run.py:102`) [F] |
| 7 | docs do controle | "0 confirmações falsas no controle" | `fixed_sources` só para VALUE_ORACLE, inativo (`loop.py:434-439`) [F, subagente] |
| 8 | `esbmc_runner.py:15-17` (comentário) | `--no-pointer-check --no-align-check` em "every run since phase 13" | a rodada de 16/11 usou o binário cru, sem essas flags [F, subagente] |
| 9 | `CONGELAMENTO_2026-11-14.md` | tag `11e`, ESBMC `fbaf8089`, sha `1a7975...` | a rodada de 16/11 usou `f086e22`, ESBMC `de72a905e0`, sha `d9f0de1f...`; a tag vigente é `11f` [F] |
| 10 | `mapa_dados.md` | rodada congelada "em andamento"; 06/11 "única fora da amostra" | rodada concluída; 06/11 também usou os 47 antes [F] |
| 11 | `artigo.tex` | 20 projetos; gabarito pela linha | 21 projetos; regra por função [F] |
| 12 | `dataset/README.md` | disciplina "não validada" e "não usada" | usada em todas as rodadas de novembro [F] |
| 13 | `dataset/README.md` | `arquivo_com_bug` com 280 | 281 entradas, uma delas `fetch_report.json` (coerente) [F] |
| 14 | manifesto, ressalva do pymodbus_2980 | `ReadFileRecordResponse.decode` | patch em `WriteFileRecordRequest.decode` [F] |
| 15 | `llm_client._run_claude_cli` (docstring) | "harness free-form Python" | a especificação é JSON [F, subagente] |
| 16 | `docs/experimentos/fase-11/partial-timeout-2026-11-03` | pasta com o nome da fase 11 | a fase 11 do README é de 12/10 [F, subagente] |

---

## 11. Mapa de dependências entre componentes

```
cli_args (perfis) --> main.mode_v2 --------------------------------------------+
                         |                                                       |
                         +--> preprocess --> llm.prompts (+ prompt_variants,     |
                         |                    prompt_routing) --> llm.backends   |
                         |                    (claude_cli, anthropic, openai,    |
                         |                     codex, google, ollama)            |
                         |                    --> llm.telemetry, failure_policy  |
                         |                                                       |
                         +--> verify.orchestrator / verify.loop                  |
                                 |--> verify.grounding --> verify.astutil        |
                                 |--> verify.spec <-- verify.caller_facts        |
                                 |                  <-- verify.llm_client (síntese)
                                 |--> verify.render --> verify.compat, rules, probes, capabilities
                                 |--> verify.esbmc_run --> verification.esbmc_runner
                                 |                     --> verify.esbmc_provenance
                                 |--> verify.replay --> replay_worker, sandbox
                                 |--> verify.outcome
                                 |--> verify.healing --> esbmc_knowledge, lessons, skills/
                                 |                   --> scan.callgraph (contexto)
                                 |--> verify.pytest_gen, string_witness
                                 +--> verify.levels, verify.report
                         +--> v2_evaluator (manifest.json, gabarito_funcoes.json) <--------+

main.mode_scan --> scan.pipeline --> scan.callgraph, context, prefilter, dedupe, graph_metrics
                                 --> verify.loop (engine) ou verify.agent_scan (agent)
maintenance.* --> verify.lessons, skills/reparos-aprendidos (desligado no congelado)
scripts/rodar_47_ruido.sh --> main (perfil congelado) --> artifacts/pgene601/congelado-*/
scripts/relatorio_bugs.py --> v2_verify_report.json --> RELATORIO_BUGS.md
```

Dependências externas: binário do ESBMC em `/mnt/e/esbmc-builds/...` (disco externo), checkout em `~/esbmc-master`, CLI `claude` (assinatura) e Python do `.venv`.

---

## 12. Evidências aproveitáveis para o artigo de CPS (entrega até 30/11)

O que já existe e se sustenta, com a ressalva de que os 47 são conjunto de desenvolvimento:

1. **Dataset descrito e rastreável:** 47 bugs de 21 projetos CPS e IoT, cada um de um PR integrado, com versão com bug, versão corrigida e patch (`manifest.json`, `ORIGEM_DOS_47_BUGS.md`, `cps_candidatos_*`) [F].
2. **Rodada pré-registrada de 16/11:** 13/47 reproduzidos, 8/47 confirmados, com intervalos já calculados na auditoria metodológica [F].
3. **Funil por bug:** onde cada bug parou (`RELATORIO_BUGS.md`; depende de commitar o script) [F].
4. **Baselines:** mypy 2/47 e 5/47; testes do PR 10/47, com 36 sem teste. Servem como contexto, com unidades de contagem explicadas [F].
5. **Custo:** 560 chamadas, US$ 42 estimados, 89% na síntese [F].
6. **Limites do ESBMC-Python:** 20 bugs recusados, com mensagem e issue (`possiveis_problemas/disciplina_pgene601/RECUSAS_ESBMC.md`), mais as issues abertas [F nos documentos].
7. **Variação entre rodadas:** a reavaliação com a regra atual mostra o conjunto confirmado mudando 2 a 3 bugs; os mesmos 4 bugs aparecem em todas [F].
8. **Scans como estudo de falso positivo:** 10 CONFIRMED triados à mão, nenhum bug novo; GSA (issue #132) achado por leitura da LLM [F nos documentos].
9. **Rastreabilidade:** `mapa_dados.md`, a procedência do ESBMC e a telemetria por chamada [F].

**O que precisa ser corrigido no texto antes de usar:** número de projetos (21), critério de acerto (por função), status da rodada congelada, e a frase "fora da amostra" sobre 06/11.

---

## 13. Lacunas que podem esperar depois de novembro

Ficam para depois da entrega da disciplina, sem prejudicar um artigo de disciplina que declare as limitações:

- Conjunto novo e independente, com regra de seleção pré-registrada.
- Detecção em funções sem bug (falso positivo, precisão).
- Repetições da configuração congelada para medir variação.
- Comparação com outro modelo de LLM.
- Ablação do healing e do refinamento.
- Prova de alcance pelo programa real.
- Segundo rotulador e concordância.
- Datas dos PRs para quantificar contaminação. É barato (API do GitHub, sem LLM): se der tempo, pode entrar antes.
- Atualizar `entendendo_o_pipeline.md`.
- Revisão bibliográfica com citações verificadas. A seção "Trabalhos relacionados" do artigo da disciplina precisa de pelo menos as referências centrais verificadas antes de 30/11.

**Não pode esperar se for para a entrega de 30/11 (sugestão; a decisão é sua):**
- commitar o resultado de 16/11 e `scripts/relatorio_bugs.py`;
- corrigir `mapa_dados.md` e os comentários do `artigo.tex`;
- escrever o texto do artigo, que hoje é só esqueleto.
