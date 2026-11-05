# Lote B: melhorias do modo scan (04/11/2026)

Feito por um agente de IA (Claude) numa cópia isolada do repositório, sem commit. Nenhuma chamada a LLM
paga foi feita: os testes usam analisadores e verificadores falsos. As medições com ESBMC usaram o build
congelado `~/esbmc-master/esbmc.sh` (d520a903ae, Bitwuzla, com `--no-pointer-check --no-align-check`).

Resumo dos padrões escolhidos:

| Item | Ligado por padrão? | Por quê |
|---|---|---|
| 6 sondas no scan | sim, como no hybrid | conserta uma limitação antiga; `--no-capability-probes` desliga |
| 16 retomada | sim | conserto; a detecção salva volta a ser usada |
| 17 async | nada novo entra na seleção | o ESBMC verifica um formato, mas nenhum dos dois verificadores chama com `await` |
| 18 tipo de variável local | sim | conserto do grafo (chamadas que ficavam como externas) |
| 19 chamadores de chamadores | não: `--scan-caller-depth N`, padrão 1 | aumenta o prompt (custo) |
| 20 `--esbmc-command` no agente | sim | conserto |
| 21 `Examples/`, `samples/` | sim | conserto |
| 22 "Nível que decidiu" | sim | conserto do texto |

## Item 6: sondas de capacidade no scan

O que mudou: o scan com o motor (`--scan-verify engine`, o padrão) agora roda as sondas como o hybrid
(`resolve_rules` com o mesmo comando ESBMC, o mesmo cache e o mesmo `--bound`), passa ao motor só as regras
que as sondas deixaram ligadas e grava o relatório das sondas em `scan_report.json`, em
`config.capabilities`. `--no-capability-probes` deixa todas as regras ligadas, como no hybrid. O conjunto de
regras entra na impressão digital da verificação (item 16): se outro ESBMC desligar outras regras, a
verificação recomeça em vez de misturar vereditos.

No modo agente as sondas não rodam: o agente escreve o próprio harness e não usa as regras de reescrita.

Arquivos: `src/main.py` (`mode_scan`), `src/research_pipeline/scan/pipeline.py` (`execute_scan` recebe
`capabilities`; conjuntos entram ordenados na impressão digital).

Teste: `test_cli_scan_engine_uses_the_capability_probes_like_hybrid` (as regras chegam ao motor, o relatório
das sondas vai para o `scan_report.json`, o modo agente não recebe `rules`).

## Item 16: retomada do scan

O que mudou: a impressão digital do checkpoint foi dividida em duas.

- Detecção: raiz, variantes, modelo do detector, foco, prompts e funções selecionadas. Se mudar, a
  retomada continua sendo recusada com erro, como antes.
- Verificação: verificador (motor ou agente), configurações do motor (caderno, `--heal`, bound, timeout,
  regras...) e agora também o backend e o modelo da LLM que escreve a especificação (antes ficava de fora).
  Se só isso mudar, a detecção salva é reaproveitada (nenhuma chamada de detecção é refeita) e a
  verificação recomeça do zero. Os vereditos antigos não se misturam com os novos: saem do checkpoint e vão
  para `scan_verify_discarded_<12 primeiros caracteres da impressão antiga>.json`, e o terminal avisa.

Isso respeita a decisão de 02/11 (não misturar resultados de verificação) e evita pagar a detecção de novo.
Um checkpoint do formato antigo (uma impressão digital só) é recusado, com a mensagem dizendo isso.

Arquivo: `src/research_pipeline/scan/pipeline.py` (`_detection_fingerprint`, `_verify_fingerprint`,
`_resume`).

Testes: `test_verify_config_change_reruns_verify_but_never_mixes_verdicts`,
`test_a_different_verifier_keeps_the_detection_and_reruns_verify_from_scratch`,
`test_a_detection_change_still_refuses_the_resume`,
`test_spec_model_and_probe_rules_enter_the_verify_fingerprint`; os testes antigos de impressão digital
passaram a usar a parte certa.

## Item 17: funções async

