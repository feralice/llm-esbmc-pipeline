# Auditoria 1: dataset BugsInPy e histórico de desenvolvimento (16/11/2026)

Documento de trabalho da Fernanda. Complementa `auditoria_pipeline_2026-11-16.md` e `auditoria_0_inventario_2026-11-16.md`.

**Como foi feito.** Claude Code (Opus 5.5), só leitura.
- Os manifestos e os relatórios das rodadas foram lidos com Python, sem gravar nada no repositório. Um mapa auxiliar de "ID que aparece em cada pasta de artefato" foi gerado no scratchpad da sessão, fora do repositório.
- O histórico de decisões vem do subagente que leu `docs/experimentos/README.md` inteiro. As afirmações dele foram conferidas por amostragem.
- **Ressalva de método:** "ID mencionado num artefato" quer dizer que o nome do bug aparece em algum JSON da pasta da rodada. Indica **exposição**, não prova de execução: um relatório pode listar o gabarito inteiro. Quando a execução foi conferida, o texto diz isso.

**Rótulos:** [F] fato verificado; [I] inferência; [H] hipótese; [NV] não verificado.

---

## 1. Inventário quantitativo

| Item | Valor | Fonte |
|---|---:|---|
| Bugs em `dataset/bugs_reais` | 289 | `manifest.json` [F] |
| Com `provenance.bugsinpy_id` (do BugsInPy) | **259** | [F] |
| BugsInPy rotulados à mão (sem `cohort`) | 85 | prefixos `ip` 23, `nm` 18, `av` 17, `tm` 11, `oob` 7, `vm` 7, `dz` 1, `io` 1 [F] |
| BugsInPy com rótulo automático (`cohort = rotulo_automatico`) | 174 | prefixo `bip_<projeto>_<n>` [F] |
| Não BugsInPy (commits de correção nos próprios projetos) | 30 | python-tabulate 4, esbmc 3, croniter 2 e outros [F] |
| Projetos BugsInPy | 17 | [F] |
| Pares (projeto, `bugsinpy_id`) repetidos | 0 | [F] |
| BugsInPy com `buggy_commit` e `fixed_commit` | 259 de 259 | [F] |
| BugsInPy com patch em `patches/` | 259 de 259 | [F] |
| BugsInPy com `arquivo_com_bug` e `arquivo_corrigido` | 251 de 259 | faltam 8, todos da coorte à mão: `ip_real_04`, `ip_real_34`, `vm_real_03`, `vm_real_04`, `vm_real_07`, `vm_real_08`, `tm_real_11`, `tm_real_12`. O trecho foi editado à mão [F] |
| Coleta automática: examinados, aceitos, recusados | 418, 199, 219 | `coleta_bugsinpy/README.md` [F] |
| Aceitos que viraram rótulo automático | 174 de 199 | 23 com expressão não encontrada, 2 com função aninhada reescrita (`dataset/README.md`) [F] |
| Revisão humana da coorte automática | 0 de 174 | `review: pending` em todos [F] |

**Versões buggy e fixed [F]:** existem para 251 dos 259, com os commits nos 259. Os commits vêm do `bug.info` do BugsInPy. No pandas, 27 bugs foram recusados porque o SHA curto do BugsInPy não resolve no GitHub, e não houve substituição pelo pai do commit (`coleta_bugsinpy/README.md`).

---

## 2. Projetos e bugs

| Projeto | À mão | Automático | Total |
|---|---:|---:|---:|
| pandas | 3 | 60 | 63 |
| youtube-dl | 9 | 18 | 27 |
| scrapy | 15 | 9 | 24 |
| keras | 2 | 21 | 23 |
| thefuck | 11 | 10 | 21 |
| luigi | 10 | 11 | 21 |
| matplotlib | 5 | 15 | 20 |
| black | 4 | 9 | 13 |
| tornado | 8 | 2 | 10 |
| fastapi | 2 | 7 | 9 |
| ansible | 4 | 4 | 8 |
| spacy | 2 | 3 | 5 |
| tqdm | 4 | 1 | 5 |
| cookiecutter | 2 | 2 | 4 |
| sanic | 2 | 1 | 3 |
| httpie | 1 | 1 | 2 |
| PySnooper | 1 | 0 | 1 |
| **Total** | **85** | **174** | **259** |

