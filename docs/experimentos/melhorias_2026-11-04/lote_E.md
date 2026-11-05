# Lote E: etapa de detecção (04/11)

Três mudanças na etapa em que o LLM aponta hipóteses de bug. Nenhuma chamada a LLM pago foi feita:
os testes usam LLM falso e as medições leem artefatos já gravados. Nada foi commitado.

## Item 1: impressão digital da retomada cobre o texto de toda variante

**Problema.** A impressão digital (o resumo que o `--resume` compara para saber se é seguro continuar
uma rodada) só incluía o prompt de sistema montado quando a rodada usava A13, A14 ou A15. Os textos em
`src/research_pipeline/prompts/v2_variants/*.txt` (A2, A8, A12, A16, A18, A20) e as variantes escritas
no código (A1, A3, A6, A7, A9, A11, A19) ficavam de fora: um prompt alterado retomava sem aviso.

**O que mudou.**
- `_v2_fingerprint` (`src/main.py`) passa a guardar o resumo do prompt de sistema já montado sempre que
  há pelo menos uma variante. Esse texto montado contém cada arquivo `.txt` que as variantes leem, então
  qualquer mudança nele muda a impressão digital. Sem variante, o prompt é o próprio
  `system_prompt_v2.txt`, que já entrava; por isso rodadas sem variante não mudam.
- Ao recusar a retomada, a mensagem agora separa os dois casos: se o conjunto de campos da impressão
  digital mudou, diz que o formato mudou (desde 04/11 inclui o texto de prompt de toda variante) e pede
  para rodar de novo em outra pasta; se só os valores mudaram, mantém a mensagem antiga.

**Checkpoints afetados.** Conferi os 78 `v2_checkpoint.json` em `artifacts/` (do repositório principal,
só leitura). Os 25 que usam variantes sem A13, A14 ou A15 vão recusar a retomada com a mensagem nova.
Dois ainda estão com status `running`:
- `artifacts/pgene601/codex-2026-11-03` (Codex, A1+A2, verificação parcial). **Hoje ele retoma** (recalculei a
  impressão digital com o código atual e ela bate); com a mudança, **deixa de retomar**. Se a verificação
  dessa rodada ainda vai continuar, é preciso terminar antes de usar este código, ou rodar de novo.
- `artifacts/v2/final-2026-10-08` (A1+A2). Este já não retomava antes: o `system_prompt_v2.txt` mudou
  depois dele.

Os outros 23 estão completos (`complete` ou `detection_complete`), mas também perdem o `--resume`, que
serve para refazer hipóteses com `PIPELINE_ERROR`. Entre eles está `artifacts/pgene601/e2e-2026-11-02`
(Claude, A1+A2).

Comando usado para conferir (script em scratchpad, sem LLM):
`.venv/bin/python fp_check.py <worktree> artifacts/pgene601/codex-2026-11-03/v2_checkpoint.json ...`,
que recalcula `_v2_fingerprint` com a configuração salva e compara com a gravada.

**Testes** (`tests/test_main_v2.py`):
- sem variante, os campos da impressão digital continuam os cinco de antes;
- para A2, A8, A12, A16 e A20, acrescentar uma linha ao `.txt` da variante muda a impressão digital
  (e uma cópia sem mudança não muda);
- um checkpoint sem o campo novo é recusado com a mensagem de formato;
- um checkpoint com o mesmo formato e prompt diferente é recusado com a mensagem antiga.

Teste de mutação: voltando a condição antiga (`{"A13", "A14", "A15"} & set(variants)`), 7 testes falham.

O teste antigo `test_fingerprint_keeps_its_keys_for_earlier_variants` foi trocado, porque ele fixava
justamente o comportamento corrigido.

## Item 2: limite de hipóteses por função (opção, desligada por padrão)

**O que mudou.** Nova opção `--max-hypotheses-per-function N`. Sem ela nada muda (sem limite).
Com ela, depois da detecção e antes do ESBMC, o pipeline mantém só as N primeiras hipóteses distintas
de cada função. As que ficaram de fora vão para o relatório em `detection.capped_candidates`, e o valor
de N entra na configuração (e portanto na impressão digital) só quando a opção é usada.

**Regra de escolha** (a mesma de `artifacts/pgene601/melhorias-2026-11-03/offline_analysis.py`):
1. a ordem é a ordem em que o LLM escreveu as hipóteses, unidade por unidade, como estão no checkpoint;
   não existe outra pontuação de prioridade no pipeline;
2. duas hipóteses são a mesma quando têm o mesmo arquivo, a mesma função e a mesma árvore sintática da
   expressão (depois de desfazer o nome `target_function` do prompt); a cópia repetida também sai da fila;
3. diferença em relação ao script: a hipótese de resultado errado (A15, `oracle = value`) não é tratada
   como repetição da hipótese de exceção na mesma expressão, porque o pipeline verifica as duas de modo
   diferente. Na amostra do script isso não aparece (ela não usa A15).

Na etapa `synthesis` (hipóteses do gabarito) o limite não se aplica.

**Arquivos.** `src/research_pipeline/hypothesis_cap.py` (novo, função `cap_per_function`), `src/main.py`
(opção, configuração e chamada logo depois do laço de detecção).