Medição primeiro. Programas pequenos em pares (um seguro, um com divisão por zero ou índice fora da lista
plantado), rodados com:

```
~/esbmc-master/esbmc.sh <arquivo>.py --unwind 5 --multi-property
```

e conferidos no CPython (o seguro roda sem erro, o com bug levanta a exceção). Os programas e o script
estão no scratchpad da sessão (`async_probes/src` e `async_probes/run.sh`), não no repositório.

| Formato | Seguro | Com bug |
|---|---|---|
| `async def` no módulo, `await` dentro de `async def main` com `asyncio.run(main())` | SUCCESSFUL | FAILED (ZeroDivisionError) |
| `async def` no módulo passado direto a `asyncio.run(f(a, b))` | SUCCESSFUL | FAILED |
| função comum que chama `asyncio.run(f(a, b))` | SUCCESSFUL | FAILED |
| `async def` que faz `await` de outra `async def` do módulo | SUCCESSFUL | FAILED |
| `await` dentro de um `for` | SUCCESSFUL | FAILED |
| `async def` com lista (`xs[0]`) | SUCCESSFUL | FAILED (IndexError) |
| método `async` de classe (`await c.ratio(10)`) | ERROR: "awaiting a value other than a call to a module-level async function is not supported" | igual |
| método `async` que faz `await self.helper()` | ERROR (mesma mensagem) | igual |
| `await asyncio.sleep(0)` dentro da função | ERROR (mesma mensagem) | igual |
| `async def` dentro de outra função | ERROR: "AsyncFunctionDef statements are not supported" | igual |

Os testes de regressão do próprio ESBMC (`regression/python/async_def_*`) também mostram que uma
`async def` decorada é recusada e que chamar uma `async def` sem `await` não roda o corpo (o ESBMC diz
SUCCESSFUL sem olhar a função).

