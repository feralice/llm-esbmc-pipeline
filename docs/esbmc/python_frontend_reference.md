# Referência do frontend Python do ESBMC para síntese de harness

Destilado de `esbmc.github.io/docs/python/` (overview, usage, supported-features,
limitations, random-operational-model, pytest-testgen) cruzado com
`~/esbmc/src/python-frontend/README.md` e `~/esbmc/src/python-frontend/models/esbmc.py`.
Versão do ESBMC conferida: 8.4.0. Última revisão: 2026-09-10.

Serve para manter `src/research_pipeline/prompts/{synth_prompt,driver_prompt,synth_prompt_loop}.txt`
alinhados com o que o frontend realmente aceita. Cada limitação abaixo aponta a
issue que a fixa quando existe.

---

## 1. Propriedades que o ESBMC-Python verifica

Quatro classes (README linha 278):

| Classe | Disparo automático | Observação |
|---|---|---|
| Divisão por zero | `//` e `%` sobre **int** | `/` sempre vira `ieee_div`, nunca dispara. Precisa `assert <divisor> != 0` explícito. |
| Erro de indexação | acesso a lista/tupla/string fora dos limites | funciona sobre índice simbólico |
| Overflow aritmético | só com `--overflow-check` | o runner já passa para `integer_overflow` |
| `assert` do usuário | sempre | é o mecanismo principal do harness |

`__ESBMC_cover(cond)` tem semântica de assert invertido: contraexemplo significa
"alcançável", prova significa "morto". Precisa `--multi-property` para reportar
todos os covers (o runner já passa). Fonte: README 237 a 246, `builder.cpp:89`.

## 2. Intrínsecos (nome exato, sem import)

Registrados em `models/esbmc.py` e interceptados pelo conversor:

```
nondet_int()  nondet_float()  nondet_bool()  nondet_str()  nondet_list()  nondet_dict()
__ESBMC_assume(cond)     assume(cond)              # mesmo efeito
__ESBMC_assert(cond, msg)
__ESBMC_cover(cond)                                # builder.cpp, não está no models/esbmc.py
__ESBMC_unreachable()                              # falha se alcançado
```

`__VERIFIER_nondet_int()` e `__VERIFIER_assume()` também são reconhecidos
(`builder.h:24`), mas são o dialeto do caminho pytest-testgen / SV-COMP. Para
harness escrito à mão, usar os nomes bare.

Regras que não mudam:
- Todo parâmetro e todo retorno precisa de type hint PEP 484. Código sem hint é
  inferido errado ou rejeitado.
- `import` de qualquer forma dentro do harness é proibido para os intrínsecos.
  Eles já existem. Exceção real: `import random`, ver seção 5.
- `def nondet_int(): ...` no próprio arquivo sombreia o intrínseco e zera as VCCs.

## 3. `nondet_float()` e `nondet_str()`

- `nondet_float()` cobre todo padrão IEEE-754, inclusive NaN e ±Inf. Para excluir
  NaN: `__ESBMC_assume(x == x)`. Para excluir Inf e limitar magnitude:
  `__ESBMC_assume(x > -1e300 and x < 1e300)`.
- `nondet_str()` tem comprimento limitado (`get_nondet_str_length()` em
  `builtins.cpp`). Transformações de caso (`upper`, `lower`, ...) sobre string
  simbólica assertam ou truncam em ~255 caracteres.

## 4. O que o frontend suporta hoje (mais do que o prompt escalar assume)

O `synth_prompt.txt` bane loop, `range` e a maioria dos builtins de propósito,
porque o rebuild escalar não precisa deles. Não é limitação do frontend. O
frontend hoje modela:

- `for` sobre `range()`, lista, string, tupla, `enumerate`, `zip`, `reversed`,
  `filter`; `while`; `for/else` e `while/else`.
- `min`, `max`, `sum`, `sorted`, `any`, `all` sobre **list literal**.
- Métodos de lista (`append`, `pop`, `insert`, slice assignment) e de string
  (predicados, busca, transformação de caso, `split`, `join`, f-string).
- `dict`, `set`, `tuple`, `complex`, `Enum`, `bytes`.
- `math`, `cmath`, `random`, `os`, `re` (parcial), `collections`, `queue`,
  `unittest`, `decimal`, `heapq`, `time`, `datetime` (só o construtor de 3 args),
  `numpy` (parcial, 1D/2D).

O harness de loop limitado (`synth_prompt_loop.txt`) usa esse espaço: lista
pequena de nondets frescos, índice real, loop com bound constante.

## 5. Módulo `random` já vem modelado

Substituído por nondet com constraint via `__ESBMC_assume` (docs random-operational-model):

