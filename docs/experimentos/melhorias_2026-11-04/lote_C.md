# Lote C (04 e 05/11/2026): regras de compatibilidade do harness e stubs

**O que é este lote:** mudanças no filtro que reescreve o harness só para o ESBMC (`verify/compat.py`), nas
sondas que ligam e desligam essas regras (`verify/capabilities.py`), no relógio usado pelo harness e na forma
como o pipeline repete uma chamada do ESBMC que estourou o tempo. Nenhuma chamada a LLM. Nada commitado.

**ESBMC de todas as medições:** `~/esbmc-master/esbmc.sh` (build `d520a903ae`, Bitwuzla, o wrapper acrescenta
`--no-pointer-check --no-align-check`), com `--unwind 5 --multi-property`, como no motor verify.

**Base do código:** branch `feat/harness-de-agente` (`dc64068`). A cópia de trabalho começou no `master`, que não
tinha os commits de 03/11 citados na tarefa (`61d1c60`, `be9a846`); ela foi avançada para `dc64068` por
fast-forward, sem commit novo.

**Uso de IA:** este registro, o código e as medições foram feitos por um agente Claude a pedido da coordenação.
As decisões de manter ou descartar cada regra seguem a regra da Fernanda (contorno que preserva comportamento vai
para o filtro) e ficam para ela conferir.

Como cada regra foi conferida, seguindo o padrão da `compat_rebound_parameter` (`61d1c60`):

1. um programa pequeno (sonda) mostra que o ESBMC `d520` recusa ou erra sem a regra;
2. o programa reescrito dá o veredito certo: SUCCESSFUL no seguro e FAILED quando o `assert` é trocado
   (checagem por mutação);
3. o CPython roda o programa original e o reescrito com o mesmo resultado;
4. quando existe, o harness real do caso também é medido.

As sondas novas entram em `capabilities.PROBES`: enquanto o ESBMC recusar o programa original, a regra fica
ligada; quando um ESBMC novo aceitar todas as sondas de uma regra, ela desliga sozinha.

## Item 4: contornos do agente que faltavam no filtro (regras 10 a 15 da skill `regras-harness`)