O que isso permite e o que não permite: o ESBMC verifica certo o formato "função `async def` do módulo,
sem decorador, cujos `await` são todos chamadas a outra `async def` do módulo". Mas o pipeline não consegue
usar isso hoje: o motor recusa uma função async como ponto de entrada (`grounding.py`, "async entry point is
not supported") e o harness dele chama a função sem `await`; as notas do agente mandam parar diante de
`async`. Por isso nenhuma função async voltou para a seleção: voltaria só para gastar uma chamada de
detecção e terminar sem veredito. Fazer o motor chamar com `asyncio.run(...)` mexe no harness, no replay no
CPython e no teste gerado, fora do modo scan; ficou como sugestão para a Fernanda decidir.

O que mudou: o motivo da exclusão ficou preciso. O grafo guarda em cada função async o motivo pelo qual o
ESBMC a recusa (`async_limit`: método ou aninhada, decorada, `async for`/`async with`, `await` de outra
coisa), e a seleção conta dois motivos separados:

- `async_esbmc`: o ESBMC-Python recusa o formato (a própria função ou uma que a contém);
- `async_harness`: o ESBMC verifica o formato, mas nenhum harness do pipeline chama com `await`.

Arquivos: `src/research_pipeline/scan/callgraph.py` (`_async_limit`), `src/research_pipeline/scan/pipeline.py`
(`_async_exclusion`; a chave `async` de `excluded` virou `async_esbmc` e `async_harness`).

Testes: `test_async_limit_names_the_shapes_esbmc_refuses`; os testes de seleção conferem as duas contagens.

Medição num repositório real, sem LLM (só o grafo e a seleção), no PyAthena (`~/alvos/PyAthena`): as 142
funções async ficam em `async_esbmc` (são métodos) e 0 em `async_harness`.

## Item 18: tipo de variável local no grafo

O que mudou: numa função, `x = Classe(...)` (ou `x = modulo.Classe(...)`) e `x: Classe = ...` (também com a
anotação entre aspas) fazem `x.metodo()` apontar para `Classe.metodo`, com herança. A regra é conservadora:
se o nome também é parâmetro, é reatribuído a outra coisa, vira variável de `for`, `with`, `except`,
`import`, `global` ou `nonlocal`, a chamada continua externa.

Arquivo: `src/research_pipeline/scan/callgraph.py` (`_local_types`, `_class_named`).

Testes: `test_a_local_built_by_a_constructor_or_annotated_resolves_to_the_class_method` e
`test_a_local_with_another_binding_stays_external`.

Medição (sem LLM): grafo do PyAthena com o código antes e depois da mudança, com o script
`measure_graph.py` do scratchpad (`python measure_graph.py <pasta src> ~/alvos/PyAthena`). Chamadas
resolvidas: 1774 para 1794 de 7498 (+20), funções com chamador: 716 para 730. Nenhuma aresta antiga sumiu.
Conferi algumas à mão, por exemplo `session = _S3WriteSession(...)` seguido de `session.start()` em
`pyathena/filesystem/s3.py:1690`.

## Item 19: chamadores de chamadores

O que mudou: `--scan-caller-depth N` (padrão 1, que é o comportamento de antes). Com 2, o contexto de
chamadas do prompt de detecção mostra também quem chama os chamadores, depois de todas as chamadas diretas,
com o cabeçalho `# call in <função>, <arquivo>, line N (to <chamador>, 1 call(s) away from the target):`. O
limite de 8 chamadas e 3000 caracteres continua valendo, então as diretas têm prioridade. Recursão e ciclos
param (um chamador já mostrado não é mostrado de novo nos níveis de cima). A profundidade vai para
`scan_selection.json` e `scan_report.json`, e muda a impressão digital da detecção (o prompt muda).

Ficou com flag porque deixa o prompt maior. No PyAthena, a soma do contexto de chamadores das 1662 funções
selecionáveis passou de 647 393 para 1 028 352 caracteres com profundidade 2 (+59%), medido com o mesmo
script (`python measure_graph.py <pasta src> ~/alvos/PyAthena 2`). Não medi se isso ajuda a detecção: seria
uma rodada paga.

Arquivos: `src/research_pipeline/scan/context.py` (`depth`, `_sites`), `src/research_pipeline/scan/pipeline.py`
(`caller_depth`), `src/main.py` (flag).

Testes: `test_depth_two_adds_the_callers_of_the_callers_after_the_direct_ones` e
`test_caller_depth_reaches_the_prompt_context_and_the_selection`.

## Item 20: `--esbmc-command` no agente do scan

O que mudou: o agente do scan recebe o comando inteiro (binário e flags), não só o primeiro item. O binário
é conferido antes de montar o agente: se não existe ou não é executável, o scan para com
`Erro: o ESBMC do agente não existe ou não é executável: <caminho>` e código 1, antes de gastar qualquer
chamada do agente.

Achado no caminho: o argparse lê uma palavra que começa com `-` como opção, então o exemplo da ajuda
(`--esbmc-command esbmc --python python3`) nunca funcionou. Agora as flags vão entre aspas numa palavra só
(`--esbmc-command "esbmc --python python3"`), que é dividida como no shell. Um caminho que existe no disco
não é dividido, mesmo com espaço. Isso vale para todos os modos, porque a opção é a mesma.

Arquivo: `src/main.py` (`_CommandWords`, `mode_scan`).

Testes: `test_cli_scan_verify_agent_uses_the_agent_verifier` (comando completo chega ao agente) e
`test_cli_scan_verify_agent_fails_clearly_without_the_esbmc_binary`.

## Item 21: exclusão de pastas sem diferenciar maiúsculas

O que mudou: `Examples/`, `Docs/` e afins agora ficam fora da seleção, e `samples/` e `sample/` entraram na
lista, junto de `examples`, `example`, `docs` e `doc`. Continuam entrando com `--scan-include-examples`.

Arquivo: `src/research_pipeline/scan/pipeline.py`.

Teste: `test_example_folders_are_excluded_whatever_their_case_and_samples_too`.

## Item 22: "Nível que decidiu"

O que mudou: a linha saía como dicionário do Python (`{'esbmc_engine': 1}`). Agora sai em texto:
`Nível que decidiu: ESBMC pelo motor: 1; só a LLM: 2.` A linha fica no `scan_summary.md` (o pedido citava
o `relatorio.md`, mas é no resumo que ela aparece).

Arquivo: `src/research_pipeline/scan/pipeline.py` (`_levels_text`).

Teste: `test_scan_report_has_levels_for_the_engine_and_for_the_agent` confere o texto novo.

## Verificação

- Suíte completa: `pytest -q` na raiz deu 1412 passados e 1 pulado em 7 min 08 s. Depois disso um teste de
  seleção ganhou um método async a mais; os 73 testes do scan (`tests/test_scan_*.py`) foram rodados de novo
  e passaram.
- Cada comportamento novo foi conferido com uma mutação: o código foi quebrado de propósito numa cópia, um
  ponto por vez, e o teste do item teve que falhar. As 14 mutações (itens 6, 16, 17, 18, 19, 20, 21 e 22)
  fizeram o teste falhar. Uma delas (no item 17, ignorar o motivo da recusa do ESBMC) passou na primeira vez,
  porque nenhum teste tinha um método async; o teste foi reforçado e a mutação passou a ser pega.
- Lint: o `pylint` não está instalado nesta máquina (nem no `.venv`, nem no Python do sistema), então usei
  o `ruff` do `.venv`. Os arquivos do scan e os testes passam limpos. Em `src/main.py` sobram 3 avisos que
  já existiam antes desta mudança (ordem dos imports e um gerador em `set(...)`); não mexi neles.
- Não houve commit.

## Item 17b: harness com asyncio.run (05/11)

Feito por um agente de IA (Claude) na cópia principal, sem commit e sem nenhuma chamada a LLM (a
especificação de entrada foi escrita à mão, como nos testes). Continua o item 17: lá o ESBMC verificava
certo um formato de função async, mas o motor não chamava a função com `await`. Agora chama.

O que mudou:

- O motor aceita como ponto de entrada uma `async def` do módulo, sem decorador, que o ESBMC consegue
  rodar: sem `async for`/`async with`, e cujos `await` são todos chamadas a outra `async def` do mesmo
  módulo que também segue essas regras. O harness chama a função com `asyncio.run(f(...))` e põe
  `import asyncio` logo antes da função do driver (`_esbmc_main`), nas duas cópias do programa (a do ESBMC
  e a do replay no CPython), então os números de linha continuam batendo. Numa hipótese de valor errado, o
  resultado continua indo para `_esbmc_result`: `_esbmc_result: int = asyncio.run(f(...))`.
- Os outros formatos async continuam recusados, agora com o motivo certo: "async entry point: async method
  or nested coroutine", "decorated coroutine", "async for or async with", "await of something other than a
  module-level async function" (por exemplo `await asyncio.sleep(0)`, ou `await` de uma `async def` que o
  ESBMC recusa) e "await of a function from another module" (o harness do motor só tem um módulo; o nome
  importado viraria um stub comum, que não pode receber `await`).
