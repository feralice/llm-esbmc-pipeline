# ESBMC-Python: construções que o ESBMC ainda não reproduz

Cada arquivo é um reprodutor mínimo de um caso em que o ESBMC-Python erra, trava ou recusa código Python
válido. Os casos vieram da verificação dos bugs reais de `dataset/bugs_reais` (setembro e outubro de 2026). A
pasta guarda só o que ainda dá problema no master; o que foi corrigido sai, e continua no histórico do git
(a versão completa do README, com todas as medições de 30/09 a 22/10, está no commit anterior a esta limpeza).

Rodar com `./rodar.sh /caminho/do/esbmc "--no-pointer-check --no-align-check"`. Flags do motor verify:
`--unwind 5 --multi-property`. As duas flags extras desligam as checagens de memória dos modelos em C;
`--no-bounds-check` não pode entrar, porque troca o `IndexError` do Python por `out-of-bounds read in list`.

## Situação no master `4a356e33eb` (27/10/2026)

Build com Bitwuzla (`~/esbmc-master/build-bw`).

| Arquivo | Construção | CPython | ESBMC `4a356e33eb` | Issue |
|---|---|---|---|---|
| `20_kwargs.py` | `kw.get('error')` com `**kw` no `__init__` | `ZeroDivisionError` | `Object "kw" not found` | #9074 (aberta) |
| `24_numpy_shape_parametro.py` | `np.array(data).shape[1]` com `data: list[list[float]]` | `ZeroDivisionError` | recusa: `numpy.array() of a value that is not a numpy array or a list or tuple literal` | #9077 (fechada pelo #9141, que troca o erro por recusa explícita) |
| `31_strip_split_laco.py` | `nondet_str().strip().split("\n")` e `split` dentro do laço | executa | com `--unwind 5` termina só com `unwinding assertion` (laços 6 e 7), esperado para string de tamanho livre; com `--unwind 12` continua sem veredito em 300 s (em `c0813af` não terminava nem com `--unwind 5`) | nenhuma: escalonamento do solver com string nondet |
| `33_atributo_ausente_uniao.py` | `x.size` com `x: Union[A, B]` valendo `B()` | `AttributeError` | recusa: `storing or passing 'x', which holds an instance of A or B` | #8408 (aberta), mesma construção |
| `45_nondet_str_contraexemplo.py` | `assert s != "ab"` com `s = nondet_str()` | `AssertionError` com `"ab"` | FAILED, sem o valor de `s` no contraexemplo (o trace só tem o `State 1` da linha 5) | #9091 (fechada como "not planned": é apresentação, não verificação) |
| `46_super_com_len_aborta.py` | `while len(self) >= self.limit` numa classe sem `__len__` | `TypeError` | FAILED com `AttributeError` (`self.limit`) | nenhuma ainda |
| `47_len_sem_dunder_len.py` | mesma condição, sem `super` | `TypeError` | FAILED com `AttributeError` | rascunho: `issues/47_len_without_dunder_len.md` |
| `48_atributo_aninhado_campo_none.py` | `current.prev.next = ...` com `prev` iniciado em `None` | `AttributeError` | `Cannot resolve nested attribute: next` | nenhuma (contorno no `verify/compat.py`) |
| `51_pytest_metodo.py` | gerador de pytest num método | ver seção abaixo | mesmo teste gerado de 22/10 | nenhuma |
| `52_pytest_varios_args.py` | gerador de pytest com vários argumentos | ver seção abaixo | mesmo teste gerado de 22/10 | nenhuma |
| `53_pytest_str.py` | gerador de pytest com `str` | ver seção abaixo | mesmo teste gerado de 22/10 | nenhuma |
| `54_chamada_posicional_mais_kwargs.py` | `g(1, **d)`: argumento explícito seguido de `**dict` | executa | aborta: `json.exception.type_error.302` | rascunho: `issues/54_positional_then_kwargs_crash.md` |
| `55_kwargs_falso_type_error.py` | `g(**d)` com `d = {"a": 1}` | executa | FAILED com `TypeError` (falso positivo) | rascunho: `issues/55_kwargs_false_type_error.md` |
| `56_atributo_criado_em_outra_instancia.py` | `a.prev = None` em um objeto, leitura de `b.prev` em outro | `AttributeError` | SUCCESSFUL (falso negativo) | rascunho: `issues/56_attribute_set_on_other_instance.md` |
| `57_global_nondet_str_lida_em_funcao.py` | função lê `len(s)` de um `s: str = nondet_str()` global | executa | aborta: `Unexpected index type in computer_pointer_offset` | nenhuma ainda |
| `58_alias_de_funcao_como_argumento.py` | `op = f; f(op(1))`: alias de função chamado dentro de argumento | executa | aborta: `type mismatch: expected code` e core dump | nenhuma ainda |
| `59_alias_de_metodo_sem_anotacao.py` | `op = obj.lt; op(x, y)` com `lt` sem anotação de tipo | executa | FAILED no `assert` (falso positivo) | rascunho: `issues/59_method_alias_false_assert.md` |

Os reprodutores 54 a 59 vieram da Tarefa 10, passo 2 (27/10): com o portão de fidelidade, o agente
manteve o corpo da função nos 5 casos, e os obstáculos que sobraram são do ESBMC. O 55, o 56 e o 59 são os
mais graves para o pipeline: dois falsos positivos e um falso negativo, não uma recusa.

