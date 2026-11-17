# Auditoria 5: histórico experimental e comparabilidade (16/11/2026)

Documento de trabalho da Fernanda. Não é texto para orientador nem para banca.

Complementa três auditorias:
- `auditoria_pipeline_2026-11-16.md`: a Parte 4 tem a linha do tempo resumida e a Parte 6.2 tem a reavaliação das rodadas dos 47;
- `auditoria_0_inventario_2026-11-16.md`;
- `auditoria_1_bugsinpy_2026-11-16.md`: matriz por família de rodada da V2 e decisões tomadas nos dados.

O que já está nessas três não é repetido aqui. Este documento aprofunda o que faltava em quatro pontos: comparabilidade rodada a rodada, níveis de resultado separados, custos somados da telemetria e estimativa de custo de experimentos novos.

**Como foi feito.**
- **Quem fez e como.** Claude Code (Opus 5.5), sozinho, sem subagentes, só com leitura de arquivos.
- **Fontes lidas:** `docs/experimentos/README.md` inteiro (1823 linhas), `ESBMC_VERSOES.md`, `REGISTRO_MODELOS_TOKENS.md`, `cronologia_desde_congelamento_2026-11-12.md`, `tabela_experimentos.md`, `mapa_dados.md`, `REGRA_DE_ACERTO_2026-11-14.md`, `consumo_tokens_2026-11-11.md`, as tags e o `git log`.
- **Contas feitas em memória com Python:**
  - soma de todos os `llm_telemetry.json` de `artifacts/pgene601/` e `artifacts/v2/`, e dos `telemetry_events` do checkpoint de 14/11;
  - reavaliação das seis rodadas dos 47 com `evaluate_functions` do próprio código, importado com `PYTHONDONTWRITEBYTECODE=1`;
  - pareamento de hipóteses entre rodadas.
- **O que não foi feito.** Nenhuma chamada de LLM, nenhum ESBMC, nenhum teste e nenhum arquivo gravado no repositório além deste. Os scripts de conta ficaram no scratchpad da sessão.
- **O que não foi conferido.** A pasta `/mnt/e` não foi lida, porque o disco já travou antes. Os scans ficam fora da conta de custo.

**Rótulos:** **[F]** fato verificado em arquivo ou artefato; **[I]** inferência; **[H]** hipótese a testar; **[NV]** não verificado.

---

## Parte 1. Achados novos (o que esta auditoria acrescenta)

1. **[F] Os tokens das rodadas anteriores a 11/11 não medem a entrada.** Nas rodadas de 06, 07, 08 e 09/11, `prompt_tokens` soma só 2.042 a 2.498 tokens na rodada inteira, porque o `claude_cli` só gravava a parte não cacheada. A correção veio no commit `6c91ba2` (11/11, 13:22). Nessas rodadas só valem o número de chamadas e os tokens de saída. Os "0,6 a 0,7 M tokens" que a telemetria mostra para elas **não podem ser comparados** com os 11,45 M de 16/11.
2. **[F] A telemetria de 06/11 e 07/11 inclui a detecção copiada.** As duas trazem 53 chamadas de detecção com exatamente 82.510 tokens de saída, os mesmos da rodada perdida de 05/11. A detecção não foi refeita nessas rodadas. Somar as três contaria a mesma detecção três vezes.
3. **[F] A rodada de 08/11 (pasta `rodada-final-2026-11-08`, terminou 09/11 às 03:49) não aparece na Parte 6.2 da auditoria do pipeline.** Pela regra atual ela dá **12 reproduzidos e 9 confirmados**. A linha "09/11" daquela tabela (12 e 8) corresponde à pasta `rodada-final-2026-11-09`, que terminou 09/11 às 22:49. As duas terminaram no mesmo dia, por isso o rótulo ficou ambíguo.
4. **[F] Com o replay estrito, o nível "confirmado" não muda em nenhuma das seis rodadas.** O replay estrito só aceita `status == "reproduced"` e não aceita falha fora da expressão.
   - Só o nível "reproduzido" cai: 13 para 11 em 16/11, 13 para 11 em 11/11, 12 para 11 em `rodada-final-2026-11-09`.
   - É a variante (a) da análise de sensibilidade pedida no P1 da auditoria do pipeline, já feita aqui.
5. **[F] A detecção nos 47, medida na expressão equivalente, quase não varia entre rodadas.** São 38, 36, 37, 37 e 36 bugs em cinco detecções independentes (05/11, 08/11, 09/11, 11/11 e 16/11), pelo campo `evaluation.detection_by_location.expression_equivalent` de cada relatório.
   - O que varia entre rodadas é a verificação, não a detecção.
   - Ressalva [I]: o prompt A2 mudou entre 05/11 e 08/11, então isso não é uma medida de ruído com configuração fixa.
6. **[F] Os relatórios gravam campos chamados `precision` e `fp`, e o README os cita** ("recall 80,9%, precisão 28,4%" em 06/11, README l. 1592-1593). Sem negativos, esse `fp` conta hipóteses que não estão na expressão rotulada, não alarmes falsos. Esses números não podem ir para o artigo como precisão.
7. **[F] A queda de custo de 11/11 (US$ 145) para 16/11 (US$ 42) tem pelo menos quatro causas possíveis ao mesmo tempo:**
   - a regra que encerra o reparo (`f55cc5a`);
   - o pulo de reparo para recusas sem contorno (`733bbfb`, 12/11);
   - o modo isolado do CLI (`7960acc`, 13/11): a entrada média por chamada de detecção caiu de 60,9 mil para 36,6 mil tokens;
   - o ESBMC novo.

   Nenhuma delas pode receber o crédito sozinha.
8. **[F] Os binários do ESBMC das rodadas antigas não foram guardados.**
   - O README diz que o binário `d520a903ae` ficou em `~/esbmc-bin/esbmc-d520a903ae` (l. 1560). Hoje a pasta só tem `build-451f54cab6.log`.
   - `~/esbmc-releases` (v8.6, usada em outubro) não existe mais.
   - Por isso nenhuma reverificação "sem LLM" de outubro ou de 06 a 11/11 pode ser refeita com o mesmo binário.
9. **[F] O commit do ESBMC de 11/11 e o de 14/11 não estão nas pastas das rodadas.** Para 11/11 a cronologia diz `b1b4d6ccf9`. Para 14/11, a linha `fbaf8089b9` do `ESBMC_VERSOES.md` foi registrada às 20:43 UTC, mas a rodada começou antes de 11:11 UTC. **[NV]** qual binário a rodada de 14/11 usou.
10. **[F] A rodada `agente-teste-2026-11-16` tem 54 chamadas, 1,09 M tokens e US$ 4,36 estimados pelo CLI.**
    - Ela cobre 3 bugs (cantools_595, mavproxy_989, minimqtt_5) e ficou com estado `running`.
    - Usou `healing.py` modificado e não commitado (`commit.txt` da pasta lista o `git status`).
    - Não está registrada no README.

---

## Parte 2. Linha do tempo experimental

### 2.1 Fases da V2 em setembro e outubro (BugsInPy e coorte à mão)

Colunas: pergunta (P), conjunto, código, prompt e modelo, ESBMC, avaliador, número de execuções (n), onde estão os dados brutos e classe. "R:" indica a linha do `docs/experimentos/README.md`.