- A regra que decide o formato ficou num lugar só (`coroutine_limit` em `verify/astutil.py`), usada pelo
  grafo do scan e pelo motor. Antes ela ficava só no grafo (`_async_limit`). Ela agora também olha as
  funções async que a função espera com `await`: se uma delas tem um formato recusado, a de fora herda o
  motivo.
- Replay no CPython: o programa do replay já tem o driver com `asyncio.run`, então a exceção sai de dentro
  da função async, na mesma linha. O filtro do que pode rodar no host (`sandbox.py`) aceita `import asyncio`
  só quando o programa usa apenas `asyncio.run`; qualquer outro uso (`asyncio.create_subprocess_shell`, o
  módulo passado como valor, `import asyncio as x`, `import asyncio.subprocess as x`, `from asyncio...
  import`) continua recusado.
- Teste gerado pelo ESBMC (`--generate-pytest-testcase`): o programa dado ao gerador chama
  `asyncio.run(f(__VERIFIER_nondet_int(), ...))`. O teste que o ESBMC escreve chama `f(a, b)` sem `await`
  (o corpo não rodaria), então o pipeline reescreve essa chamada para `asyncio.run(f(a, b))` antes de rodar
  o pytest.
- Scan: a função async do módulo com formato aceito volta para a seleção, e também uma função comum
  definida dentro dela (o motor a copia para o nível do módulo, como já fazia com outras funções internas).
  O grupo `async_harness` agora conta só as funções async que fazem `await` de uma função de outro módulo;
  `async_esbmc` continua com os formatos que o ESBMC recusa.

