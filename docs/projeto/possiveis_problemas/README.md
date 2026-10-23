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
| `18_for_lista_global_in_none.py` | `for p in patterns: if p in stderr` com `patterns` lista global de 2 strings e `stderr = None` | `TypeError` | não termina em 60 s (`--unwind 5`) | não medido | FAILED em segundos |
| `19_args_em_atributo.py` | `self._args = args` com `*args` no `__init__` | `ZeroDivisionError` | `Variable args not found` | não medido | FAILED |
| `20_kwargs.py` | `kw.get('error')` com `**kw` no `__init__` | `ZeroDivisionError` | `Object "kw" not found` | não medido | FAILED |
| `21_class_name.py` | `self.__class__.__name__` | `ZeroDivisionError` | `Cannot resolve nested attribute: __name__` | não medido | FAILED |
| `22_tipo_como_valor.py` | `isinstance(data, s)` com `s: type` recebido como parâmetro | `ZeroDivisionError` | `NameError: name 's' is not defined` | não medido | FAILED |
| `23_bytes_literal.py` | função `-> bytes` que devolve `b"ab"` | `IndexError` | FAILED (`array bounds violated`) | não medido | FAILED; o master recusa o programa |
| `24_numpy_shape_parametro.py` | `np.array(data).shape[1]` com `data: list[list[float]]` | `ZeroDivisionError` | `uncaught exception: AttributeError` (falso) | não medido | FAILED com `ZeroDivisionError` |
| `25_atributo_em_none.py` | `a.nxt.val` com `a.nxt = None` (idem leitura e escrita em local `Optional`) | `AttributeError` | FAILED (`dereference failure: NULL pointer`) | não medido | FAILED com `AttributeError` |
| `26_in_str_none.py` | `"ab" in s` com `s: Optional[str] = None` | `TypeError` | SUCCESSFUL | não medido | FAILED |
| `27_metodo_append_do_usuario.py` | método do usuário chamado `append` | `ZeroDivisionError` | FAILED só por checagens de memória em `list_push` | não medido | FAILED com `ZeroDivisionError` |
| `28_raise_no_else_do_try.py` | `raise` no `else:` de um `try` com `except` do mesmo tipo | `ValueError` | SUCCESSFUL | não medido | FAILED |
| `29_optional_dict_como_valor.py` | `dict[str, Optional[dict[str, str]]]` em atributo, depois `"t" in h` | `TypeError` | falha de segmentação | não medido | FAILED |
| `30_desempacotar_aridade.py` | `a, b = parts` com um elemento | `ValueError` | FAILED (`out-of-bounds read in list` e falhas de memória) | não medido | FAILED com `ValueError` |
| `31_strip_split_laco.py` | `nondet_str().strip().split("\n")` e `split` dentro do laço | executa | não termina em 120 s (ignora o `timeout`, foi preciso `kill -9`) | não medido | veredito em segundos |
| `32_is_float_parametro.py` | `t is float` com `t: type` parâmetro | `ZeroDivisionError` | SUCCESSFUL | não medido | FAILED |
| `33_atributo_ausente_uniao.py` | `x.size` com `x: Union[A, B]` valendo `B()` | `AttributeError` | FAILED (`Access to object out of bounds: heap object`) | não medido | FAILED com `AttributeError` |
| `34_pop_encadeado.py` | `jobs.pop("b").stop()` com chave ausente | `KeyError` | SUCCESSFUL | não medido | FAILED |
| `35_chr_surrogate.py` | `chr(n)` com `n` entre 0xD800 e 0xDFFF | executa | FAILED (`chr() arg is a surrogate code point`) | não medido | SUCCESSFUL |
| `36_isinstance_classes_vazias.py` | `assert isinstance(h.item, A)` com `item = B()`, classes só com `pass` | `AssertionError` | SUCCESSFUL | não medido | FAILED |
| `37_str_de_chamada.py` | `str(label(x))` com `label` levantando `ValueError` | `ValueError` | SUCCESSFUL | não medido | FAILED |
| `38_not_isinstance_optional.py` | `if not isinstance(text, str): raise` com parâmetro `Optional[str]` | `TypeError` | SUCCESSFUL | não medido | FAILED |
| `39_int_de_none.py` | `int(status)` com `status: Optional[str] = None` | `TypeError` | SUCCESSFUL | não medido | FAILED |
| `40_sequence_indice.py` | `xs[1]` com `xs: Sequence[str]` de um elemento | `IndexError` | SUCCESSFUL | não medido | FAILED |
| `41_lista_mais_tupla.py` | `[1] + t` com `t` tupla | `TypeError` | SUCCESSFUL | não medido | FAILED |
| `42_tupla_de_str_retorno.py` | função `-> tuple[str, str]` que devolve dois `nondet_str()` | `ValueError` | `Incompatible struct in cast-to-struct` | não medido | FAILED |
| `43_optional_str_nondet.py` | `text: Optional[str] = None` trocado por `nondet_str()` num ramo, depois `assert text is not None` | `AssertionError` | SUCCESSFUL | não medido | FAILED |
| `44_funcao_definida_depois.py` | `caller` chama `callee(n)` definida depois | `ZeroDivisionError` | `Variable 'k' is not defined in function 'caller'` | não medido | FAILED |

