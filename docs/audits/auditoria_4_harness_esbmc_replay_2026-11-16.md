# Auditoria 4: harness, ESBMC, self-healing e replay (16/11/2026)

Documento de trabalho para a Fernanda. Escrito por IA (Claude) a pedido dela, só com leitura de código e de artefatos.
Nada foi executado além de scripts Python que leem o JSON da rodada e imprimem contagens. Não rodei pipeline, ESBMC,
testes nem LLM. As decisões sobre o que fazer com os achados são dela.

**Marcações.** [F] fato conferido no código ou no artefato citado. [I] inferência minha a partir de fatos. [H] hipótese
que precisa de teste. [NV] não verificado.

**Base.** Rodada `artifacts/pgene601/congelado-2026-11-16-r1/` (commit `f086e22`, igual a `f55cc5a` em `src/` [F:
`git diff f55cc5a f086e22 -- src` vazio]). Os números de linha de `healing.py` são os da versão `f086e22`: o arquivo
tem hoje uma mudança não comitada (só um `Protocol`, que desloca as linhas depois da 442) [F: `git diff`]. Os
outros arquivos citados de `verify/` são iguais ao commit da rodada [F]. "Rodada" abaixo é sempre a de 16/11.

Esta auditoria aprofunda as Partes 3 e 7 de `auditoria_pipeline_2026-11-16.md` e a Parte 2 de
`auditoria_0_inventario_2026-11-16.md`, sem repetir o que já está lá.

---

## Resumo em oito achados

1. **O replay quase nunca usa o contraexemplo do ESBMC.** Em 12 das 13 confirmações, nenhum valor do contraexemplo
   chegou ao replay; ele achou a entrada sozinho, numa busca em domínios pequenos. Só no simpleio_43 o valor do
   ESBMC (`-0.0`) entrou [F, recalculado com `counterexample_seeds` sobre os logs]. A confirmação significa "o
   ESBMC e uma busca independente no CPython concordam no tipo da exceção", e não "o CPython reproduziu a entrada
   do ESBMC".
2. **No pymodbus_2921, o ESBMC e o CPython verificaram programas diferentes.** O healing trocou a anotação do
   parâmetro do alvo para `data: str`, e isso só valeu para a cópia do ESBMC. O replay rodou `data: bytes`. Com
   `str`, o CPython levantaria `TypeError` em `int.from_bytes`, antes do `IndexError`. O modelo do ESBMC aceitou
   `int.from_bytes(str)` e ainda acusou acesso fora dos limites dentro do próprio `models/int.py` [F]. O bug existe no
   CPython, mas a parte "provada pelo ESBMC" dessa confirmação não vale para o código real.
3. **A troca de assinatura é permitida pelo desenho.** `same_code` ignora a assinatura do alvo (`preservation.py:321-326`)
   e o prompt de healing autoriza anotar a assinatura. `body_edits` trata a edição da linha `def` como simplificação
   do corpo, então ela não vai para o replay (`healing.py:201-208, 484-487`) [F]. Em 6 hipóteses o healing editou a
   linha `def` do alvo; uma delas virou CONFIRMED [F].
4. **No blinka_434, a violação que o ESBMC achou está na guarda que o pipeline injetou.** O `AttributeError` vem de
   `_esbmc_none_attribute` (linha 4 do programa), chamada na linha da suspeita [F]. A sonda `none_metodo_cadeia`
   mostra que esse ESBMC não acusa chamada de método sobre `None` (`recusa`, "safe") [F: `config.capabilities`].
   Sem a guarda, o ESBMC provavelmente diria "seguro" [I].
5. **O mavproxy_881 confirmou um estado que o código real não produz.** O `KeyError` exige `g` em `read_gaps` sem
   chave em `read_gap_times`. O harness gera as duas estruturas de forma independente, mas o código real sempre
   altera as duas juntas (`arquivo_com_bug/cps_mavproxy_881.py:378-380, 398-403`) [F]. Provável falso positivo de
   harness [I].
6. **A regra oficial de "apontado e reproduzido" conta artefatos de stub.** Ela aceita `other_failure` dentro da
   função. Em pycomm3_331 e piouart_6, a exceção esperada saiu de valores inventados por stubs: `bytes([-1])` vindo
   de `chain.from_iterable` e `memoryview(list)` vindo de `array.array` [F nos programas de replay]. Na variante
   estrita, 13 cai para 11.
7. **Análise de sensibilidade nos 8 confirmados por bug** (seção 9): a variante (a) mantém 8, a (b) dá 7, a (c)
   dá 7 (ou 4 se também exigir ausência de asserções de desenrolamento), a (d) dá 5 e todas juntas dão 4: gps_60,
   gpiozero_716, simpleio_43 e paho_118.
8. **Taxonomia (seção 10).** Das 65 hipóteses sem veredito do ESBMC, 32 batem em limite do frontend Python sobre o
   código do projeto, 7 em recusa provocada pelo que o harness gerou, 8 em contexto do harness, 5 em erro interno do
   ESBMC, 12 em limite de voltas ou de tempo e 1 na LLM [I: minha reclassificação do grupo `other`]. Além disso, 4
   resultados "com veredito" têm só mensagens `Unsupported:` do ESBMC, contadas como violação [F].

---

## 1. Fluxo completo de verificação (o que o código faz)

Cada hipótese passa por `verify_with_healing` (`healing.py:445-504`), que chama `verify_hypothesis`
(`loop.py:200-357`) uma vez e depois uma vez por rodada de reparo.

| Passo | Quem decide | O que acontece | Onde |
|---|---|---|---|
| 1. Pré-checagem | código | Localiza função e expressão (grounding por AST), monta um programa com tipos `int` provisórios, pergunta ao ESBMC que membros de biblioteca ele recusa e os troca por stub. Para com UNSUPPORTED, GROUNDING_FAILED ou MISSING_DEPENDENCY sem gastar LLM. | `loop.py:175-197, 226-228` [F] |
| 2. Especificação | LLM | Devolve só JSON com `params`, `attributes`, `stubs`, `assumptions`. | `prompts/input_spec_prompt.txt` [F] |
| 3. Validação do JSON | código | Tipos permitidos, assunções sintáticas, guardas dos chamadores viram assunções (`spec_context: callers`). JSON recusado gera reparo. | `attempts.py`, `spec.py:184-213`, `caller_facts.py:341-358` [F] |
| 4. Montagem | código | Receptor com `__init__` trocado por uma "casca" de atributos nondet, stubs, driver `_esbmc_main`. Gera duas cópias: a do ESBMC (com reescritas) e a do replay (sem elas). | `render.py:496-590` [F] |
| 5. ESBMC | código | `--unwind 5 --multi-property`, com escalonamento (seção 6). | `esbmc_run.py:91-200` [F] |
| 6. Reparo da especificação | LLM | Se o ESBMC recusa ("repairable"), a LLM recebe a mensagem e tenta de novo, até 2 vezes. | `loop.py:290-293` [F] |
| 7. Replay | código | Executa a cópia do replay no CPython isolado, com busca determinística. | `replay.py:110-171`, `replay_worker.py:277-331` [F] |
| 8. Refinamento | LLM | Se o replay falha na função mas fora da suspeita, pede uma assunção nova, até 2 vezes. | `loop.py:326-338, 360-373` [F] |
| 9. Veredito | código | Combina leitura do ESBMC e replay. | `outcome.py:126-143`, `loop.py:313-346` [F] |
| 10. Self-healing | LLM | Se o veredito é UNSUPPORTED, MISSING_DEPENDENCY ou GROUNDING_FAILED, a LLM propõe edições ou stubs e o passo 1 recomeça. | `healing.py:445-504` [F] |
| 11. Avaliação | código | Por função, contra o `expected_type` do gabarito. | `v2_evaluator.py:281-331` [F] |