A regra 14 (65, `compat_rebound_parameter`) já existia. A 15 (lambda em método, #9840) muda a estrutura da
função, então não é contorno do filtro. Situação dos outros:

| Reprodutor | Regra da skill | Resultado |
|---|---|---|
| 66 (`a, b = n.m[0]`) | 13 | **feito**: regra `compat_attribute_item` |
| 58 (`op = f; f(op(1))`) | 11 | **feito**: regra `compat_function_alias` |
| 57 (string nondet global lida em função) | 10 | **não feito**: nenhum contorno preserva o corpo da função |
| 61 e 62 (`or` com atributo inexistente) | 12 | **não feito**: o único contorno que funciona muda linhas e exige provar que o atributo não existe |

### 66: `compat_attribute_item`

- **O que faz:** `a, b = n.m[k]`, quando `m` é anotado com uma classe `M` que define `__getitem__`, vira na
  cópia do ESBMC `_esbmc_item1: M = n.m; a, b = _esbmc_item1[k]`, na mesma linha. O CPython avalia `n.m`, depois
  `k`, depois `__getitem__`, nas duas formas. A regra só vale quando toda ligação do atributo tem a mesma
  anotação, a classe não tem subclasse no módulo e o programa não usa `setattr`, `delattr`, `__dict__`,
  `locals`, `vars`, `eval`, `exec` ou `globals`. A reexecução no CPython continua usando o programa sem a regra.
- **Sondas:** `probes/atributo_getitem_valor.py` (seguro) e `probes/atributo_getitem_violacao.py` (`assert`
  trocado). No `d520`, as duas dão `ERROR: Cannot unpack pointer - only tuples and arrays can be unpacked`:
  regra ligada.
- **Reescrito:** reprodutor 66 reescrito: SUCCESSFUL; com `assert a == 2`: FAILED (`assertion a == 2`). CPython:
  roda sem erro antes e depois.
- **Harness real (agente, caso `09c8208ce2b3`, `dz_real_04`,
  `artifacts/v2/tarefa10-passo4-2026-10-28/cases/09c8208ce2b3/harness.py`):** a regra reescreve as 7 linhas
  `... = nl.mgrid[...]`. No `d520`, o harness original para antes, em `NameError: name '...' is not defined`
  (anotação `tuple[Grid, ...]` do stub do agente). Trocando só essa anotação por `tuple` nas duas cópias:
  original `Cannot unpack pointer`; reescrito passa desse ponto e para em `Cannot unpack tuple: expected 3
  values, got 5`, que é o stub do agente devolvendo tuplas de tamanho variável (o README já dizia que o stub
  estava errado). Ou seja: a regra resolve o obstáculo dela no programa real, mas o caso ainda não chega a
  veredito por causa do stub.
- **Motor de regras:** o harness do motor para o `dz_real_04` (`36e448914bc9`) para antes, em `Cannot unpack
  symbol` no `src_arr.shape` (parâmetro anotado com a classe vazia `nt_tensor`), outro problema, fora deste lote.
- **Observação:** o braço de agente não passa pelo `compat.py` (`agent_arm.py` não chama `rewrite_compat`); para
  ele, a regra 13 da skill continua valendo.

### 58: `compat_function_alias`

- **O que faz:** com `op = f` no nível do módulo, toda chamada `op(...)` vira `f(...)` na cópia do ESBMC. Só quando
  `op` e `f` são ligados uma única vez no programa inteiro (nem parâmetro, nem variável local, nem `global`), `f`
  é uma função do módulo sem decorador, e nada que roda antes de `op = f` pode chamar código (só imports,
  definições, classes sem decorador e atribuições cujas chamadas são `nondet_*`).
- **Sondas:** `probes/alias_de_funcao_valor.py` e `probes/alias_de_funcao_violacao.py`. No `d520`, as duas dão
  `ERROR: Function ... @op' type mismatch: expected code` (exit 134): regra ligada.
- **Reescrito:** reprodutor 58 reescrito (`f(f(1))`): SUCCESSFUL; com `assert f(f(1)) == 2`: FAILED.
- **Medição extra:** dentro de uma função, `f(op(1))` como instrução sozinha também aborta; reescrito, SUCCESSFUL.
  `assert f(op(1)) == 1` e `x = op(1)` não abortam. Um alias local (`op = f` dentro da função) e o alias
  condicional do `bip_pandas_7` (`if c: op = lt` / `else: op = le`) também não abortam: SUCCESSFUL e, com o
  `assert` trocado, FAILED. O caso real `bip_pandas_7` não chega a essa linha no motor: para antes em `__new__`
  (`UNSUPPORTED` em `final-2026-10-17`).

### 57: não feito

Variantes medidas no `d520`, todas abortam com `Unexpected index type in computer_pointer_offset`: global
inicializada por função auxiliar, global atribuída por uma função com `global`, `__ESBMC_assume(len(s) < 4)`
logo depois, `nondet_str() + ""`, e a mesma leitura com `n = len(s)` ou `s.split()`. Curiosamente,
`assert len(s) >= 0` na função não aborta. Só funciona passar a string como argumento ou como variável local,
o que muda o corpo da função alvo. No motor, isso pode aparecer quando um stub de constante de biblioteca é
`str` (`render._stubs` declara a constante no nível do módulo com `nondet_str()`). Uma saída seria trocar a
constante por um conjunto pequeno de strings concretas, mas isso reduz o que o ESBMC explora; fica para ela
decidir.

### 61 e 62: não feito

- `if A or c.limit:` partido em `if A: ... elif c.limit: ...`: FAILED com `AttributeError`, certo. Mas
  duplica o corpo e muda o número de linhas, e o filtro precisa manter as linhas.
- Na mesma linha, `True if A else c.limit` e `False if False else c.limit` abortam do mesmo jeito (`Can't
  generate zero for type empty`).
- Uma função auxiliar que lê o atributo funciona (FAILED com `AttributeError`), mas só é exata se o atributo
  comprovadamente não existe, o que pede análise da classe inteira (herança, `__getattr__`, `setattr`).
- No harness do motor para o `nm_real_25` (`4cccb483dd7c`), os atributos lidos no `or` existem (`_Obj_start_line`
  declara `method` e `version`): o motor declara todo membro que o código lê, então o caso vem dos stubs do
  agente. Com a #9838 aberta e o 62 sendo falso negativo silencioso, não entrou regra.

## Item 5: guardas de None que o ESBMC congelado já não precisa

**Sondas no `d520`** (todas as sondas do catálogo, pelo mesmo `check()` do pipeline): aceitas todas as de
`none_guards_attribute`, `none_guards_membership`, `none_guards_ordering` e `none_guards_arithmetic`;
recusadas `none_indice_local`, `none_indice_campo` e `none_len_local` (o ESBMC dá a mensagem de limitação
`TypeError: object of this type has no len()`, não a exceção do Python). Ou seja, no `d520` as sondas já
desligariam as quatro primeiras regras.

**Casos reais** (sem LLM: specs gravadas da rodada `artifacts/v2/final-2026-10-17/v2_verify_report.json`,
`dataset/bugs_reais/arquivo_com_bug`, timeout 120 s, mesmo `verify_hypothesis` do pipeline, com um script
temporário que só escolhe o conjunto de regras). Foram os 19 casos dessa rodada em que uma guarda entrou e o
veredito era CONFIRMED ou ESBMC_MISSED.

| Braço | Regras desligadas | Diferenças contra o braço com todas as regras |
|---|---|---|
| 1 | atributo, `in`, ordem, aritmética | 3 confirmações perdidas: `dd4967e9983d` (bip_thefuck_11) vira UNVALIDATED, `91509f265939` (ip_real_22) vira BOUND_INCONCLUSIVE, `0ddf1474a20f` (tm_real_10) vira ESBMC_MISSED |
| 2 | só atributo | as mesmas 3 perdas |
| 3 | `in`, ordem, aritmética | nenhuma: 19 de 19 com o mesmo veredito (2 casos perdem a guarda e continuam CONFIRMED) |

**O que mudou:**

- **Saíram** as guardas de `in`, comparação de ordem e aritmética: o código em `compat._guarded_values`, as três
  constantes de `rules.py` e as 18 sondas delas (o histórico do git guarda os arquivos).
- **Ficou** a guarda de atributo, e ganhou a sonda `probes/none_metodo_cadeia.py` (com o gêmeo seguro), reduzida
  do `tm_real_10`: método chamado no fim de uma cadeia de campos cujo último elo é None. No `d520`: SUCCESSFUL
  (falso negativo; o CPython dá `AttributeError`). Sem essa sonda, as sondas antigas desligariam a regra de
  atributo no `d520` e o pipeline perderia as 3 confirmações acima. Esse é o achado mais importante do item.
- **Ficaram** as de índice e de `len`/`int`/`float` (sondas recusadas).

## Item 10: `Optional[tuple]` sob `is not None` (`ip_real_32`): não feito

O `ip_real_32` para em `spec_problems` porque o LLM tipa `d_m_y` como `Optional[tuple[int, int, int]]` e o
código desempacota `d, m, y = d_m_y` dentro de `elif d_m_y is not None:`. Medido no `d520` com um programa
reduzido (função com esse desempacotamento e `g[d]` depois):

| Variante | `d520` |
|---|---|
| parâmetro e entrada anotados `Optional[tuple[int, int, int]]` | `Cannot unpack non-tuple type: tag-Optional_struct` |
| local anotado no ramo: `_t: tuple[int, int, int] = d_m_y; d, m, y = _t` | o mesmo erro |
| índices: `d, m, y = d_m_y[0], d_m_y[1], d_m_y[2]` | Bitwuzla aborta (a #9843) |
| parâmetro sem anotação, driver chama com tupla ou com `None` | `Cannot unpack pointer` |
| parâmetro anotado `tuple[...]` e `None` passado num ramo | `type mismatch: got pointer, expected struct` (exit 134) |
| parâmetro e entrada só `tuple[int, int, int]` (sem o caminho `None`) | FAILED com `IndexError`, certo |

Nenhuma forma mantém o caminho com `d_m_y = None`. A única que funciona tira esse caminho da entrada, o que
reduz o que o ESBMC explora. Nos 8 registros do `ip_real_32` em `final-2026-10-17`, a linha suspeita fica fora
do ramo `d_m_y is not None` (por exemplo `H += 12`, que é o bug do gabarito), então restringir a entrada perderia
caminhos que levam ao suspeito. Não entrou regra; a decisão de aceitar essa restrição é dela.

## Item 11: relógio nondet para `time.time()`: feito

- **O que faz:** na cópia do ESBMC, `time.time()` (com `import time`) e `time()` (com `from time import time`)
  viram `_esbmc_clock()`, e o programa ganha no topo este modelo (linhas em branco na reexecução, para os números
  de linha baterem):

  ```python
  _esbmc_clock_now: float = 0.0


  def _esbmc_clock() -> float:
      global _esbmc_clock_now
      step: float = nondet_float()
      __ESBMC_assume(step >= 0.0 and step <= 1e10)
      _esbmc_clock_now = _esbmc_clock_now + step
      return _esbmc_clock_now
  ```

  A primeira leitura pode ser qualquer valor entre 0 e 1e10, e as seguintes nunca voltam. Só vale quando o nome
  vem só daquele import. Regra `nondet_clock` em `rules.py`; função `compat.nondet_clock`; ligada em
  `render.render_program`.
- **Sondas:** `probes/relogio_inicial.py` (`assert started() < 1.0`: o CPython dá `AssertionError` com o relógio
  real; o modelo do ESBMC começa em 0.0 e dá SUCCESSFUL, então a regra fica ligada) e `probes/relogio_monotono.py`
  (duas leituras, diferença `>= 0.0`, seguro: SUCCESSFUL).
- **Reescrito:** `relogio_inicial` reescrito: FAILED (`assertion ... < 1.0`), como o CPython. `relogio_monotono`
  reescrito: SUCCESSFUL; com `> 0.0` no lugar de `>= 0.0`: FAILED (o modelo permite duas leituras iguais).
- **Falsos positivos nos casos MAVProxy:** nas rodadas gravadas da disciplina, as hipóteses cuja função chama
  `time.time()` são as 8 do `cps_mavproxy_1032` (`FakeGPSModule.idle_task`, relatório
  `artifacts/pgene601/melhorias-2026-11-03/baseline_partial_report.json`). Specs gravadas, timeout 120 s, com e
  sem a regra: os 8 vereditos são iguais (3 UNVALIDATED com as mesmas exceções, 5 ESBMC_ERROR por SIGSEGV, o
  reprodutor 67). Nenhuma confirmação nova nem perdida. Como a reexecução no CPython usa o relógio real, um
  contraexemplo que dependa de um horário específico não é confirmado: a regra não cria CONFIRMED falso.

## Item 12: mais tempo só quando o log parcial já mostra a exceção: feito

- **O que faz:** em `esbmc_run.check`, quando todas as tentativas estouraram o tempo mas uma delas já tinha impresso
  um contraexemplo completo de exceção no programa alvo (o caso que o `be9a846` lê como "timeout parcial"), roda
  uma vez mais com 300 s (`ESCALATED_TIMEOUT`), com o mesmo bound e o solver que imprimiu o contraexemplo. Se essa
  rodada termina, o veredito completo substitui o parcial (`how["timeout_escalated"] = 300`); se não termina, fica
  o parcial, como antes. Não acontece quando o limite já é 300 s ou mais, nem num timeout sem contraexemplo. O
  limite global não mudou.
- **Testes:** `tests/test_verify_esbmc_run.py` (a rodada extra tem 300 s e usa o último solver; o veredito completo
  substitui o parcial; sem rodada extra com 300 ou 900 s; sem rodada extra em timeout comum).
- **Medição:** os dois programas GPS do bug oficial (`0f099ccc2b47_a0.py`, `ea8f3d26e5fe_a0.py`, copiados de
  `artifacts/pgene601/melhorias-2026-11-03/timeout-300/`), `check()` com 180 s: os dois deram timeout parcial
  (`ValueError` e `IndexError` no log), a rodada de 300 s rodou, imprimiu 6 propriedades violadas, mas também não
  terminou, e ficou o parcial. Atenção: a máquina estava com várias rodadas do ESBMC de outros agentes ao mesmo
  tempo (carga perto de 8 em 16 núcleos); em 03/11, sozinha, a mesma chamada de 300 s terminou em 236 e 247 s.
  Falta repetir com a máquina livre.

## Arquivos

- `src/research_pipeline/verify/compat.py`: `compat_attribute_item`, `compat_function_alias`, `nondet_clock` e
  `CLOCK_MODEL`; guardas de `in`, ordem e aritmética retiradas.
- `src/research_pipeline/verify/rules.py`: `ATTRIBUTE_ITEM`, `FUNCTION_ALIAS`, `NONDET_CLOCK`; saem
  `NONE_MEMBERSHIP`, `NONE_ORDERING`, `NONE_ARITHMETIC`.
- `src/research_pipeline/verify/capabilities.py` e `probes/`: 8 sondas novas, 18 retiradas.
- `src/research_pipeline/verify/render.py`: o modelo do relógio entra no topo como as guardas.
- `src/research_pipeline/verify/esbmc_run.py`: rodada extra de 300 s.
- Testes: `tests/test_verify_compat.py`, `tests/test_verify_render.py`, `tests/test_verify_capabilities.py`,
  `tests/test_verify_esbmc_run.py`. Os testes antigos de guarda que usavam `in` e aritmética passaram a usar
  índice e `int`/`len`.
- `docs/projeto/possiveis_problemas/README.md`: linhas do 58 e do 66 e a nota das guardas.

## O que estes resultados permitem afirmar

- No `d520`, 3 de 6 tipos de guarda de None já não mudam veredito nos 19 casos medidos; a de atributo ainda é
  necessária e as sondas antigas não percebiam isso.
- As regras do 58 e do 66 resolvem o obstáculo delas nos reprodutores e, no 66, no harness real; nenhum caso
  novo foi confirmado por elas nestas medições.
- O relógio nondet não mudou nenhum veredito nos 8 casos MAVProxy que usam `time.time()`.
- A rodada de 300 s não deu veredito novo nesta medição, com a máquina carregada.