Leitura por tipo de problema:

- **Falso negativo** (o programa quebra, o ESBMC diz que está seguro): 01, 03, 05, 06, 10, e 11 na
  PR #8014.
- **Falso positivo** (o programa é seguro, o ESBMC acusa): 09, e 13 quando o método não é resolvido.
- Exceção errada ou ausente no contraexemplo: 07.
- **Falha do verificador** (crash ou veredito duplo): 02, 04, 11 no 8.5.0, 12.
- Recusa de código Python válido: 08, 14, 15, 16, 17.
- **Desempenho** (o verificador não termina num caso pequeno): 18. Medido em 08/10/2026 no 8.5.0,
  60 s por variante: sem o laço (`'ab' in stderr`) dá FAILED em 2 s; o mesmo laço com a lista local
  dá FAILED em 47 s; com índice (`while i < 2: patterns[i] in stderr`) dá FAILED em 10 s; o mesmo
  laço com `stderr` string, sem `None`, termina em 4 s. A explosão vem do `for` sobre a lista global
  junto com `in` aplicado a `None`. Trocar `.lower()` por um modelo barato não resolve (a variante com
  `.lower()` também não termina).

Nos 25 a 44, medidos no 8.5.0 e no master (seção do master abaixo), predominam os falsos negativos:
26, 28, 32, 34, 36 a 41 e 43 dão SUCCESSFUL nas duas versões, e 25, 27 e 33 também no master com
as flags do motor. O 35 é falso positivo. O 30 acusa o erro errado (`out-of-bounds` no lugar de
`ValueError`). Crash ou recusa aparecem em 29, 42 e 44, e o 31 é de desempenho.

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
| 18 | `ip_real_22` (thefuck, regra `sudo`, `match`): estoura 180 s, 600 s e 900 s (com 900 s, falta memória), inclusive com a entrada fixada em `stderr = None` |
| 19, 20, 21, 22 | `vm_real_02` (schema, `Schema.validate`): barreiras em sequência, que aparecem depois da correção do harness de 12/10 |
| 23 | stubs `-> bytes` do harness (10 recusas na reverificação com o master) |
| 24 | `dz_real_01` (matplotlib, `makeMappingArray`): segunda barreira, depois da do 15 |
| 25 | `nm_real_12` (`PamdService.remove`, `current_line.next.prev`) |
| 26 | `nm_real_08` (`"//" in self.app.config.SERVER_NAME`) |
| 27 | `bip_pandas_152` (`Series.append`), `av_real_03` (`new_values.copy()`), `ip_real_17` (`http_RESPONSES.get`), `nm_real_12` (`PamdService.remove`) |
| 28 | `nm_real_23` (`try`/`except TypeError`/`else`), `bip_pandas_133` |
| 29 | `nm_real_23` (`extras: dict[str, Optional[dict[str, str]]]`) |
| 30 | `ip_real_32` (`H, M = t`), `oob_real_15` (`ns, tag = c`), `bip_thefuck_4` (`name, value = ...split(' ', 1)`) |
| 31 | `bip_thefuck_4` (aliases do fish) |
| 32 | `tm_real_09` (`valtype is float`) |
| 33 | `nm_real_25` (`s.method` com `s` de uma união de classes) |
| 34 | `bip_scrapy_21` (`self._parsers.pop(netloc).callback(None)`) |
| 35 | `ip_real_07` (`compat_chr`), `nm_real_02` |
| 36 | `av_real_03` (`isinstance(self.index, PeriodIndex)`) |
| 37, 38, 39 | `ip_real_17` (`response_status_message`) |
| 40 | `oob_real_14` |
| 41 | `bip_pandas_152` (`[self] + to_append`) |
| 42 | `ip_real_11` (`scheme, credentials = get_authorization_scheme_param(...)`) |
| 43 | `nm_real_04` (`allowed_domains: list[Optional[str]]`) |
| 44 | `oob_real_10` (`_expand_iterable` definida depois de `_wrap_text_to_colwidths`) |
| 48 | `nm_real_12` (`current_line.prev.next = ...`, com `prev` iniciado em `None`) |
| 49 | `ip_real_15` (`Factory(dict)` que o harness carregou do `attr.dataclass`; no caso, o campo nem fica no caminho do bug) |
| 50 | `ip_real_15` (`maybe_empty_lines` desempacota o retorno de `_maybe_empty_lines`, definido depois) |