| # | Data | Experimento (pasta) | P | Conjunto | Código | Prompt / modelo | ESBMC | Avaliador | n | Dados brutos | Classe |
|---|---|---|---|---|---|---|---|---|---:|---|---|
| E1 | 02 a 08/09 | `driver-slice-117-rerun`, `end-to-end-117` (R:53-62) | a LLM escrevendo o harness confirma bugs? | 117 hipóteses do gabarito; 104 arquivos | b0a112e a 831c344 | scan; gpt-4o-mini, síntese Codex | 8.5.0 | `confirmed_driver` | 2 | `docs/experimentos/fase-1/` | exploratório; métrica abandonada |
| E2 | 11 a 22/09 | 10 rodadas `e2e-*` (R:64-80) | quais backends funcionam? | 3, 40, 97 ou 121 arquivos | 8d05475 a 50f0fdf | gpt-4o-mini, Gemini 2.5/3.x, Claude CLI, qwen | 8.5.0 | `confirmed_driver` | 10, várias incompletas por cota | `fase-2/` | exploratório; comparação entre modelos inválida (entradas e completude diferentes) |
| E3 | 25 a 28/09 | `e2e-2026-09-27/28-*`, `fp12-*` (R:82-92) | detecção em estágios ajuda? | 97 | de3c35f a 064af9e | gpt-4o-mini, gpt-4.1-mini, Codex | 8.5.0 | idem | 9 | `fase-3/` | exploratório |
| E4 | 29/09 | `exp-oracle-repair` ×3, `-resample` ×3, `-fixed` (R:99-104) | reparo guiado pelo erro do ESBMC ajuda? | 125 hipóteses do gabarito | 4d73e76 a 6dc6845 | spec JSON; gpt-4o-mini | 8.5.0 | CONFIRMED com CPython | 7 | `fase-4/` | **controlada** (um fator, 3 réplicas) |
| E5 | 29 e 30/09 | `exp-oracle-repair-cobertura` e controle (R:108-117) | regras de recorte aumentam confirmações? | 125 | 76135ea, 1095afa | idem | 8.5.0 | idem | 2 | `fase-5/` | parcialmente controlada (antes e depois, n=1) |
| E6 | 01/10 | `engine-2026-10-01` e `-fixed` (R:120-126) | o motor novo destrava casos sem LLM? | specs gravadas, 125 | f7819c2 a 2aa34a6 | sem LLM | 8.5.0 | idem | 2 | `fase-6/` | **controlada** (sem LLM, só o motor muda) |
| E7 | 04/10 | `triage-2026-10-04-sonnet-20` e `-prompt2` (R:151-171) | prompt sem categoria | 20 sorteados (semente 42) | 01a289f, + não commitado | A0; Sonnet CLI | 8.5.0 | função e linha | 2 | `fase-7/` | exploratório; ajuste nos mesmos 20 |
| E8 | 04 a 06/10 | `full-2026-10-04-sonnet`, `-regrounded`, `control-fixed` (R:190-237) | primeiro número ponta a ponta | 277 | 02d5785 (+ retomada) | A0; Sonnet CLI | 8.5.0 | linha e CONFIRMED | 1 + reaplicação | `fase-7/`, `fase-8/` | descritiva; `-regrounded` reaproveita a detecção (parcialmente controlada) |
| E9 | 05 e 06/10 | `agent-2026-10-05-sonnet`, `agent-2026-10-06-e2e` (R:211-259) | o agente destrava casos? | 28 escolhidos pelo gabarito; 82 de 156 | 48a3b67, fcf3611 | agente Sonnet | 8.5.0 | CONFIRMED | 2, uma parada | `fase-8/` | exploratório; seleção pelo gabarito |
| E10 | 06/10 | F9: `det-2026-10-06-amostra-*` (R:283-305) | qual variante de prompt detecta mais? | amostra de 50 | ~5f96e8a | A0 (×2), A1, A2, A3, A5, A6; Sonnet | não usa | "causa ou quebra" | 1 por variante | `fase-9/`, `comparacao-variantes.json` | parcialmente controlada |
| E11 | 06 a 09/10 | F10: `orq-*`, `audit-2026-10-09`, `regress-2026-10-09`, `solver-profiles` (R:308-401) | busca no CPython, auditoria dos 7, regressão | 20 difíceis; 229; 23; 14 | aff456c, 72a1989 | sem LLM (e 5 casos com agente) | 8.5.0 | FUZZ_FOUND; CONFIRMED | ~10 | `fase-10/` | regressão 23/23: controlada; rota: exploratória |
| E12 | 12/10 | F11: A7 a A11 (R:414-434) | técnicas sobre a A5 | 50 | não commitado | A5 + A7..A11 | não usa | causa ou quebra | 1 cada | `artifacts/v2/det-2026-10-12-*` | parcialmente controlada |
| E13 | 12/10 | 8.5.0 contra master `333d07cc8a` (R:443-470) | o ESBMC novo muda vereditos? | 232 specs gravadas | não commitado | sem LLM | master; 1ª rodada com flags erradas (não vale) | CONFIRMED | 3 | `artifacts/v2/esbmc-master-*` | **controlada** depois da correção das flags |
| E14 | 12 a 14/10 | F12 e F13, lotes 1 a 5 (R:493-631) | regras de harness | 232 specs; 45 alvos do gabarito | não commitado | sem LLM | master 333d07cc8a | métrica 7 → 11 | ~12 | `artifacts/v2/esbmc-master-lote*` | sem LLM, mas regras escolhidas olhando os alvos; carga da máquina confunde o lote 4 |
| E15 | 14 e 15/10 | `agent-anthropic-*` (R:632-656) | agente pela API | 5; 39 alvos | não commitado | agente Sonnet API | master | CONFIRMED | 2 | `artifacts/v2/agent-anthropic-*` | exploratório |
| E16 | 15/10 | F14: `final-2026-10-15`, `-codex` (R:690-731) | rodada final com o harness congelado | 277 | `88ad57a` (tag `harness-freeze-2026-10-15`) | A5; spec mista Sonnet e Codex | master 333d07cc8a | **união de rodadas** (12 → 14) | 1, incompleta (114 PIPELINE_ERROR) | `artifacts/v2/final-2026-10-15*` | inválida como medida única |
| E17 | 16 e 17/10 | F15 a F20, `semana3-base/novo` (R:733-838) | itens do plano, sem rodada de LLM | 35 hipóteses | a1fccb4 | sem LLM | v8.6 | veredito 7 → 8 | 2 | `artifacts/v2/semana3-*` | controlada sem LLM |
| E18 | 17/10 | F21: A9, A13, A14 (R:840-856) | variantes novas | 50 | ~8945f97 | A5 + A9/A13/A14 | não usa | `at_bug_line` (gabarito novo) | 1 cada | `artifacts/v2/det-2026-10-17-*` | parcialmente controlada |
| E19 | 17 a 19/10 | F22: `final-2026-10-17` (R:858-899) | rodada final do item 6 | 289 (277 arquivos) | 7a3ab0e | A1,A2,A15; Sonnet | v8.6 | 13 na rodada; **17 pela união** | 1 (4 tentativas) | `artifacts/v2/final-2026-10-17/` | descritiva; a união é inválida |
| E20 | 19 e 20/10 | F23 a F25: self-healing, alucinação (R:901-959) | o healing destrava? | 4, 7 e 10 casos; 1263 hipóteses | d7c18ff antes | Sonnet | master 5d17828 | CONFIRMED; AST | ~5 | `artifacts/v2/self-healing-piloto-*`, `alucinacao-*` | exploratório |
| E21 | 20/10 | F26: juiz LLM, A12, A16 (R:961-984) | filtros e variantes | 48 | d7c18ff | Sonnet | não usa | `at_bug_line` | 1 cada | `artifacts/v2/juiz-*`, `det-2026-10-20*` | parcialmente controlada |
| E22 | 20/10 | F27: `det-2026-10-20-sc1..3` (R:986-1001) | quanto a detecção varia? | 48 | d7c18ff | A5; Sonnet | não usa | `at_bug_line` | 3 | `artifacts/v2/det-2026-10-20-sc*` | **controlada** (variância) |
| E23 | 22 a 29/10 | F28 a F30, S6 (R:1003-1153) | agente com portão de fidelidade | 5; 30 | 702c38a, eacaa0d, 4a4f9a0 | agente Sonnet | master 4a356e33eb e outros | CONFIRMED | 5 | `artifacts/v2/teste-ab-*`, `tarefa10-*`, `s6-*` | exploratório; S6 base contra grafo: n=1, quedas de rede |
| E24 | 31/10 | A5 em inglês r1 e r2 (R:1155-1165) | o idioma muda a detecção? | 48 | 957461d | A5 EN | não usa | `at_bug_line` | 2 | `artifacts/v2/det-2026-10-31-*` | controlada contra a faixa da A5 PT (data e modelo hospedado diferentes) |
| E25 | 31/10 | PyAthena semeado (R:1296-1306) | o scan acha bug semeado? | 3 sementes | bcde343 | Sonnet | | REPRODUCED_CPYTHON | 4, duas falharam | `artifacts/semeado/` | inválido (limite da assinatura) |

