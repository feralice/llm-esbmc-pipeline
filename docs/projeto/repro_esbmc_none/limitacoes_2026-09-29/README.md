# ESBMC-Python: limites encontrados ao verificar código real (29/09/2026)

Continuação de `../limitacoes_2026-09-28/`. Cada arquivo é um reprodutor mínimo, levantado ao
rodar o motor verify do pipeline sobre os bugs reais de `dataset/v2_real_world`. Rodar com
`./rodar.sh` (ESBMC do PATH) ou `./rodar.sh /caminho/do/esbmc`.

Versões comparadas:

- **8.5.0**: release oficial (`/usr/local/bin/esbmc`).
- **PR #8014**: build do branch `fix/python-optional-is-none` (`~/.local/bin/esbmc-pr8014`).

Flags: `--unwind 5 --multi-property` (solver padrão, Bitwuzla), as mesmas do motor verify. O 05
usa `--incremental-bmc --max-k-step 5 --multi-property`, que é o que ele demonstra. A coluna
CPython foi medida executando o mesmo arquivo com valores pequenos enumerados para cada `nondet_*`
(executor de reexecução do pipeline, até 200 execuções).

| Arquivo | Construção | CPython | ESBMC 8.5.0 | PR #8014 | Esperado |
|---|---|---|---|---|---|
| `01_while_pop_falso_positivo.py` | `while len(defs) > 0 and defs[-1] >= d: defs.pop()` | seguro em 200 execuções | FAILED (`out-of-bounds read in list`) | FAILED (idem + `IndexError`) | SUCCESSFUL |
| `02_optional_soma_falso_negativo.py` | `v + 1` com `v: Optional[int] = None` | `TypeError` (linha 5) | SUCCESSFUL | SUCCESSFUL | FAILED |
| `03_ternario_segfault.py` | `None if nondet_bool() else nondet_str()` seguido de `.upper()` | `AttributeError` (linha 5) | falha de segmentação (código 139), sem veredito | FAILED só por `unwinding assertion` | FAILED com a exceção |
| `04_excecao_linha_zero.py` | `a // b` com `b` nondet | `ZeroDivisionError` (linha 2) | FAILED, violação sem arquivo nem linha | FAILED na linha 2 (corrigido) | FAILED com localização |
| `05_incremental_failed_e_unknown.py` | `xs.pop()` em lista possivelmente vazia | `IndexError` (linha 3) | imprime `VERIFICATION FAILED` e `VERIFICATION UNKNOWN` na mesma execução | imprime `VERIFICATION FAILED` duas vezes | um único veredito |
| `06_classe_aninhada_metodo.py` | `np.random.randint(n)` com `random` como classe aninhada | `ZeroDivisionError` (linha 11) | `Undefined function 'randint'`, violação `Unsupported function 'randint' is reached` | idem | resolver o método estático aninhado |
| `07_async.py` | `async def` | executa (corrotina não aguardada) | `AsyncFunctionDef statements are not supported` | idem | suporte ou mensagem de limite |
| `08_numpy_fatia_2d.py` | `a[:, j]` com `a` vindo de `np.array` 2x2 literal | código válido | `2-D column slicing (a[:, j]) requires a fixed-shape 2-D array` | idem | aceitar forma fixa conhecida |
| `09_desempacotar_args.py` | `add(*xs)` com `xs` de dois elementos | `ZeroDivisionError` (linha 2) | pré-processador: `add() missing 1 required positional argument: 'b'` | idem | aceitar a chamada |
| `10_formatacao_percent.py` | `"%s %s" % (code, name)` com valores nondet | executa | `unsupported: non-constant argument in str % formatting` | idem | aceitar `%s` com argumento não constante |

Leitura por tipo de problema:

- **Falso positivo** (o programa é seguro, o ESBMC acusa): 01, e 06 quando o método não é resolvido.
- **Falso negativo** (o programa quebra, o ESBMC diz que está seguro): 02, e 03 na PR #8014.
- **Falha do verificador** (crash, veredito duplo ou sem localização): 03 no 8.5.0, 04 no 8.5.0, 05.
- **Construção não suportada** (o ESBMC recusa código Python válido): 07, 08, 09, 10.

## Como o pipeline lida com cada um

- 01 e 06: a confirmação exige que a reexecução no CPython reproduza a mesma exceção na linha da
  hipótese; sem isso o caso fica `UNVALIDATED`, nunca `CONFIRMED`.
- 02 e 03: quando a reexecução reproduz o bug e o ESBMC não, o caso é contado como
  `ESBMC_MISSED` (falso negativo do verificador), separado das confirmações.
- 03 no 8.5.0: `VERIFICATION UNKNOWN` e crash sem veredito viram `ESBMC_ERROR`, nunca "seguro".
- 04: a linha vem da reexecução no CPython.
- 05: o motor verify usa `--unwind N` em vez de `--incremental-bmc`.
- 06: o motor não gera classe aninhada; referências `lib.a.b` são renomeadas para `lib_a.b`, que o
  ESBMC resolve.
- 07 a 10: o caso sai `UNSUPPORTED` com a mensagem do ESBMC; é onde o braço experimental com
  agente (Claude Code + plugin ESBMC) é tentado.

## Casos do dataset afetados

| Reprodutor | Casos de `dataset/v2_real_world` onde apareceu |
|---|---|
| 01 | `ip_real_15` (black, `EmptyLineTracker`) |
| 07 | `ip_real_11` (`HTTPBearer.__call__`), `ip_real_13` (`StaticFileHandler.get`) |
| 08 | `dz_real_01` (matplotlib, `makeMappingArray`) |
| 09 | `tm_real_07` (`MarkerStyle._recache`): mesma mensagem do pré-processador; a causa no caso real não foi isolada |
| 10 | `nm_real_03` (`FacebookIE._real_extract`), `nm_real_04` (`OffsiteMiddleware.get_host_regex`), `nm_real_23` (`Markdown._html_class_str_from_tag`), `vm_real_05` (`LocalFileSystem.move`) |

Casos levantados dos logs das rodadas de 29/09 (mensagem de erro do ESBMC associada a cada
hipótese). O 06 apareceu na geração de stubs, antes de chegar ao dataset: o motor deixou de gerar
classe aninhada.