[F] `manifest.json`. O pandas sozinho tem 24% do total e 34% da coorte automática.

**Tipo de falha (`failure_kind`) [F]:**

| Tipo | À mão | Automático | Total |
|---|---:|---:|---:|
| `resultado_errado` (nada quebra) | 45 | 122 | 167 (64%) |
| `excecao_local` | 30 | 15 | 45 |
| `excecao_modelavel` | 8 | 13 | 21 |
| `excecao_nao_modelavel` | 2 | 20 | 22 |
| `incerto` | 0 | 4 | 4 |

**Categorias [F]:**
- **À mão:** `invalid_precondition` 21, `none_misuse` 20, `assertion_violation` 13, `type_mismatch` 10, `incorrect_result` 8, `variable_misuse` 8, `out_of_bounds` 7, `division_by_zero` 1, `integer_overflow` 1.
- **Automático:** 136 de 174 são `unclassified`. A categoria vem de uma heurística sobre o diff e não foi revisada.

**Funções [F].** Cada bug tem `function` e `provenance.source_function`. Os IDs, commits e funções de cada bug estão no `manifest.json`. O documento não repete as 259 linhas.

---

## 3. Compatibilidade com o frontend Python do ESBMC

| Critério | BugsInPy | Fonte |
|---|---:|---|
| Alcançáveis em princípio (`excecao_local` + `excecao_modelavel`) | **66 de 259** (25%) | rótulo `failure_kind`, lido do patch [F] |
| Bug de valor errado, sem propriedade para o ESBMC sem oráculo | 167 (64%) | [F] |
| Dependem de biblioteca complexa (TensorFlow, pandas por dentro) | 22 | [F] |
| Harnesses manuais de 09/09 que o ESBMC rodava | 18 elegíveis | `harness_bugs_reais/elegiveis_0909/manifest.json` [F] |

O rótulo `failure_kind` é uma **previsão** feita lendo o patch. Não é uma medida do ESBMC, e 13 rótulos automáticos usaram também o teste do BugsInPy (`dataset/README.md`).

---

## 4. Origem e seleção: houve seleção pelo sucesso do ESBMC?

**Coorte à mão (85 BugsInPy + 30 de commits): sim [F].** `dataset/bugs_reais/README.md`, seção *Method*:
- o bug foi abstraído à mão num harness "ESBMC-verifiable";
- o passo 6 diz: "Confirmed every item with `esbmc ... --unwind 6`: all produce `VERIFICATION FAILED`".

Os itens entraram no dataset original porque o ESBMC confirmou uma abstração feita à mão. É viés de sobrevivência a favor da ferramenta, embora a confirmação tenha sido sobre o harness manual e não sobre o pipeline. O mesmo README registra bugs **descartados** por limite do ESBMC: `thefuck/27` e `thefuck/31`, por `str.replace()` caro demais.

**Coorte automática (174): não pelo ESBMC, mas por localidade [F].** O critério da coleta é o patch alterar exatamente um arquivo e uma única função (`coleta_bugsinpy/README.md`). Isso favorece bugs localizados, o que facilita a verificação modular, mas não filtra pelo resultado do ESBMC.

**Subconjuntos derivados [F]:**

| Subconjunto | Tamanho | Como foi escolhido | Depende de resultado anterior? | BugsInPy |
|---|---:|---|---|---:|
| `amostra_deteccao.json` | 50, depois 48 | estratificação por `failure_kind` e ordem por hash do ID ("nobody chooses a case") | não | 46 (18 à mão, 28 automáticos) |
| triagem de 20 (F7) | 20 | sorteio com semente 42 | não | [NV] composição |
| `conjunto_dificil.json` | 20 | hipóteses de uma rodada terminada que apontam a linha do gabarito | **sim**: usa vereditos de `full-2026-10-05-regrounded` | 18 (9 automáticos) |
| alvos dos lotes F13 | 45 alvos, 33 bugs | hipóteses na linha do gabarito | **sim** | [NV] |
| `amostra_harness.json` | 30 hipóteses | semente 20261022, hipóteses de `final-2026-10-17` | **sim**: só bugs que chegaram a hipótese naquela rodada | 22 (13 automáticos) |
| `elegiveis_0909` | 18 | harness manual que o ESBMC rodava | **sim**: capacidade do ESBMC | [NV] |