### 2.2 Os 47 da disciplina (18/10 a 16/11)

| # | Data | Pasta (`artifacts/pgene601/`) | P | Código | Prompt | ESBMC | Detecção | Avaliador da época | n | Estado |
|---|---|---|---|---|---|---|---|---|---:|---|
| D1 | 18/10 | `sondas-2026-10-18`, `mypy-2026-10-18` | o ESBMC e o mypy lidam com os 47? | não registrado | não se aplica | não registrado | | linha | 1 | baseline e sondas |
| D2 | 02/11 | `e2e-2026-11-02` | primeira passada nos 47 | 6c13902 | A5 EN original | d520a903ae (no comando) | nova | `at_bug_line`: 36 de 47 | 1 | só a detecção vale (118 PIPELINE_ERROR) [F] |
| D3 | 02/11 | `gpt-5.4-mini-2026-11-02` | outro modelo | 6c13902 | | | | | 0 | falha de requisição (`api_budget.json`), não vale [F] |
| D4 | 03/11 | `codex-2026-11-03` | Codex na detecção | não registrado | A5 | | nova (gpt-6.1-sol) | 39 de 47 na linha | 1 | incompleta (`running`); só a detecção serve |
| D5 | 03/11 | `mypy-2026-11-03`, `pytest-2026-11-03` | baselines | 6c13902 | | | | ver Parte 8 | 1 cada | baselines |
| D6 | 03/11 | `melhorias-2026-11-03`, `synth-gabarito-2026-11-03`, `codex-pilot-2026-11-03` | timeout parcial, witness, spec pelo gabarito | working tree sobre 6c13902 | | d520a903ae, 0945ac9 | specs gravadas | caso a caso | vários | exploratórias; motivaram `be9a846` e `176ecb9` |
| D7 | 05/11 | `congelado-c-2026-11-05` | rodada do congelamento c | d553e97 | A2 original | ausente (build apagado) | nova | | 1 | inválida (105 ESBMC_ERROR) |
| D8 | 06/11 | `congelado-c-2026-11-06` | rodada do congelamento c | d553e97 (tag 11c, mesmo `src`) | A2 original | 39590bbd26 | **copiada de D7** | expressão: 5; função antiga: 8 | 1 | completa (4 tentativas); `auto_lessons: true` |
| D9 | 07/11 | `ajustes-2026-11-07` | efeito dos ajustes de 07/11 | d553e97 + diff de 7 arquivos | A2 original | 822227ff96 | **copiada de D8** | 5 e 8 | 1 | completa; caderno do commit, `auto_lessons: true` |
| D10 | 08/11 | `replay-`, `async-stub-`, `logger-heal-`, `prompt-a2-`, `prompt-a2b-2026-11-08`, `rodada-2026-11-08` | consertos e prompt em subconjuntos | não registrado | A2 e A2b | não registrado | parcial | | 6 | exploratórias; levaram à edição do A2 (`2b148ba`) |
| D11 | 08 e 09/11 | `rodada-final-2026-11-08` | pipeline depois dos consertos de 08/11 | 8579920 | **A2 editado** | 95f025adf4 | nova | 9 e 14 | 1 | completa (7 tentativas) |
| D12 | 09/11 | `rodada-subconjunto-2026-11-09` | subconjunto | a347d3d + alterações | | 8.6.0 | | não conferido | 1 | exploratória |
| D13 | 09/11 | `rodada-final-2026-11-09` | regras novas de 09/11 | a347d3d (mesmo `src` de 8579920) + patch de 12 arquivos | A2 editado | b76980aaa0 | nova | 9 e 14 | 1 | completa |
| D14 | 11 e 12/11 | `rodada-2026-11-11` | rodada no congelamento 11d | 63c9e42 (tag 11d) | A2 editado | b1b4d6ccf9 segundo a cronologia; **não está na pasta** | nova | 9 e 15 | 1 | completa (3 tentativas) |
| D15 | 14/11 | `ruido-2026-11-14-r1` | ruído entre repetições | e346b00 | A2 editado | [NV] | nova | | 1 | interrompida: 89 de 128 verificações, 6 limites de uso; não vale |
| D16 | 16/11 | `congelado-2026-11-16-r1` | rodada pré-registrada, perfil congelado | f086e22 (só doc depois da tag 11f) | A2 editado | de72a905e0, sha256 gravado | nova | **regra por função**: 13 e 8 | 1 | completa na 1ª tentativa |
| D17 | 16/11, noite | `agente-teste-2026-11-16` | agente no healing | f086e22 + `healing.py` não commitado | A2 editado | [NV] | nova, 3 bugs | | 1 | `running`; não registrada |

**Diferenças de código entre rodadas consecutivas dos 47** (arquivos de `src/` diferentes, `git diff --name-only`) **[F]:**
- D8 para D11: 13 arquivos;
- D11 para D13: 0 arquivos commitados, mais o patch de 12 arquivos;
- D13 para D14: 54 arquivos;
- D14 para D15: 36 arquivos;
- D15 para D16: 13 arquivos.

Todas as rodadas consecutivas mudam código, e quase todas mudam também o ESBMC.

---

## Parte 3. Matriz de comparabilidade

Classes:
- **C** controlada: um fator muda, os outros ficam;
- **PC** parcialmente controlada: um fator, mas n=1 ou outro fator fraco junto;
- **E** exploratória;
- **X** inadequada para inferência causal: vários fatores mudam juntos;
- **NV** não verificável: falta registro.

### 3.1 Comparações já feitas ou implícitas nos documentos