| Chamada | Resultado |
|---|---|
| `random.random()` | float em `[0.0, 1.0)` |
| `random.uniform(a, b)` | float em `[min(a,b), max(a,b)]` |
| `random.randint(a, b)` | int em `[a, b]` inclusivo |
| `random.randrange(...)` | int com semântica de `range()` |
| `random.getrandbits(k)` | int em `[0, 2**k - 1]`, `ValueError` se `k < 0` |
| `random.choice(seq)` | elemento com índice em `[0, len-1]`, `IndexError` se vazio |

`import random` funciona no harness (testado 2026-09-10). Quando o bug depende de
um valor de `random.*` alimentando a expressão suspeita, chamar o modelo direto
dá os limites exatos de graça, em vez de `nondet_float()` mais assume manual.
Sub-aproximações: `shuffle()` é no-op, `sample()` devolve os primeiros `k`,
`seed()` é no-op.

## 6. Armadilhas que produzem resultado espúrio

Dobrar no prompt. Cada uma vira um harness que "passa" ou "falha" sem relação com
o bug real.

| Armadilha | Efeito | Fonte |
|---|---|---|
| `re.match`/`search`/`fullmatch` devolve **bool**, não `Optional[Match]` | `if m is None:` é sempre falso; `.group()` não existe | limitations.md |
| Método de string em receiver **simbólico** degrada para nondet | `nondet_str().removeprefix(p)`, `.center(n)`, `.format(...)`, `.partition(x)` (vira `("","","")`), `.splitlines()` (vira `[]`) não carregam semântica; assert sobre eles é vacuo | limitations.md |
| `isinstance(x, T)` contra classe de usuário ou agregado | sempre `False`; valor dinâmico com tag só guarda bool/int/float/str | limitations.md |
| valor declarado tipo `T` sendo checado com `isinstance(_, T)` | sempre `True` em ESBMC-Python; não prova nada. Usar tipo nondet diferente como stand-in | prompt regra 9, EXP-03 |
| `/` sobre qualquer operando | nunca dispara div-by-zero; precisa assert explícito | `esbmc-python-guide` gotcha 3 |
| resultado descartado | slicer remove a computação; 0 VCCs, SUCCESSFUL vazio. `print(r)` não conta como uso | gotcha 4 |
| `min([])` / `max([])` | levantam `IndexError`, não `ValueError` | limitations.md |
| `--no-unwinding-assertions` com loop truncado | SUCCESSFUL falso. Nunca usar em harness de loop | CLAUDE.md, G2 |
| comparação encadeada `0 <= i < n` no assert marcado | ESBMC checa em passos separados; só um carrega o marcador. Ligar a um bool nomeado antes | prompt regra 9 |
| `set.add` / `set.remove` / `set.discard` / `set.isdisjoint` | não suportados | limitations.md |
| método `union`/`intersection`/`difference` de set | aceita exatamente 1 argumento | limitations.md |
| `Counter.most_common()` | resultado inutilizável em expressão, trip "Unsupported comparison" | [#4665](https://github.com/esbmc/esbmc/issues/4665) |
| `deque.extend` / `rotate` / `maxlen` | não suportados | limitations.md |
| dict com chave tupla-de-string em parâmetro | não tratado | [#5571](https://github.com/esbmc/esbmc/issues/5571) |
| walrus `:=` em operando de `and`/`or` ou em `while` | não suportado | limitations.md |
| lambda | inferência de retorno ingênua, cai para `float` | limitations.md |

## 7. Flags do ESBMC que o runner usa

`run_esbmc_direct` (harness a nível de módulo):
`--incremental-bmc --max-k-step <bound> --multi-property`

`run_esbmc_on_function` (Flow A/B, arquivo original):
`--function <nome> [--class <C>] --incremental-bmc --max-k-step <bound>`
mais `--assign-param-nondet` sempre e `--overflow-check` para `integer_overflow`.

`--incremental-bmc` sobe o k sozinho até o bound, então loop com bound pequeno é
coberto sem `--unwindset`. As unwinding assertions ficam ligadas por padrão, então
loop truncado vira violação, não SUCCESSFUL falso.

## 8. Links externos da doc

- Repositório: <https://github.com/esbmc/esbmc>
- Discussões: <https://github.com/esbmc/esbmc/discussions>
- `ast` do CPython: <https://docs.python.org/3/library/ast.html>
- ast2json: <https://pypi.org/project/ast2json/>
- PEP 484: <https://peps.python.org/pep-0484/>
- Issues citadas acima: [#5571](https://github.com/esbmc/esbmc/issues/5571),
  [#4665](https://github.com/esbmc/esbmc/issues/4665),
  [#4581](https://github.com/esbmc/esbmc/issues/4581),
  [#4583](https://github.com/esbmc/esbmc/issues/4583),
  [#4584](https://github.com/esbmc/esbmc/issues/4584),
  [#4579](https://github.com/esbmc/esbmc/issues/4579),
  [#6745](https://github.com/esbmc/esbmc/issues/6745)
