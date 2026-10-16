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

## Auditoria dos 7 confirmados e regressão do harness (09/10)

Motivo: uma segunda opinião apontou que o `CONFIRMED` do pipeline une uma violação do ESBMC de um
tipo de exceção (propriedade global, linha 0) com uma reexecução no CPython que levanta esse tipo na
linha do bug, possivelmente com outra entrada; o ESBMC 8.5.0 não imprime os valores do contraexemplo
nesses programas (e `--no-slice` derruba o ESBMC), então a entrada exata não pode ser reconstruída.

- **Localização formal** (`scripts/v2_audit_confirmed.py`, `fase-10/audit-2026-10-09`): numa cópia do
  programa verificado, a instrução da hipótese fica dentro de
  `try/except <Exceção>: __ESBMC_assert(False, "AUDIT_TARGET")`; uma falha de `AUDIT_TARGET` prova que
  a exceção nasce naquela instrução. Testado antes num par com bug e seguro.

| Bug | Nível | Exceção | Linha provada pelo ESBMC | Stub ou modelo na linha | Comportamento possível na biblioteca real |
|---|---|---|---|---|---|
| av_real_01 | 1 | AssertionError | sim (o `assert` da linha 14 falha) | nenhum | sim |
| oob_real_01 | 1 | IndexError | sim | `re.findall` vira lista qualquer | sim: `re.findall` devolve `[]` quando nada casa |
| oob_real_02 | 1 | IndexError | sim | nenhum | sim |
| bip_pandas_33 | agente | ValueError | sim | `Arr.min` do agente | sim: `min()` de array vazio do NumPy levanta o mesmo `ValueError` |
| ip_real_14 | agente | ZeroDivisionError | sim | `np.ceil` do agente; objeto montado sem o `__init__` real | provável: depende de `batch_size * stride` poder ser 0 no construtor real |
| nm_real_14 | agente | TypeError | sim | `to_bytes` do agente | sim: o `to_bytes` do Scrapy levanta `TypeError` com `None` |
| bip_luigi_21 | agente | AttributeError | **não**: o ESBMC acusa ponteiro nulo dentro do modelo de `list.insert`, e há duas chamadas `insert` no caminho | nenhum | sim |

  **Critério estrito: 6 de 7** com a linha provada pelo ESBMC; bip_luigi_21 fica como evidência mais
  fraca (ESBMC e CPython concordam no caminho, sem prova de qual `insert`). ip_real_14 tem a ressalva do
  construtor.
- **Regressão** (`fase-10/regress-2026-10-09`): as 23 hipóteses com veredito do ESBMC de
  `full-2026-10-05-regrounded`, reverificadas com o código atual e as mesmas especificações: 23 de 23
  com o mesmo veredito. As mudanças das fases 9 e 10 não alteraram o nível 1.

- **Experimento A, perfil do solver** (`scripts/v2_solver_profiles.py`, `fase-10/solver-profiles-2026-10-09`,
  09/10): os 14 programas de `full-2026-10-05-regrounded` que o ESBMC aceitou mas não terminaram
  (`ESBMC_TIMEOUT` e `ESBMC_ERROR`), com o perfil atual e com `--z3 --smt-during-symex --smt-symex-guard`,
  `--unwind 5 --multi-property`, 300 s. Nenhum passou a ter veredito. Nos 5 de tempo esgotado, o perfil
  novo estoura de novo em 2 (ip_real_22, oob_real_06) e o Z3 para com erro interno em 3 (`Sorts
  struct_type_pointer_struct and (_ BitVec 64) are incompatible`); nos 9 inconclusivos, os dois perfis
  saem sem veredito em segundos, e o Z3 dá `rm and fp sorts expected` em bip_keras_25 e bip_tornado_5.
  A pista do reprodutor 18 (10 s com esse perfil) não se repete nos casos reais.

## Fase 11 (12/10): técnicas de prompt sobre o A5 e ESBMC master

### Variantes A7 a A11 na amostra de 50

Mudança no pipeline (sem commit até a data): variantes novas em `llm/prompt_variants.py`, schema por
variante (`llm/schema.py`, `v2_findings_schema`), opção `--context-sources` (A11 lê o contexto do arquivo
completo da versão com bug).

- **Comando:** `scripts/run_detection_variants.sh 2026-10-12-amostra dataset/bugs_reais/amostra_deteccao.json A1,A2,A9 A1,A2,A7 A1,A2,A11 A1,A2,A8 A1,A2,A10` (Claude Sonnet via `claude_cli`); avaliação por `scripts/v2_union_detection.py --sample`, regra "causa ou quebra".