| Comparação | Fatores que mudam | O que fica fixo | Métrica | Resultado | Classe | Observação |
|---|---|---|---|---|---|---|
| E4: reparo contra nova amostragem | estratégia de spec | hipóteses, modelo, ESBMC | CONFIRMED por réplica | 3, 2, 3 contra 2, 2, 1 | C | 8 contra 5 em 375 hipóteses-réplica cada; Fisher bilateral p = 0,58: **efeito não demonstrado** [F, conta própria] |
| E6: motor novo sem LLM | motor | specs | hipóteses com veredito | 11 → 17 | C | uma execução; ESBMC determinístico, tempo pode oscilar perto de 180 s |
| E10: A5 contra A0 | prompt | amostra, modelo, código | bugs na linha (50) | 24 contra 15 e 17 | PC | a diferença passa da faixa de ruído medida depois (22 a 26), mas a A5 foi escolhida olhando a mesma amostra (otimismo de seleção) |
| E12, E18, E21: outras variantes | prompt | idem | idem | todas dentro ou abaixo de 22 a 26 | PC | n=1; "nenhuma melhora" é a leitura certa |
| E13: 8.5.0 contra master | ESBMC e flags | specs | CONFIRMED por hipótese | 6 → 7 | C | só depois de corrigir as flags; a 1ª reverificação não vale |
| E14: lotes de regras | regras | specs, ESBMC | métrica 7 → 11 | | PC | regras escolhidas nos 45 alvos medidos; o lote 4 sofreu carga da máquina e o lote 5 precisou de recheck |
| E16 e E19 contra outubro | tudo | | **união de rodadas** 12 → 14 → 17 | | X | a união soma rodadas; não é a medida de uma execução |
| E22: A5 ×3 | nada | tudo | bugs na linha (48) | 22, 23, 24 | C | é a única medida de variância da detecção, e está na V2, não nos 47 |
| E24: A5 EN contra PT | idioma | amostra, código | idem | 23 e 22 contra 22 a 26 | PC | datas diferentes; modelo hospedado sem versão fixa |
| S6 base contra grafo | ferramenta de grafo | amostra de 30 | bugs confirmados | 4 contra 4 | PC | n=1 por braço, quedas de rede refeitas |
| D2 Claude contra D4 Codex | modelo | 47, prompt | hipótese certa | 36 contra 39 | PC | n=1; o Codex não terminou a verificação |
| **D8 contra D9 (06 contra 07/11)** | ESBMC (55 commits) e diff do pipeline | **a mesma detecção** (120 hipóteses idênticas) | por hipótese e por bug | 95 de 120 hipóteses com o mesmo veredito; regra atual 6 → 5 | X | dois fatores juntos; por ter a detecção fixa, é o par mais limpo dos 47, mas não separa ESBMC de código |
| D9 contra D11 | código, ESBMC, A2, detecção nova | | expressão 5 → 9; regra atual 5 → 9 | | X | |
| D11 contra D13 | patch de 12 arquivos, ESBMC, detecção nova | | regra atual 9 → 8 | 70 de 89 hipóteses pareadas com o mesmo veredito | X | o README diz que as regras de 09/11 "não aumentaram os confirmados", mas não há como separar do ruído |
| D13 contra D14 ("ruído", `PLANO_2026-11-12:234`) | 54 arquivos, ESBMC, detecção nova | | regra atual 8 → 9 | 69 de 84 pareadas iguais | X | não é medida de ruído |
| D14 contra D16 | código (41 arquivos desde 63c9e42), ESBMC, isolamento do CLI, regra de reparo | | regra atual 9 → 8; custo US$ 145 → 42 | 66 de 84 pareadas iguais | X | ver achado 7 |
| D15 contra D16 (custo) | 13 arquivos, regra de reparo, ESBMC, isolamento [NV] | | tokens 28,4 M (parcial) contra 11,45 M | | X | o README já avisa isso (l. 1822) |
| Métrica antiga contra regra por função | definição | | 9 e 15 (11/11, antiga) contra 9 (atual) | | não é comparação de pipeline | só mostra o peso da definição |

### 3.2 Pares de hipóteses entre rodadas dos 47

O par é a mesma hipótese, com arquivo, função e expressão suspeita iguais **[F, conta própria]**.

| Par | Hipóteses (a, b) | Iguais | Mesmo veredito |
|---|---|---:|---:|
| 06/11 × 07/11 | 120, 120 | 120 | 95 |
| 07/11 × 08/11 | 120, 118 | 102 | 83 |
| 08/11 × 09/11 | 118, 106 | 89 | 70 |
| 09/11 × 11/11 | 106, 114 | 84 | 69 |
| 11/11 × 16/11 | 114, 105 | 84 | 66 |
| 06/11 × 16/11 | 120, 105 | 83 | 45 |

**Leitura [I].**
- A LLM repete cerca de 75 a 85% das hipóteses entre detecções novas.
- Mesmo com a hipótese igual, 15 a 25% mudam de veredito de uma rodada para outra. Entre 06/11 e 16/11, quase metade das hipóteses iguais mudou.
- A mudança vem da verificação (código, ESBMC, síntese não determinística) e não da detecção.
- A rodada r2 prevista em `rodar_47_ruido.sh` (verificação de novo, com a detecção fixa) é exatamente o experimento que separa "síntese não determinística" de "mudança de código".

---

## Parte 4. Métricas que mudaram de definição

| Data | Mudança | Efeito medido | Fonte |
|---|---|---|---|
| 29/09 | CONFIRMED passa a exigir quebra no CPython; `confirmed_driver` sai | F1 a F3 não comparáveis com nada depois | R:39-43 |
| 04/10 | sem categoria: a LLM decide `verifiable` | triagem vira métrica | R:47 |
| 06/10 | "causa ou quebra" na amostra de 50 | F9 a F11 | R:283 |
| 15/10 | controles `STUB_INDUCED` e `FIXED_ALSO_FAILS` no agente | ip_real_21 e bip_pandas_10 caem | R:647-656 |
| 15/10 | **métrica por união de rodadas** | 12 → 14 → 17 | R:719, R:837 |
| 16/10 | gabarito com `cause_expressions` e `crash_expressions` (289 itens) | `at_bug_line` muda | R:765-775 |
| 19/10 | `expressions_equivalent` aceita cabeçalhos e compostos | 147 → 153 bugs com hipótese na linha, na mesma rodada | R:907-909 |
| 19/10 | gabarito revisado em 7 casos; amostra 50 → 48 | A5: 24 e 26 | R:910-913 |
| 28/10 | `ESBMC_MISSED` por limite de laço vira `BOUND_INCONCLUSIVE` (`b31bf1f`) | | R:1069-1071 |
| 31/10 | nível `REPRODUCED_CPYTHON`, à parte | +1 bug por braço no S6 | R:1167-1194 |
| 03/11 | contraexemplo parcial em timeout vira CONFIRMED com replay (`be9a846`) | 1 CONFIRMED em 16/11 vem daí (auditoria do pipeline) | R:1441-1443 |
| 05/11 | "função alvo mantida" menos rígida | agente: 73 → 52 recusados; motor: 86 → 6 | R:1491-1550 |
| 05/11 | lições automáticas: resultado depende da ordem dos casos | todas as rodadas de 06 a 11/11 têm `auto_lessons: true` [F, `config`] | R:1471-1489 |
| 09/11 | replay aceita subconjunto seguro de `os` | amplia o que vale como evidência | R:1675-1684 |
| 09/11 | driver do replay consome geradores | pythoncan_225 | R:1692-1697 |
| 11/11 | telemetria passa a contar cache e custo do CLI (`6c91ba2`) | tokens antes e depois não comparáveis (achado 1) | `git log` |
| 14/11 | **regra por função em dois níveis, com `expected_type`** | 11/11: 15 pela função antiga, 9 pela atual | `REGRA_DE_ACERTO_2026-11-14.md` |
| 14/11 | avaliador aceita `other_failure` dentro de `target_range` | +2 reproduzidos em 16/11 (achado 4) | `v2_evaluator.py:279-289` |
| esquema do replay | `target_range` existe em 25 de 123 resultados (06/11) e em 45 de 106 (16/11) | a regra da linha anterior se aplica menos nas rodadas antigas | [F, conta própria] |