### Respostas às perguntas 1 a 3 da tarefa

**Hipótese para especificação [F].** A LLM recebe nome da função, expressão suspeita, texto da hipótese, lista de
parâmetros e atributos sem tipo, chamadas de biblioteca trocadas por stub, membros usados nos objetos e o recorte
literal do módulo (`loop.py:98-123`). Ela não escreve código: o prompt diz "You never write code".

**Campos que a LLM define [F].**
- `params`: tipo de cada parâmetro sem anotação. Se a assinatura já tem anotação, ela vence o tipo da LLM. No gps_127
  a LLM pediu `Optional[str]` e o programa saiu com `str` (`programs/b045b79082a6_a0.py:30`).
- `attributes`: tipo de cada `self.x` que a casca precisa criar.
- `stubs`: tipo de retorno de cada chamada de biblioteca e de cada membro de objeto tipado `object`.
- `assumptions`: expressões booleanas sobre entradas; só `len()` é chamada permitida (`spec.py:184-206`).

**Como isso vira programa [F].** Cada tipo vira um valor não determinístico (`render.py:130-165`):
- um `Optional[T]` vira `x = None; if nondet_bool(): x = <valor>`;
- um `bytes` vira só dois valores possíveis, `b"ab"` ou `b""` (`render.py:146-147`);
- uma lista recebe no máximo 2 elementos (1 quando aninhada); listas simples usam `nondet_list(3, ...)`;
- um `object` vira uma classe `_Obj_<nome>` cujos campos são nondet.

As assunções viram `__ESBMC_assume(...)` no driver, junto com as guardas do `__init__` real (`constructor_guards`,
`grounding.py:280`) (`render.py:424-426`). O mesmo driver vai para as duas cópias, então as assunções valem também
no replay (`replay_worker.py:149-151`, `assume` descarta a execução).

---

## 2. Matriz de transformações e riscos semânticos (perguntas 4 e 5)

"Onde" diz em que cópia a transformação existe. O replay roda a cópia sem as reescritas de compatibilidade, mas
**com** a casca, os stubs, os cortes de fatiamento e as edições de healing feitas fora do corpo do alvo.

| Transformação | Onde | O que faz | Efeito semântico | Risco |
|---|---|---|---|---|
| `receiver_init_replaced` / `_added` | ambas | Troca o `__init__` por casca de atributos nondet (`slicing.py:170-209`) | Superaproxima: estados que nenhuma construção real produz ficam possíveis. Mitigado só pelas guardas do `__init__`. | **alto** (é a origem do mavproxy_881) [I] |
| `properties_as_attributes` | ambas | Uma `@property` vira atributo livre | Superaproxima: ignora o cálculo da propriedade | médio [I] |
| `unreachable_methods_removed`, `special_methods_removed`, `unused_class_attributes_removed` | ambas | Apaga métodos e atributos de classe que o alvo não alcança (`slicing.py:170-209`) | Preserva o caminho do alvo | baixo [I] |
| `unused_definitions_removed` | só ESBMC | Apaga definições que nada nomeia, inclusive `__repr__`/`__str__` (`compat.py:594-617`) | Preserva o caminho do alvo | baixo [I] |
| `stubbed_imports`, `external_chains_flattened`, `opaque_values` | ambas | Biblioteca vira stub que devolve nondet | Superaproxima: o stub pode devolver o que a biblioteca nunca devolve | **alto** para exceções nascidas no stub (pycomm3_331, piouart_6, pymodbus_2980) [F nos replays] |
| `dead_guards_folded` | ambas | Dobra `TYPE_CHECKING` e `sys.version_info` | Preserva no CPython do replay | baixo [F: `dead_guards.py:1-6`] |
| `decorators_removed:property` | ambas | Tira o decorador para chamar o alvo | Preserva | baixo |
| `cut_after_suspect` | só ESBMC | Corta o que vem depois da suspeita; dentro de laço, só a 1ª volta | Subaproxima: pode esconder falha, não cria (`compat.py:634-672`) | baixo para falso positivo; causa NOT_CONFIRMED como o pycomm3_331 [I] |
| `none_guards` | só ESBMC | Injeta `raise AttributeError/TypeError` se um valor usado é `None` (`compat.py:765-816`) | Cria a exceção que o ESBMC não modela; o replay decide | médio: a prova do ESBMC passa a ser sobre a guarda (blinka_434) [F] |
| `nondet_clock` | só ESBMC | `time.time()` vira relógio nondet crescente | Superaproxima o relógio; o replay usa o relógio real | baixo [F: `compat.py:819-863`] |
| `compat_bytearray`, `compat_percent_format`, `compat_rebound_parameter`, `compat_attribute_item`, `compat_io_error_alias`, `conditional_assignments_split` | só ESBMC | Reescritas ligadas por sondas de capacidade | Pensadas para preservar; `bytearray` perde o `ValueError` de byte > 255 (`compat.py:463`) | baixo a médio |
| `typing_import_added`, `builtin_exceptions_stubbed` | ESBMC (replay recebe linhas em branco) | Declarações | Preserva | baixo |
| Healing: edição fora do corpo | ambas | Muda classes, imports, construtores | Pode mudar comportamento (pymodbus_1738 tirou `**kwargs`; mavproxy_881 trocou o módulo `time`) | médio |
| Healing: edição dentro do alvo, incluindo a linha `def` | só ESBMC | Simplifica corpo ou troca anotação | ESBMC e replay verificam programas diferentes | **alto** (pymodbus_2921) [F] |
| Refinamento | ambas | Assunção nova | Pode forçar a entrada do bug | médio (pymodbus_2980) |

---

## 3. Self-healing: o que ele pode alterar (pergunta 6)