| Variante | Pasta (`artifacts/v2/`) | Função | Linha | Fora do bug |
|---|---|---|---|---|
| A5 (base, fase 9) | `det-2026-10-06-amostra-A1,A2` | 44 | 24 | 72 |
| A5 + A7 raciocínio antes do JSON | `det-2026-10-12-amostra-A1,A2,A7` | 42 | 22 | 80 |
| A5 + A8 três exemplos sintéticos | `det-2026-10-12-amostra-A1,A2,A8` | 44 | 22 | 73 |
| A5 + A9 causa e local da quebra | `det-2026-10-12-amostra-A1,A2,A9` | 45 | 25 | 121 |
| A5 + A10 docstring mantida | `det-2026-10-12-amostra-A1,A2,A10` | 46 | 25 | 89 |
| A5 + A11 contexto do arquivo | `det-2026-10-12-amostra-A1,A2,A11` | 43 | 24 | 82 |

- Nenhuma passa da variação da base entre rodadas (cerca de 2). A9 quase dobra o ruído porque cada
  achado com local da quebra vira dois.
- **Decisão (proposta):** A5 continua o prompt final. A detecção com o Sonnet está no teto das técnicas de
  prompt testadas; o gargalo segue na verificação.

### Reprodutores do ESBMC-Python no master (333d07cc8a)

- **Comando:** `docs/projeto/possiveis_problemas/rodar.sh ~/esbmc-master/build/src/esbmc/esbmc` (build com Z3).
- 14 de 18 dão o resultado esperado (01 a 11, 13, 17 aceito; 12 parcial). Continuam: 14 (`async`),
  15 (#8257), 16 (`*xs` com tamanho desconhecido) e 18 (`in` em `Optional[str]` com None dá NULL pointer
  em `strstr`).

### Reverificação da rodada completa com o master

- **Comando:** `scripts/v2_replay_specs.py artifacts/v2/full-2026-10-05-regrounded/v2_verify_report.json --esbmc ~/esbmc-master/build/src/esbmc/esbmc --timeout 180 --out artifacts/v2/esbmc-master-2026-10-12 --shard i/4`.
- 232 hipóteses: CONFIRMED 6 → 1, UNSUPPORTED 115 → 145, ESBMC_TIMEOUT 5 → 9.
- Causas: (1) o master gera checagens de memória nos modelos em C (oob_real_02: 535 propriedades contra 4 no
  8.5.0; 277 s); (2) desde o #7902 uma função `-> bytes` só é aceita se devolver `bytes([...])` ou
  `nondet_bytes(n)`, e os stubs devolviam `b"ab"`/`b""` (10 recusas). Até `return b"ab"` é recusado:
  regressão (reprodutor 23 em `docs/projeto/possiveis_problemas`).
- Flags: `--no-pointer-check --no-align-check` acha o `IndexError` do oob_real_02 em 14 s.
  `--no-bounds-check` não serve: troca o `IndexError` do Python por `out-of-bounds read in list`. (Uma
  versão anterior desta nota dizia que as três flags juntas achavam o `IndexError` em 109 s; a leitura
  estava errada, o `IndexError` era do log sem flags.) A rodada `artifacts/v2/esbmc-master-flags-2026-10-12`
  usou as três flags e não vale.
- Correção no harness: stub `-> bytes` devolve `nondet_bytes(2)` (`verify/render.py`); `--esbmc` do
  script aceita flags.

### Reverificação com as flags certas

- **Pasta:** `artifacts/v2/esbmc-master-flags2-2026-10-12`. **Comando:** o de cima com
  `--esbmc "~/esbmc-master/build/src/esbmc/esbmc --no-pointer-check --no-align-check"`.
- 8.5.0 → master: CONFIRMED 6 → 7 (oob_real_03 novo, fora da linha do bug), ESBMC_TIMEOUT 5 → 1,
  UNSUPPORTED 115 → 142. Nenhuma confirmação do 8.5.0 se perdeu, então juntar as duas versões
  (portfólio) não acrescenta nada. **Métrica principal: 7, sem mudança.**
- Os UNSUPPORTED a mais são casos que antes falhavam por outro motivo (18 eram dependência ausente,
  7 erro do ESBMC) e agora param numa recusa do frontend. Nenhum era confirmado.
- Os bugs de origem dos reprodutores das issues #8247 a #8258 não mudaram: cada um para numa barreira
  anterior que não estava no reprodutor (tabela "Casos do dataset afetados" em
  `docs/projeto/possiveis_problemas/README.md`).

### ip_real_22 e oob_real_12 com mais desenrolamento

- Os dois davam ESBMC_MISSED por `unwinding assertion` com a reexecução reproduzindo o bug. Rodados
  com `--unwind 10`, `--unwind 25` e `--incremental-bmc --max-k-step 40`, 600 s cada.
- ip_real_22: com 10, falha em 1 s no laço do `__python_str_lower` (`string.c` linha 511), antes da
  linha do bug; com 25 e com o incremental, estoura 600 s. oob_real_12: com 10, falha em 5 s nos laços
  de `strlen`, `__memcpy_impl` e no laço 20 do programa; com 25 e com o incremental, estoura 600 s.
- Nenhum chega à linha do bug. Métrica continua 7. O custo está nos laços de string dos modelos em C.