**Contagem [F]:** a tabela tem 19 mudanças de definição ou de critério de evidência. A auditoria do pipeline falava em "pelo menos 13"; não conferi quais 13 eram, então não digo quais seriam as novas.

---

## Parte 5. Resultados por nível, rodada a rodada (os 47)

Tudo recalculado em memória a partir de `v2_verify_report.json` de cada pasta **[F]**. Cada coluna é uma rodada. **Nenhuma linha soma rodadas**, exceto a última, marcada como união.

### 5.1 Por bug (47)

| Nível | 06/11 (D8) | 07/11 (D9) | 08/11 (D11) | 09/11 (D13) | 11/11 (D14) | 16/11 (D16) |
|---|---:|---:|---:|---:|---:|---:|
| Apontado (função do rótulo) | 47 | 47 | 47 | **46** | 47 | 47 |
| Apontado e reproduzido, regra atual | 9 | 8 | 12 | 12 | 13 | 13 |
| Apontado e reproduzido, replay estrito | 9 | 8 | 12 | 11 | 11 | 11 |
| Confirmado pelo ESBMC, regra atual | 6 | 5 | 9 | 8 | 9 | 8 |
| Confirmado, replay estrito | 6 | 5 | 9 | 8 | 9 | 8 |
| Métrica antiga "pela função" (CONFIRMED no arquivo, sem exigir o tipo) | 8 | 8 | 14 | 14 | 15 | 13 |
| Métrica antiga "pela expressão" (CONFIRMED na expressão equivalente) | 5 | 5 | 9 | 9 | 9 | 8 |
| CONFIRMED na expressão exata | 2 | 2 | 4 | 4 | 4 | 5 |

Os 47 de "apontado" valem por construção: os arquivos de entrada só têm funções do rótulo.

Na métrica antiga "pela função", a coluna 16/11 (13) nunca foi publicada. É o `confirmed_by_location.file.tp` gravado pelo próprio pipeline.

**Bugs confirmados pela regra atual [F]:**
- **Nas seis rodadas:** blinka_434, gpiozero_716, paho_118, simpleio_43.
- **Em algumas:** pythoncan_1293 (06, 07, 08, 09 e 11/11; sai em 16/11), mavproxy_1572 (06, 08, 09 e 11/11), dronekit_890 (08, 11 e 16/11), gps_126 (08, 09, 11 e 16/11), ros2cli_1112 (08 e 09/11), gps_60 (11 e 16/11), pymodbus_2921 (só 16/11).
- **Reproduzidos sem confirmação naquela rodada:** opcua_671 e pycomm3_331 (nas seis), cantools_804 (09, 11 e 16/11), gps_60 (06 a 09/11; confirmado depois), ros2cli_646 (11/11), mavproxy_1447 e piouart_6 (16/11).

**União das seis rodadas (não é medida de uma execução):** 11 bugs confirmados em pelo menos uma rodada.

### 5.2 Por hipótese

| | 06/11 | 07/11 | 08/11 | 09/11 | 11/11 | 16/11 |
|---|---:|---:|---:|---:|---:|---:|
| Resultados | 123 | 123 | 119 | 109 | 116 | 106 |
| Hipóteses distintas (arquivo, função, expressão) | 120 | 120 | 118 | 106 | 114 | 105 |
| CONFIRMED | 9 | 9 | 17 | 14 | 15 | 13 |
| LLM_ONLY | 69 | 70 | 73 | 54 | 64 | 52 |
| Com healing | 86 | 84 | 83 | 71 | 80 | 66 |

### 5.3 Por expressão (detecção, antes do ESBMC)

| | 05/11 (usada em 06 e 07/11) | 08/11 | 09/11 | 11/11 | 16/11 |
|---|---:|---:|---:|---:|---:|
| Bugs com hipótese na expressão equivalente | 38 | 36 | 37 | 37 | 36 |
| Hipóteses fora da expressão rotulada (campo `fp`) | 96 | 92 | 77 | 93 | 78 |

O campo `fp` **não é** falso positivo. Ver o achado 6.

### 5.4 Por função irmã

A tabela "mesmo padrão em outra função" (`evaluate_functions`, `mesmo_padrao_em_outra_funcao`) existe no código. Não a recalculei rodada a rodada **[NV]**.

---

## Parte 6. O que influenciou mudanças no pipeline (só os 47)

A parte da V2 está na seção 7 da `auditoria_1`. Aqui fica só o que veio dos 47, em ordem.

| Data | Experimento de origem | Mudança | Ainda vigente em 16/11? |
|---|---|---|---|
| 03/11 | três harnesses GPS (D6) | timeout parcial (`be9a846`), witness por propriedade (`176ecb9`) | sim [I] |
| 03/11 | análise offline do Codex (D4) | limite de 12 hipóteses por função | não adotado (R:1390-1391) |
| 07/11 | erros de 06/11 (D8) | `%u` e constante de namespace (diff de D9) | sim [I] |
| 08/11 | subconjuntos de 08/11 (D10) | edição do A2 (`2b148ba`) e consertos de 08/11 | sim [F] |
| 09/11 | erros de D11 | `compat_bytearray`, bound menor depois de timeout, stub que substitui função, `os` no replay, gerador no replay, `piouart_6` | sim, em boa parte [I] |
| 14/11 | rodadas de 06 a 11/11 | regra de acerto por função | sim [F] |
| 16/11 | D13, D14 e D15 | regra que encerra o reparo (`f55cc5a`: "nas rodadas dos 47 bugs (09/11, 11/11, 14/11) a regra cortaria 55 a 60%") | sim [F] |
| 16/11 | `piouart_6` [I] | `fdf7178` (`Optional[int]` em `bytearray(n)`), commitado 3 h antes da rodada | sim [F] |

**Leitura [I]:** a rodada de 16/11 roda um pipeline calibrado nas rodadas D8 a D15. A rodada de 06/11 também não era limpa (ver o achado 4 da auditoria do pipeline). A tabela acima mostra que o ajuste continuou até poucas horas antes da rodada congelada.

---

## Parte 7. Reprodutibilidade e caráter exploratório

### 7.1 O que pode ser refeito

| Grupo | Reproduzível? | Por quê |
|---|---|---|
| Contagens a partir dos JSON (avaliação, funil, pareamento, este documento) | **sim** | os artefatos estão no disco e o avaliador está no código; o caso de `relatorio_bugs.py` (não commitado) está na auditoria do pipeline |
| Reverificação sem LLM a partir de specs gravadas (E6, E13, E14, E17) | **não exatamente** | os binários do ESBMC daquela época não foram guardados (achado 8); com outro binário vira outro experimento |
| Rodadas com LLM (todas) | **não** | modelo hospedado sem semente, sem temperatura e sem identificador de versão; o contexto do CLI não é gravado |
| Rodada de 16/11, verificação | **em parte** | o binário `de72a905e0` está em `/mnt/e` com sha256 gravado, mas o `~/esbmc-master` já avançou para `f389d9f2e6` (README l. 1823); se o build for recompilado no mesmo caminho, o binário se perde |
| Baselines mypy e pytest | **sim, em princípio** | versões gravadas (`mypy_version.txt`, `environment_versions.json`); os worktrees do pytest ficaram em `/tmp` [NV se ainda existem] |
| `artifacts/` em geral | **só nesta máquina** | `artifacts/` está no `.gitignore` [F]; só as fases 1 a 10 e um item da fase 11 foram arquivados em `docs/experimentos/fase-*` |

