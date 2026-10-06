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
| 06/10 em diante | `agent-2026-10-06-e2e` | **agente em todas as 156 travadas**, sem filtro | fcf3611 | em andamento |

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

### agent-2026-10-06-e2e (em andamento)

- **Objetivo:** número ponta a ponta honesto do nível 2: agente em todas as hipóteses travadas no
  nível 1, sem usar o gabarito na escolha.
- **Entrada:** 156 hipóteses (as 184 travadas distintas menos as 28 já feitas em `agent-2026-10-05-sonnet`).
- **Comando:** `scripts/v2_agent_arm.py --report artifacts/v2/agent-2026-10-06-e2e/input_report.json --model claude-sonnet-5-5 --out artifacts/v2/agent-2026-10-06-e2e`.
- **Observação:** processos `esbmc` órfãos do agente acumularam memória (21 de 23 GB) e foram
  encerrados com `kill -9` em 06/10; correção planejada (parte 0 da especificação de 06/10).

## Resultado consolidado (até 06/10)

Bugs do gabarito confirmados na linha (causa ou quebra), ESBMC mais CPython, função preservada:
**7** (av_real_01, oob_real_01, oob_real_02 pelo nível 1; bip_luigi_21, bip_pandas_33, ip_real_14,
nm_real_14 pelo agente). Confirmações fora do gabarito que dependem do contrato do chamador:
bip_thefuck_11, ir_real_03.