### Harness: receptor construído com argumentos

- vm_real_02: o `Schema.validate` chama `Schema(type(s), error=e)`, e o harness trocava o `__init__`
  real por um sem parâmetros, então o próprio programa ficava inválido (`__init__() takes 1 positional
  argument but 2 were given`). Correção (`verify/grounding.py`, `verify/render.py`): quando o módulo
  constrói a classe com argumentos, o `__init__` real fica e o estado não determinístico vai para uma
  subclasse `_Receiver` (transformação `receiver_subclass`). Teste em `tests/test_verify_review_fixes.py`.
- Rodada: `artifacts/v2/esbmc-master-subclass-2026-10-12` (`--only` nas 3 hipóteses do vm_real_02).
  Continua UNSUPPORTED, agora pelo ESBMC (`Variable args not found`). Em sequência vêm `**kw`,
  `self.__class__.__name__` e tipo como valor: reprodutores 19 a 22.
- Testes: 551 passaram (`tests/test_verify_*.py`, `tests/test_prompt_variants.py`, `tests/test_v2_*.py`).

## Fase 12 (13/10): contornos no harness sugeridos pela segunda opinião

Prompt em `docs/projeto/segunda_opiniao_2026-10-12.md`, respondido pelo Codex (gpt-6-astra): 11 ideias,
estimativa de 2 a 5 bugs a mais. Regra nova: reescrever a função vale se preservar o comportamento,
porque a confirmação continua exigindo que o código original quebre no CPython na linha do bug.

Mudanças (lote 1), todas com teste que falha sem a mudança:

- Tuplas: entrada ou retorno desempacotado em N nomes com tipo escalar vira `tuple[T, ..., T]`
  (`spec.shape_unpacked`). Bug achado no caminho: o programa de sondagem antes da LLM usava `int` em
  tudo e recusava esses casos sem chamar a LLM (9 hipóteses); corrigido em `loop._placeholder_spec`.
- Membros de objetos: o que os auxiliares usam numa entrada repassada entra no objeto gerado
  (`grounding._forwarding_chain`).
- Anotação de tipo nos parâmetros da função alvo e dos auxiliares que recebem as entradas, escrita no
  lugar sem mudar linhas (`render._annotate_inputs`). Anotação não executa no CPython; a auditoria de
  preservação compara só o corpo.
- Replay: `random` entra nos módulos permitidos (`verify/sandbox.py`).
- Ideia 11 (exceções antes dos modelos em C) testada no ip_real_22 e descartada: com `stderr = None`
  fixado e `--unwindset 2:50`, ainda estoura 500 s.

Rodadas (ESBMC master 333d07cc8a, `--no-pointer-check --no-align-check`, sem LLM):

- `artifacts/v2/esbmc-master-lote1full-2026-10-12` (232 hipóteses): UNSUPPORTED 141 → 130,
  CONFIRMED 7 → 7 (nenhuma perdida), UNVALIDATED 3 → 7, SPEC_FAILED 3 → 7 (membros novos pedem tipo da
  LLM), ESBMC_TIMEOUT 1 → 3 (os dois luigi, que antes paravam na recusa).
- `artifacts/v2/esbmc-master-dz03-2026-10-13` (com `random` liberado): dz_real_03 CONFIRMED em 2
  hipóteses (`bb4c66bf`, `97f127f1`): `ZeroDivisionError` na linha do gabarito, tipos preenchidos 0,
  função preservada. Antes: `symbolic_type_excp`; destravou pela anotação de tipos.
- Controle `artifacts/v2/esbmc-master-dz03-control-2026-10-13` (versão corrigida): sem
  `ZeroDivisionError` (`97f127f1` dá `IndexError` e `CroniterBadCronError`; `bb4c66bf` não acha a
  expressão, que mudou na correção).
- **Métrica principal: 7 → 8** (dz_real_03).

## Fase 13 (13 e 14/10): regras do harness a partir dos bugs na linha do gabarito

**Critério novo de prioridade:** contar bugs com hipótese na linha do gabarito e que quebram
(`at_bug_line` e `should_reach_esbmc`), não hipóteses destravadas. São 45 hipóteses em 33 bugs ainda
não confirmados (lista em `scratchpad/alvos.tsv` da sessão). As ideias 1 e 2 do Codex (`*args`,
função em variável) quase não tocam nesses bugs: os 9 `opfunc` do youtube_dl_4 apontam para outra linha.

**Exploração por agentes (sem editar o repositório):** 5 agentes, um por grupo de barreira, editaram
cópias dos programas gerados até o ESBMC achar a violação na linha do bug, anotando a regra geral de
cada edição. Resultado com edições à mão: A (atributos) 6/7, B (nomes e imports) 6/8, C (erros de tipo do
ESBMC) 7/8, D (laços e falsos negativos) 5/6, E (variados) 4/5. Também acharam cerca de 20 limitações
novas do ESBMC master (atributo e `in` em None não checados, método de usuário chamado `remove`, `get`,
`copy` ou `append` despachado como método de lista ou dict, `isinstance` que não distingue classes
vazias, entre outras); falta passar para `docs/projeto/possiveis_problemas`.