**Quando roda [F].** Só quando o veredito é UNSUPPORTED, MISSING_DEPENDENCY ou GROUNDING_FAILED (`healing.py:49`).
Até 3 rodadas por obstáculo e 9 no total (`healing.py:460, 469-472`). Para quando a mensagem é igual à anterior
(`healing.py:466-467`) ou quando aparece erro interno conhecido (`healing.py:441-465`). A recusa sem contorno
(`async`, parâmetro numpy) só é testada no primeiro resultado (`healing.py:453`), e não dentro do laço: no
pymodbus_2921 a mensagem "numpy array parameter is expected" apareceu nas rodadas 1 e 3 e o reparo continuou [F].

**O que a LLM pode mandar [F].** `edits` (troca de texto que aparece uma vez), `definitions` (stubs),
`function`/`expression` (mover a hipótese, no caso de grounding) (`healing.py:59-65, 396-437`). Código real do
repositório pode entrar pelo grafo de chamadas (`healing.py:371-376`).

**Quais travas existem [F].**
- Os stubs não podem levantar exceção, fazer `assert` nem devolver valor fixo (`stub_problems`, `healing.py:155-177`).
- O corpo do alvo pode mudar só se a expressão suspeita continuar lá (`patch_problems`, `healing.py:180-198`).
- A edição dentro do alvo é aplicada só à cópia do ESBMC; as edições de fora vão para as duas (`healing.py:484-487`).
- A assinatura do alvo não é comparada (`preservation.py:321-326`).

**O que isso permite na prática.** Ele pode alterar arquivo (só a cópia em memória), assinatura do alvo
(anotações), corpo do alvo (na cópia do ESBMC), construtores e classes vizinhas, e módulos inteiros por stub.

**Números da rodada [F, script sobre `v2_verify_report.json`].**

| Medida | Valor |
|---|---|
| Hipóteses com healing | 66 de 106 |
| Rodadas de healing registradas | 99 (21 sem patch aplicado: recusado pelas travas ou sem reparo utilizável) |
| Hipóteses em que a LLM propôs stubs em alguma rodada | 52 |
| Hipóteses com edição da linha `def` do alvo | 6 (gpiozero_716 `__init__`, mavproxy_989 duas vezes, piouart_6, pymavlink_1217, pymodbus_2921) |
| Hipóteses com `**kwargs` removido | 2 |
| Veredito final das 66 | 52 LLM_ONLY, 5 BOUND_INCONCLUSIVE, 3 UNVALIDATED, 3 CONFIRMED, 2 NOT_CONFIRMED, 1 OTHER_FAILURE |

**Efeito colateral da troca de assinatura [F].** Quando o healing anota a assinatura e o replay fica sem a anotação,
o replay não consegue ser montado: "original body cannot be rendered for the replay: parameter 'min_temp': missing
type" (gpiozero_716), o mesmo em mavproxy_989 e piouart_6. O replay fica "unavailable".

---

## 4. Validações semânticas automáticas que existem (pergunta 7)

O que o código verifica sozinho [F]:
- **Tipos permitidos e forma** do JSON (`spec_problems`), inclusive número de itens quando o código desempacota um stub.
- **Assunções:** só a sintaxe e os nomes usados (`spec.py:184-206`). Não há teste de satisfatibilidade nem de que a
  assunção não implica o gatilho.
- **Guardas dos chamadores** viram assunções e uma especificação que as contradiz é recusada (`caller_facts.py:341-358`).
- **Guardas do `__init__` real** viram assunções sobre a casca (`grounding.py:280-283`).
- **Preservação do alvo** depois do healing, sem olhar a assinatura (`preservation.py:308-326`).
- **Stubs sem valor fixo** (`healing.py:155-177`).
- **Replay no CPython** com a linha dentro da expressão suspeita e o tipo da exceção entre os do ESBMC (`outcome.py:130-137`).
- **HANDLED_BY_CALLER**, quando todos os chamadores capturam a exceção (`outcome.py:135-136`).
- **DEPENDS_ON_LIBRARY**, quando o `KeyError` vem de dicionário devolvido por stub (`loop.py:339-343`).
- **AttributeError de membro herdado** que o harness não tem vira replay indisponível (`loop.py:413-422`).

O que não existe [F por ausência no código lido]:
- comparação entre o programa do ESBMC e o do replay;
- checagem da linha onde o ESBMC achou a violação;
- checagem de invariantes entre atributos gerados;
- checagem de que o valor que causou a exceção não veio de um stub (fora o caso do dicionário).

Um detalhe: no caminho do contraexemplo parcial (timeout), o código devolve CONFIRMED antes das checagens de
HANDLED_BY_CALLER e DEPENDS_ON_LIBRARY (`loop.py:313-320`) [F]. Isso valeu para o gps_127.

---

## 5. Refinamento (pergunta 8)

**Regra [F].** Se o veredito é OTHER_FAILURE e o replay falhou dentro da função, mas fora da suspeita, a LLM
recebe: "add an assumption ... that excludes the input making that line fail" (`loop.py:369-373`). Até 2 vezes
(`MAX_REFINEMENTS`, `loop.py:360`). Se não chega a CONFIRMED, o resultado volta ao primeiro OTHER_FAILURE guardado.

**Na rodada [F].** 11 hipóteses refinaram; 10 terminaram OTHER_FAILURE e 1 CONFIRMED (pymodbus_2980).

**O caso pymodbus_2980, em detalhe [F nos programas `f330a5b2a35a_a0/a1`].**
- Na primeira tentativa, o replay achou `ModbusException` na linha 64 com `data = b"ab"`: `byte_count = 97`, e o stub
  de `struct.unpack` devolveu um `record_length` ímpar, rejeitado por `FileRecord.__post_init__`.
- A busca enumera a última escolha primeiro (`_next_vector`, `replay_worker.py:121-126`). A primeira escolha, que
  decide entre `b"ab"` e `b""`, só mudaria depois de esgotar as combinações dos stubs dentro do laço [I]. Por isso o
  replay não chegou a `b""`, que dá `IndexError` na suspeita.
- A LLM então pôs `len(data) == 0`, e o replay achou o `IndexError` em 85 execuções.

Leitura [I]: aqui a assunção compensou uma limitação da busca e um artefato de stub. A entrada `b""` é legítima para
o código real, mas a assunção fixa exatamente o gatilho. O prompt de especificação proíbe "an assumption that rules
out the trigger", não uma que o force; nada no código impede isso.

---

## 6. ESBMC: flags, limites, solvers, estratégias (pergunta 9)

