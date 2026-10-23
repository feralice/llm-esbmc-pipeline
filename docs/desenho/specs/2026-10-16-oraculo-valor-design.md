# Oráculo de valor errado no harness (item 5 do plano geral)

Data: 16/10/2026. Item 5 de `docs/historico/PLANO_GERAL_2026-10-15.md`. Sem experimento nem medição neste
item: a rodada que mede o efeito é a do item 6.

## Objetivo

O gabarito tem 289 bugs; 178 têm `failure_kind = "resultado_errado"` (`dataset/bugs_reais/ground_truths.json`):
a função termina sem exceção e devolve um valor errado (ou deixa `self` num estado errado). Hoje nenhum
deles pode ser confirmado, porque a cadeia inteira só reconhece exceção:

- a detecção descarta o achado: `src/main.py:1370-1380` manda ao ESBMC só achados com `verifiable` true, e o
  prompt base diz que valor errado é `verifiable` false (`src/research_pipeline/prompts/system_prompt_v2.txt:52-53`);
- a avaliação marca esses bugs como "não deve ir ao ESBMC" (`src/research_pipeline/v2_evaluator.py:26-27`);
- o harness não tem nada a verificar depois da chamada: o driver só chama a função
  (`src/research_pipeline/verify/render.py:351-372`), e o corte depois da suspeita apaga o resto do corpo,
  inclusive o `return` (`render.py:465`, `src/research_pipeline/verify/compat.py:374`);
- o replay só confirma exceção levantada dentro do trecho suspeito da função alvo
  (`src/research_pipeline/verify/replay_worker.py:337-344`), e o veredito final exige que a exceção do replay
  esteja entre as que o ESBMC relatou (`src/research_pipeline/verify/outcome.py:90-98`).

Este item abre esses 178 bugs para a métrica de confirmação. Para uma hipótese de valor errado, o LLM escreve
a propriedade que o resultado correto cumpre (uma pós-condição sobre entradas e valor devolvido); o harness
coloca `assert <propriedade>` logo depois da chamada à função real; o ESBMC procura uma entrada que viole o
`assert`; o replay no CPython confirma que o código ORIGINAL viola a propriedade com essa entrada; e um controle
exige que a versão corrigida NÃO viole a mesma propriedade com a mesma entrada. Se a corrigida também viola,
a propriedade está errada, e a hipótese recebe `PROPERTY_REJECTED`.

Hoje 172 dos 178 bugs de valor errado têm versão corrigida em `dataset/bugs_reais/arquivo_corrigido`.

## Como o pipeline funciona hoje (pontos de contato)

| Etapa | Onde | O que importa para este item |
|---|---|---|
| Hipótese | `verify/hypothesis.py:11-37` | `BugHypothesis` é congelada; `hypothesis_id` vem de arquivo, função, linha e expressão (`:20-23`). Não há campo que diga se a hipótese é de exceção ou de valor. |
| Candidato | `verify/candidate.py:11-31`, `main.py:1381-1389` | O candidato da detecção vira hipótese por `BugHypothesis.from_candidate` (`hypothesis.py:25-34`). |
| Variantes de detecção | `llm/prompt_variants.py:108-120`, `llm/schema.py:104-116`, `llm/findings.py:70-82` | Mudanças nomeadas do prompt de detecção (A1 a A12); A9 mostra o padrão de campo novo em `metadata`, no prompt e no schema. |
| Spec de entrada | `verify/spec.py:68-75`, `:144-161`, `:205-235`, `:272-307` | O LLM devolve só JSON (tipos, stubs, suposições). As suposições passam por uma validação de subconjunto seguro de AST (`_ALLOWED_NODES`, `_assumption_problem`). `shape_unpacked` reconstrói `InputSpec` posicionalmente (`:269`). |
| Prompt da spec | `prompts/input_spec_prompt.txt`, `verify/loop.py:69-90` | O LLM vê a função, a expressão suspeita, a hipótese e a fatia verbatim do módulo com bug. |
| Harness | `verify/render.py:414-488` | Monta stubs, módulo e driver; a cópia para o replay (`replay_source`) é feita antes das reescritas de compatibilidade (`:441`). As reescritas preservam a numeração, exceto `split_conditional_assignments` (`compat.py:665`), que acrescenta linhas só na cópia do ESBMC; nesse caso `driver_start` é recalculado para ela (`render.py:481-485`). |
| ESBMC | `verify/esbmc_run.py:39-71`, `verification/esbmc_runner.py:641-725` | O runner guarda, por propriedade violada, `kind` e `line` em `details["violated_property_records"]`. |
| Replay | `verify/replay.py:105-159`, `verify/replay_worker.py:325-410` | Status `reproduced`, `other_failure`, `not_reproduced`, `unavailable`. Com `inputs`, roda exatamente aquela sequência uma vez (`_fixed`, `:351-361`); hoje uma execução descartada (suposição falsa ou tempo) nesse modo vira `not_reproduced`. |
| Veredito | `verify/outcome.py:90-98`, `verify/loop.py:192-203` | `final_verdict` combina a leitura do ESBMC e o replay. |
| Controle com a corrigida | `verify/agent_arm.py:271-278`, `:321-347` | Só no braço do agente: a função alvo é trocada pela corrigida dentro do harness (`_replay_original`) e rodada com as entradas que quebraram a original; se ainda quebra, `FIXED_ALSO_FAILS`. |
| Roteamento e métrica | `verify/routing.py:190-232`, `verify/orchestrator.py:242`, `scripts/v2_orchestrate.py:30-55`, `verify/report.py:45-61` | `confirmed_at_bug` conta `CONFIRMED` na linha do gabarito (`at_bug_line`, `v2_evaluator.py:79-85`). |