O 13 apareceu na geração de stubs, antes de chegar ao dataset: o motor deixou de gerar classe
aninhada.

## Medição no master 333d07cc8a (12/10/2026)

Build com Z3 (sem Bitwuzla), `./rodar.sh ~/esbmc-master/build/src/esbmc/esbmc "--no-pointer-check
--no-align-check"`. As duas flags desligam as checagens de memória que o master passou a gerar dentro
dos modelos em C; sem elas o `--multi-property` fica lento. `--no-bounds-check` não pode entrar: troca o
`IndexError` do Python por `out-of-bounds read in list`.

| Arquivo | Master | Issue |
|---|---|---|
| 01 a 07, 10, 13 | FAILED com a exceção esperada | #8247, #8248, #8249, #8250, #8251, #8252, #8256 |
| 08 | SUCCESSFUL, como esperado | #8253 |
| 09 | SUCCESSFUL, como esperado | #8254 |
| 11 | FAILED com `AttributeError` e `unwinding assertion` | |
| 12 | dois FAILED na mesma execução | #8255 (aberta) |
| 14 | `AsyncFunctionDef statements are not supported` | |
| 15 | mesma recusa de `a[:, j]` | #8257 (aberta) |
| 16 | `*x` aceito só quando `x` é lista ou tupla de tamanho conhecido | #8258 cobre só o tamanho fixo |
| 17 | FAILED só por `unwinding assertion` (antes recusava `%s`) | |
| 18 | FAILED só por `unwinding assertion`, sem `TypeError` | #8249 corrigiu dict e list, não `str` |
| 19 | `Variable args not found` (igual ao 8.5.0) | a reportar |
| 20 | `Object "kw" not found` (igual ao 8.5.0) | a reportar |
| 21 | `Cannot resolve nested attribute: __name__` (igual ao 8.5.0) | a reportar |
| 22 | `NameError: name 's' is not defined` (igual ao 8.5.0) | a reportar |
| 23 | `cannot determine the length of a -> bytes return value`; o 8.5.0 achava o bug | regressão do #7902, a reportar |
| 24 | `Tuple index out of range (size: 1)`: trata o array 2-D como 1-D | a reportar |
| 25 | SUCCESSFUL; sem `--no-pointer-check`, FAILED com `dereference failure: NULL pointer`, sem `AttributeError` | a reportar |
| 26 | SUCCESSFUL | #8249 corrigiu dict e list, não `str` |
| 27 | SUCCESSFUL; sem `--no-pointer-check`, FAILED só por checagens de memória em `__ESBMC_list_push` | a reportar |
| 28 | SUCCESSFUL | a reportar |
| 29 | `Z3 error Sorts \|struct_type_tag-Optional_struct` (aborta) | a reportar |
| 30 | FAILED com `out-of-bounds read in list`, sem `ValueError` | a reportar |
| 31 | não termina em 120 s | a reportar |
| 32 | SUCCESSFUL | a reportar |
| 33 | SUCCESSFUL; sem `--no-pointer-check`, FAILED com `Access to object out of bounds: heap object` | a reportar |
| 34 | SUCCESSFUL | a reportar |
| 35 | FAILED com `chr() arg is a surrogate code point` (falso positivo) | a reportar |
| 36 | SUCCESSFUL | a reportar |
| 37 | SUCCESSFUL | a reportar |
| 38 | SUCCESSFUL | a reportar |
| 39 | SUCCESSFUL | a reportar |
| 40 | SUCCESSFUL | a reportar |
| 41 | SUCCESSFUL | a reportar |
| 42 | `Incompatible struct in cast-to-struct` (aborta) | a reportar |
| 43 | SUCCESSFUL | a reportar |
| 44 | `Variable 'k' is not defined in function 'caller'` | a reportar |
| 45 | FAILED, sem o valor de `s` no contraexemplo | a reportar (rascunho em `../rascunho_issue_nondet_str.md`) |

