# Registro de experimentos

Toda rodada do pipeline entra aqui: o que foi, quando, com qual código, com qual comando, onde está a
saída e o que deu. As saídas ficam em `artifacts/v2/<pasta>` (fora do git); este registro é a parte
versionada. Rodada nova = linha nova na tabela e seção nova abaixo, antes de discutir o resultado.

Os arquivos de cada rodada ficam em `fase-N/<pasta>/`: relatório, checkpoint (as respostas da LLM,
que permitem recalcular tudo sem chamá-la de novo), resultados do agente, telemetria, log e um
`resumo.json`. Os programas e harnesses gerados ficam só em `artifacts/` (cerca de 225 MB). Rodada
nova: `python scripts/archive_runs.py <pasta> --fase N`.

Código: o commit vigente quando a rodada começou. "+ não commitado (→ X)" quer dizer que a rodada usou
uma mudança que só depois virou o commit X.

Comando base da V2 (variações indicadas em cada rodada):

```
PYTHONPATH=src .venv/bin/python src/main.py --mode hybrid --v2-stage end-to-end \
  --input <entrada> --ground-truth dataset/bugs_reais/ground_truths.json \
  --verification-sources dataset/bugs_reais/arquivo_com_bug \
  --backend claude_cli --model claude-sonnet-5-5 --synth-backend claude_cli --synth-model claude-sonnet-5-5 \
  --bound 5 --timeout 180 --output-dir artifacts/v2/<pasta>
```

ESBMC: `/usr/local/bin/esbmc` 8.5.0 (release oficial). Limite de memória `ulimit -v 8000000`.

## Linha do tempo da V2

Cada fase é uma mudança no pipeline; as rodadas embaixo dela são as que mediram aquela versão. As
fases 1 a 3 usavam o motor antigo, em que a LLM escrevia o harness inteiro e não havia reexecução no
CPython: os "confirmados" daquela época (`confirmed_driver`, `confirmed_on_abstraction`) **não são
comparáveis** com os `CONFIRMED` de hoje. As auditorias de 09/09 e 28/09 acharam harnesses com
asserção tautológica e confirmações só na abstração, e por isso a confirmação passou a exigir que o
código original quebre no CPython (fase 4).

| Fase | Período | Mudança no pipeline | Commits principais |
|---|---|---|---|
| 1 | 01 a 09/09 | modo `scan`: a LLM sintetiza o harness inteiro (escalar, driver, recorte); filtros de tautologia | b0a112e, fc9a07f, fea37e1, 6ee8821, 831c344 |
| 2 | 10 a 22/09 | `hybrid` vira o pipeline V2 principal; dataset auditado; backends Gemini, Claude CLI e Ollama; só categorias formais | 8d05475, b5a726d, 423df64, 50f0fdf |
| 3 | 25 a 28/09 | detecção em estágios e com evidência; 4 estratégias de harness como categoria; rejeita artefatos do verificador | de3c35f, d9a2455, 064af9e |
| 4 | 29/09 | **motor `verify`**: a LLM só dá tipos em JSON, harness montado pelo código, stubs de biblioteca, reexecução no CPython; agente experimental | 4d73e76, 1811867, 6d534cd, 2b7aef1, 6dc6845 |
| 5 | 29 a 30/09 | cobertura do harness: regras gerais de recorte; correções da revisão | 76135ea, 1095afa |
| 6 | 01/10 | oráculo do ESBMC decide o que vira stub; limites maiores e troca de solver; reexecução com o contraexemplo; agente vira nível 2 | f7819c2, 463b0fd, 58e052b, 2aa34a6 |
| 7 | 01 a 04/10 | dataset com 289 bugs; `failure_kind` e `crash_expressions`; **sem categoria**: a LLM decide o que vai ao ESBMC; triagem | 55a653e, abe21dc, 5a8b31c, 01a289f, 1a4b70f, 190e3a4, 02d5785 |
| 8 | 05 a 06/10 | harness: imports aninhados, oráculo lê constante e classe base; aterramento aceita `if ...:`; ponteiro nulo em modelo; retomada refaz falhas de infraestrutura | ae3e7c7, 48a3b67, 4160200, fcf3611 |

### Fase 1: modo `scan`, a LLM escreve o harness (01 a 09/09)