---

## 5. Quais bugs foram executados e em quais experimentos

### 5.1 Exposição

- **[F] Nenhum dos 259 deixa de aparecer em artefato.** Todos os 174 automáticos aparecem em pelo menos 10 pastas de `artifacts/v2/`. Os 85 à mão aparecem em 20 a mais de 90 pastas cada.
- **[F] A coorte automática aparece em 74 das cerca de 200 pastas com IDs**, todas a partir de 04/10. Ela entrou no dataset em 01/10 (`c9a9e48`, "a second cohort of 176 real bugs").
- **[F] Execução de detecção conferida.** `full-2026-10-04-sonnet` processou os 277 itens sem contexto de patch, e 135 bugs tiveram hipótese. Os 12 fora dos 277 são `av_real_04/06/08/10/12/13/15/21`, `ip_real_08/09/12` e `nm_real_16`. Todos entraram nos 289 de `final-2026-10-17`.
- **[I] Na prática, não existe BugsInPy "nunca visto" pelo pipeline:** todos passaram por pelo menos uma rodada completa de detecção. A ausência de registro detalhado de alguns usos não muda isso.

### 5.2 Matriz grupo × experimento × configuração

Resumo por família de rodada. A matriz bug a bug pode ser recalculada a partir de `artifacts/v2/*/` (ver seção 9).

| Família de rodada | Exemplos | Bugs | Modelo | Configuração | Cobre |
|---|---|---:|---|---|---|
| F1 e F2 (setembro) | `end-to-end-117`, `e2e-gpt-4o-mini`, `e2e-gemini-*`, `e2e-ollama-40` | 39 a 115 | gpt-4o-mini, gemini 2.5/3.x, qwen3-coder, Claude CLI | LLM escreve o harness; bound 6 ou 20 | só à mão |
| F3 e F4 (27 a 29/09) | `e2e-2026-09-27-*`, `verify-2026-09-29-*-oracle-r1..r5`, `exp-oracle-repair/resample-rep1..3` | 92 a 115 | gpt-4o-mini, gpt-4.1-mini, Codex, gpt-5.5 | spec em JSON; bound 5; timeout 180 | só à mão |
| F6 motor sem LLM (01/10) | `engine-2026-10-01`, `engine-fixed-2026-10-01` | 98 a 115 | | | só à mão |
| F7 (04 e 05/10) | `triage-2026-10-04-*`, `full-2026-10-04-sonnet`, `full-2026-10-05-regrounded`, `smoke-*` | 20 / 277 / 289 | Sonnet 5.5 (CLI) | prompt A0; bound 5 | à mão + automático |
| F8 (05 e 06/10) | `agent-*`, `control-fixed-2026-10-06`, `replay-*` | 6 a 133 | Sonnet | agente, controle nas corrigidas | ambos |
| F9 a F27, seleção de prompt (06/10 a 31/10) | `det-2026-10-06-amostra-*` até `det-2026-10-31-en-r2-*` (22 pastas) | 50 | Sonnet | só detecção; A0 a A16 | amostra de 50 (46 BugsInPy) |
| F11 a F13, ESBMC master sem LLM (12 a 14/10) | `esbmc-master-*` (16 pastas) | 135 | | specs gravadas; master `333d07cc8a` mais flags | ambos |
| F14 (15/10) | `final-2026-10-15`, `-codex`, `rules-after-freeze-2026-10-15` | 277 | Sonnet + Codex na spec | A1+A2 | ambos |
| F22 (17 a 19/10) | `final-2026-10-17`, `master-2026-10-19`, `v86-replay-2026-10-19` | 289 | Sonnet | A1+A2+A15; ESBMC v8.6 | ambos |
| F28 a S6 (22 a 31/10) | `teste-ab-*`, `tarefa10-*`, `s6-*` | 5 a 30 | Sonnet | agente e grafo | amostra_harness (22 BugsInPy) |

**Resultados por rodada grande [F, recálculo próprio a partir de `results`]:**