**Regras implementadas (todas com teste):**

- `oracle.py`: `NameError: name 'x' is not defined` de nome importado de modelo parcial da stdlib
  (`datetime` sem `timedelta`) vira membro recusado, com stub.
- `compat.py` `cut_after_suspect` (só cópia do ESBMC): o que vem depois da instrução de topo que contém o
  suspeito é apagado; função sem retorno anotado termina ali, com retorno anotado ganha
  `_esbmc_end_path()` (um `__ESBMC_assume(False)` no fim dobrava o tempo de um laço no 8.5). Não vale
  para função recursiva nem gerador.
- `compat.py` `remove_unused`: funções, classes e métodos que nada nomeia saem (na cópia do ESBMC também
  `__repr__`/`__str__`); roda também no grounding antes de planejar stubs, para que decoradores de
  métodos inalcançados (`Substitution(...)`) não peçam stub.
- `compat.py` `none_guards`: na instrução suspeita, antes do que ela avalia sempre, levanta o que o
  CPython levanta quando o valor é None (AttributeError para atributo; TypeError para `in`, índice,
  `len`/`int`/`float`, ordenação e aritmética). Mesma linha (`guarda; instrução` ou `if guarda and
  bool(teste):`), sem guarda em entrada tipada como não-None nem no receptor do método.
- `replay.py`/`replay_worker.py`: strings constantes curtas da função alvo entram no domínio de `str`
  da reexecução.
- Cadeias de atributos (`self.a.b.c()`): donos aninhados em `object_members`, elo intermediário sem tipo
  vira `object`, uma classe por nível (internas primeiro), só para cadeias que saem de entrada `object`.
- Atributo do receptor que só é chamado (`self.write(x)`) vira método stub no shell.

Rodadas (ESBMC master 333d07cc8a, `--no-pointer-check --no-align-check`, sem LLM, specs gravadas de
`full-2026-10-05-regrounded`):

- `artifacts/v2/esbmc-master-lote2-alvos-2026-10-14` (45 hipóteses na linha, só as 4 primeiras regras):
  CONFIRMED novos em oob_real_03 (`57916072238c`, IndexError no segundo `pop`, destravado pelas strings
  constantes: a reexecução nunca sorteava `'-u'`) e oob_real_05 (`6178dac8e931`, IndexError em
  `src_txt[-1]`, destravado pelo corte). Tipos preenchidos 0 nos dois.
- Controle `artifacts/v2/esbmc-master-lote2-control-2026-10-14` (versão corrigida): oob_real_03 dá
  OTHER_FAILURE (IndexError na linha 49, `stderr.split('\n')[-3]`; o `pop` da linha do bug fica em
  `try/except IndexError`); oob_real_05 GROUNDING_FAILED (a correção troca `src_txt[-1]` por
  `src_txt[-1:]`).
- **Métrica principal: 8 → 10** (oob_real_03, oob_real_05).
- `artifacts/v2/esbmc-master-lote2full-2026-10-14` (232 hipóteses, todas as regras), contra
  `esbmc-master-lote1full-2026-10-12`: UNSUPPORTED 130 → 120, MISSING_DEPENDENCY 40 → 36, CONFIRMED 7 → 15
  hipóteses, NOT_CONFIRMED 9 → 13, nenhuma confirmação anterior perdida. Na linha do gabarito, novos:
  tm_real_10 (`6e9d7c84fc8b`, AttributeError em `metrics.configure_http_handler(self)`: o retorno em
  bytes de `generate_latest()` não tem o método; destravado pelas cadeias de atributos) e ip_real_22
  (`91509f265939`, AttributeError com `command.stderr` None). 5 PIPELINE_ERROR por um `pass` escrito
  dentro de classe já removida pela poda (corrigido, com teste); refeitas em
  `esbmc-master-lote2-pe-2026-10-14`: bip_luigi_18 e 19 passam a UNVALIDATED (o ESBMC acha violação),
  dz_real_03 `330ff664aa17` CONFIRMED (IndexError, outra hipótese do mesmo bug).
- Controle `artifacts/v2/esbmc-master-lote2full-control-2026-10-14`: tm_real_10 GROUNDING_FAILED (a
  correção chama o método no coletor, a expressão some). ip_real_22 **não conta**: o bug do gabarito é
  resultado errado (falta tratar `sudo`), e a quebra achada é outra (stderr None) na mesma linha.