## Fluxo

1. **Entrada da hipótese.** Uma variante nova do prompt de detecção, `A15`, pede em `metadata.failure_mode`
   como o bug se manifesta (`excecao`, `resultado_errado` ou `outro`). Com `A15` ligada, um achado com
   `failure_mode = "resultado_errado"` vira candidato com `oracle = "value"`, mesmo com `verifiable` false.
   Sem `A15`, nada muda na detecção.
2. **Hipótese.** `BugHypothesis` e `Candidate` ganham o campo `oracle` (`""` para exceção, `"value"` para
   valor errado). O `hypothesis_id` inclui o oráculo só quando ele é `"value"`, de modo que os ids já
   gravados em checkpoints e relatórios continuam válidos.
3. **Propriedade.** Na mesma chamada que já pede os tipos (etapa de spec), uma hipótese de valor recebe um
   acréscimo ao prompt do sistema pedindo duas chaves a mais no JSON: `returns` (tipo devolvido) e
   `postcondition` (a propriedade). O LLM vê a função com bug, a expressão suspeita, a hipótese e a fatia do
   módulo com bug; nunca a versão corrigida, nem o patch, nem o gabarito.
4. **Validação.** `spec_problems` valida a propriedade com a linguagem permitida (abaixo). Um problema volta ao
   LLM como hoje (reparo guiado, até `max_repairs`).
5. **Harness.** O driver guarda o valor da chamada em `_esbmc_result` (anotado com `returns`) e termina com
   `assert <propriedade>`, onde `result` vira `_esbmc_result` e `self` vira `_receiver`. O corte depois da
   suspeita não é aplicado a hipóteses de valor. `Program` ganha `property_line` (linha do `assert` na cópia do
   ESBMC) e `replay_property_line` (na cópia do replay); as duas diferem quando a separação de atribuições
   condicionais cresce só a cópia do ESBMC.
6. **ESBMC.** Conta como violação da propriedade só um registro de `violated_property_records` cujo `kind`
   começa com `assertion` e cuja `line` é `property_line` (a da cópia do ESBMC).
7. **Replay no original.** Com a linha da propriedade na cópia do replay, o worker classifica como `property_violated` uma
   `AssertionError` levantada no driver (`_esbmc_main`) na linha da propriedade, e a busca para no primeiro
   `property_violated`. Uma exceção em outro lugar segue as regras atuais (`reproduced` ou `other_failure`).
8. **Controle.** Quando há versão corrigida, a função alvo do programa de replay é trocada pela corrigida, a
   linha da propriedade é deslocada pela diferença de tamanho, e o programa roda uma vez com as entradas do
   replay que violou o original. A versão corrigida é lida por `run_verify` e só é usada depois que o LLM
   terminou.
9. **Veredito e métrica.** Ver as seções seguintes.

## Linguagem permitida da propriedade

A mesma base das suposições da spec (`spec.py:205-209`), com dois acréscimos e uma exigência:

- nós permitidos: comparações (`==`, `!=`, `<`, `<=`, `>`, `>=`, `is`, `is not`, `in`, `not in`), `and`, `or`,
  `not`, menos unário, `+`, `-`, `*`, constantes, nomes e tuplas de constantes;