| Data | Pasta | Modelo | Entrada | Resultado |
|---|---|---|---|---|
| 02/09 | `local_validation` | deepseek-r1-7b, glm-4.7-flash, qwen2.5-coder-7b, qwen3-coder-30b (Ollama) | `dz_real_01` | teste de viabilidade com modelos locais |
| 05/09 | `driver-slice-117-rerun` | gpt-4o-mini, síntese via Codex | 117 hipóteses do gabarito (`--v2-stage synthesis`) | 66 `confirmed_driver`, 15 na abstração, 20 seguros, 2 harness inválido |
| 08/09 | `end-to-end-117` | gpt-4o-mini, síntese via Codex | 104 arquivos, ponta a ponta | 100 hipóteses: 71 `confirmed_driver`, 14 na abstração |

Conclusão da época: números altos, mas a auditoria seguinte mostrou que muitos harnesses testavam uma
abstração escrita pela LLM, não o código real.

### Fase 2: `hybrid` como V2 principal, vários backends (10 a 22/09)

| Data | Pasta | Modelo | Entrada | Resultado |
|---|---|---|---|---|
| 11/09 | `e2e-smoke-gpt4o-mini` | gpt-4o-mini | 3 arquivos | 2 hipóteses, 2 confirmadas (teste de encanamento) |
| 11/09 | `e2e-gemini-smoke` | gemini-3.6-flash | 3 arquivos | 4 hipóteses, 3 confirmadas (teste de encanamento) |
| 11/09 | `e2e-gemini-40` | gemini-3.6-flash | 40 arquivos | incompleta (cota); 11 funções analisadas |
| 11/09 | `e2e-gemini-40-lite` | gemini-3.1-flash-lite | 40 arquivos | 70 hipóteses: 36 driver, 5 nativas, 10 na abstração, 12 seguras |
| 20/09 | `e2e-gemini-40-retry` | gemini-3.6-flash | 40 arquivos | incompleta (cota) |
| 21/09 | `e2e-claude-cli-40` | Claude via CLI | 40 arquivos | só detecção (48 funções, 46 achados) |
| 21/09 | `e2e-gemini-40-v2` | gemini-2.5-flash | 40 arquivos | detecção parcial (20 funções) |
| 22/09 | `e2e-ollama-40` | qwen2.5-coder:7b local | 40 arquivos | só detecção (37 funções, 71 achados) |
| 22/09 | `e2e-gemini-2026-09-22` | gemini-2.5-flash | 121 arquivos | detecção parcial (15 funções) |
| 22/09 | `e2e-gpt-4o-mini` | gpt-4o-mini | 97 arquivos | 147 hipóteses: 43 inconclusivas, 24 harness inválido, 29 na abstração, 9 driver, 6 nativas |

Conclusão: com o dataset auditado, as confirmações caíram e o "harness inválido" e o "inconclusivo"
dominaram; vários backends pararam por cota.

### Fase 3: detecção em estágios e estratégias de harness (25 a 28/09)

| Data | Pasta | Modelo | Entrada | Resultado |
|---|---|---|---|---|
| 27/09 | `e2e-2026-09-27-codex-single` | Codex CLI | 97 arquivos | incompleta |
| 27/09 | `e2e-2026-09-27-gpt-4.1-mini-single` | gpt-4.1-mini | 97 arquivos | incompleta (19 funções) |
| 28/09 | `e2e-2026-09-27-gpt-4o-mini-single` | gpt-4o-mini | 97 arquivos | 135 hipóteses: 34 inconclusivas, 33 harness inválido, 25 na abstração, 8 driver, 6 nativas |
| 28/09 | `e2e-2026-09-28-gpt-4o-mini-two-stage` | gpt-4o-mini | 97 arquivos, detecção em 2 estágios | interrompida (111 funções, 57 achados) |
| 28/09 | `fp12-new-pipeline`, `fp12-gpt4o-mini`, `fp12-gpt4o-mini-rerun`, `fp12-gpt4o-mini-full`, `fp12-invalid-gpt4o-mini-fixed` | gpt-4o-mini | subconjunto para investigar falsos positivos | a mais completa (`-full`): 20 hipóteses, 9 harness inválido, 3 driver, 2 na abstração |

Conclusão: o harness escrito pela LLM continuava inválido ou abstrato demais; decisão de trocar o motor.

### Fase 4: motor `verify` (29/09)

A LLM passa a dar só tipos em JSON; o código monta o harness; confirmação exige reexecução no CPython.
"Oráculo" = hipóteses tiradas do gabarito (mede só a verificação).