- **Métrica principal: 10 → 11** (tm_real_10).
- Lote 3 (mesmo dia): guarda de divisão por zero (retirada depois: o master já checa `/` em float,
  conferido no reprodutor descartado 21 de `possiveis_problemas`), corte também nos blocos internos (dentro de laço fica só a primeira passada,
  subaproximação) e contêiner aninhado com 1 item (2 por nível estourava o tempo com 3 níveis).
  `artifacts/v2/esbmc-master-lote3full-2026-10-14` (232): CONFIRMED 15 → 17 hipóteses (nm_real_06
  ValueError e dz_real_03 IndexError, ambas fora da linha do gabarito), PIPELINE_ERROR 5 → 0, nenhuma
  perdida. dz_real_02 passa a converter e estoura o tempo. Métrica inalterada (11).
- **Lote 4 (14/10), objetivo: mais hipóteses chegando ao ESBMC.** Na lote3full só 49 das 232 tinham
  veredito do ESBMC; 118 paravam em UNSUPPORTED (76 por erro de conversão do ESBMC, 42 por recusa do
  harness), em uns 30 padrões. Regras genéricas novas, todas com teste:
  - `grounding.py` `_hoist_nested`: alvo definido dentro de outra função é copiado para o fim do módulo;
    os nomes que ele pega da função de fora (via `symtable`) viram parâmetros só-palavra-chave, o corpo
    fica igual. Fica de fora quem usa `nonlocal` ou classe que pega nomes de fora. 8 das 10 hipóteses
    aninhadas passam a ser montadas.
  - `slicing.py` `_drop_external_decorators`: decorador de biblioteca stubada vira linha em branco
    (`Substitution`, `Appender`, `cache_readonly`, `contextmanager`).
  - `slicing.py` `_name_spread_arguments`: `lib.f(*a, **k)` vira `lib.f(_star0=a, _kw0=k)`; o stub ignora
    os argumentos e os valores continuam avaliados.
  - `grounding.py` `_inline_inherited`: membro herdado de classe base do mesmo arquivo é copiado para o
    fim da classe do receptor (3 dos 4 casos de herança).
  - `slicing.py` `_flatten_result_members`: `np.finfo(x).tiny` vira o stub `np.finfo__tiny(x)`.
  - `compat.py` `rename_builtin_named_methods` (só cópia do ESBMC): método do usuário com nome de
    método de lista, dict ou str (`get`, `pop`, `copy`, `append`, ...) vira `esbmc_<nome>`, com as
    referências por `Classe.m`, `self.m` e o receptor do driver. Sondado no master: `get`, `pop`, `copy`,
    `update` e `clear` dão `Dictionary variable not found`; `append`, `insert`, `sort`, `split` e
    `replace` são tratados como os da lista ou str.
  - `compat.py` `remove_unused`: na cópia do ESBMC, valor calculado no corpo da classe
    (`_re = re.compile(...)`) que nada lê também sai (`Cannot infer type for class attribute`).
  - `artifacts/v2/esbmc-master-lote4full-2026-10-14` mediu só as 3 primeiras (as outras entraram com a
    rodada já em curso): chegam ao ESBMC 49 → 50, UNSUPPORTED 118 → 108, CONFIRMED 17 → 12. As 5
    confirmações perdidas viraram ESBMC_TIMEOUT (dz_real_03 x3, bip_thefuck_11, oob_real_03) com a
    máquina carregada por testes e sondas em paralelo; refeita sem carga em
    `esbmc-master-lote5full-2026-10-14` (abaixo). As aninhadas destravadas param agora em nome que falta
    (`Object "m" not found`, `Function "convert" not found`).
  - `artifacts/v2/esbmc-master-lote5full-2026-10-14` (as 8 regras, sem outra carga na máquina): chegam ao
    ESBMC 49 → 54, UNSUPPORTED 118 → 105, MISSING_DEPENDENCY 36 → 44 (aninhadas que agora param em nome
    que falta). CONFIRMED novos: bip_matplotlib_16, bip_matplotlib_17 e io_real_01 (ZeroDivisionError
    em `1e6 / tiny`, destravado pelo `np.finfo__tiny`), os três **fora** da linha do gabarito.
    Perdas aparentes: av_real_01 virou UNVALIDATED por bug da regra de renomeio (o `def get` da classe
    de objeto virou `esbmc_get`, mas não a chamada `params.get(...)` em variável anotada com a classe;
    a remoção de não usados apagou o método). Corrigido, com teste. E 4 timeouts (oob_real_02,
    oob_real_03, dz_real_03, bip_thefuck_11) com programas idênticos aos da lote3 (só saiu a função
    auxiliar de divisão por zero, não usada).
  - Recheck num processo só (`esbmc-master-lote5-recheck-2026-10-14`): av_real_01 e oob_real_02
    CONFIRMED, dz_real_03 1 de 3 hipóteses CONFIRMED (as outras 2 estouram), bip_thefuck_11 estoura.
    Esses casos ficam perto dos 180 s e oscilam entre rodadas; nenhuma perda por regra. **Métrica: 11.**