### 7.2 Exploratórios

São exploratórios E1 a E3, E7, E9, E11 (rota), E15, E20, E23, E25, D6, D10, D12 e D17. Também são todas as comparações entre D8 e D16 (Parte 3).

---

## Parte 8. Custos e tempos registrados

### 8.1 Os 47, por rodada

Soma de `llm_telemetry.json`; para 14/11, soma de `telemetry_events` do checkpoint **[F]**. US$ = estimativa informada pelo CLI (`cost_source: cli_reported`, `billing: assinatura`). Não houve cobrança.

| Rodada | Chamadas (det. + síntese) | Tokens totais | US$ estimado | Det.: chamadas, tokens, US$ | Síntese: chamadas, tokens, US$ | Horas somadas de chamada | Falhas |
|---|---|---:|---:|---|---|---:|---:|
| 02/11 | 73 + 153 | sub. | 0 | 73 | 153 (118 PIPELINE_ERROR) | 0,40 | 138 |
| 05/11 | 53 + 176 | sub. | 0 | 53 | 176 | 0,72 | 2 |
| 06/11 | 53* + 1158 | sub. (saída 0,73 M) | 0 | *copiada | 1158 | 3,10 | 9 |
| 07/11 | 53* + 926 | sub. (saída 0,59 M) | 0 | *copiada | 926 | 2,20 | 1 |
| 08/11 (D11) | 53 + 959 | sub. (saída 0,64 M) | 0 | 53 | 959 | 2,74 | 7 |
| 09/11 (D13) | 53 + 988 | sub. (saída 0,74 M) | 0 | 53 | 988 | 3,28 | 2 |
| 11/11 | 54 + 1055 | **48,12 M** | **145,08** | 54; 3,37 M; 8,28 | 1055; 44,75 M; 136,80 | 2,69 | 2 |
| 14/11 (parcial) | 53 + 589 | **28,36 M** | **89,42** | 53; 3,04 M; 8,17 | 589; 25,32 M; 81,25 | 2,54 | 14 |
| 16/11 | 53 + 507 | **11,45 M** | **42,04** | 53; 2,03 M; 4,44 | 507; 9,42 M; 37,61 | 1,54 | 1 |
| agente 16/11 (3 bugs) | 3 + 51 | 1,09 M | 4,36 | | | | |
| subconjuntos de 08/11 (5 pastas) | 50 + 319 | sub. | 0 | | | | |

"sub." = subcontado (achado 1). Para as rodadas antes de 11/11, só as chamadas e os tokens de saída valem.

**Tempo de relógio [F]:**
- **16/11:** de 13:11:17 (`commit.txt`) a 17:51:27 (`status.log`), cerca de 4 h 40 min, sem retomada.
- **Tempo somado por hipótese** (`results[].seconds`): 2,65 h em 06/11, 2,42 h em 07/11, 3,65 h em 08/11, 4,80 h em 09/11, 4,66 h em 11/11 e 3,46 h em 16/11.
- **Outras rodadas:** o relógio total não pode ser reconstruído com segurança, porque o `status.log` só registra o fim de cada tentativa.

**Inconsistência [F]:** em 16/11, `results[].llm_calls` soma 229, enquanto a telemetria tem 507 chamadas de síntese. A `consumo_tokens_2026-11-11.md` achou a mesma diferença em outubro. Não sei qual chamada fica fora de `llm_calls` [NV].

### 8.2 V2 (setembro e outubro)

Os 55 arquivos `llm_telemetry.json` de `artifacts/v2/` somam **12.473 chamadas e 6,67 M tokens de saída** **[F]**. Para o `claude_cli`, a entrada está subcontada e o custo é zero. Para OpenAI e Gemini, o custo não está registrado.

As únicas cobranças reais por token de que há registro são as do agente pela API Anthropic [F, tokens × US$ 2 e US$ 10 por milhão, como no README]:
- piloto: 33 chamadas, US$ 0,79;
- lote 5: 240 chamadas, US$ 11,96.

Os scans estão no `REGISTRO_MODELOS_TOKENS.md` e em `/mnt/e` [não somados aqui].

---

## Parte 9. Baselines

### 9.1 Existentes

| Baseline | Pasta | O que conta | Unidade | Resultado | Estado |
|---|---|---|---|---|---|
| mypy padrão | `mypy-2026-11-03` (e `mypy-2026-10-18`) | erro na linha do rótulo ou em `crash_expressions` | bug, por linha, sem tipo de exceção | 2/47 | [F] |
| mypy `--check-untyped-defs` | idem | idem | idem | 5/47; 3 com a mensagem certa; só 1 some na corrigida | [F] |
| testes do PR | `pytest-2026-11-03` | falha na versão com bug e passa na corrigida | bug, por comportamento; não exige a exceção (opcua_1955 falha por asserção de valor) | 10 de 11 com teste; 36 sem teste | [F] |
| LLM sozinha, na expressão | checkpoints das rodadas | hipótese na expressão equivalente | bug, por expressão, sem execução | 36 a 39/47 | [F] |
| LLM + harness + replay, sem prova do ESBMC | `congelado-2026-11-16-r1` | nível "apontado e reproduzido" | bug, por função, com tipo de exceção, no harness | 13/47 (11 no replay estrito) | [F]; não é baseline independente: usa a síntese e o healing, guiados pelo ESBMC |
| juiz do conserto | `scripts/juiz_conserto.py` | a entrada deixa de falhar na corrigida | | "4" citado no `PLANO_CODEX_3`, **sem arquivo de resultado** | [NV]; não rodou em 16/11 |
| controle nas corrigidas (V2) | `control-fixed-*`, `orq-*-control`, `exp-oracle-fixed*` | CONFIRMED na versão corrigida | hipótese | 0 a 1 por rodada (ir_real_03) | [F]; só na V2 |

### 9.2 As unidades são equivalentes? (pergunta 14)

**Não [F].**

| Método | Recebe | Unidade | Exige exceção? | Executa? | Denominador real |
|---|---|---|---|---|---|
| mypy | arquivo inteiro | linha | não | não | 47 |
| pytest do PR | projeto e teste da correção | teste | não | sim, no projeto real | 11 (36 sem teste) |
| LLM na expressão | só a função recortada | expressão | não | não | 47 |
| pipeline "reproduzido" | função recortada + harness | função | tipo igual | sim, no harness | 47 |
| pipeline "confirmado" | idem + ESBMC | função | tipo igual nos dois | sim, no harness | 47 |

**Três assimetrias impedem uma tabela "pipeline contra baselines" na mesma linha:**
1. **Informação de entrada.** O pipeline recebe a localização da função. O mypy recebe o arquivo, mas só conta na linha rotulada. O pytest recebe um teste escrito por quem já conhecia o bug.
2. **Critério.** mypy e LLM na expressão não exigem exceção; o pipeline exige o tipo; o pytest exige o comportamento do teste.
3. **Cobertura.** O pytest só tem 11 casos.