| Data | Pasta | O que foi | Resultado |
|---|---|---|---|
| 29/09 | `verify-2026-09-29-gpt-4o-mini-oracle` a `-r5` | ajustes sucessivos do motor, gpt-4o-mini, hipóteses do gabarito | r5 (125 hipóteses): 0 `CONFIRMED`, 7 `NOT_CONFIRMED`, 65 `UNSUPPORTED`, 26 dependência, 14 especificação |
| 29/09 | `agent-arm-smoke`, `agent-arm-2026-09-29-oracle` | agente (Claude Code + plugin ESBMC) nos casos em que o motor parava | 49 casos: 4 `CONFIRMED` (6 depois da reavaliação de 01/10) |
| 29/09 | `exp-2026-09-29-oracle-repair`, `exp-oracle-repair-rep2`, `-rep3` | reparo guiado pelo erro do ESBMC, 3 repetições | 3, 2 e 3 `CONFIRMED` |
| 29/09 | `exp-2026-09-29-oracle-resample`, `exp-oracle-resample-rep2`, `-rep3` | linha de base: pedir de novo sem o erro | 2, 2 e 1 `CONFIRMED` |
| 29/09 | `exp-2026-09-29-oracle-fixed` | controle nas versões corrigidas | 0 `CONFIRMED` |
| 29/09 | `verify-2026-09-29-gpt-4o-mini-e2e` | ponta a ponta com o motor novo | função 101, expressão equivalente 42; 1 `CONFIRMED` |

### Fase 5: cobertura do harness (29 a 30/09)

| Data | Pasta | O que foi | Resultado |
|---|---|---|---|
| 29/09 | `exp-oracle-repair-cobertura.pre-review` | regras gerais de recorte, antes da revisão de código | parcial: 3 `CONFIRMED` |
| 30/09 | `exp-oracle-repair-cobertura` | idem, depois das correções da revisão | 125 hipóteses: 3 `CONFIRMED`, 6 `NOT_CONFIRMED`, 72 `UNSUPPORTED`, 21 dependência |
| 30/09 | `exp-oracle-fixed-cobertura` | controle nas versões corrigidas | 0 `CONFIRMED` |
| 29/09 | `e2e-gpt-4o-mini-cobertura`, `e2e-gpt-5.5-cobertura` | ponta a ponta com a cobertura nova | incompletas (a de gpt-5.5 parou na detecção, 28 funções) |

Conclusão: a cobertura do harness não aumentou as confirmações (3 → 3); 11 "recusas do ESBMC" eram
erro do recorte ou dos stubs.

### Fase 6: oráculo do ESBMC e agente como nível 2 (01/10)

| Data | Pasta | O que foi | Resultado |
|---|---|---|---|
| 01/10 | `engine-2026-10-01` | especificações gravadas de 30/09 passadas pelo harness novo, sem LLM | 125 hipóteses: 3 `CONFIRMED`, 9 `NOT_CONFIRMED`, 76 `UNSUPPORTED`; com veredito 17 (eram 11) |
| 01/10 | `engine-fixed-2026-10-01` | controle nas versões corrigidas | 0 `CONFIRMED` |
| 01/10 | reavaliação de `agent-arm-2026-09-29-oracle` | harnesses do agente com a reexecução nova | `CONFIRMED` 4 → 6 |

Detalhes: `docs/projeto/harness_oraculo_esbmc_2026-10-01.md`.

## Fases 7 e 8 (04 a 06/10)