**Comando da rodada [F].** O binário `/mnt/e/esbmc-builds/esbmc-master-build-bw/src/esbmc/esbmc` foi chamado
diretamente (`config.esbmc_command`), sem o `esbmc.sh` que acrescenta `--no-pointer-check --no-align-check`
(`~/esbmc-master/esbmc.sh`). Linha base: `--unwind 5 --multi-property <programa>` (`esbmc_runner.py:63-67`,
`esbmc_run.py:102`). Solver padrão: Bitwuzla 0.9.0 (aparece no log do pymodbus_2921). Commit `de72a905e0`,
`dirty: true`. O comentário de `esbmc_runner.py:14-17` e o `possiveis_problemas/README.md` falam das duas flags,
que não valeram nesta rodada.

**Escalonamento, na ordem [F: `esbmc_run.py:111-200`].**
1. Se só há asserções de desenrolamento em laços de biblioteca: `--unwindsetname` com 64 nesses laços.
2. Se só há asserções de desenrolamento: unwind 10 e depois 20.
3. Ainda só isso em 20: `--incremental-bmc`, depois `--k-induction`.
4. Em timeout: `--boolector`, depois `--z3`.
5. Timeout com contraexemplo parcial: uma reexecução de 300 s.
6. Timeout sem nada: uma reexecução de 300 s.
7. Ainda timeout: unwind 3 e 2, aceitando só violação.
8. Por fim, aceita o contraexemplo parcial, se houver.

**O que a rodada usou [F].** Na última tentativa de cada hipótese: unwind 5 em 84, 20 em 6, 10 em 2, sem ESBMC em 8.
Nenhuma ficou em `incremental` ou `k-induction` como resultado final. Houve 3 tentativas com contraexemplo parcial
(uma virou o CONFIRMED do gps_127, com Z3 a 300 s).

**Limite de tempo.** 180 s por execução (`config.timeout`), 300 s no escalonamento.

---

## 7. Contraexemplo e replay (perguntas 10 e 11)

**Extração [F].** `counterexample_seeds` (`replay.py:55-69`) lê só números (`int` e `float`), só dos estados do
driver `_esbmc_main`, até 8 por tipo. Strings não aparecem no trace do ESBMC: é a issue #9091, fechada como "not
planned" (`possiveis_problemas/README.md`, reprodutor 45). Para strings existe `string_witness`, que só roda quando o
replay falhou (`loop.py:296-311`).

**Replay [F: `replay_worker.py:277-331`].**
1. Uma passada de até 100 execuções com os valores do contraexemplo, se houver.
2. A busca completa em domínios pequenos: `int` em {0, 1, -1, 2}, `float` em {0.0, 1.0, -1.0}, `str` em {"", "a"} mais
   literais curtos do alvo, listas de até 2 itens; até 400 execuções e 20 s.
3. Para na primeira execução que levanta exceção na suspeita. Se nenhuma levanta, guarda a primeira falha de outro
   lugar como `other_failure`.

**Na rodada [F, recalculado sobre os logs com a mesma função].** Nas 13 confirmações, só o simpleio_43 teve valor do
driver no contraexemplo (`-0.0`). Nas outras 12, o ESBMC atribuiu os valores dentro de construtores ou métodos, não
no driver, ou eram strings e `bytes`, que não são lidos. O replay usou a busca padrão. Entradas que vieram dos
literais do alvo: `'*.'` no paho_118 e `'0<4'` no gps_127.

**Então a resposta à pergunta 11 é:** o replay faz outra busca. Ele roda o harness, não o projeto, e não exige a
mesma entrada do ESBMC. O modo `seeds_only` existe (`replay.py:114-117`) mas não é usado no veredito [F].

**Outra evidência de que é independente.** O único teste gerado pelo próprio ESBMC (`--generate-pytest-testcase`) que
reproduziu foi o do simpleio_43. Nos outros 12, o gerador não aceita método ou entrada não escalar [F: campo `pytest`].

**Linha da violação no ESBMC [F, logs].** Em 12 das 13, a violação do ESBMC está na linha da suspeita. No blinka_434
está na função `_esbmc_none_attribute` (linha 4), a guarda injetada. O veredito não confere a linha do ESBMC
(`outcome.py:130-137`).

---

## 8. Como cada veredito é decidido (pergunta 12)

Lido em `outcome.py:126-143` e `loop.py:313-357` [F]:

| Veredito | Condição |
|---|---|
| CONFIRMED | O ESBMC dá violação, o replay levanta exceção dentro das linhas da suspeita e o tipo dela está entre os tipos que as mensagens do ESBMC indicam (qualquer linha, qualquer propriedade). |
| CONFIRMED (timeout) | Timeout com contraexemplo parcial de `uncaught exception` e replay reproduzido com esse tipo (`loop.py:313-320`). |
| UNVALIDATED | Violação, mas o replay não reproduz, não roda, ou reproduz um tipo que o ESBMC não listou. |
| OTHER_FAILURE | Violação e o replay falha em outro lugar (depois do refinamento, se houver). |
| NOT_CONFIRMED | O ESBMC diz seguro (`no_violation_found` ou `no_vcc_generated`) e o replay não reproduz. |
| ESBMC_MISSED | O ESBMC diz seguro e o replay reproduz (0 na rodada). |
| BOUND_INCONCLUSIVE | Só asserções de desenrolamento ou falhas dentro dos modelos do ESBMC. |
| ESBMC_TIMEOUT | Timeout sem contraexemplo aproveitável. |
| LLM_ONLY | O ESBMC nunca aceitou o programa, mesmo depois do healing (`healing.py:497-498`). |

O mapeamento de mensagem para exceção (`outcome.py:69-83`) também converte "array bounds" em `IndexError` e "null
pointer" em `AttributeError` ou `TypeError`, mesmo quando a falha está num modelo interno do ESBMC [F]. Uma mensagem
`Unsupported: ...` conta como violação (não é artefato), mas não vira exceção [F].

---

## 9. As 13 confirmações, uma a uma

Coluna "Risco" = risco de a confirmação não valer para o código real, com o motivo. "Opt." = atributo, parâmetro ou
stub `Optional` na especificação final.