- chamadas permitidas: `len(x)` e `isinstance(x, T)` com `T` um nome entre `int`, `float`, `bool`, `str`,
  `bytes`, `list`, `dict`, `tuple`, `set`, `frozenset`;
- nomes permitidos: os parâmetros da função, `result` (o valor devolvido) e, em métodos, `self.<atributo>` dos
  atributos de entrada do receptor;
- atributos: só `self.<atributo>` de método; `result.x`, `x.y` e chamadas de método ficam de fora;
- exigência: a propriedade lê `result` ou algum `self.<atributo>`; uma propriedade só sobre as entradas não
  diz nada sobre o que a chamada fez;
- `returns`: um tipo aceito por `parse_type`, exceto `object`; `"None"` quando a função não devolve nada, e
  nesse caso a propriedade não pode ler `result`;
- um parâmetro chamado `result` torna a propriedade ambígua e é rejeitado.

As entradas lidas pela propriedade têm o valor de depois da chamada (semântica do Python). Valores de antes
da chamada (estilo `old(x)`) ficam fora deste item.

Exemplos aceitos: `result >= 0`, `len(result) <= len(xs)`, `isinstance(result, int)`,
`result in ('GET', 'HEAD')`, `result is None or result > x`, `self.total >= 0`.
Exemplos recusados: `x > 0` (não lê o resultado), `result[0] == 1` (subscrito), `sorted(xs) == result`
(chamada), `result.strip() == ''` (método), `isinstance(result, Foo)` (tipo que não é embutido).

## Novos vereditos

Nomes conferidos contra todos os vereditos existentes (`CONFIRMED`, `ESBMC_MISSED`, `UNVALIDATED`,
`OTHER_FAILURE`, `NOT_CONFIRMED`, `GROUNDING_FAILED`, `MISSING_DEPENDENCY`, `UNSUPPORTED`, `SPEC_FAILED`,
`ESBMC_TIMEOUT`, `ESBMC_ERROR`, `PIPELINE_ERROR`, `NO_SOURCE`, `AGENT_FAILED`, `CONFIRMED_SIMPLIFIED`,
`STUB_INDUCED`, `FIXED_ALSO_FAILS`, `FUZZ_FOUND`, `FUZZ_OTHER`, `FUZZ_NOTHING`, `FUZZ_UNAVAILABLE`, `PINNED_SAFE`,
`PINNED_UNAVAILABLE`, `LLM_INPUT_NOTHING`, `LLM_INPUT_UNAVAILABLE`, `ARM_FAILED`, `TARGET_ALTERED`):

| Veredito | Quando |
|---|---|
| `VALUE_VIOLATION` | O ESBMC acusa o `assert` da propriedade e o replay do original o viola, mas não houve controle conclusivo (sem versão corrigida, função ausente nela, ou a corrigida levantou exceção ou ficou indisponível). Evidência, não confirmação. |
| `VALUE_CONFIRMED` | Como acima, e a versão corrigida, com as mesmas entradas, termina e respeita a propriedade. |
| `PROPERTY_REJECTED` | Como acima, mas a versão corrigida também viola a propriedade: a propriedade está errada. |

Os demais casos reaproveitam vereditos existentes com o mesmo sentido: `UNVALIDATED` (o ESBMC acusa violação
mas não a da propriedade, ou o replay não a reproduz), `OTHER_FAILURE` (o replay levantou exceção em vez de
violar a propriedade), `ESBMC_MISSED` (o ESBMC não achou violação e o replay achou), `NOT_CONFIRMED` (nenhum
dos dois achou) e os terminais (`ESBMC_TIMEOUT`, `ESBMC_ERROR`, `UNSUPPORTED`, `MISSING_DEPENDENCY`).
Os três novos entram em `VERDICTS` e `CHECKED` (`outcome.py:28-31`).

## Controle com a versão corrigida

- Fonte: `arquivo_corrigido/<mesmo nome>` passado por `--fixed-sources` (novo argumento do `main.py`) até
  `run_verify`, que lê o arquivo só para hipóteses de valor e o entrega a `verify_hypothesis` como
  `fixed_source`.
- Programa: o `replay_source` do harness com a função alvo trocada pela da versão corrigida (mesma técnica de
  `agent_arm._replay_original`, `agent_arm.py:321-347`); stubs, receptor e driver continuam iguais.