| Data | Pasta (`artifacts/v2/`) | O que foi | Código | Resultado principal |
|---|---|---|---|---|
| 04/10 | `triage-2026-10-04-sonnet-20` | teste do prompt sem categoria, 20 bugs | 01a289f | função 12/20, linha 3/20; segurou 6 de 8 que quebram |
| 04/10 | `agent-control-fixed-2026-10-04` | controle do agente nas versões corrigidas | 01a289f | 0 confirmações falsas (2 testáveis) |
| 04/10 | `triage-2026-10-04-sonnet-20-prompt2` | mesmo, com exceção de biblioteca valendo | + não commitado (→ 190e3a4) | mandou 4 de 5 que quebram; função 9/20 |
| 04/10 | `smoke-2026-10-04` | encanamento sem LLM, etapa 0 | 02d5785 | 204/289 prontos; 65/82 alcançáveis |
| 04/10 | `smoke-2026-10-04-esbmc` | encanamento sem LLM, etapa 1 (tipos chutados) | 02d5785 | 0 erros internos |
| 04 a 05/10 | `full-2026-10-04-sonnet` | **rodada grande**, nível 1, 277 arquivos | 02d5785 (+ retomada → ae3e7c7) | função 178/277, linha 82/277; 22 vereditos; 5 confirmados |
| 05/10 | `replay-2026-10-05-imports` | imports dentro de funções, sem LLM | + não commitado (→ 48a3b67) | erro de módulo some; +2 vereditos |
| 05/10 | `replay-2026-10-05-bases` | classe base ausente, sem LLM | + não commitado (→ 48a3b67) | erro de classe base some; 0 vereditos novos |
| 05 a 06/10 | `agent-2026-10-05-sonnet` | agente em 28 casos escolhidos pelo gabarito | 48a3b67 | 2 confirmados; 12/28 com veredito |
| 06/10 | `full-2026-10-05-regrounded` | rodada grande refeita nas 35 "expressão não encontrada" | + não commitado (→ 4160200) | 25 aterram de novo; +1 confirmado (falso alarme) |
| 06/10 | `agent-2026-10-05-sonnet-reverify.json` | reavaliação dos harnesses do agente, sem agente | + não commitado (→ fcf3611) | confirmados 2 → 4 |
| 06/10 | `control-fixed-2026-10-06` | controle do nível 1 nas versões corrigidas | + não commitado (→ 4160200, fcf3611) | 1 confirmação na versão corrigida (ir_real_03) |
| 06/10 | `replay-2026-10-06-nullrule` | regra do ponteiro nulo nos "seguro" do nível 1 | fcf3611 | nenhum veredito mudou |
| 06/10 em diante | `agent-2026-10-06-e2e` | **agente em todas as 156 travadas**, sem filtro | fcf3611 | parado em 82 de 156: 4 confirmações, nenhuma no bug do gabarito |

## Rodadas

### triage-2026-10-04-sonnet-20

- **Objetivo:** primeiro teste real do prompt V2 sem categoria (a LLM decide `verifiable`).
- **Entrada:** 20 bugs sorteados (semente 42): 10 que quebram (6 locais, 4 modeláveis) e 10 que não
  quebram (7 resultado errado, 3 não modeláveis). Lista: nm_real_25, bip_luigi_33, av_real_02,
  oob_real_09, bip_youtube_dl_21, bip_spacy_1, bip_pandas_142, bip_keras_3, bip_keras_25,
  vm_real_06, ip_real_24, bip_fastapi_9, tm_real_02, bip_tornado_5, bip_ansible_5, bip_ansible_3,
  bip_httpie_4, bip_pandas_102, bip_pandas_106, bip_pandas_35.
- **Comando:** base, com `--input` nos 20 arquivos de `funcao_com_bug/`.
- **Resultado:** função 12/20, linha 3/20 (6/20 depois do gabarito com `crash_expressions`). Dos 8
  que quebram e foram achados, mandou 2 e segurou 6 ("vem de biblioteca"). Verificação: 0 de 5 com
  veredito. 29 chamadas da LLM, 0 falhas.
- **Conclusão:** o prompt funciona, mas segura exceção de biblioteca; motivou 190e3a4.

### triage-2026-10-04-sonnet-20-prompt2

- **Objetivo:** mesmo teste com o prompt ajustado (exceção de biblioteca documentada conta).
- **Resultado:** mandou 4 de 5 que quebram; o que manda costuma ser outra quebra da mesma função.
  Função 9/20 (variação da LLM). Verificação: 1 de 11 com veredito.
- **Conclusão:** o gargalo é achar a linha exata; os mesmos 20 bugs inspiraram o ajuste, então o
  ganho aqui é otimista.

### agent-control-fixed-2026-10-04

- **Objetivo:** controle de confirmação falsa do nível 2 nas versões corrigidas.
- **Entrada:** os 6 bugs que o agente confirmou em 30/09; em 4 a linha do bug não existe na versão
  corrigida, então só `nm_real_12` e `ip_real_14` testam algo.
- **Comando:** `scripts/v2_agent_arm.py --report <entrada> --verification-sources dataset/bugs_reais/arquivo_corrigido`.
- **Resultado:** 0 confirmações falsas. `ip_real_14`: o ESBMC acusou `ZeroDivisionError` e o CPython
  não reproduziu (a reexecução barrou um falso positivo).

### smoke-2026-10-04 e smoke-2026-10-04-esbmc

- **Objetivo:** validar o encanamento nos 289 bugs antes da rodada grande, sem LLM.
- **Comando:** `scripts/v2_verify_smoke.py --out ...` (etapa 0) e com `--esbmc /usr/local/bin/esbmc --timeout 60` (etapa 1).
- **Resultado:** etapa 0: 204 prontos, 69 não suportados, 12 dependência, 4 aterramento (limites
  conhecidos: `async`, classe aninhada, nível de módulo). Etapa 1: 0 `PIPELINE_ERROR`; os vereditos
  não valem como resultado (tipos chutados).