- **Agente LLM pela API do Claude (15/10).** `verify/llm_client.py` ganhou o backend `anthropic`
  (Messages API, sem `thinking` explícito; resposta cortada em `max_tokens` vira erro), e
  `v2_orchestrate.py` a opção `--api-agent-everywhere` (todo caso sem veredito formal vai ao
  `api_agent`; a rota normal manda quase tudo ao Claude Code, que usa a assinatura). O agente grava os
  tokens de cada chamada em `llm_usage.jsonl`. Alvo: 39 hipóteses na linha do gabarito, em 37 bugs fora
  da métrica, sem veredito formal na lote5 (`agent_targets.json`).
  - Piloto `artifacts/v2/agent-anthropic-pilot-2026-10-14` (5 casos, `claude-sonnet-5-5`, ESBMC master):
    33 chamadas, **US$ 0,79** (US$ 2 / 10 por milhão de tokens). 1 veredito novo (ESBMC_MISSED), 1
    timeout, 3 ainda recusados pelo ESBMC depois das 8 rodadas. Depois disso as notas do agente
    (`verify/esbmc_python_notes.md`) ganharam as armadilhas medidas no master (nomes de método de
    lista ou dict, `**kwargs`, atributo de resultado de stub, função aninhada, valor de classe calculado).
  - Rodada `artifacts/v2/agent-anthropic-lote5-2026-10-15/part{0,1,2}` (39 hipóteses, 3 processos):
    240 chamadas, **US$ 11,96** (o dobro da estimativa). Final: UNSUPPORTED 18, AGENT_FAILED 5 (harness
    que não parseia ou sem o alvo), ESBMC_MISSED 4, CONFIRMED 3, MISSING_DEPENDENCY 2, OTHER_FAILURE 2,
    UNVALIDATED 2, ESBMC_TIMEOUT 2, NOT_CONFIRMED 1. Das 3 confirmações:
    - **oob_real_10** (`554b072a0396`, `_wrap_text_to_colwidths`): IndexError em `list_of_lists[0]` com
      a lista vazia, como no gabarito; corpo do alvo intacto. Controle à mão: o mesmo harness com o
      corpo da versão corrigida (`if len(list_of_lists): ... else: num_cols = 0`) roda sem erro no
      CPython. **Conta: métrica 11 → 12**, a primeira pela camada do agente.
    - ip_real_21 (`2629816a29ef`) **não conta**: o gabarito espera KeyError; o TypeError vem de
      `len(that)` numa classe `Other` que o agente inventou sem `__len__`.
    - bip_pandas_10 (`2f90e86be25f`) **não conta**: o bug do gabarito é resultado errado.
  - Falta automatizar o controle do agente na versão corrigida (hoje feito à mão) e barrar stubs
    inventados que causam a própria exceção (caso ip_real_21).
- **15/10, as duas checagens automatizadas** (`verify/agent_arm.py`, sem custo de API):
  - `STUB_INDUCED`: a confirmação cai quando a exceção nasce dentro de uma classe ou função que só
    existe no harness (o replay agora guarda a mensagem e a linha mais interna do traceback) ou quando a
    mensagem nomeia uma classe inventada (`object of type 'Other' has no len()`).
  - `FIXED_ALSO_FAILS` (só avaliação): o alvo é trocado pela versão de `--fixed-sources`
    (padrão `dataset/bugs_reais/arquivo_corrigido`, vazio no modo scan) e reexecutado com as mesmas
    entradas da quebra; se a função corrigida levanta a mesma exceção, a confirmação cai.
  - Re-checagem das 3 confirmações da rodada acima (harness salvo, ESBMC master, sem LLM):
    oob_real_10 continua CONFIRMED, controle `not_reproduced`; bip_pandas_10 vira STUB_INDUCED
    (`TypeError raised inside the stub ndarray.__len__`); ip_real_21 dá UNVALIDATED com as flags
    `--no-pointer-check --no-align-check`, e a regra da mensagem o barraria. Métrica segue 12.
  - Suíte rápida: 791 passed.
- **15/10, passo 3: braço `llm_input`** (`verify/llm_input.py`, rota `solver` = dynamic → llm_input →
  pinned). Quando a busca no CPython não acha a quebra, o LLM propõe a sequência de valores nondet; ela
  só vale se o replay do código original, com exatamente esses valores, quebra na expressão suspeita
  (até 3 rodadas, com o resultado do replay como retorno). O pinned usa a entrada da busca ou do LLM.
  - OpenAI sem crédito (`credit_balance_exhausted`) em 15/10: braço não rodou com LLM ainda.
  - Parte gratuita nos 11 ESBMC_TIMEOUT de `esbmc-master-lote5full-2026-10-14`
    (`artifacts/v2/llm-input-timeouts-2026-10-15/free`, `--arms dynamic,pinned --timeout 180`):
    7 FUZZ_FOUND, 6 viram CONFIRMED pelo pinned (dz_real_03 ×3, oob_real_02, oob_real_03,
    bip_thefuck_11); na linha do gabarito: dz_real_03, oob_real_02, oob_real_03, já contados.
    dz_real_02 quebra na linha do gabarito no CPython, mas o pinned estoura 180 s, e também 900 s
    (`dz02_t900`): fica como evidência dinâmica, sem prova formal.
  - Sobram para o LLM: bip_scrapy_18 e nm_real_25 (busca não achou nada), oob_real_06 e um dz_real_03
    (busca achou outra exceção).
  - Rodada com LLM via Codex CLI (OpenAI sem crédito; Codex cobra no plano, não por token):
    `artifacts/v2/llm-input-timeouts-2026-10-15/codex`, `--arms dynamic,llm_input,pinned --api-backend codex`,
    4 casos, 11 propostas. **0 quebras na linha**: 6 propostas vazias ou curtas demais, 3 rodam sem erro,
    2 levantam outra exceção (KeyError em oob_real_06, ZeroDivisionError em outra linha do dz_real_03).
    Causa no nm_real_25: o harness dá a `start_line` uma classe que sempre tem `method`, então o
    AttributeError da hipótese não existe para nenhuma entrada; o limite é o modelo do objeto, não o valor.
    **Métrica segue 12.**
  - Suíte rápida: 794 passed.