- Execução: uma vez, com `inputs` igual às entradas do replay que violou o original.
- Leitura: `not_reproduced` (terminou e o `assert` valeu) dá `VALUE_CONFIRMED`; `property_violated` dá
  `PROPERTY_REJECTED`; qualquer outro status (exceção, indisponível, execução descartada) mantém
  `VALUE_VIOLATION` com o motivo.
- Execução descartada: no modo propriedade, uma execução com entradas fixas cortada por suposição ou por
  tempo passa a ser `unavailable`, nunca `not_reproduced`; sem isso, um corte seria lido como "a corrigida
  respeita a propriedade".
- O resultado do controle fica em `result["control"]`.

## Contagem na métrica

Uma hipótese de valor conta na métrica de confirmação só quando as três condições valem juntas:

1. o original viola a propriedade (ESBMC acusa o `assert` e o replay no CPython o viola);
2. a versão corrigida não viola com a mesma entrada (veredito `VALUE_CONFIRMED`);
3. a hipótese está na linha do gabarito (`at_bug_line`: função e expressão equivalentes a `expression`,
   `cause_expressions` ou `crash_expressions` do item).

`scripts/v2_orchestrate.py` passa a relatar `value_confirmed_at_bug` ao lado de `confirmed_at_bug`, e
`confirmed_at_bug_with_value` com a soma; `verify/report.py` relata `value_confirmed_by_location` ao lado de
`confirmed_by_location`. As duas partes aparecem sempre separadas; o número da dissertação é a soma, com as
partes ao lado. `VALUE_VIOLATION` e `PROPERTY_REJECTED` nunca contam.

Hoje os itens de valor errado ainda não têm `cause_expressions` no gabarito (a aplicação é pendência do
item 1); até lá, a linha do gabarito é `expression`.

## Erros e casos de borda

| Situação | Resultado |
|---|---|
| JSON sem `returns` ou sem `postcondition` numa hipótese de valor | Problema devolvido ao LLM; esgotados os reparos, `SPEC_FAILED`. |
| Propriedade fora da linguagem | Idem, com a mensagem que diz o nó, a chamada ou o nome recusado. |
| `returns` é `object` ou tipo não aceito | Idem. |
| `returns: "None"` e a propriedade lê `result` | Idem. |
| Entrada por construtor (`entry == "constructor"`) | `RenderError` já no `precheck`: `UNSUPPORTED`, sem gastar chamada ao LLM. |
| `returns`/`postcondition` numa hipótese de exceção | Ignorados e registrados em `ignored`, como chaves a mais hoje. |
| O ESBMC acusa violação noutra linha | `UNVALIDATED` (nunca confirmação). |
| `AssertionError` de um `assert` do próprio código alvo | Segue as regras atuais (`reproduced`/`other_failure`), nunca `property_violated`. |
| Worker devolve `property_violated` noutra linha | `unavailable` (mesma desconfiança que `replay.py:145-149` aplica a `reproduced`). |
| Função alvo ausente na versão corrigida ou troca que não compila | Controle `unavailable`: `VALUE_VIOLATION`. |
| Hipótese de valor sem veredito formal (tempo, erro) | Nenhum braço do orquestrador roda: os braços procuram exceção e não conhecem a propriedade. |

## Testes

Todos com LLM falso e runner do ESBMC falso (monkeypatch de `esbmc_run.run_esbmc_direct`, como em
`tests/test_verify_loop.py:38-58`, e de `loop.convert`); o replay usa o CPython de verdade, como os testes
atuais de `tests/test_verify_replay.py`.

- Hipótese: id antigo estável, id próprio para valor, ida e volta por `to_dict`; candidato leva o oráculo.
- Detecção: variante `A15` no prompt e no schema; `failure_mode` lido do JSON; com `A15`, achado de valor
  vira hipótese `value`; sem `A15`, continua segurado.
- Spec: tabela de propriedades aceitas e recusadas; `returns` obrigatório e sem `object`; `result` com
  `returns: "None"`; parâmetro chamado `result`; chaves ignoradas em hipótese de exceção; `shape_unpacked`
  preserva as chaves novas.
- Harness: driver com `_esbmc_result` e `assert`; cada cópia aponta o seu `assert`, inclusive quando só a do
  ESBMC cresce; método
  com `self.<atributo>`; sem corte depois da suspeita; construtor recusado.