Candidatos descartados ao montar 19 a 24: `len(self)` num objeto sem `__len__` (o ESBMC acha o
`TypeError`; o erro interno do `nm_real_11` vem de um atributo `popitem` criado pelo harness) e classe
que herda de `dict` (o erro do `nm_real_01` vem do harness, que troca a base importada por uma classe
vazia).

Os 25 a 44 vieram dos agentes exploradores de 13/10/2026 e foram medidos em 14/10/2026 com as mesmas
flags (`--unwind 5 --multi-property --no-pointer-check --no-align-check`, Z3). Dois candidatos
saíram. A divisão de `float` por zero já é checada pelo master: `1.0 / n` com `n = 0.0` dá FAILED com
`ZeroDivisionError`. O elemento `None` de `list[Optional[str]]` montado no `__init__` e lido por
atributo também não é limitação própria: com `"a"` no lugar de `nondet_str()` o `assert x is not None`
falha como devia, e o que some com o `None` é o `nondet_str()`, isolado no 43.

Algumas variantes ficaram registradas só no comentário do arquivo, por darem outro sintoma da mesma
causa. No 27, o nome `remove` com um argumento acusa `ValueError` de `list.remove`, e `append` ou
`remove` com dois argumentos recusam o programa; `Codes.get(0)` com `get` estático dá `Dictionary
variable not found: Codes`, e `nv.copy()` com `nv = self.v` aborta com `irep2_cast_error`. No 29, as
versões sem classe abortam com `bad optional access` ou terminam só com `unwinding assertion`. No 34,
sem encadear (`j = jobs.pop("b")`), o master aborta com `irep2_cast_error`. Nos 25, 27 e 33 a leitura
depende das flags: sem `--no-pointer-check` o master acusa falha de memória, mas nunca a exceção do
Python. O 31 foi medido com a máquina carregada (outras rodadas do master em paralelo); o mesmo laço
sem o `split` interno termina em 4 s, e `strip` seguido de `split` sem laço, em 7 s.

## Medição de 19/10/2026: v8.6 × master

Mesmo `rodar.sh`, com `--no-pointer-check --no-align-check`. **v8.6**: release de 15/10. **master**:
`df93f12` de 19/10 (`~/esbmc-master`). Só as linhas que mudaram; nas outras 37 as duas dão o mesmo veredito.