| Caso (função) | Esperada | ESBMC | Replay (linha; entradas) | Healing | Refin. | Opt. | Transformações relevantes | Risco |
|---|---|---|---|---|---|---|---|---|
| blinka_434 (`PWMOut.deinit`) | AttributeError | AttributeError, na guarda injetada | AttributeError l.55; `[0, False]` = `_pwmpin` None | não | não | `_pwmpin: Optional[object]` | casca, `cut_after_suspect:2`, `none_guards:1` | **médio** |
| dronekit_890 (`Vehicle.is_armable`) | TypeError | TypeError + 3 desenrolamentos | TypeError l.459; `fix_type` None | não | não | `fix_type: Optional[int]` e 2 atributos | casca, `properties_as_attributes` (21), stubs | **baixo** |
| gpiozero_716 (`CPUTemperature.value`) | ZeroDivisionError | ZeroDivisionError | l.83; `[0.0, 0.0, 0.0]` | não | não | não | casca, `temperature` vira atributo | **baixo** |
| gps_126 (`GPS._update_timestamp_utc`) | ValueError | ValueError + 1 desenrolamento | l.47; `time_utc = ''` | não | não | `timestamp_utc: Optional[object]` (fica depois do corte) | casca, `cut_after_suspect:4` | **baixo** |
| gps_60 (`_parse_talker`) | IndexError | IndexError | l.3; `data_type = b""` | não | não | não | `cut_after_suspect:1` | **baixo** |
| paho_118 (`Client._host_matches_cert`) | IndexError | IndexError + 2 desenrolamentos | l.191; `('', '*.')` | não | não | não | casca, `dead_guards_folded:8`, corte | **baixo** |
| pymodbus_2921 (`FramerTLS.decode`) | IndexError | 2 falhas no `models/int.py`, IndexError, 3 desenrolamentos | l.25; `data = b"ab"` | **4 rodadas: tira o retorno, `bytes` para `bytearray` para `bytes` para `str`** | não | não | casca nova, corte | **alto** |
| simpleio_43 (`map_range`) | ZeroDivisionError | ZeroDivisionError | l.9; cinco `-0.0` (do contraexemplo) | não | não | não | corte | **baixo** |
| gps_127 (`_parse_degrees`) | IndexError | ValueError (parcial, Z3 300 s) | ValueError l.22; `'0<4'` | não | não | pedido, ignorado | `cut_after_suspect:4`, `none_guards:1` | médio |
| mavproxy_1032 (`FakeGPSModule.idle_task`) | AttributeError | ZeroDivisionError | l.77; `rate = 0.0` | não | não | não | casca, `nondet_clock:1`, corte | médio |
| mavproxy_881 (`FTPModule.check_read_send`) | TypeError | KeyError | l.195; 257 execuções | 1 rodada: `import time` vira stub `_TimeModule` | não | não | casca com 13 atributos, `compat_bytearray`, corte | **alto** |
| pymodbus_1738 (`calculateRtuFrameSize`) | struct.error | IndexError | l.55; `buffer` curto | 1 rodada: tira `**kwargs` de 2 construtores | não | não | stubs, corte | médio |
| pymodbus_2980 (`ReadFileRecordRequest.decode`) | struct.error | IndexError | l.61; `data = b""`, 85 execuções | não | **sim: `len(data) == 0`** | não | casca, stubs, corte | médio |

### Fichas curtas

**blinka_434 [F, salvo marcação].** O código real põe `_pwmpin = None` no `__init__` (linha 22) e no fim de `deinit`
(linha 54), então `None` é um estado real. O bug do gabarito é o segundo `deinit`; o harness não chama duas vezes, ele
parte de um estado em que `_pwmpin` já é `None`. A violação do ESBMC está em `_esbmc_none_attribute`, a guarda do
pipeline. Diferença entre os programas: o do ESBMC tem a guarda e o corte; o do replay tem o corpo inteiro e um stub
de `GPIO`. Risco médio porque a "prova" é a guarda e não a semântica do ESBMC [I].

**dronekit_890 [F].** `self._fix_type = None` está na linha 1175 do arquivo real, antes da primeira mensagem de GPS.
A escolha `Optional[int]` tem base no código. A diferença entre os programas fica em stubs de `logging` e
`mode_mapping`, sem efeito no caminho. Risco baixo.

**gpiozero_716 [F].** Atributos `float` livres; `min_temp == max_temp` dá a divisão por zero. A propriedade
`temperature` virou atributo livre. Os programas diferem só no `__repr__`. Risco baixo [I].

**gps_126 [F].** `int('')` na primeira linha suspeita. O atributo `Optional` só é lido depois do corte, então não
participa. Risco baixo.

**gps_60 [F].** `data_type[0]` com `b""`. O domínio de `bytes` tem só dois valores. A expressão do gabarito é outra
(`bytes(data_type.upper(), "ascii")`, em `GPS.update`), mas a regra é por função. Risco baixo.

**paho_118 [F].** O ESBMC tem `_esbmc_end_path()` depois da suspeita; o replay roda até o fim. A entrada `'*.'`
veio dos literais do alvo. Risco baixo.

**pymodbus_2921 [F].** Rodadas do healing: (0) tirou `-> tuple[int, int, int, bytes]` por causa de "tuple[bytes, ...]
annotations are not supported"; (1) trocou para `bytearray` por "a list passed where a numpy array parameter is
expected"; (2) voltou para `bytes` por "bytearray is not supported"; (3) trocou para `str`, e o ESBMC aceitou. Todas
marcadas `simplified_body: true`, então nenhuma foi para o replay.

Diferença relevante:
- ESBMC (`programs/8432febfbe95_a0.py:22-24`): `def decode(self, data: str):` e `data: str = nondet_str()`.
- Replay (`_a0_replay.py:22-25`): `def decode(self, data: bytes) -> tuple[...]` e `data = b"ab"` ou `b""`.

No log, as duas primeiras violações estão em `/esbmc-vfs/python/models/int.py` linha 28, função `from_bytes`
("array bounds violated" e "Access to object out of bounds"). Para `str`, o CPython levanta `TypeError` em
`int.from_bytes` [I, conhecimento de CPython; não executei]. O replay prova o bug no programa com `bytes`; o ESBMC não
verificou esse programa. Risco alto para a afirmação "confirmado pelo ESBMC". Pode ser também um defeito do modelo
`int.from_bytes` do ESBMC, que aceita `str` [H, a conferir com reprodutor mínimo antes de qualquer issue].

**gps_127 [F].** ESBMC: timeout a 180 s, contraexemplo parcial com Z3 a 300 s. O replay achou `ValueError` com `'0<4'`,
um pedaço de literal do alvo (`f"{raw[1][:4]:0<4}"`). O bug do gabarito é `IndexError` em `raw[1]`. O CONFIRMED saiu
pelo caminho parcial, sem as checagens de chamador e de stub. Risco médio [I].

**mavproxy_1032 [F].** `rate` vem de um objeto de configurações livre; o padrão real é 5 (linha 21 do arquivo real).
Divisão por zero só com configuração 0. O ESBMC usa o relógio nondet; o replay, o real. Risco médio [I].

**mavproxy_881 [F].** O healing tirou `time` do `import` e definiu `_TimeModule` com `time()` nondet, nas duas cópias.
O `KeyError` exige um estado que o código real não cria (as duas estruturas mudam juntas nas linhas 378-380 e 398-403).
A exceção esperada era `TypeError` (`last_gap_send = None`). Risco alto [I].

