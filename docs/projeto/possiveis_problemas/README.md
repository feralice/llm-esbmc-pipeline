# ESBMC-Python: construções que o ESBMC não reproduz

Cada arquivo é um reprodutor mínimo de um caso em que o ESBMC-Python erra, trava ou recusa
código Python válido, inclusive com a PR #8014. Todos foram levantados ao verificar os bugs reais
de `dataset/bugs_reais` (entre 22/09 e 29/09/2026) e medidos de novo em 30/09/2026. Rodar com
`./rodar.sh` (ESBMC do PATH) ou `./rodar.sh /caminho/do/esbmc`.

Versões comparadas:

- **8.5.0**: release oficial (`/usr/local/bin/esbmc`).
- **PR #8014**: build do branch `fix/python-optional-is-none` (`~/.local/bin/esbmc-pr8014`, que é
  também o `esbmc` do PATH).

Flags: `--unwind 5 --multi-property` (solver padrão, Bitwuzla), as mesmas do motor verify. O 12
usa `--incremental-bmc --max-k-step 5 --multi-property`, que é o que ele demonstra. A coluna
CPython vem da execução do arquivo com valores pequenos para cada `nondet_*`, forçando o caminho
com `None` quando existe.

| Arquivo | Construção | CPython | ESBMC 8.5.0 | PR #8014 | Esperado |
|---|---|---|---|---|---|
| `01_methNone.py` | `e.shutdown()` com `e = None` | `AttributeError` | SUCCESSFUL | SUCCESSFUL | FAILED |
| `02_mul.py` | `t * s` com `t = None` | `TypeError` | falha de segmentação com Bitwuzla; com `--z3`, erro `ast is not an expression` | erro do Z3 (`ast is not an expression`) | FAILED |
| `03_ge.py` | `n >= limit` com `limit = None` | `TypeError` | SUCCESSFUL | SUCCESSFUL | FAILED |
| `04_inNone.py` | `tag in classes` com `classes = None` | `TypeError` | exceção interna (`irep2_cast_error`) | idem | FAILED |
| `05_callstr.py` | `t.path()` com `path` sendo `@property` que retorna `str` | `TypeError` | SUCCESSFUL | SUCCESSFUL | FAILED |
| `06_floatstr.py` | `float("abc")` | `ValueError` | SUCCESSFUL | SUCCESSFUL | FAILED |
| `07_unbound.py` | `return k` depois de laço sobre dict vazio | `UnboundLocalError` | FAILED no `assert` seguinte (valor arbitrário) | idem | FAILED com `UnboundLocalError` |
| `08_getattr_d.py` | `getattr(t, "total", None)` | sem erro (retorna `None`) | `Unsupported function 'getattr' is reached` | idem, mais erro do Z3 | SUCCESSFUL |
| `09_while_pop_falso_positivo.py` | `while len(defs) > 0 and defs[-1] >= d: defs.pop()` | seguro em 200 execuções | FAILED (`out-of-bounds read in list`) | FAILED (idem + `IndexError`) | SUCCESSFUL |
| `10_optional_soma_falso_negativo.py` | `v + 1` com `v: Optional[int] = None` | `TypeError` | SUCCESSFUL | SUCCESSFUL | FAILED |
| `11_ternario_segfault.py` | `None if nondet_bool() else nondet_str()` seguido de `.upper()` | `AttributeError` | falha de segmentação, sem veredito | FAILED só por `unwinding assertion` | FAILED com a exceção |
| `12_incremental_failed_e_unknown.py` | `xs.pop()` em lista possivelmente vazia | `IndexError` | `VERIFICATION FAILED` e `VERIFICATION UNKNOWN` na mesma execução | `VERIFICATION FAILED` duas vezes | um único veredito |
| `13_classe_aninhada_metodo.py` | `np.random.randint(n)` com `random` como classe aninhada | `ZeroDivisionError` | `Unsupported function 'randint' is reached` | idem | resolver o método estático aninhado |
| `14_async.py` | `async def` | executa (corrotina não aguardada) | `AsyncFunctionDef statements are not supported` | idem | suporte ou mensagem de limite |
| `15_numpy_fatia_2d.py` | `a[:, j]` com `a` vindo de `np.array` 2x2 literal | código válido | `2-D column slicing (a[:, j]) requires a fixed-shape 2-D array` | idem | aceitar forma fixa conhecida |
| `16_desempacotar_args.py` | `add(*xs)` com `xs` de dois elementos | `ZeroDivisionError` | pré-processador: `add() missing 1 required positional argument: 'b'` | idem | aceitar a chamada |
| `17_formatacao_percent.py` | `"%s %s" % (code, name)` com valores nondet | executa | `unsupported: non-constant argument in str % formatting` | idem | aceitar `%s` com argumento não constante |