| Arquivo | Esperado | v8.6 | master | Leitura |
|---|---|---|---|---|
| `12_incremental_failed_e_unknown.py` | um único veredito | FAILED duas vezes | FAILED uma vez (`IndexError`) | corrigido |
| `15_numpy_fatia_2d.py` | aceitar forma fixa conhecida | recusa (`2-D column slicing ... requires`) | aceita (FAILED por `ZeroDivisionError` e `IndexError`) | aceito agora |
| `22_tipo_como_valor.py` | FAILED | `NameError: name 's' is not defined` | FAILED (`ZeroDivisionError`) | corrigido |
| `27_metodo_append_do_usuario.py` | FAILED com `ZeroDivisionError` | SUCCESSFUL (falso negativo) | FAILED (`ZeroDivisionError`) | corrigido |
| `32_is_float_parametro.py` | FAILED | SUCCESSFUL (falso negativo) | FAILED (`ZeroDivisionError`) | corrigido |
| `33_atributo_ausente_uniao.py` | FAILED com `AttributeError` | SUCCESSFUL (falso negativo) | recusa com mensagem sobre `x.size` | melhor (recusa explícita), ainda não FAILED |
| `29_optional_dict_como_valor.py` | FAILED | falha de segmentação (código 139) | erro do Z3 (`Sorts ... Optional_struct`) | ainda quebrado |
| `31_strip_split_laco.py` | veredito em segundos | só `unwinding assertion` | sem veredito em 300 s | piorou |