**Uma tabela honesta tem colunas por unidade** e deixa vazias as células que não existem, como já faz o `tabela-comparacao-parcial.md`.

**Recálculos possíveis sem LLM [I]:**
- mypy pela regra por função: erro em qualquer linha da função do rótulo, com e sem exigir que suma na corrigida;
- pytest restrito aos 11 casos, cruzando com os níveis do pipeline nesses mesmos 11.

### 9.3 Ausentes

- **LLM sozinha com a mesma pergunta e a mesma unidade:** detecção mais "qual exceção, com qual entrada", sem harness, avaliada pela regra por função.
- **Pipeline sem ESBMC:** harness e replay, sem a escada do ESBMC e sem o healing guiado por ele. É o que mediria o valor do ESBMC.
- **Pipeline sem healing** e **sem refinamento** na mesma configuração.
- **Outros analisadores:** pyright (há um `pyrightconfig.json` não rastreado, sem resultado nos 47 [F]), ruff/pylint e fuzzing (por exemplo, Hypothesis ou a própria busca do replay sem LLM).
- **Outro modelo** na configuração congelada. O D2 contra D4 foi só na detecção e com o Codex incompleto.
- **Detecção nas corrigidas e funções sem bug** (negativos), preparada (`scripts/deteccao_corrigidas.sh`) e nunca executada.

---

## Parte 10. É possível atribuir melhoria a algum componente? (pergunta 15)

| Afirmação possível | Evidência | Veredito |
|---|---|---|
| A5 detecta mais que A0 (V2) | E10 contra E22: 24 contra 15 e 17; a faixa da A5 é 22 a 26 | **sustentada só na amostra de desenvolvimento**, com otimismo de seleção |
| Variantes A7 a A16, A20 e o idioma não mudam a detecção | E12, E18, E21, E24 | sustentada como "nenhum efeito detectado" (n=1) |
| As regras de harness de outubro aumentaram confirmações | E14 sem LLM: 7 → 11 | atribuível às regras **nos specs medidos**; risco de sobreajuste (alvos do gabarito) |
| O ESBMC master melhorou | E13: 6 → 7 | atribuível (controlada), efeito de uma hipótese |
| Reparo guiado pelo erro é melhor que nova amostragem | E4: 8 contra 5, p = 0,58 | **não demonstrado** |
| O self-healing ajuda | não existe rodada sem healing na mesma configuração | **não atribuível** |
| A regra que encerra o reparo cortou custo sem perder confirmações | D14 contra D16: quatro fatores (achado 7); a simulação no commit é sobre rodadas antigas | **não atribuível** à regra; a simulação é uma estimativa, não uma medida |
| O pipeline melhorou de 06/11 para 16/11 | 6 → 8 pela regra atual; código, ESBMC, A2 e detecção mudam | **não atribuível**; diferença dentro da variação entre rodadas parecidas (2 a 3 bugs) |
| O replay barra falsos alarmes do ESBMC | V2: ip_real_14 e ir_real_03 em controles; 47: 5 bugs com ESBMC sem validação no CPython em 16/11 | sustentado como **descrição** (há casos barrados); a taxa não é mensurável sem negativos |

**Conclusão [I]:** a única atribuição causal defensável é a de mudanças medidas sem LLM sobre specs gravadas (E6, E13, E14, E17), e só para aquelas hipóteses. Nenhuma melhoria do pipeline de ponta a ponta nos 47 pode ser atribuída a um componente.

---

## Parte 11. Resultados confiáveis e resultados com ressalva

### 11.1 Confiáveis (com o enquadramento certo)

1. **16/11, pela regra pré-registrada:** 13/47 reproduzidos e 8/47 confirmados [F], rodada única, conjunto de desenvolvimento. Com o replay estrito: 11/47 e 8/47 [F].
2. **Quatro bugs confirmados em todas as seis rodadas completas** (blinka_434, gpiozero_716, paho_118, simpleio_43) [F]. É a evidência mais estável que existe.
3. **A detecção na expressão equivalente fica entre 36 e 38 de 47** em cinco detecções [F]. Com a ressalva da mudança do A2.
4. **Variância da detecção na V2:** 22 a 26 de 48 com a configuração fixa [F, E22].
5. **Funil do ESBMC em 16/11:** veredito em 40 de 105 hipóteses [F].
6. **Custo de 16/11:** 560 chamadas, 11,45 M tokens, US$ 42,04 estimados, 89% na síntese [F].
7. **Baselines mypy e pytest,** cada um na própria unidade [F].
8. **Comparações sem LLM com specs gravadas** (E6, E13, E17) e a regressão 23/23 de outubro [F].

### 11.2 Exigem ressalva

- **06/11 como "fora da amostra":** não é (auditoria do pipeline, achado 4), e a detecção é copiada de 05/11.
- **Números de 06 a 11/11:** cada um vale só como a medida daquela rodada. Usam `auto_lessons: true`, então o resultado de um caso depende dos anteriores (R:1287-1290). O `notebook_version` por caso não foi conferido [NV].
- **Métricas de outubro por união** (14, 17): não são medidas de uma rodada.
- **"Precisão" e "recall" gravados nos relatórios e citados no README:** inválidos sem negativos.
- **Tokens e custo de antes de 11/11:** subcontados.
- **14/11:** incompleta; o ESBMC é desconhecido.
- **Confirmações:** valem para o harness (auditoria do pipeline, Parte 7.2).
- **Juiz do conserto "4":** sem arquivo de resultado.

---

## Parte 12. Estimativa de custo de novos experimentos

**Base A**, a rodada de 16/11, é a única com a configuração atual e telemetria completa:
- total: US$ 42,04 / 47 bugs = **US$ 0,894 por bug**;
- detecção: US$ 4,44 / 53 chamadas = **US$ 0,0838 por chamada** (38,2 mil tokens por chamada); por bug, US$ 4,44 / 47 = US$ 0,0945;
- síntese: US$ 37,61 / 507 chamadas = **US$ 0,0742 por chamada** (18,6 mil tokens); 507 / 106 = 4,78 chamadas por hipótese; US$ 37,61 / 106 = **US$ 0,355 por hipótese**;
- hipóteses: 106 / 47 = 2,26 por bug, 106 / 53 = 2,0 por função;
- por bug confirmado: US$ 42,04 / 8 = US$ 5,26; por bug reproduzido: US$ 42,04 / 13 = US$ 3,23;
- relógio: 280 min / 47 = cerca de 6 min por bug, sem limite de uso.

**Base B**, a rodada de 11/11, serve de cenário pessimista: é o mesmo modelo antes da regra de reparo e do modo isolado:
- total: US$ 145,08 / 47 = **US$ 3,087 por bug**;
- detecção: US$ 8,28 / 54 = US$ 0,153 por chamada;
- síntese: US$ 136,80 / 1055 = US$ 0,130 por chamada; 9,09 chamadas por hipótese; US$ 136,80 / 116 = **US$ 1,18 por hipótese**.

A 14/11 (parcial) dá valores por chamada parecidos com os de B: US$ 0,154 na detecção e US$ 0,138 na síntese.

**Premissas [H]:**
- um conjunto novo tem a mesma distribuição de hipóteses por função;
- o pipeline fica igual ao de 16/11;
- os valores são estimativa do CLI, não cobrança.