| Rodada | Resultados | Bugs com hipótese | Hipóteses CONFIRMED | Bugs com CONFIRMED na função do rótulo | Desses, BugsInPy |
|---|---:|---:|---:|---:|---:|
| `full-2026-10-04-sonnet` | 232 | 135 | 5 | 4 | 4 |
| `full-2026-10-05-regrounded` | 232 | 135 | 6 | 5 | 4 |
| `final-2026-10-15` | 564 | 230 | 14 | 11 | 11 |
| `final-2026-10-15-codex` | 564 | 230 | 24 | 15 | 14 |
| `final-2026-10-17` | 742 | 254 | 40 | 26 | 22 |

**Esta contagem não é a métrica oficial da época.** Ela aceita qualquer CONFIRMED na função do rótulo, sem olhar a expressão ou a exceção. O README registra para `final-2026-10-17` **13 bugs na rodada** e 17 pela união com rodadas anteriores (critério pela linha). A diferença de 13 para 22 mostra o peso da escolha da métrica.

BugsInPy com CONFIRMED na função do rótulo em `final-2026-10-17`: `av_real_01`, `av_real_02`, `av_real_07`, `bip_matplotlib_16`, `bip_matplotlib_17`, `bip_pandas_142`, `bip_pandas_145`, `bip_pandas_89`, `bip_thefuck_11`, `bip_tornado_5`, `io_real_01`, `ip_real_10`, `ip_real_17`, `ip_real_22`, `nm_real_11`, `nm_real_15`, `oob_real_01`, `oob_real_02`, `oob_real_03`, `oob_real_05`, `tm_real_10`, `vm_real_06`.

Nessa lista, `bip_matplotlib_16`, `bip_matplotlib_17` e `io_real_01` são o mesmo patch (ver seção 6).

---

## 6. Duplicações e bugs relacionados

- **[F]** Nenhum par (projeto, `bugsinpy_id`) se repete.
- **[F] 16 grupos de bugs com a mesma função (projeto, arquivo, função), somando 38 bugs.** Exemplos: `thefuck/rules/git_push.py::get_new_command`, `youtube_dl/utils.py::_match_one` e `unified_strdate`, `matplotlib/transforms.py::nonsingular`, `pandas/core/series.py::Series._get_with`, `black.py::EmptyLineTracker._maybe_empty_lines`.
- **[F]** 44 grupos com o mesmo arquivo, somando 147 bugs.
- **[F]** O README de `bugs_reais` diz que `matplotlib/16` e `matplotlib/17` são o mesmo patch e contam como um bug. O `io_real_01` é a abstração manual dele. Hoje os três estão no dataset como IDs separados (`bip_matplotlib_16`, `bip_matplotlib_17`, `io_real_01`). [I] Em contagens por bug, eles podem inflar o resultado.
- **[I]** A amostra efetiva é bem menor que 259. As análises deveriam agrupar por projeto e por função.

---

## 7. O que influenciou o pipeline (linha do tempo de decisões)

Fonte principal: `docs/experimentos/README.md` (referências às linhas, via subagente). **[F]** quando a decisão está registrada.