O modo agente não mudou: as notas dele continuam mandando parar diante de `async`.

Arquivos: `src/research_pipeline/verify/astutil.py` (`find_function` passa a achar uma `async def` do
módulo, mas não um método async; `coroutine_limit`; `entry_of` continua só com funções comuns),
`verify/grounding.py` (`Grounded.coroutine`, `_module_coroutine_limit`), `verify/render.py` (driver),
`verify/sandbox.py` (`_only_asyncio_run`), `verify/pytest_gen.py` (`pytest_reproducer(coroutine=...)`,
`awaited_test`), `verify/loop.py` (passa `coroutine`), `scan/callgraph.py` (`_async_limit` usa a regra
comum), `scan/pipeline.py` (`_async_exclusion` e a frase do terminal).

Testes novos ou alterados (pytest, sem LLM; os que rodam o ESBMC usam o build congelado):

- `tests/test_verify_grounding.py`: `test_a_module_level_coroutine_grounds_as_a_coroutine_entry` e
  `test_coroutine_shapes_esbmc_or_the_harness_cannot_run_stay_refused` (5 formatos recusados, com o motivo).
- `tests/test_verify_render.py`: `test_a_coroutine_target_is_run_by_asyncio_in_both_copies` e
  `test_a_coroutine_value_hypothesis_keeps_the_awaited_result`.
- `tests/test_verify_replay.py`: `test_a_rendered_coroutine_replays_through_asyncio_run` (ZeroDivisionError
  na linha da hipótese).
- `tests/test_verify_sandbox.py`: `test_asyncio_may_run_a_coroutine_and_nothing_else`.
- `tests/test_verify_pytest_gen.py`: `test_awaited_test_runs_each_call_of_the_coroutine_with_asyncio` e
  `test_a_coroutine_reproducer_awaits_the_target` (roda o ESBMC e o pytest).
- `tests/test_verify_esbmc_integration.py`: `test_a_coroutine_is_verified_through_asyncio_run` (uma
  versão segura e uma com bug, do começo ao fim no motor).
- `tests/test_scan_callgraph.py`: o teste de funções internas agora espera a async do módulo e a função
  dentro dela na seleção (e o método async fora); o teste dos motivos ganhou o caso herdado;
  `test_a_coroutine_awaiting_another_module_is_left_to_the_harness_bucket` é novo.
- `tests/test_scan_pipeline.py`: `fetch` (async do módulo) entra na seleção; `async_harness` vai a 0.
- `tests/test_verify_review_fixes.py`: o teste antigo dizia que toda função async era recusada; agora ele
  confere que um método async é recusado.

Checagem por mutação: 15 mutações, uma por mudança (tirar o `asyncio.run` do driver, tirar o `import
asyncio`, ignorar o motivo da recusa, não marcar `coroutine`, não reconhecer o nome importado, não
reescrever o teste gerado, não pôr `asyncio.run` no programa do gerador, a reescrita errar o nome, liberar
todo o asyncio no sandbox, não liberar nenhum, aceitar `import asyncio.subprocess as x`, o scan tratar toda async como recusada, o grupo
`async_harness` nunca ser usado, o grafo não herdar o motivo, o loop não passar `coroutine`). Todas foram
pegas por algum teste. O script está no scratchpad da sessão (`a17b/mut.py`), não no repositório.

Medições (ESBMC congelado d520a903ae). Primeiro, o motor do começo ao fim, sem LLM: o script `a17b/e2e.py`
do scratchpad chama `verify_hypothesis` com uma especificação fixa (`a`, `b` inteiros; `xs` lista de
inteiros) e `--unwind 5`, sobre este módulo:

```
async def scale(b):
    return b * b + 1

async def safe_ratio(a, b):     # seguro: b * b + 1 nunca é 0
    d = await scale(b)
    return a // d

async def ratio(a, b):          # bug: d - 5 é 0 quando b é 2 ou -2
    d = await scale(b)
    return a // (d - 5)

async def first(xs):            # bug: xs[0] com a lista vazia
    total = 0
    for x in xs:
        total += await scale(x)
    return xs[0] + total
```

| Alvo | ESBMC | Veredito do motor | Replay no CPython | Teste do ESBMC |
|---|---|---|---|---|
| `safe_ratio` | SUCCESSFUL | NOT_CONFIRMED | nada reproduzido | (não se aplica) |
| `ratio` | FAILED (ZeroDivisionError, linha 7) | CONFIRMED | ZeroDivisionError na linha 7, entradas `[-2, -2]` | reproduz |
| `first` | FAILED (IndexError, linha 9) | CONFIRMED | IndexError na linha 9, entradas `[0, 0]` (lista vazia) | não gerado: o gerador só aceita entradas escalares |

Os mesmos harnesses gravados pelo motor, rodados à mão com

```
~/esbmc-master/esbmc.sh <harness>.py --unwind 5 --multi-property
```

deram SUCCESSFUL para `safe_ratio` e FAILED para `ratio` (`[ratio.assertion.1] line 7 uncaught exception:
ZeroDivisionError`) e `first` (`[first.assertion.3] line 9 uncaught exception: IndexError`). No caso seguro,
o log mostra que as propriedades da própria `safe_ratio` (divisão por zero na linha 7) foram checadas e
passaram, então o SUCCESSFUL não vem de o ESBMC ter pulado o corpo. O ESBMC avisa "no operational model for
module 'asyncio'", mas trata `asyncio.run` mesmo assim, como já mostrava a tabela do item 17. Rodar o
harness de `ratio` no CPython com as entradas do replay (`a = -2`, `b = -2`) termina em
`File "ratio_replay.py", line 7, in ratio` / `ZeroDivisionError: integer division or modulo by zero`, de
dentro do `asyncio.run`.

Scan num repositório real, sem LLM (só o grafo e a seleção), no PyAthena (`~/alvos/PyAthena`): nada muda.
As 135 funções async de lá são 122 métodos ou funções internas, 12 com `await` de outra coisa e 1 decorada;
nenhuma é uma `async def` do módulo com formato aceito. Com as funções comuns definidas dentro delas, 142
ficam em `async_esbmc` e 0 em `async_harness`; 1662 funções selecionáveis, nenhuma async. Ou seja, nesse
alvo a mudança não traz função nova; ela só vale para repositórios com funções async no nível do módulo.

O que continua de fora: métodos async (`await c.m()`, `await self.helper()`), funções async internas,
decoradas, com `async for`/`async with`, com `await` de qualquer coisa que não seja uma `async def` do
mesmo módulo (inclusive `await asyncio.sleep(0)`) e com `await` de função de outro módulo. O teste gerado
pelo ESBMC continua limitado a entradas escalares, como para funções comuns.

Testes rodados (cada um com `timeout 10m`, `.venv/bin/python -m pytest -q -p no:cacheprovider`):
`tests/test_scan_*.py` (93 passaram), `tests/test_verify_[a-l]*.py` (496 passaram),
`tests/test_verify_[m-z]*.py` (481 passaram, depois de atualizar o teste antigo de
`test_verify_review_fixes.py`), e os arquivos tocados de novo no fim (307 passaram). Lint: `ruff` do
`.venv` nos arquivos alterados, sem aviso novo nas linhas desta mudança (os avisos que sobram já existiam:
ordem de imports em `loop.py`, `scan/pipeline.py`, `test_verify_esbmc_integration.py` e
`test_verify_review_fixes.py`, e `exec` em testes).