### full-2026-10-04-sonnet (rodada grande)

- **Objetivo:** primeiro número ponta a ponta do pipeline sem categoria, nível 1.
- **Entrada:** `dataset/bugs_reais/funcao_com_bug` (277 arquivos; os 12 de contexto de patch ficam fora).
- **Comando:** base; lançado com `setsid nohup`, retomado com `--resume` depois do limite da
  assinatura (37 hipóteses) e de um timeout de rede (1 hipótese).
- **Resultado:**
  - detecção: arquivo 181/277, função 178/277 (64%), linha 82/277 (30%); 0 erros de detecção;
  - triagem (bugs achados na linha): mandou 43/45 dos que quebram, segurou 24/36 dos que não quebram;
  - verificação: 232 hipóteses, 22 com veredito do ESBMC, 5 `CONFIRMED` em 4 bugs (av_real_01,
    oob_real_01, oob_real_02 e bip_thefuck_11, este uma quebra fora do gabarito);
  - travadas: contexto do harness 115, LLM com expressão inexistente 44, ESBMC 49 (linguagem 27,
    falha interna 13, tempo 5, outros 4).

### replay-2026-10-05-imports e replay-2026-10-05-bases

- **Objetivo:** medir correções do harness sem LLM, reaproveitando os tipos da rodada grande.
- **Comando:** `scripts/v2_replay_specs.py artifacts/v2/full-2026-10-04-sonnet/v2_verify_report.json --esbmc /usr/local/bin/esbmc --timeout 180 --only <ids>`.
- **Resultado:** imports: 15 hipóteses, o erro de módulo some em todas, 2 ganham veredito. Classes
  base: 5 hipóteses, o erro some, todas param no limite seguinte do ESBMC.

### agent-2026-10-05-sonnet

- **Objetivo:** medir se mais contexto (agente, nível 2) destrava casos.
- **Entrada:** 28 hipóteses travadas no nível 1 que apontam a linha do bug do gabarito e são
  alcançáveis (escolha usa o gabarito: serve para medir o ganho de contexto, não como resultado
  ponta a ponta).
- **Comando:** `scripts/v2_agent_arm.py --report <entrada> --model claude-sonnet-5-5 --out ...`.
- **Resultado:** 12/28 com veredito, 2 `CONFIRMED` (ip_real_14, nm_real_14); 5 `ESBMC_MISSED`.
- **Reavaliação** (`agent-2026-10-05-sonnet-reverify.json`, `scripts/v2_agent_reverify.py`, com a
  regra do ponteiro nulo): 4 `CONFIRMED` (+ bip_luigi_21, bip_pandas_33). Falsos negativos do
  ESBMC restantes: av_real_03, bip_thefuck_4, tm_real_09, tm_real_10.

### full-2026-10-05-regrounded

- **Objetivo:** refazer as 35 hipóteses descartadas como "expressão não encontrada" com o
  aterramento que aceita `if ...:` e `;`.
- **Comando:** cópia de `full-2026-10-04-sonnet`, sem os 35 vereditos, e `--resume`.
- **Resultado:** 25 aterram; 1 vira `CONFIRMED` (ir_real_03, falso alarme: ver controle abaixo);
  as outras param no harness ou no ESBMC. Total do nível 1: 23 vereditos, 6 `CONFIRMED`.

### control-fixed-2026-10-06

- **Objetivo:** controle de confirmação falsa do nível 1 nas versões corrigidas.
- **Comando:** `scripts/v2_replay_specs.py artifacts/v2/full-2026-10-05-regrounded/v2_verify_report.json --sources dataset/bugs_reais/arquivo_corrigido --strict-sources`.
- **Resultado:** 1 `CONFIRMED` na versão corrigida: ir_real_03. A função recebe `pattern` e
  `pattern_len` separados e o chamador sempre passa `len(pattern)`; o harness os gera incoerentes.
  Limitação: a função é verificada sem o contrato de quem chama.

### replay-2026-10-06-nullrule

- **Objetivo:** ver se a regra do ponteiro nulo muda vereditos "seguro" do nível 1.
- **Resultado:** nenhuma das 9 hipóteses mudou. (O `scripts/v2_reverdict.py` não serve para isso: ele
  reexecuta sem os valores do contraexemplo e não refaz a leitura do ESBMC.)

### agent-2026-10-06-e2e (parado em 82 de 156)