Remedido no mesmo dia com o master `5d17828` (9 commits novos no frontend Python, entre eles #8884, #8856 e
#8852): os 45 arquivos dão o mesmo veredito do `df93f12`, e o 31 continua sem veredito em 300 s. Em relação à
tabela de 12/10, três já estavam corrigidos desde a v8.6: o 30 acusa `ValueError`, o 36 dá FAILED no
`isinstance` e o 44 acusa `ZeroDivisionError`.

## Medição de 22/10/2026: master `7da3564`

Master de 22/10 (98 commits depois do `5d17828`, 40 deles no frontend Python), build com Z3,
`./rodar.sh ~/esbmc-master/build/src/esbmc/esbmc "--no-pointer-check --no-align-check"`. Só dois arquivos
mudaram em relação a 19/10; os outros 43 dão o mesmo veredito.

| Arquivo | Esperado | master 19/10 (`5d17828`) | master 22/10 (`7da3564`) | Leitura |
|---|---|---|---|---|
| `33_atributo_ausente_uniao.py` | FAILED com `AttributeError` | recusa com mensagem sobre `x.size` | recusa: `storing or passing 'x', which holds an instance of A or B` | outra recusa explícita, ainda não FAILED |
| `34_pop_encadeado.py` | FAILED com `KeyError` | SUCCESSFUL (falso negativo) | recusa: `calling method 'stop' on a value whose class is not known` | melhor (recusa no lugar de falso negativo), ainda não FAILED |

Situação dos 45 nesta versão:

- **Resultado esperado (22):** 01 a 10, 12, 13, 15, 16, 22, 27, 30, 32, 36, 44, e 11 e 17 quando se
  aceita o `unwinding assertion` junto da exceção (11) ou sozinho num programa agora aceito (17).
- **Exceção ausente (1):** 18, FAILED só por `unwinding assertion`, sem o `TypeError`.
- **Falso negativo, SUCCESSFUL (10):** 25, 26, 28, 37, 38, 39, 40, 41, 43; e 45 dá FAILED mas sem o valor
  de `s` no contraexemplo.
- **Falso positivo (1):** 35 (`chr()` de surrogate).
- **Recusa ou erro interno (10):** 14 (`async`), 19, 20, 21, 23, 24, 29 (erro do Z3), 33, 34, 42.
- **Desempenho (1):** 31, sem veredito em 300 s.

Esses grupos são a lista de partida para as issues; cada uma só é aberta depois de remedida no master
do dia e com Bitwuzla.

## Validação de 22/10/2026

Master `7da3564` com Z3 (`~/esbmc-master/build`) e com Bitwuzla 0.9.0 (`~/esbmc-master/build-bw`, `--bitwuzla`),
sempre com `--no-pointer-check --no-align-check`. Para cada arquivo: CPython 3.12 com stubs dos `nondet_*`
(valores pequenos que forçam o caminho do bug), as flags do `rodar.sh` (`--unwind 5 --multi-property`) e duas
variações de robustez, `--unwind 10 --multi-property` e `--unwind 5` sem `--multi-property`. Duplicatas
procuradas com `gh issue list` e `gh search issues` no esbmc/esbmc. Os `_min.py` são versões menores, com o
mesmo erro, gravadas ao lado do original; os rascunhos de issue (em inglês, não postados) estão em `issues/`.

| Arquivo | CPython | ESBMC master (Z3) | Bitwuzla | Robusto a unwind/multi-property? | Issue existente | Pronto para issue? |
|---|---|---|---|---|---|---|
| `14_async.py` | executa; a corrotina não é aguardada, o corpo não roda | `AsyncFunctionDef statements are not supported` | igual | sim | nenhuma | sim, com a variante `14_async_run.py` (`asyncio.run`, `ZeroDivisionError`); ver nota abaixo |
| `18_for_lista_global_in_none.py` | `TypeError` (linha 8) | FAILED só por `unwinding assertion` em `strstr` | igual | sim (também com `--unwind 30` no `_min`) | #8249 (fechada) cobre dict e list, não str | sim, junto com o 26 (`issues/26_in_optional_str_none.md`) |
| `19_args_em_atributo.py` | `ZeroDivisionError` | `Variable args not found` | igual | sim | #7543, #8498, #8959 tratam de outros casos de `*args` | sim |
| `20_kwargs.py` | `ZeroDivisionError` | `Object "kw" not found.` | igual | sim | #8497, fechada em 21/10 pelo #9002, que não cobre `__init__` | sim, citando a #8497 |
| `21_class_name.py` | `ZeroDivisionError` | `Cannot resolve nested attribute: __name__` | igual | sim | nenhuma | sim |
| `23_bytes_literal.py` | `IndexError` | `cannot determine the length of a -> bytes return value` | igual | sim | nenhuma (regressão do #7902) | sim, com o `_min` |
| `24_numpy_shape_parametro.py` | `ZeroDivisionError` | `Tuple index out of range (size: 1)` | igual | sim | #4666 (fechada) é outra mensagem | sim |
| `25_atributo_em_none.py` | `AttributeError` | SUCCESSFUL (propriedades de `AttributeError` provadas) | igual | sim | #8325 (fechada pelo #8756) cobre o caso sem ramo | sim, citando a #8325 |
| `26_in_str_none.py` | `TypeError` | SUCCESSFUL (0 VCC) | igual | sim | #8249 (fechada) cobre dict e list | sim, com o `_min` |
| `28_raise_no_else_do_try.py` | `ValueError` | SUCCESSFUL | igual | sim | nenhuma | sim, com o `_min` |
| `29_optional_dict_como_valor.py` | `TypeError` | aborta: `Z3 error Sorts ... Optional_struct` (134) | SIGSEGV (139) | sim | nenhuma | sim |
| `31_strip_split_laco.py` | executa | sem veredito em 300 s | sem veredito em 300 s | `--unwind 1`: 1 s; `--unwind 2`: 38 s; `--unwind 3`: mais de 300 s | nenhuma | não: é escalonamento do solver com string nondet, sem alvo de tempo que sustente a issue |
| `33_atributo_ausente_uniao.py` | `AttributeError` | recusa: `holds an instance of A or B depending on the path` | igual | sim | #8408 (aberta), mesma construção | não: duplicata da #8408 (no máximo um comentário lá) |
| `34_pop_encadeado.py` | `KeyError` | recusa: `calling method 'stop' on a value whose class is not known` | igual | sim | nenhuma | sim |
| `35_chr_surrogate.py` | executa | FAILED (`chr() arg is a surrogate code point`) | igual | sim | nenhuma | sim |
| `37_str_de_chamada.py` | `ValueError` | SUCCESSFUL (0 VCC) | igual | sim | nenhuma | sim, com o `_min` |
| `38_not_isinstance_optional.py` | `TypeError` | SUCCESSFUL | igual | sim | nenhuma | sim |
| `39_int_de_none.py` | `TypeError` | SUCCESSFUL (0 VCC) | igual | sim | #6260 (fechada) é outra operação | sim, com o `_min` |
| `40_sequence_indice.py` | `IndexError` | SUCCESSFUL (0 VCC) | igual | sim | #3045 (fechada) é outro sintoma | sim |
| `41_lista_mais_tupla.py` | `TypeError` | SUCCESSFUL (0 VCC) | igual | sim | nenhuma | sim, com o `_min` (uma linha) |
| `42_tupla_de_str_retorno.py` | `ValueError` com `"bearer"` | aborta: `Incompatible struct in cast-to-struct` (134) | igual | sim | nenhuma | sim, com o `_min` |
| `43_optional_str_nondet.py` | `AssertionError` | SUCCESSFUL | igual | sim | nenhuma | sim |
| `45_nondet_str_contraexemplo.py` | `AssertionError` com `"ab"` | FAILED sem o valor de `s` | igual | sim | nenhuma | sim (atualiza `../rascunho_issue_nondet_str.md`) |
| `46_super_com_len_aborta.py` | `TypeError` (linha 11) | aborta: `Couldn't convert expression in unrecognised format` (134) | igual | sim | nenhuma (#8927 é outro `cpp_throw`) | sim, junto com o 47 |
| `47_len_sem_dunder_len.py` | `TypeError` | SUCCESSFUL (0 VCC) | igual | sim | nenhuma | sim (`issues/47_exception_in_condition.md`) |

Resumo: 23 dos 25 prontos, que viram 21 rascunhos (18 entra no do 26; 46 no do 47). Duplicata clara só o 33.
Nenhum arquivo deixou de reproduzir, e nenhuma variação de unwind ou de `--multi-property` mudou veredito.

O que a redução mostrou:

- 46 e 47 têm a mesma causa. A exceção que o frontend gera para `len()` sem `__len__` ou para atributo
  ausente some quando a expressão é condição de `if` ou `while` (`if len(c) > 0:` dá SUCCESSFUL, `n = len(c)`
  dá FAILED). Quando a condição de um `while` levanta e há outra propriedade depois do laço, o `cpp_throw`
  chega ao solver e o ESBMC aborta. O `super` e o `len` do 46 original não são necessários.
- O 18 deixou de ser caso de desempenho no master: termina em 2 s, mas só com `unwinding assertion` em
  `strstr`, sem `TypeError`, também com `--unwind 30`. É a mesma falta do 26 (`in` sobre str `None`), por
  outro caminho (parâmetro em vez de variável local).
- No 28 basta um `try`/`except ValueError`/`else: raise ValueError` no nível do módulo; com `except
  KeyError` o ESBMC acusa.
- O 42 aborta mesmo com o primeiro elemento literal (`("x", nondet_str())`) e um `assert a == "x"`.

Achados laterais, sem arquivo próprio: `def f(**kw): return kw.get('error')` com `assert f() is None` dá
FAILED (`None returned from a function whose return type cannot hold None`), falso positivo citado no
rascunho do 20; `xs: Sequence[str] = ["a"]` no nível do módulo dá `NameError: name 'Sequence' is not
defined`, citado no rascunho do 40; `super().put()` com a base sem `put` dá `uncontrolled recursion in put`
em vez de `AttributeError`.

Nota sobre o 14: a coluna CPython da tabela original ("executa (corrotina não aguardada)") já estava certa.
O esperado é SUCCESSFUL no 14 e FAILED com `ZeroDivisionError` no `14_async_run.py`. Às 22:14 o binário Z3
de `~/esbmc-master/build` foi recompilado por outra frente com um patch local não commitado
(`coroutine_lowering.py`); com ele o 14 dá SUCCESSFUL e o `14_async_run.py` dá FAILED com
`ZeroDivisionError`, ambos corretos. Os vereditos do master limpo na tabela vêm das rodadas anteriores à
recompilação e do build Bitwuzla (compilado às 22:05). Rodei de novo os outros 24 arquivos no binário com o
patch e nenhum veredito mudou. Se o patch virar PR, o rascunho `issues/14_async_def.md` serve de issue
para ela.

Bitwuzla: única diferença em relação ao Z3 é o 29, que troca o erro do Z3 por SIGSEGV ao codificar o claim
de `__ESBMC_list_contains`.

## Achados dos pareceres do teste A/B (22/10/2026)

Os pareceres do consultor sobre `nm_real_12` e `ip_real_15` (`artifacts/v2/teste-ab-2026-10-22/C/`) rodaram no
`build` com o patch de `async`. As sondas foram refeitas no master limpo `7da3564` (Z3 e Bitwuzla) e dão o mesmo
resultado. A falta de `AttributeError` ao ler ou escrever atributo de `None` (sondas `sonda_l.py` e `sonda_m.py`)
é o 25. A regra é abrir issue só do que não dá para contornar simplificando a função sem mudar o comportamento. O 48 e o 50 têm contorno assim e vão para o filtro do `verify/compat.py`; o 49 não tem, e virou a #9093.

| Arquivo | CPython | Z3 | Bitwuzla | Issue existente | Contorno sem mudar o comportamento |
|---|---|---|---|---|---|
| `48_atributo_aninhado_campo_none.py` | `AttributeError` | `Cannot resolve nested attribute: next` | igual | #9075 tem a mesma mensagem, mas outra causa (`__class__.__name__`) | `self.prev = self` logo antes de `self.prev = None` no `__init__`; depois ainda é preciso o guard de `None` do 25 |
| `49_dict_como_valor.py` | executa | FAILED com `KeyError` em `defaultdict(dict)` (falso positivo); `f(dict)` dá `Variable 'dict' is not defined` | igual | #4356 (fechada) corrigiu a fábrica de `defaultdict` para `list` e `int`, não para `dict` | nenhum: `lambda: {}` no lugar de `dict` aborta. Aberta como #9093 |
| `50_desempacotar_funcao_definida_depois.py` | executa | `Cannot unpack empty` | igual | #8918 é outro caso de unpack | definir a função chamada antes de quem chama (move linhas). Guardar o retorno numa variável anotada é aceito mas dá valor errado, falso positivo |

## Gerador de pytest no master (22/10/2026)

`--generate-pytest-testcase --pytest-output-dir <pasta> --unwind 5`, master `7da3564` com Bitwuzla
(`~/esbmc-master/esbmc.sh`). Formato de entrada da documentação
([pytest-testgen](https://esbmc.github.io/docs/python/pytest-testgen/)): o `nondet_*` vai direto na chamada, e a
linha da chamada sai do programa antes de rodar o `pytest` (o `from prog import *` reexecuta o módulo). O nome
do arquivo precisa ser módulo Python válido (não pode começar com dígito).

| Arquivo | Teste gerado | Roda e reproduz? | Com ajuste |
|---|---|---|---|
| `51_pytest_metodo.py` | `media(n)`, sem o objeto | não: `NameError` | `--no-slice` piora: `Conta(ctor_self, n)`, `TypeError`. Sem ajuste no gerador |
| `52_pytest_varios_args.py` | só `c`: `f(c)` | não: `TypeError` (faltam `a`, `b`) | `--no-slice`: `f(a, b, c)`, reproduz o `ZeroDivisionError` |
| `53_pytest_str.py` | `""` (pegou o `unwinding assertion` do `strlen`) | não | `--no-unwinding-assertions`: `"ab"`, reproduz o `ValueError` |

Também: guardar o `nondet` numa variável antes da chamada gera nomes internos (`k&0#1`) que não são Python.

Decisão para a Tarefa 7 do plano do harness de agente: **função livre com vários argumentos, sim** (com
`--no-slice` e o `nondet` direto na chamada); **método com receptor, não**: vai pela rota `free_function`
(`pytest_reproducer`). Pela regra das issues (só o que não dá para contornar), nenhum dos três vira issue por
enquanto: todos têm contorno do lado do pipeline. O 51 é o candidato mais forte se ela decidir reportar.