**Duas coisas mudam a leitura dos valores [I]:**
- Pela assinatura, o limite real é a cota de uso. Na rodada de 14/11 ela estourou 6 vezes, e cada retomada espera 30 min.
- Pela API, o valor vira cobrança. A memória do projeto registra um crédito de US$ 100 para API [NV se o saldo atual é esse].

| Experimento | Conta (base A) | US$ (A) | US$ (B) | Tokens (A) | Relógio (A) |
|---|---|---:|---:|---:|---|
| r2 só verificação dos 47 (reaproveita a detecção de 16/11) | 1 × 37,61 | 37,61 | 136,80 | 9,4 M | ~4 h |
| r2 + r3 só verificação | 2 × 37,61 | 75,22 | 273,60 | 18,8 M | ~8 h |
| 2 rodadas completas novas (com a r1 já feita, ficam 3 detecções) | 2 × 42,04 | 84,08 | 290,16 | 22,9 M | ~9 h 20 min |
| 3 rodadas completas novas | 3 × 42,04 | 126,12 | 435,24 | 34,4 M | ~14 h |
| Detecção nas corrigidas, só detecção (53 funções [I]) | 53 × 0,0838 | 4,44 | 8,13 | 2,0 M | ~16 min |
| Idem ×3 | 3 × 4,44 | 13,32 | 24,38 | 6,1 M | ~50 min |
| Corrigidas com verificação (106 hipóteses supostas [H]) | 4,44 + 106 × 0,355 | 42,05 | 133,13 | ~11 M | ~4 h 40 min |
| Teste de 1 chamada do contexto do CLI | 1 × 0,0838 | 0,08 | 0,15 | 38 mil | minutos |
| LLM sozinha (só detecção, mesma unidade) ×3 | 3 × 4,44 | 13,32 | 24,38 | 6,1 M | ~50 min |
| Conjunto novo, N = 30, uma rodada | 30 × 0,894 | 26,83 | 92,60 | 7,3 M | ~3 h |
| N = 50, uma rodada | 50 × 0,894 | 44,72 | 154,34 | 12,2 M | ~5 h |
| N = 50, três rodadas | 3 × 44,72 | 134,17 | 463,02 | 36,5 M | ~15 h |
| N = 100, três rodadas | 3 × 89,45 | 268,34 | 926,04 | 73,1 M | ~30 h |
| Negativos: 1 função sem bug por bug, N = 50, uma rodada | 50 × (0,0838 + 2,0 × 0,355) | 39,69 | 125,60 | | ~4 h |
| Ablação sem healing nos 47 (verificação só) | ≤ 37,61 (o healing gasta síntese) | ≤ 37,61 | ≤ 136,80 | | ~4 h |
| Outro modelo | sem telemetria desse modelo nesta configuração | **não estimável** | | | |

**Pacote mínimo com LLM para a disciplina** (r2 + r3, corrigidas só detecção e teste de contexto): 75,22 + 4,44 + 0,08 = **US$ 79,74** (base A) ou 273,60 + 8,13 + 0,15 = **US$ 281,88** (base B).

---

## Parte 13. Experimentos mínimos para o artigo da disciplina CPS (entrega 30/11/2026)

São sugestões; a escolha é sua. Faltam 14 dias.

**Sem LLM (custo zero, podem ser feitos já):**
1. **Tabela de sensibilidade de 16/11:** regra atual 13/8; replay estrito 11/8 (já calculado aqui); sem o pymodbus_2921 (healing trocou o tipo): 13/7 [I, conta direta]; e a variante "exceção do ESBMC como única violação", ainda não calculada.
2. **Juiz do conserto em 16/11** (`scripts/juiz_conserto.py`), para ter o número com arquivo e não só o "4" citado.
3. **Baselines na mesma página, cada um na sua unidade.** Se quiser, acrescentar o mypy pela regra por função e o cruzamento dos 11 casos com pytest.
4. **Nível "LLM + harness + replay" (13) contra "confirmado" (8)**, com a ressalva de que o replay não é independente do ESBMC.
5. **Variação entre rodadas:** a tabela 5.1 e o pareamento 3.2, apresentados como rodadas exploratórias de configurações diferentes, nunca como réplicas.
6. **Datas dos PRs**, pela API do GitHub, sem LLM.
7. **Commitar** o resultado de 16/11 e o `relatorio_bugs.py`, e registrar a `agente-teste-2026-11-16`.

**Com LLM (opcional):**
- **r2 e r3** (só verificação): medem a variância da verificação na configuração congelada. É o que permite dizer se 8 é estável. US$ 75 (A) a US$ 274 (B).
- **Detecção nas corrigidas:** dá a primeira estimativa de quanto o detector aponta em código sem o bug. US$ 4,44 (A).
- **Teste de contexto de 1 chamada:** fecha a hipótese 10 da auditoria do pipeline. US$ 0,08.

Com isso, o artigo pode dizer, sem exagero:
- quanto o pipeline confirma numa rodada pré-registrada;
- quanto a verificação varia;
- como o resultado muda com a definição da métrica;
- como ele se situa ao lado de mypy e testes, em unidades explicadas.

---

## Parte 14. Experimentos essenciais para publicação futura

1. **Conjunto novo e independente:** regra de seleção escrita e commitada antes da primeira consulta, bugs corrigidos depois do corte do modelo, sem bônus para o que o ESBMC suporta. Com N = 50 e 3 rodadas, a estimativa é US$ 134 a US$ 463.
2. **Negativos:** funções sem bug do mesmo arquivo e versões corrigidas, para que precisão e falso positivo existam.
3. **Pelo menos 3 rodadas completas por configuração**, com análise pareada por bug (McNemar exato ou modelo misto com bug e projeto).
4. **Baselines na mesma unidade e com a mesma informação de entrada:**
   - LLM sozinha;
   - pipeline sem ESBMC;
   - mypy/pyright pela regra por função;
   - fuzzing simples;
   - testes, onde existirem.
5. **Ablações:** sem healing, sem refinamento, sem o nível de timeout parcial.
6. **Segundo modelo** na mesma configuração.
7. **Reprodutibilidade:**
   - modelo chamado pela API com parâmetros gravados;
   - contexto enviado gravado por chamada;
   - binário do ESBMC arquivado com sha256 (fora do caminho do build);
   - `git status` e versão do CLI em cada rodada.
8. **Segundo rotulador** numa amostra, com concordância.
9. **Prova de alcance pelo programa real** em uma amostra das confirmações.

---

## Parte 15. Perguntas que ficaram abertas

1. Qual binário do ESBMC a rodada de 14/11 usou?
2. Por que `llm_calls` (229) não fecha com a telemetria (507 de síntese) em 16/11?
3. O `notebook_version` mudou dentro das rodadas de 06 a 11/11 (lições automáticas ligadas)?
4. O juiz do conserto "4" veio de qual rodada e de qual comando?
5. As funções da detecção nas corrigidas são 53, como as com bug? (O script recorta pelo nome do rótulo, mas eu não contei.)
6. A rodada `agente-teste-2026-11-16` deve ser registrada como piloto ou descartada?

---

## Uso de IA neste documento

Este documento foi escrito pelo Claude Code (Opus 5.5) a pedido da Fernanda: leitura de arquivos, contas em memória e interpretação dos resultados. As classificações (controlada, exploratória etc.), os vereditos da Parte 10 e as sugestões das Partes 13 e 14 são interpretação da IA. Não são decisões da autora e precisam da revisão dela.