- **Objetivo:** número ponta a ponta honesto do nível 2: agente em todas as hipóteses travadas no
  nível 1, sem usar o gabarito na escolha.
- **Entrada:** 156 hipóteses (as 184 travadas distintas menos as 28 já feitas em `agent-2026-10-05-sonnet`).
- **Comando:** `scripts/v2_agent_arm.py --report artifacts/v2/agent-2026-10-06-e2e/input_report.json --model claude-sonnet-5-5 --out artifacts/v2/agent-2026-10-06-e2e`.
- **Observação:** processos `esbmc` órfãos do agente acumularam memória (21 de 23 GB) e foram
  encerrados com `kill -9` em 06/10; corrigido em `procs.run_group` (o pipeline adota e mata os
  órfãos), que também pega os laços de espera que o agente deixava em segundo plano.
- **Resultado (parado em 06/10, 82 de 156):** UNSUPPORTED 29, UNVALIDATED 17, AGENT_FAILED 13,
  CONFIRMED 4, NOT_CONFIRMED 4, ESBMC_ERROR 4, MISSING_DEPENDENCY 4, ESBMC_TIMEOUT 3, ESBMC_MISSED 3,
  OTHER_FAILURE 1. As 4 confirmações (bip_fastapi_10, bip_matplotlib_16, bip_matplotlib_6,
  bip_youtube_dl_3) não estão na linha do bug do gabarito.
- **Decisão:** parado porque não acrescentava à métrica principal. Daqui em diante as mudanças de
  harness são medidas num conjunto fixo de casos difíceis, não em rodadas completas.

## Fase 9 (06/10): validação dos vereditos e variantes do prompt de detecção

Mudança no pipeline: ferramentas de validação (`scripts/v2_validate.py`), modo só detecção
(`--v2-stage detection`), variantes do prompt (`--v2-variants`), amostra fixa de 50 bugs para
comparar prompts (`dataset/bugs_reais/amostra_deteccao.json`) e conjunto fixo de 20 casos difíceis
para medir o harness (`dataset/bugs_reais/conjunto_dificil.json`). Branch `feat/validacao-deteccao`.

### Validação de `full-2026-10-05-regrounded` (`validation.json` na pasta da fase 8)

- **Comando:** `scripts/v2_validate.py artifacts/v2/full-2026-10-05-regrounded --control artifacts/v2/control-fixed-2026-10-06/report_0of1.json --mutants` (código 4a4d790).
- **Função preservada (V1):** 0 alteradas em 23 vereditos com programa. A primeira passada acusou 7,
  todos trocas do próprio recorte (`re.findall` virando o stub `_esbmc_re_findall`; `email.utils`
  virando `email_utils`); a checagem passou a aceitar esses nomes de stub (commits dd8303d e 4a4d790).
  A passada antiga ficou em `validation-v1-rigida.json`.
- **Vacuidade (V2):** 3 `NOT_CONFIRMED` eram vazios (o ESBMC não alcança a linha): as 3 hipóteses de
  `urljoin` (bip_youtube_dl_13 e 21), agora `NOT_CONFIRMED_VACUOUS`.
- **Controle (V3 natural):** 5 confirmações só na versão com bug; 1 nas duas (ir_real_03, falso alarme
  já conhecido); nenhuma só na corrigida.
- **Mutantes (V3):** 13 gerados, 0 contados. Os perto de linhas inalcançáveis não podem ser pegos, e
  nos outros a busca do CPython (4 entradas) não reproduz o que o ESBMC acha. Inconclusivo: é a
  Tarefa 1 do plano do orquestrador (busca aleatória no CPython).

### Variantes do prompt na amostra de 50 (`fase-9/comparacao-variantes.json`)

- **Comando:** `scripts/run_detection_variants.sh 2026-10-06-amostra dataset/bugs_reais/amostra_deteccao.json <variante>` (Claude Sonnet via `claude_cli`, cerca de 15 min por rodada); avaliação por `scripts/v2_union_detection.py --sample`, regra "causa ou quebra".
- A amostra: 30 resultado errado, 11 exceção local, 4 modeláveis, 4 não modeláveis, 1 incerto.