O que mudou no 46 e no 47: até o master `7da3564` a exceção na condição do `while` sumia (47) ou abortava o
encoder (46), o que a #9092 corrigiu. Agora o ESBMC acusa, mas a exceção errada: o CPython avalia
`len(self)` primeiro e para no `TypeError`, enquanto o ESBMC chega ao `self.limit` e acusa `AttributeError`.
É um problema novo, de ordem de avaliação dos operandos, ainda sem issue.

## Rascunhos de issue

`issues/` guarda rascunhos em inglês, nada postado: ela avalia antes de abrir. Em 27/10: 47, 54, 55, 56 e 59
(os de veredito errado, 55, 56 e 59, primeiro). 57 e 58 não têm rascunho: têm contorno que preserva o comportamento
(driver e filtro). Os rascunhos das issues já abertas (#9073, #9074, #9077, #9091) saíram da pasta.

## Corrigidos entre 25/10 e 27/10

| Reprodutor | Issue | Correção |
|---|---|---|
| 19 (`self._args = args` com `*args` no `__init__`) | #9073 (ainda aberta no GitHub em 27/10) | FAILED com `ZeroDivisionError`, igual ao CPython, no `4a356e33eb` |

## Corrigidos entre 22/10 e 25/10

Saíram da pasta os reprodutores abaixo: no master `c0813af` todos dão o resultado esperado. As issues são as
abertas em 23/10.

| Reprodutor | Issue | Correção |
|---|---|---|
| 14 (`async def`) | | #9072 |
| 18 e 26 (`in` sobre `str` None) | #9079 | #9101 |
| 21 (`self.__class__.__name__`) | #9075 | #9173 |
| 23 (`-> bytes` com literal) | #9076 | #9116; volta a dar FAILED por `array bounds`, como no 8.5.0 |
| 25 (atributo de Optional None) | #9078 | #9120 |
| 28 (`raise` no `else` do `try`) | #9080 | #9102 |
| 29 (`dict[str, Optional[dict]]` em atributo) | #9081 | #9152, #9154; FAILED com `TypeError` e `unwinding assertion`, só com as flags do `rodar.sh` (ver nota) |
| 34 (`dict.pop(...).metodo()`) | #9082 | #9138 |
| 35 (`chr()` de surrogate) | #9083 | #9121 |
| 37 (`str(f())`) | #9084 | #9109 |
| 38 (`isinstance` com `Optional[str]`) | #9085 | #9115 |
| 39 (`int(None)`) | #9086 | #9099, #9100 |
| 40 (índice de `Sequence[str]`) | #9087 | #9112 |
| 41 (`list + tuple`) | #9088 | #9097, #9103 |
| 42 (`tuple[str, str]` com `nondet_str()`) | #9089 | #9139 |
| 43 (`Optional[str]` com `nondet_str()` num ramo) | #9090 | #9115 |
| 46_min e 47_min (exceção na condição de `if`/`while`) | #9092 | #9113 |
| 49 (`defaultdict(dict)`) | #9093 | #9128 |
| 50 (desempacotar retorno de função definida depois) | | sem issue; SUCCESSFUL no `c0813af` |

Nota sobre o 29: sem `--no-pointer-check --no-align-check`, o teste de regressão do mesmo caso
(`regression/python/github_9081_optional_dict_value_fail`, do #9154) falha no master: o ESBMC para numa
violação de alinhamento em `__ESBMC_list_contains` antes de chegar ao `TypeError`. O `d = {}` dentro do `if`
não chega a ser gravado em `d`, que fica com `keys = nil`. O bisect aponta o #9169 (`77bf4678c1`, symex), e
a linha responsável é a do `symex_dead`: o DEAD de uma variável local passou a apagar também o value set dos
membros (`value_set.erase_object`). Voltando só essa linha para `value_set.erase`, o teste passa de novo.

Consequência para o pipeline: as regras `none_guards_*` do `verify/compat.py` contornam falsos negativos que
o master já não tem (25, 26, 39). Vale remedir o filtro antes de removê-las.

## Casos do dataset afetados

| Reprodutor | Casos de `dataset/bugs_reais` |
|---|---|
| 20 | `vm_real_02` (schema, `Schema.validate`; o 19, do mesmo caso, já passa) |
| 24 | `dz_real_01` (matplotlib, `makeMappingArray`) |
| 31, 57 | `bip_thefuck_4` (aliases do fish; com o corpo preservado, o 57 aparece antes do 31) |
| 33 | `nm_real_25` (`s.method` com `s` de uma união de classes) |
| 46, 47 | `nm_real_11` (`LocalCache`, base `OrderedDict` trocada por classe vazia pelo harness) |
| 48 | `nm_real_12` (`current_line.prev.next = ...`, com `prev` iniciado em `None`) |
| 58, 59 | `bip_pandas_7` (`np.where(op(l, r) | ...)` com `op = operator.lt` ou `operator.le`) |
| 54, 55 | `nm_real_08` (`Request.url_for` repassa `**kwargs` a `app.url_for`) |
| 56 | `nm_real_12` (o `PamdRule` real não chama `super().__init__`; o primeiro nó fica sem `prev`) |

## Gerador de pytest (medido no master `7da3564`, 22/10/2026; igual no `c0813af`)

`--generate-pytest-testcase --pytest-output-dir <pasta> --unwind 5`, com Bitwuzla. Formato de entrada da
documentação ([pytest-testgen](https://esbmc.github.io/docs/python/pytest-testgen/)): o `nondet_*` vai direto na
chamada, e a linha da chamada sai do programa antes de rodar o `pytest` (o `from prog import *` reexecuta o
módulo). O nome do arquivo precisa ser módulo Python válido (não pode começar com dígito).

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