| Data | Decisão de engenharia | Dados que a motivaram | Natureza |
|---|---|---|---|
| 02 a 08/09 | abandono do harness escrito pela LLM ("abstração, não código real", R:61-62) | 117 hipóteses da coorte à mão | exploratória |
| 09/09 | harnesses manuais e lista de 18 elegíveis | coorte à mão | seleção pelo ESBMC |
| 29/09 | CONFIRMED passa a exigir quebra no CPython (R:96) | 125 hipóteses da coorte à mão | mudança de métrica |
| 29/09 | spec em JSON em vez de código | idem | engenharia |
| 01/10 | coorte automática de 174 (176 no commit) | coleta BugsInPy | dataset |
| 04/10 | prompt de triagem sem categoria (`190e3a4`), escolhido em 20 sorteados; o próprio registro chama o ganho de "otimista" (R:163, R:170-171) | 20 sorteados | ajuste no conjunto de medida |
| 04/10 | rótulo `failure_kind` em todos os bugs (`5a8b31c`) e linha da quebra (`02d5785`) | patches | gabarito |
| 05 e 06/10 | `conjunto_dificil` (20) para medir o harness num conjunto fixo (R:258) | vereditos de `full-2026-10-05-regrounded` | ajuste no conjunto de medida |
| 06/10 | A5 (A1+A2) escolhida, com uma rodada por variante (R:290-305) | amostra de 50 | seleção de prompt |
| 12/10 | A5 mantida, nenhuma variante passa do ruído (R:431-434) | amostra de 50 | confirmação |
| 13 e 14/10 | regras de harness escolhidas pelos alvos do gabarito (R:528-539): métrica de 8 para 11 | 45 alvos, 33 bugs | ajuste no conjunto de medida |
| 15/10 | regras novas no dia do congelamento, medidas nos mesmos specs (R:703-710); métrica por união | 277 | ajuste pós-congelamento |
| 17/10 | A15 adotada sem medição (R:854-856) | amostra de 50 | escolha sem dado |
| 19/10 | `expressions_equivalent` muda (147 para 153); gabarito revisado em 7 casos; consertos de grounding tirados da rodada final (R:907-919) | amostra de 48 e `final-2026-10-17` | mudança de métrica e de gabarito |
| 20/10 | variância: três repetições de A5 dão 22, 23 e 24 (R:988-991) | 48 | **medida controlada** |
| 22/10 | `amostra_harness` (30) tirada de `final-2026-10-17` | hipóteses daquela rodada | ajuste no conjunto de medida |
| 31/10 | A5 em inglês adotada (23 e 22, R:1162-1164) | 48 | seleção de prompt |

**Contagem [F, subagente]:** pelo menos 12 decisões de pipeline tomadas com base nos conjuntos da V2 (20, 50/48, 277, 30). O plano `PLANO_2026-10-19.md:71` diz que "o teste fora da amostra da dissertação fica com a V2 (289 bugs)". Isso **não se sustenta**, porque os 289 foram usados para ajustar o pipeline.

**Exploratório e controlado:**
- **Controladas:** F4 (repair contra resample, 3 réplicas cada), ESBMC 8.5.0 contra master (specs gravadas), F27 (três repetições).
- **Exploratórias ou inválidas para causa:** todas as comparações entre rodadas finais (`final-10-15` contra `final-10-17`) e a métrica por união.

---

## 8. Métricas históricas: comparáveis e não comparáveis

| Métrica | Período | Comparável com | Não comparável com |
|---|---|---|---|
| confirmed_driver / abstraction | F1 a F3 | entre si, com ressalvas | tudo depois de 29/09 (o CONFIRMED mudou) |
| CONFIRMED com quebra no CPython | desde 29/09 | dentro do mesmo motor | F1 a F3 |
| Detecção "causa ou quebra" na amostra de 50 | F9 a F11 | variantes entre si (n=1 cada) | F21 em diante (gabarito novo) |
| Detecção `at_bug_line` com gabarito de causa e quebra | F21 a F27 | entre si (A5: 22 a 26 em 48) | F9 a F11 |
| `expressions_equivalent` novo | desde 19/10 | rodadas posteriores | anteriores (147 contra 153 na mesma rodada) |
| Métrica por união de rodadas | F14, F22 | nada (não é medida de uma rodada) | |
| Confirmados na rodada (pela linha) | F14 (12 a 14), F22 (13) | parcialmente, entre si | rodadas com outro ESBMC ou outro gabarito |
| Regra por função em dois níveis (14/11) | só os 47 | não aplicada aos BugsInPy | todas as métricas da V2 |

**[F]** O `manifest.json` de `bugs_reais` não tem `expected_type`, então a regra atual dos 47 ("apontado e reproduzido") **não pode ser aplicada** aos BugsInPy sem rotular a exceção esperada.

---

## 9. Riscos de contaminação e viés

| Risco | Evidência | Gravidade | Classe |
|---|---|---|---|
| Uso no desenvolvimento | 12 ou mais decisões tomadas nos mesmos dados (seção 7) | alta | [F] |
| Seleção pelo sucesso do ESBMC (coorte à mão) | README de `bugs_reais`, passo 6 | alta para a coorte à mão | [F] |
| Subconjuntos escolhidos por resultados anteriores | `conjunto_dificil`, alvos F13, `amostra_harness` | alta para essas medidas | [F] |
| Contaminação do modelo | BugsInPy é de 2020 e os projetos são populares | média a alta | **risco, não prova** [H] |
| Rótulos automáticos sem revisão | 174 `pending`; 136 `unclassified` | média | [F] |
| Duplicações e agrupamento | 16 grupos com a mesma função; pandas com 24%; matplotlib 16/17/io_real_01 | média | [F] |
| Viés para bugs localizados | critério "uma única função" na coleta | baixa a média; limita a generalização | [F] |
| Seleção de prompt com n=1 | F9, F21 | média | [F] |