## Fase 14 (15/10): harness congelado e rodada final

- **Congelamento:** tag `harness-freeze-2026-10-15` (commit 88ad57a). Daqui em diante, nenhuma regra
  nova no harness antes de terminar a rodada final.
- **Rodada final** `artifacts/v2/final-2026-10-15` (em andamento):
  - detecção com o prompt A5 (`--v2-variants A1,A2`) e spec pelo Claude Code CLI (Sonnet 5.5, assinatura,
    sem custo de API), 277 arquivos (os 12 de contexto de patch ficam fora);
  - ESBMC master 333d07cc8a com `--no-pointer-check --no-align-check` (`esbmc.sh` na pasta), limite 180 s,
    `ulimit -v 8000000`;
  - comando: `run.sh` na pasta (comando base com as variações acima);
  - depois: orquestrador com `dynamic,llm_input,pinned` e o agente, LLM pelo Codex CLI, controle na
    versão corrigida.

- **15/10, regras depois do congelamento** (patch `docs/projeto/regras_pos_congelamento_2026-10-15.patch`,
  ainda fora do master): decoradores do projeto tirados da cópia do ESBMC, `x = a if c else lambda`
  reescrito como if/else, autorreferência não conta como uso. Medição sem LLM nos specs gravados
  (`artifacts/v2/rules-after-freeze-2026-10-15/full`, 2 shards, timeout 180) contra o lote 5:
  CONFIRMED 13 → 20 e ESBMC_TIMEOUT 11 → 4, mas as viradas são timeouts do lote 5 (máquina carregada);
  nenhuma confirmação nova vem das regras. **Métrica segue 12**, nenhuma perda. ip_real_22 confirma na
  linha, mas com AttributeError (`command.stderr` None); o gabarito é resultado errado, então não conta.
  Testes das 3 regras escritos no patch (o da autorreferência falha no código antigo).
- **Rodada final retomada** com `run.sh --resume` depois de cair na detecção (183/277).
- **15/10, rodada final terminada com lacunas.** A detecção completou (277 arquivos, 541 hipóteses), mas
  o limite da assinatura do Claude acabou no meio da verificação: 209 hipóteses ficaram `PIPELINE_ERROR`
  ("claude -p saiu com código 1"). Retomada em cópia `artifacts/v2/final-2026-10-15-codex` (checkpoint
  copiado, fingerprint com `synth_backend: codex`, `run.sh --resume`): o spec dessas hipóteses passou a
  vir do Codex CLI, as demais mantêm o spec do Sonnet (**spec misto**). O limite do Codex também acabou:
  **114 hipóteses ainda `PIPELINE_ERROR`**. Nível 1: CONFIRMED 24, 93/541 com veredito do ESBMC.
- **Orquestrador sem LLM** (`--arms dynamic,pinned`, controle `--fixed-sources`, timeout 180,
  `orq_free/`): `confirmed_at_bug` 8, `fuzz_found_at_bug` 4.
  - Na linha e contando: av_real_01, dz_real_03 (já contados), **av_real_02** (novo: `assert self.stream
    is not None`, AssertionError, o tipo do gabarito) e **dz_real_02** (novo, pelo `pinned`: ZeroDivisionError
    em `float(not_parsed)/float(num_substrings)` com a entrada achada pelo dinâmico; antes dava timeout. A
    correção protege exatamente esse caso).
  - Na linha, mas sem contar: bip_scrapy_15 (gabarito UnicodeError do idna; o achado é AttributeError com
    `netloc` None), av_real_07 e ip_real_22 (gabarito resultado errado).
  - Só evidência dinâmica na linha: ip_real_14 (já contado pelo agente), ip_real_17, bip_pandas_162,
    ip_real_05 (resultado errado).
- **Métrica: 12 → 14** (união com as rodadas anteriores: + av_real_02, + dz_real_02). Os outros 10 dos 12
  vieram do agente/nível 1 de rodadas anteriores e ainda não foram refeitos aqui.