| Variante | Pasta (`artifacts/v2/`) | Função | Linha | Achados | Fora do bug |
|---|---|---|---|---|---|
| A0 base, rodada 1 | `full-2026-10-04-sonnet` (filtrada) | 34 | 15 | 60 | 44 |
| A0 base, rodada 2 | `det-2026-10-06-amostra-A0-r2` | 34 | 17 | 64 | 46 |
| A1 reportar sem contexto | `det-2026-10-06-amostra-A1` | 40 | 21 | 86 | 60 |
| A2 checklist de entradas | `det-2026-10-06-amostra-A2` | 40 | 20 | 82 | 57 |
| A3 até 5 hipóteses | `det-2026-10-06-amostra-A3` | 35 | 16 | 59 | 42 |
| A4 união das 2 bases | (as duas A0) | 36 | 19 | 76 | 55 |
| **A5 = A1 + A2** | `det-2026-10-06-amostra-A1,A2` | **44** | **24** | 101 | 72 |
| A6 qualquer comportamento errado | `det-2026-10-06-amostra-A6` | 35 | 16 | 55 | 37 |

- A base varia de 15 a 17 entre rodadas; A1 e A2 passam disso, e juntas (A5) somam: linha de ~16 para
  24 (+50%), função de 34 para 44, ao custo de mais achados fora do bug (de ~45 para 72), que a
  triagem e o ESBMC filtram.
- A3 não muda nada. A6 não acha mais, mas tem o menor ruído (37) e 7 de resultado errado contra 5 e 6
  da base: diferença pequena demais para 50 casos.
- Rodar a base duas vezes (A4) dá menos que A1 sozinho e custa o dobro.
- **Decisão:** A5 (A1 + A2) é a candidata a prompt padrão; a rodada completa com ela fica para o fim
  da etapa do harness, para medir detecção e confirmação juntas uma vez só.

## Fase 10 (06/10): orquestrador de harness e busca no CPython

Mudança no pipeline: a reexecução no CPython ganhou uma passada aleatória com semente fixa
(`concrete_replay(random_runs=, seed=)`); o braço dinâmico (`verify/dynamic.py`) roda essa busca no
programa já gerado de um caso travado; a rota (`verify/routing.py`) escolhe os braços pelo motivo do
travamento; o orquestrador (`verify/orchestrator.py`, `scripts/v2_orchestrate.py`) aplica a rota
sobre um relatório pronto. Código aff456c. `FUZZ_FOUND` é evidência dinâmica, contada à parte de
`CONFIRMED`. Especificação e plano: `docs/superpowers/{specs,plans}/2026-10-06-orquestrador-harness*`.

- **Rota dos 229 resultados distintos de `full-2026-10-05-regrounded`** (sem rodar nada): limite do
  ESBMC 140 (só a busca), falta de contexto 64 (agente Claude Code, depois a busca), harness ruim 10
  (agente API, depois Claude Code, depois a busca), já com veredito 15.

| Data | Pasta (`artifacts/v2/`) | O que foi | Resultado |
|---|---|---|---|
| 06/10 | `orq-2026-10-06-dyn-20` | só a busca, nos 20 casos difíceis (4 s) | 3 `FUZZ_FOUND` na linha do bug: dz_real_02, ip_real_22, oob_real_12 |
| 06/10 | `orq-2026-10-06-dyn-20-control` | o mesmo nas versões corrigidas | 0 na linha do bug |
| 06/10 | `orq-2026-10-06-dyn-all` | só a busca, em todos os resultados | 25 `FUZZ_FOUND`, 6 na linha do bug |
| 06/10 | `orq-2026-10-06-dyn-all-control` | o mesmo nas versões corrigidas | 16 `FUZZ_FOUND`, 1 na linha do bug (ip_real_17, que quebra nas duas) |
| 06/10 | `orq-2026-10-06-full-20` | rota completa nos 20 (agente API por `claude_cli`, agente Claude Code Sonnet; cerca de 30 min) | os agentes rodaram em 5 casos e não confirmaram nenhum; resultado igual ao `dyn-20` |

- **Comando:** `scripts/v2_orchestrate.py artifacts/v2/full-2026-10-05-regrounded/v2_verify_report.json --only-file dataset/bugs_reais/conjunto_dificil.json --arms dynamic[,api_agent,claude_agent] --out ...`; controle com `artifacts/v2/control-fixed-2026-10-06/report_0of1.json --verification-sources dataset/bugs_reais/arquivo_corrigido`.
- **Busca, comparando versão com bug e corrigida por hipótese:** 5 achados na linha do bug só na
  versão com bug (dz_real_02, ip_real_14, ip_real_22, oob_real_05, oob_real_12). Em dz_real_02 e
  oob_real_12 a versão corrigida roda e não quebra ali (evidência mais forte); nas outras 3 a versão
  corrigida não roda no CPython. ip_real_14 já era confirmado pelo agente; os outros 4 nenhum harness
  tinha alcançado. 15 achados fora da linha do bug aparecem nas duas versões: vêm dos stubs ou de
  outra quebra, não do bug.