Leitura por tipo de problema:

- **Falso negativo** (o programa quebra, o ESBMC diz que está seguro): 01, 03, 05, 06, 10, e 11 na
  PR #8014.
- **Falso positivo** (o programa é seguro, o ESBMC acusa): 09, e 13 quando o método não é resolvido.
- Exceção errada ou ausente no contraexemplo: 07.
- **Falha do verificador** (crash ou veredito duplo): 02, 04, 11 no 8.5.0, 12.
- Recusa de código Python válido: 08, 14, 15, 16, 17.

## Audit com a PR #8014 (30/09/2026)

Os 17 arquivos passaram pelas quatro passadas do `/esbmc-plugin:audit` com o build da PR (`--z3`,
`--unwind 5`; o 12 com `--incremental-bmc --max-k-step 5`): padrão, `--memory-leak-check`,
`--overflow-check --unsigned-overflow-check` e `--ub-shift-check`. Em nenhum deles alguma passada
chegou ao resultado esperado. Nos falsos negativos 01 e 05, a passada de memória acusa
`forgotten memory: dynamic_1_value`, que é artefato do modelo de memória e não a exceção que o
CPython levanta.

Três reprodutores saíram da pasta porque a PR #8014 dá o resultado esperado (o conteúdo continua
no histórico do git):

| Reprodutor removido | 8.5.0 | PR #8014 |
|---|---|---|
| função devolve `None` para entrada nondet, depois `assert r is not None` | SUCCESSFUL (falso negativo) | FAILED na linha do `assert` |
| `dict.get` com chave ausente, depois `assert r is not None` | SUCCESSFUL (falso negativo) | FAILED na linha do `assert` |
| `a // b` com `b` nondet | FAILED sem arquivo nem linha | FAILED com `ZeroDivisionError` na linha 2 |

## Como o pipeline lida com cada um

- 09 e 13: a confirmação exige que a reexecução no CPython reproduza a mesma exceção na linha da
  hipótese; sem isso o caso fica `UNVALIDATED`, nunca `CONFIRMED`.
- Nos falsos negativos (10, 11), quando a reexecução reproduz o bug e o ESBMC não, o caso é
  contado como `ESBMC_MISSED`, separado das confirmações.
- `VERIFICATION UNKNOWN` e crash sem veredito (11 no 8.5.0) viram `ESBMC_ERROR`, nunca "seguro".
- O motor verify usa `--unwind N` em vez de `--incremental-bmc` por causa do 12.
- 13: o motor não gera classe aninhada; referências `lib.a.b` são renomeadas para `lib_a.b`, que o
  ESBMC resolve.
- De 14 a 17, o caso sai `UNSUPPORTED` com a mensagem do ESBMC.

## Casos do dataset afetados

| Reprodutor | Casos de `dataset/bugs_reais` |
|---|---|
| 01 (método em None) | `nm_real_01`, `nm_real_24` |
| 02 (`None * n`) | `nm_real_02` |
| 03 (comparação com None) | `nm_real_11` |
| 04 (`in None`) | `nm_real_23` |
| 05 (chamar string) | `tm_real_12` |
| 06 (`float("abc")`) | `tm_real_09` |
| 07 (variável não ligada) | `vm_real_02` |
| 08 (`getattr` com default) | `nm_real_09`, `nm_real_25` (o fix usa `getattr`) |
| 09 | `ip_real_15` (black, `EmptyLineTracker`) |
| 14 | `ip_real_11` (`HTTPBearer.__call__`), `ip_real_13` (`StaticFileHandler.get`) |
| 15 | `dz_real_01` (matplotlib, `makeMappingArray`) |
| 16 | `tm_real_07` (`MarkerStyle._recache`): mesma mensagem do pré-processador; a causa no caso real não foi isolada |
| 17 | `nm_real_03`, `nm_real_04`, `nm_real_23`, `vm_real_05` |

O 13 apareceu na geração de stubs, antes de chegar ao dataset: o motor deixou de gerar classe
aninhada.