- **Pendente** (precisa de limite de LLM): refazer as 114 hipóteses (`run.sh --resume` na pasta codex),
  braços `llm_input` e `api_agent` pelo Codex.

## Fase 15 (16/10): spec com contexto dos chamadores (item 3 do plano geral), sem rodada

- **Objetivo:** item 3 do plano geral, sem rodada. O pedido de spec passa a mostrar as chamadas reais da
  função, as referências sem chamada (`partial(f, ...)`) e fatos de uso das entradas, e um tipo
  contrariado pelo uso (`int` com `.groups()`, escalar subscrito) volta ao LLM pelo laço de reparo antes
  do ESBMC. Flag nova `--spec-context {none,callers}`, padrão `callers`.
- **Commit:** (o da Fernanda, se ela commitar).
- **Comando:** `timeout 10m .venv/bin/python -m pytest -q tests --ignore=tests/test_verify_esbmc_integration.py`
  → 945 passed (921 antes do item, 24 testes novos).
- **Linha de base:** a regra "tipo contrariado pelo uso é rejeitado" fica no bloco de contexto, não em
  `input_spec_prompt.txt`, que voltou ao texto de antes do item (mesmo sha256). Com `--spec-context none`
  o prompt de sistema e o pedido são idênticos aos de antes do item 3 (teste
  `test_without_context_the_system_prompt_is_the_pre_item_3_one`).
- **Retomada:** o hash do prompt do spec não muda mais, mas o `config` do fingerprint ganhou
  `spec_context`, e a comparação é do dicionário inteiro; então `artifacts/v2/final-2026-10-15-codex`
  continua **não retomável** com este código, nem com `--spec-context none`.
- Medição adiada para o item 6 (`--spec-context none` contra `callers`).

## Fase 16 (16/10): variantes A13 e A14 (item 4 do plano geral), sem rodada

- **Objetivo:** item 4 do plano geral, sem rodada. `llm/example_pool.py` (pool do gabarito, similaridade
  Jaccard por AST, exclusão do projeto do bug), variantes A13 e A14 em `llm/prompt_variants.py`, campos
  `quoted_line` e `trigger` no esquema com A14, `--example-pool`/`--example-k` no `main.py`, impressão
  digital ampliada só para A13 e A14, `scripts/print_detection_prompt.py` e `BACKEND`/`MODEL` em
  `scripts/run_detection_variants.sh`.
- **Commit:** (o da Fernanda, se ela commitar).
- **Sem rodada:** nenhuma chamada a LLM. A comparação fica para o item 6 do PLANO_GERAL.
- **Pool real:** 227 dos 289 itens entram como exemplo; varredura dos 289 sem nenhum exemplo do mesmo
  projeto. Inspeção de `bip_pandas_84` com A1,A2,A13,A14: cerca de 3.425 tokens de entrada.
- **Comando:** `timeout 10m .venv/bin/python -m pytest -q tests --ignore=tests/test_verify_esbmc_integration.py`
  → 966 passed (945 antes do item, 21 testes novos).

## Fase 17 (16/10): gabarito com causas do patch e linhas da quebra (item 1 do plano geral), sem rodada

- **O que mudou:** depois da revisão da Fernanda na tabela `docs/projeto/revisao_linha_da_quebra_2026-10-15.md`,
  `scripts/propose_crash_lines.py apply` gravou em `ground_truths.json`, `manifest.json`, `manifest_full.json`
  e `coleta_bugsinpy/labels.json`.
- **Resultado:** 289 itens alterados. Todos os 289 têm `cause_expressions` (242 `patch`, 47 `patch_revisado`).
  58 têm `crash_expressions` (`llm_patch_revisado`); nos outros aceitos a quebra é a própria linha da causa.
  Quebras em dúvida (8) e rejeitadas (5) ficaram de fora. Reaplicar não muda nada (0 itens).
- **Comando:** `PYTHONPATH=src .venv/bin/python scripts/propose_crash_lines.py apply`; testes
  `tests/test_v2_evaluator.py tests/test_propose_crash_lines.py` → 43 passed.
- **Métrica:** não medida (item 6). Continua 14 até a rodada final.

## Resultado consolidado (até 06/10)

Bugs do gabarito confirmados na linha (causa ou quebra), ESBMC mais CPython, função preservada:
**7** (av_real_01, oob_real_01, oob_real_02 pelo nível 1; bip_luigi_21, bip_pandas_33, ip_real_14,
nm_real_14 pelo agente). Confirmações fora do gabarito que dependem do contrato do chamador:
bip_thefuck_11, ir_real_03.

Evidência dinâmica (CPython quebra na linha do bug só na versão com bug, sem prova formal), fase 10:
dz_real_02, ip_real_22, oob_real_05, oob_real_12 (dz_real_02 e oob_real_12 com a versão corrigida
executada sem quebrar ali).