- **Agentes nos 5 casos que a rota manda para eles:** ESBMC estourou o tempo (ansible_16), recusou
  construções (keras_33, keras_38, nm_real_04) ou o agente perdeu a expressão (dz_real_02). Nesta
  amostra o agente não acrescentou; o ganho do orquestrador veio da busca.
- **Correção da revisão (07/10):** os 6 achados na linha do bug vêm da busca exaustiva que já existia
  (5 na primeira execução); rodando de novo sem a passada aleatória, todos se repetem. A passada
  aleatória só acrescentou 2 achados fora da linha, que também aparecem nas versões corrigidas. O
  ganho veio de rodar o CPython nos casos travados, o que antes não acontecia, e não da passada nova.
  Na rodada, a passada aleatória ainda dividia o prazo com a exaustiva e quase não rodava (corrigido
  depois).
- **Correção da rota (07/10):** dos 140 casos que a rota mandava só para a busca, 62 eram recusa do
  ESBMC; 51 eram o harness por código desistindo (função aninhada, `*args`, decorador, stub sem tipo)
  e 17 falhas de aterramento, que um agente escrevendo o harness pode contornar. A rota passou a
  mandar esses 68 ao agente; harness já julgado ruim deixou de ir à busca. Rota nova nos 229:
  limite do ESBMC 72, falta de contexto 64, harness por código 51, aterramento 17, já com veredito 15,
  harness ruim 10.
- **`timeout900-2026-10-07`** (07/10): as 5 hipóteses `ESBMC_TIMEOUT` de novo com 900 s
  (`scripts/v2_replay_specs.py ... --timeout 900 --only <5 ids> --shard i/5`, `ulimit -v 4500000`).
  ip_real_22, oob_real_12 e oob_real_06 passaram a esgotar a memória; oob_real_03 na linha do bug deu
  OTHER_FAILURE (CPython quebra na linha 33, fora da hipótese); a outra hipótese de oob_real_03 deu
  CONFIRMED fora da linha do bug (a mesma quebra aparece na versão corrigida). Métrica principal
  inalterada (7): o limite é o tamanho da fórmula (strings livres em conjuntos), não o tempo.
- **Entrada fixada (`verify/pinned.py`, 08/10):** o ESBMC verifica só o caminho da entrada que a
  busca no CPython achou. Nos 20 casos difíceis (`orq-2026-10-08-pinned-20` com 180 s e
  `orq-2026-10-08-pinned-20-t600` com 600 s por solver): ip_real_22 e oob_real_12 estouram o tempo
  mesmo com a entrada fixada (o CPython reproduz a quebra com ela); oob_real_03 não tem entrada que
  quebre na linha do bug. Métrica principal inalterada (7). No ip_real_22 a causa foi isolada: um
  `for` sobre lista global com `in` aplicado a `None` não termina no ESBMC-Python, enquanto a mesma
  verificação sem o laço termina em 2 s (reprodutor 18 em `docs/projeto/possiveis_problemas`).
- **Achado do CPython só conta contra o controle:** `--control` no `v2_orchestrate.py` conta os achados
  na linha do bug que a versão corrigida não repete.

- **Auditoria do preparo do harness (08/10, base `72a1989`):** varredura das 229 hipóteses distintas e
  sondas locais no ESBMC 8.5.0, sem API. Métrica principal permanece 7. SMT durante execução
  simbólica terminou o reprodutor 18 em 10,26 s; padrão não terminou em 35 s. O ganho não se repetiu
  no `ip_real_22` completo nesse prazo. Literais diretos nos dois candidatos e recorte por escopo
  não demonstraram novas confirmações. Comandos, resultados e caminho de melhorias em
  [harness-audit-2026-10-08](fase-10/harness-audit-2026-10-08/README.md).

## Resultado consolidado (até 06/10)

Bugs do gabarito confirmados na linha (causa ou quebra), ESBMC mais CPython, função preservada:
**7** (av_real_01, oob_real_01, oob_real_02 pelo nível 1; bip_luigi_21, bip_pandas_33, ip_real_14,
nm_real_14 pelo agente). Confirmações fora do gabarito que dependem do contrato do chamador:
bip_thefuck_11, ir_real_03.

Evidência dinâmica (CPython quebra na linha do bug só na versão com bug, sem prova formal), fase 10:
dz_real_02, ip_real_22, oob_real_05, oob_real_12 (dz_real_02 e oob_real_12 com a versão corrigida
executada sem quebrar ali).