- Replay: violação achada pela busca; corrigida sem violação; entrada fixa; `assert` dentro do alvo não conta;
  sem `property_line` o comportamento antigo; execução descartada vira `unavailable`.
- Oráculo: tabela de vereditos; leitura do ESBMC por linha; troca pela corrigida com deslocamento de linha;
  controle sem entradas; nomes novos sem colisão.
- Loop: `VALUE_CONFIRMED`, `PROPERTY_REJECTED`, `VALUE_VIOLATION` sem corrigida; reparo de propriedade ausente;
  a versão corrigida nunca aparece em prompt algum; prompt de exceção inalterado; `run_verify` entrega a
  corrigida só a hipóteses de valor; `--fixed-sources` chega a `run_verify`.
- Métrica e roteamento: hipótese de valor sem braço; orquestrador mantém o veredito do motor; contagem à parte e
  só na linha; `--api-agent-everywhere` pula hipóteses de valor; relatório por localização à parte.

## Fora do escopo

- Rodar experimento, medir ou comparar (item 6).
- Mudar o prompt base de detecção ou a métrica de triagem (`_REACHES_ESBMC`); ver decisões.
- Propriedades com subscrito, chamadas de método, `old(x)`, quantificadores ou comparação com outra execução
  (propriedade diferencial).
- Braços do orquestrador (busca dinâmica, entradas do LLM, ESBMC fixado, agente) para hipóteses de valor.
- Harness escrito pelo agente para hipóteses de valor.
- Trocar no controle também os helpers que a correção mudou (só a função alvo é trocada).
- Sondas do ESBMC para `assert` em Python e anotação de variável com o valor devolvido (item 2).

## Decisões tomadas sem a Fernanda

1. **A propriedade é pedida na etapa de spec, não na detecção.** A chamada de spec já vê a fatia verbatim e
   a hipótese, já tem reparo guiado e já devolve só JSON; pedir na detecção mexeria no prompt que o item 4
   compara.
2. **A entrada das hipóteses de valor é a variante `A15`**, com o campo `metadata.failure_mode`, em vez de
   mudar o prompt base ou de ler o prefixo "resultado errado" de `violated_property`. Sem `A15`, nada muda.
3. **O `hypothesis_id` só inclui o oráculo quando ele é `"value"`**, para não invalidar ids já gravados.
4. **Vereditos de exceção reaproveitados** (`UNVALIDATED`, `OTHER_FAILURE`, `ESBMC_MISSED`,
   `NOT_CONFIRMED`) quando o sentido é o mesmo; só três nomes novos.
5. **A violação do ESBMC é identificada pela linha do `assert`**, e a do replay pela `AssertionError` no
   driver na linha da cópia do replay; não depende do texto que o ESBMC imprime para a mensagem do
   `assert`. Cada cópia guarda a sua linha, já que uma reescrita pode crescer só a do ESBMC.
6. **O controle só aceita `not_reproduced`.** Se a corrigida levanta exceção ou não roda, não dá para dizer
   que ela respeita a propriedade: fica `VALUE_VIOLATION`, que não conta.
7. **Execução descartada com entradas fixas vira `unavailable` só no modo propriedade.** O comportamento atual
   dos braços de exceção (`llm_input`, `pinned`) não muda neste item.
8. **Sem corte depois da suspeita em hipótese de valor**, mesmo que a fórmula fique maior: o valor errado só
   aparece depois do `return`.
9. **`returns` obrigatório, sem `object`**, e anotado só na variável do driver; a função alvo continua sem
   anotação de retorno (preserva o código real). Se o ESBMC recusar essa forma, vira sonda do item 2.
10. **Construtor fica de fora**: a chamada não devolve valor útil e não há receptor antes dela.
11. **Nenhum braço do orquestrador roda em hipótese de valor**, inclusive em `--api-agent-everywhere`.
12. **Métrica à parte e somada**: `value_confirmed_at_bug` ao lado de `confirmed_at_bug`, com a soma em
    `confirmed_at_bug_with_value`; nenhuma das duas partes some do relatório.
13. **A métrica de triagem não muda agora.** Com `A15`, mandar um bug de valor errado ao ESBMC continua
    contando como "deveria segurar" em `_triage_metrics`; o item 6 decide se o rótulo muda.
14. **A propriedade lê as entradas depois da chamada.** Um método que muda uma lista recebida verá a lista
    já mudada; está documentado no prompt.