**Exposição indireta [I]:** mesmo os bugs automáticos que nunca motivaram uma decisão específica passaram pela detecção completa e entraram nas rodadas usadas para escolher regras (F14, F22). A exposição existe mesmo sem uma decisão nomeada.

---

## 10. O que os resultados permitem afirmar

**Permitido [F]:**
- A coleta automática do BugsInPy aceitou 199 de 418 bugs pelo critério de patch numa única função, e 174 viraram rótulo automático.
- Pela leitura dos patches, 64% dos 259 bugs BugsInPy são de valor errado, sem exceção. Só 25% são exceções alcançáveis em princípio pelo ESBMC-Python sem oráculo de valor.
- Na amostra de desenvolvimento de 48 casos, a detecção A1+A2 na linha do bug variou de 22 a 26 entre repetições da mesma configuração.
- Nas rodadas completas de outubro, poucos bugs chegaram a CONFIRMED: de 4 a 5 em 04 e 05/10, e 13 na rodada pela linha em 17/10.

**Não permitido:**
- Usar os BugsInPy como teste independente ou "fora da amostra".
- Comparar números de setembro, outubro e novembro como evolução do pipeline.
- Falar em taxas de precisão, recall ou falso positivo.
- Afirmar que o modelo não conhecia os bugs.
- Contar matplotlib 16, 17 e `io_real_01` como três observações independentes.

---

## 11. O que pode entrar no artigo de CPS e o que fica para o mestrado

**Pode entrar no artigo de CPS (como contexto, não como resultado principal):**
1. **Motivação para o recorte em exceções:** 64% dos BugsInPy são de valor errado, e a seleção dos 47 privilegia exceções locais.
2. **História do desenvolvimento em uma frase:** o pipeline foi desenvolvido e ajustado em bugs do BugsInPy e depois aplicado aos 47 de CPS, que também acabaram usados no ajuste.
3. **Variação da detecção** (22 a 26 em 48, repetições iguais), como evidência de que diferenças pequenas não são confiáveis.

**Reservado para o mestrado:**
- Avaliação no BugsInPy com a regra por função, o que exige rotular `expected_type`.
- Revisão dos 174 rótulos automáticos.
- Comparação de prompts e modelos.
- Um conjunto BugsInPy limpo, por exemplo os 219 recusados ou bugs novos, não serve como teste do mesmo pipeline sem uma regra pré-registrada.
- Análise de contaminação.

---

## 12. Recomendações de baixo custo para a documentação (sem LLM)

1. **Escrever no `dataset/bugs_reais/README.md` que a coorte à mão foi selecionada por `VERIFICATION FAILED` em harness manual,** e que o dataset inteiro é de desenvolvimento.
2. **Corrigir `PLANO_2026-10-19.md:71`** ("teste fora da amostra fica com a V2"), ou anotar ao lado que deixou de valer.
3. **Marcar os grupos duplicados** (matplotlib 16/17 com `io_real_01`, e os 16 grupos com a mesma função) num campo `grupo` do manifesto.
4. **Criar `dataset/bugs_reais/USO.md`** com a matriz bug × rodada. A matriz é recalculável por um script de leitura dos `artifacts/v2/*/` (o desta auditoria ficou no scratchpad da sessão). O ideal é gravá-la como arquivo derivado, com a ressalva "mencionado não é executado".
5. **Registrar, para cada subconjunto,** se ele dependeu de resultado anterior (`conjunto_dificil`, `amostra_harness`, alvos F13). Isso cabe no campo `rule` que já existe.
6. **Registrar a composição da triagem de 20 (F7)** e a lista dos 45 alvos de F13, que não encontrei como arquivo.
7. **Atualizar o `README.md` de `bugs_reais`.** Ele ainda cita `harness_manual_0909/` com 123 arquivos e um desenho de setembro. Basta marcar o trecho como histórico, sem reescrever.