**pymodbus_1738 [F].** O healing tirou `**kwargs` de dois construtores por "Variable 'kwargs' is not defined"
(relacionado à #9074, citada em `docs/projeto/HANDOFF.md`). O alvo é método de classe e não usa esses construtores
[I]. `buffer` curto dá `IndexError` em `buffer[7]`; se os chamadores reais garantem tamanho, não analisei [NV].
Risco médio.

**pymodbus_2980.** Ver seção 5. Risco médio.

**Resumo de risco [I].** Baixo: 6 (dronekit, gpiozero, gps_126, gps_60, paho, simpleio). Médio: 5 (blinka, gps_127,
mavproxy_1032, pymodbus_1738, pymodbus_2980). Alto: 2 (pymodbus_2921, mavproxy_881). Entre os 8 confirmados por
bug: 6 baixos, 1 médio (blinka), 1 alto (pymodbus_2921).

---

## 10. Casos representativos dos outros vereditos

| Veredito | Caso | O que aconteceu [F] | Leitura [I] |
|---|---|---|---|
| UNVALIDATED (tipo diferente) | cantools_804 | Replay reproduziu `UnboundLocalError`, a esperada; o ESBMC disse `AttributeError` | O ESBMC não modela variável local não atribuída como Python |
| UNVALIDATED (só `Unsupported`) | mavproxy_1447 | ESBMC: "Unsupported: non-constant argument in str % formatting"; replay: `KeyError`, a esperada | O ESBMC não decidiu nada, mas o resultado conta como "chegou a veredito" |
| UNVALIDATED (replay barrado) | pyrtcm_34 (3), pyspartn_4, ros2cli_1112 | "not executed on host: uses introspection attribute __dict__" / "uses os as a value" | Limite do sandbox do replay, não do código |
| OTHER_FAILURE | pythoncan_225 (6 resultados) | IndexError no ESBMC; replay falha na linha 81, fora da suspeita | O refinamento não resolveu |
| OTHER_FAILURE | gps_126 (outra hipótese) | Assunção `len(time_utc) == 6`; replay `ValueError` na linha 57 | A hipótese irmã já tinha confirmado |
| NOT_CONFIRMED | pycomm3_331 | ESBMC seguro (programa cortado); replay `ValueError` na linha 23, vindo do stub `chain.from_iterable` | Subaproximação do corte e artefato de stub juntos |
| NOT_CONFIRMED | pymodbus_1738 (outra hipótese) | Assunção `len(buffer) > 7` | A LLM excluiu o gatilho de outra hipótese |
| BOUND_INCONCLUSIVE | opcua_671 | Só "unwinding assertion loop 1"; replay reproduziu `TypeError`, a esperada | Bug real que o ESBMC não fechou no limite |
| BOUND_INCONCLUSIVE | piouart_6 | Replay: `memoryview: a bytes-like object is required, not 'list'` | Artefato de stub conta como "reproduzido" na regra oficial |
| ESBMC_TIMEOUT | pymavlink_1217, ros2cli_370 | "ESBMC direto excedeu o tempo limite de 180s." | Limite de tempo |
| LLM_ONLY, crash | mavproxy_741, mavproxy_989 | "ERROR: uncaught exception [N6type2t18symbolic_type_excpE]" | Erro interno do ESBMC contado como recusa |
| LLM_ONLY, linguagem | pythoncan_1811 (8) | "calling ASCReader._datetime_to_timestamp without a converted definition is not yet supported" | Frontend |
| LLM_ONLY, contexto | pymavlink_1259 (3) | "external array.array is both called and read" | Recusa do próprio pipeline |
| LLM_ONLY, `other` | pymodbus_2977 | "Tuple unpacking only supports simple names, not Attribute" | Frontend, mal classificado como `other` |
| SPEC_FAILED | pyserial_820 | Stub `select.select` com tipo errado nas 3 tentativas | Falha da LLM |
| UNSUPPORTED | opcua_1826 | "async entry point: async method or nested coroutine" | Frontend, sem contorno |

---

## 11. Análise de sensibilidade (separada da regra oficial)

A regra oficial não muda. As variantes abaixo foram recalculadas por script a partir do relatório da rodada, com a
mesma lógica de `v2_evaluator.py:281-331` e uma condição a mais em cada uma.

- **(a)** Só replay `reproduced`, sem aceitar `other_failure`.
- **(b)** Exclui hipótese cujo healing editou a linha `def` do alvo.
- **(c1)** Exclui hipótese com mais de uma propriedade violada, sem contar asserções de desenrolamento.
- **(c2)** Exige que a primeira propriedade violada, sem contar desenrolamento, seja `uncaught exception: <esperada>`.
- **(c3)** Como c1, mas também sem nenhuma asserção de desenrolamento.
- **(d)** Exclui harness com `Optional` em parâmetro, atributo ou stub da especificação final.
- **(d')** Mais branda: exclui só quando a mensagem do replay mostra que a exceção veio de `None`.

### Por bug (47 bugs; só aparecem os 13 com algum acerto)

| Bug | Esperada | Reproduzido (oficial) | Reproduzido (a) | Confirmado (oficial) | (a) | (b) | (c1) | (c2) | (c3) | (d) | (d') | b+c1+c2+d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| blinka_434 | AttributeError | sim | sim | sim | sim | sim | sim | sim | sim | não | não | não |
| dronekit_890 | TypeError | sim | sim | sim | sim | sim | sim | sim | não | não | não | não |
| gpiozero_716 | ZeroDivisionError | sim | sim | sim | sim | sim | sim | sim | sim | sim | sim | sim |
| gps_126 | ValueError | sim | sim | sim | sim | sim | sim | sim | não | não | sim | não |
| gps_60 | IndexError | sim | sim | sim | sim | sim | sim | sim | sim | sim | sim | sim |
| paho_118 | IndexError | sim | sim | sim | sim | sim | sim | sim | não | sim | sim | sim |
| pymodbus_2921 | IndexError | sim | sim | sim | sim | não | não | não | não | sim | sim | não |
| simpleio_43 | ZeroDivisionError | sim | sim | sim | sim | sim | sim | sim | sim | sim | sim | sim |
| cantools_804 | UnboundLocalError | sim | sim | não | | | | | | | | |
| opcua_671 | TypeError | sim | sim | não | | | | | | | | |
| mavproxy_1447 | KeyError | sim | sim | não | | | | | | | | |
| pycomm3_331 | ValueError | sim | **não** | não | | | | | | | | |
| piouart_6 | TypeError | sim | **não** | não | | | | | | | | |
| **Total** | | **13** | **11** | **8** | **8** | **7** | **7** | **7** | **4** | **5** | **6** | **4** |

### Por hipótese (13 CONFIRMED)

| Variante | Ficam |
|---|---|
| Oficial | 13 |
| (a) | 13 (todas `reproduced`) |
| (b) | 12 (sai pymodbus_2921) |
| (c1) e (c2) | 12 (sai pymodbus_2921) |
| (c3) | 9 (saem também dronekit, gps_126, paho) |
| (d) | 10 (saem blinka, dronekit, gps_126; no gps_127 o `Optional` foi ignorado) |
| Sem healing | 10 |
| Sem refinamento | 12 |

**Leitura [I].**
- A variante (a) não muda o número de confirmados, porque todo CONFIRMED já tem replay `reproduced`. Ela só muda o
  nível "apontado e reproduzido", e tira exatamente os dois artefatos de stub.
- A variante (c3) é dura demais para BMC. Uma asserção de desenrolamento junto de uma exceção não invalida a exceção
  achada dentro do limite. Eu a reportaria só como informação.
- A (d) pune casos em que o `None` tem base no código (dronekit, blinka) ou nem participa (gps_126). A (d') é a mais
  justa das duas.
- O núcleo que resiste a todas as variantes razoáveis (b, c1, c2, d) tem 4 bugs: gps_60, gpiozero_716, simpleio_43
  e paho_118. Com (d') no lugar de (d), entra o gps_126 e fica 5.
- Uma variante que eu não pus na tabela porque quase zera tudo: "o replay usou a entrada do ESBMC". Só o simpleio_43
  passa (seção 7).

---

## 12. Taxonomia das falhas (perguntas 13 e 14)

Contagem por hipótese no resumo de níveis da rodada (105 hipóteses; uma repetida, `efd0d98e1388`, do pyspartn_4).
O relatório oficial agrupa as 65 sem veredito assim: `esbmc_language` 25, `other` 15, `harness_context` 8,
`esbmc_bound` 8, `esbmc_crash` 4, `esbmc_timeout` 4, `llm_spec` 1 [F]. Reclassifiquei lendo cada mensagem [I]:

| Categoria | Hipóteses | Exemplos de mensagem real |
|---|---|---|
| Frontend do ESBMC sobre construção do projeto | 32 | "Could not resolve type of receiver in member call '.attrib.get()'"; "Cannot resolve nested attribute: _meta"; "calling ... without a converted definition is not yet supported"; "passing a dynamically-typed variable to a function is not yet supported"; "async entry point"; e 14 que estavam em `other`: "Cannot resolve attribute 'Time' on Subscript result", "Tuple unpacking only supports simple names, not Attribute", "bytes.fromhex() is only supported on a constant string", "keyword argument 'error_code' to the modelled method Exception", "except with a dotted/attribute exception type is not supported", "subscripting a value whose type is not known", "bytearray is not supported", "calling attribute 'on_connect', whose value is not known", "class 'PlatformSpecific' is defined 2 times" |
| Frontend recusando algo que o harness criou | 7 | "attribute '_sock' holds a '_Obj_self__sock' and is assigned a '_Opaque'" (minimqtt_5, umqtt_1149); "'AsciiCodec.__init__' does not call the base __init__" (udsoncan_291) |
| Contexto do harness (pipeline) | 8 | "external array.array is both called and read"; "Cannot unpack empty/unsignedbv"; "Function ...@F@_fire_events not found" |
| Erro interno do ESBMC | 5 | "uncaught exception [N6type2t18symbolic_type_excpE]" (4); "Unexpected type in int/ptr typecast" (1, estava em `other`) |
| Limite de voltas | 8 | "unwinding assertion loop 5" mesmo depois de unwind 20 |
| Limite de tempo | 4 | "ESBMC direto excedeu o tempo limite de 180s." |
| LLM (especificação) | 1 | "stub 'select.select' ... needs tuple[...] with 3 items" |
| **Total** | **65** | |

Problemas fora dessas 65, entre as que chegaram ao ESBMC [F]:
- **4 resultados com só `Unsupported:`** no lugar de veredito (mavproxy_1380, mavproxy_1447 duas vezes,
  mavproxy_1032), contados como violação.
- **5 replays barrados pelo sandbox** (`__dict__`, `os` como valor).
- **4 replays que não puderam ser montados** porque o healing anotou a assinatura só na cópia do ESBMC.

**Infraestrutura [F].** 0 falhas operacionais registradas, 1 chamada de síntese com timeout, 0 `PIPELINE_ERROR`. O disco
E:, onde está o binário, ficou inacessível depois do fim da rodada (`docs/experimentos/README.md`, seção da rodada de
16/11). O registro diz que os 229 resultados de tentativa não têm erro de acesso.

**Por bug [F: `RELATORIO_BUGS.md`].** 20 dos 47 bugs pararam porque o ESBMC não aceitou o programa, e 3 por limite.

---

## 13. Limitações do ESBMC-Python (com mensagem real e issue citada nos documentos)

Mensagens copiadas do relatório e dos logs da rodada [F]. As issues são as que os documentos do repositório citam;
não conferi o estado delas no GitHub [NV].

| Limitação | Mensagem real (rodada de 16/11) | Issue nos documentos |
|---|---|---|
| `**kwargs` | "Variable 'kwargs' is not defined in function 'ReadDeviceInformationResponse'" | #9074 (aberta, PR em andamento, `HANDOFF.md`) |
| `bytearray` | "bytearray is not supported; use bytes for an immutable byte sequence" | #10207 (aberta), contorno `compat_bytearray` |
| Anotação `tuple[bytes, ...]` | "tuple[bytes, ...] annotations are not supported" | nenhuma encontrada [NV] |
| `int.from_bytes` com `bytes` | "TypeError: a list passed where a numpy array parameter is expected is not supported" | nenhuma encontrada [NV] |
| `int.from_bytes` com `str` | aceito, com "array bounds violated" dentro de `models/int.py:28` | nenhuma [H] |
| Atributo aninhado | "Cannot resolve nested attribute: _meta" | reprodutor 48, sem issue, contorno em `compat.py` |
| Atributo de resultado de subscrito | "Cannot resolve attribute 'SourceTimestamp' on Subscript result" | nenhuma encontrada [NV] |
| Atributo com classes diferentes | "an attribute holding instances of unrelated classes is not modelled" | #8408 e #10792 tratam de construção parecida (`Union`) |
| `%` com argumento não constante | "Unsupported: non-constant argument in str % formatting" | regra `compat_percent_format`; recusa só em `%d` com float e `%r` (sondas) |
| `None` em cadeia de método | não acusa (sonda `none_metodo_cadeia`: "safe") | contorno `none_guards` |
| `None` em índice ou `len` | exceção errada: "TypeError: object of this type has no len()" (sondas) | contorno `none_guards` |
| Strings no contraexemplo | o valor de `nondet_str` não aparece no trace | #9091 (fechada, "not planned") |
| Erro interno | "uncaught exception [N6type2t18symbolic_type_excpE]" | nenhuma encontrada [NV] |
| Variável local não atribuída | ESBMC dá `AttributeError` onde CPython dá `UnboundLocalError` (cantools_804) | nenhuma [H] |
| `async` | "async entry point: async method or nested coroutine" | sem contorno (`healing.py:52`) |

**Documento citado que não existe.** `docs/experimentos/README.md` e a Auditoria 0 citam
`docs/projeto/possiveis_problemas/disciplina_pgene601/RECUSAS_ESBMC.md`, que não existe no repositório nem no
histórico do git [F: `find` e `git log --all`].

---

## 14. Confirmados com mudança relevante de tipo, assinatura, stub ou pré-condição (pergunta 15)

| Caso | Mudança | Vale para o ESBMC, para o replay ou para os dois | Afeta a conclusão? |
|---|---|---|---|
| pymodbus_2921 | assinatura `bytes` para `str` e retorno removido | só ESBMC | sim: o ESBMC verificou outro programa [F] |
| mavproxy_881 | módulo `time` trocado por stub nondet | os dois | parcial; o problema maior é a casca [I] |
| pymodbus_1738 | `**kwargs` removido de 2 construtores | os dois | provavelmente não, fora do caminho [I] |
| pymodbus_2980 | pré-condição `len(data) == 0` | os dois | fixa o gatilho, mas a entrada é válida [I] |
| blinka_434, dronekit_890 | `Optional` gerado pela LLM | os dois | o `None` tem base no código real [F] |
| gps_126 | `Optional` gerado | os dois | não, fica depois do corte [F] |
| todos com casca (10 de 13) | `__init__` trocado por atributos nondet | os dois | risco geral de estado irreal; concretizado no mavproxy_881 [I] |

---

## 15. Evidências que podem entrar no artigo de CPS (entrega 30/11)

O que pode ser dito com segurança, com a fonte:
1. **Funil por hipótese e por bug** da rodada única de 16/11 (`v2_verify_report.json`, `RELATORIO_BUGS.md`), com a
   ressalva de conjunto de desenvolvimento já registrada pela Fernanda.
2. **8 bugs confirmados pela regra oficial**, com a tabela de sensibilidade da seção 11 ao lado. O núcleo robusto tem
   4 bugs (5 com d'). Mostrar os dois números parece mais defensável que mostrar só o 8 [I].
3. **A taxonomia da seção 12**, com mensagens reais. Sustenta a frase "o gargalo principal é o frontend Python do
   ESBMC" (32 a 39 das 65 sem veredito) [I].
4. **O replay como filtro.** 9 UNVALIDATED e 10 OTHER_FAILURE mostram violações do ESBMC que não viraram confirmação
   [F]. Mas é preciso dizer que o replay faz busca própria e roda o harness, não o projeto (seção 7).
5. **Dois exemplos qualitativos de risco**, um de cada tipo: pymodbus_2921 (healing mudou o tipo só para o ESBMC) e
   mavproxy_881 (casca com estado impossível). Isso mostra que a auditoria olhou caso a caso.
6. **Limitações do ESBMC-Python** da seção 13, só com as issues que estão nos documentos.

O que não deve entrar sem nova medida [I]:
- "o ESBMC provou o bug no código real";
- "mesma entrada no ESBMC e no CPython";
- qualquer taxa de falso positivo, já que o controle não rodou em 16/11 (Auditoria 1).

---

## 16. Melhorias propostas (as decisões são da Fernanda)

### Essenciais para o mestrado

1. **Registrar a divergência entre os dois programas.** Gravar no resultado a assinatura do alvo nas duas cópias e
   marcar o caso quando elas diferem; hoje isso só aparece lendo os `.py`. Mudar `body_edits` para não tratar a linha
   `def` como corpo seria outra opção, mas muda o pipeline congelado e exige nova rodada (regra 1 de 16/11).
2. **Gravar de onde veio a entrada do replay:** passada do contraexemplo, busca padrão ou literal do alvo. Dá para
   rodar o `seeds_only` como evidência extra, sem mudar o veredito.
3. **Gravar a linha e a função da violação do ESBMC** e mostrar quando ela não está na suspeita (blinka_434) ou está
   num modelo interno (pymodbus_2921).
4. **Separar `Unsupported:` de violação** na classificação; hoje 4 resultados contam como "ESBMC chegou a veredito"
   sem ter chegado.
5. **Contar `symbolic_type_excp` e `int/ptr typecast` como erro interno do ESBMC**, fora de LLM_ONLY. A regex
   `_INTERNAL` de `healing.py:441` não pega essas mensagens.
6. **Reportar a variante (a) ao lado do "apontado e reproduzido" oficial**, ou anotar que 2 dos 13 vêm de stub.
7. **Criar o `RECUSAS_ESBMC.md`** que os documentos já citam, ou tirar a citação.
8. **Fixar as variantes de sensibilidade antes da próxima rodada** e registrá-las em `docs/experimentos/README.md`,
   como foi feito com as regras de 16/11.

### Opcionais e trabalhos futuros

- Checar invariantes simples entre atributos da casca, por exemplo duas coleções que o código sempre altera juntas.
- Detectar exceção que nasce de valor de stub em geral, não só do dicionário (`external_origin.py`).
- Barrar ou sinalizar assunção que fixa o gatilho, como `len(data) == 0` sobre o índice `data[0]`.
- Ampliar o domínio de `bytes` (hoje `b"ab"` e `b""`) e de inteiros na busca do replay.
- Fazer o replay no projeto real, com o chamador real, para os confirmados.
- Fazer reprodutores mínimos para `int.from_bytes(str)` aceito pelo ESBMC e para `UnboundLocalError` virando
  `AttributeError`, e conferir no GitHub se já há issue ou PR antes de abrir.
- Fazer mais de uma rodada, para medir variação.

---

## 17. Como conferir o que está aqui

- Os campos citados estão em `v2_verify_report.json`: `results[].attempts`, `healing`, `replay`, `harness_state`,
  `levels.rows`, `evaluation.by_function.cases`, `config.capabilities`.
- Os programas estão em `programs/<id>_aN.py` e `_aN_replay.py`; os logs do ESBMC, em `programs/<id>_aN/esbmc_*/esbmc_outputs/`.
- Os scripts de leitura que usei ficaram no rascunho da sessão (`seeds.py`, `variants.py`, `loc.py`) e só leem
  arquivos. Se quiser, eles podem ser copiados para `scripts/`.

**Uso de IA.** Este documento foi produzido por IA (Claude) a partir de leitura de código, artefatos e contagens por
script. As classificações de risco e a reclassificação da taxonomia são interpretação da IA e precisam da revisão
da Fernanda.