**Medição.** Rodei `cap_per_function` sobre o mesmo checkpoint da análise de 03/11
(`artifacts/pgene601/melhorias-2026-11-03/baseline_checkpoint.json`), conferindo com
`at_bug_line`. Comando: `.venv/bin/python cap_check.py <worktree> <repo>` (script em scratchpad).
Resultado igual à tabela de 03/11:

| N | Hipóteses mantidas (de 253 brutas) | Bugs na linha | Hipóteses na linha |
| ---: | ---: | ---: | ---: |
| 1 | 48 | 18 | 19 |
| 2 | 88 | 23 | 31 |
| 3 | 117 | 26 | 37 |
| 12 | 222 | 39 | 54 |
| sem limite (só repetições saem) | 232 | 39 | 54 |

O número 12 continua escolhido na mesma amostra: por isso a opção fica desligada por padrão e precisa
ser testada em outra amostra antes de virar regra.

**Testes** (`tests/test_hypothesis_cap.py`): ordem e contagem por função; repetição por árvore sintática,
pelo nome `target_function` e pelo oráculo; pela linha de comando, o relatório mostra as N enviadas e as
que ficaram de fora; sem a opção, nada é cortado e a configuração não ganha campo novo.
Teste de mutação: trocando `>=` por `>` no limite, 2 testes falham.

## Item 3: falha em outra linha da mesma função vira contagem à parte

**Problema.** Quando o ESBMC acha uma violação e a reexecução em CPython quebra numa linha diferente da
hipótese, o veredito é `OTHER_FAILURE` e some da avaliação, mesmo quando a quebra acontece dentro da
função certa.

**O que mudou.**
- A reexecução (`src/research_pipeline/verify/replay.py`) passa a gravar `target_range`, as linhas da
  função alvo no programa reexecutado. Antes o resultado só tinha a linha da quebra, sem dizer se ela
  estava dentro da função.
- `src/research_pipeline/verify/report.py`:
  - `failed_in_function(result)`: verdadeiro para um `OTHER_FAILURE` cuja linha da quebra está dentro
    da função da hipótese;
  - `summarize` ganha `same_function_other_line`, o número dessas hipóteses (elas continuam contadas
    em `by_verdict["OTHER_FAILURE"]`);
  - `evaluate_verify` ganha `same_function_other_line` com `hypotheses`, `bugs` (bugs do gabarito cuja
    função teve uma dessas falhas), `bugs_not_confirmed_at_line` (desses, os que não têm `CONFIRMED` na
    linha do gabarito) e `bug_ids`.
- A métrica principal (`confirmed_by_location`, bugs confirmados na linha do gabarito) não mudou.

Limite: "outra linha" é em relação à hipótese, não ao gabarito. A quebra pode vir de um substituto
grosseiro do harness (o cuidado do caso `url_concat`), então essa contagem não é bug confirmado.
Uma função aninhada dentro da função alvo conta como dentro dela, porque o critério é o intervalo de linhas.

**Medição offline** em `artifacts/v2/final-2026-10-17` (A1+A2+A15, 742 hipóteses, rodada completa),
sem LLM e sem ESBMC: para cada `OTHER_FAILURE` guardado, li o programa reexecutado salvo para achar o
intervalo da função e usei a linha da quebra já gravada. Comando:
`.venv/bin/python other_line.py <worktree> <repo> artifacts/v2/final-2026-10-17/v2_verify_report.json dataset/bugs_reais/ground_truths.json`
(script em scratchpad).

- `OTHER_FAILURE`: 26 hipóteses; 2 sem programa salvo legível, ficaram fora da contagem.
- Nova contagem `same_function_other_line`: **23 hipóteses**, cobrindo **19 bugs** do gabarito;
  **14** desses 19 não têm confirmação na linha do gabarito.
- Uma das 24 com programa quebrou fora da função (`_parse_filter`, linha 25, função nas linhas 7 a 13).
- Métrica principal recalculada: 12 bugs confirmados na linha (`expression_equivalent`), igual ao valor
  gravado no relatório.

**Testes:** `tests/test_verify_replay.py` (a reexecução devolve o intervalo) e `tests/test_verify_report.py`
(a contagem só pega quebra dentro do intervalo; intervalo desconhecido não conta; a métrica principal fica
igual; bug já confirmado na linha sai de `bugs_not_confirmed_at_line`; outra função não conta).
Teste de mutação: tirando a comparação com o intervalo, 1 teste falha.

## O que ficou de fora

- O modo agente (`agent_arm.py`) também produz `OTHER_FAILURE`, mas sem `target_range`: essas
  hipóteses não entram na contagem nova. O código dessa parte está com outro lote.
- A mensagem impressa no fim da rodada (perto da linha 690 de `src/main.py`) não mostra a contagem nova;
  ela fica só no JSON. Essa região está sendo editada pelo Lote B.
- `pylint` não está instalado neste ambiente (nem global nem no `.venv`), e sem rede não deu para
  instalar. Usei `ruff`: os arquivos novos e `report.py` passam; os avisos que sobram em `main.py` e
  `replay.py` (ordem de imports, `re.M`, um gerador) já existiam antes.

## Uso de IA

O código, os testes, as medições e este texto foram feitos pelo Claude (agente de código), seguindo os
três itens pedidos. As decisões de pesquisa (adotar o limite, como ler a contagem nova) ficam com a
Fernanda.
