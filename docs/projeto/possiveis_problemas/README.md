# ESBMC-Python: construções que o ESBMC ainda não reproduz

Cada arquivo é um reprodutor mínimo de um caso em que o ESBMC-Python erra, trava ou recusa código Python
válido. Os casos vieram da verificação dos bugs reais de `dataset/bugs_reais` (setembro e outubro de 2026). A
pasta guarda só o que ainda dá problema no master; o que foi corrigido sai, e continua no histórico do git
(a versão completa do README, com todas as medições de 30/09 a 22/10, está no commit anterior a esta limpeza).

Rodar com `./rodar.sh /caminho/do/esbmc "--no-pointer-check --no-align-check"`. Flags do motor verify:
`--unwind 5 --multi-property`. As duas flags extras desligam as checagens de memória dos modelos em C;
`--no-bounds-check` não pode entrar, porque troca o `IndexError` do Python por `out-of-bounds read in list`.

## Situação no master `451f54c` (05/11/2026)

Build com Bitwuzla (worktree `~/esbmc-wt/issue-9843`, master `451f54cab6`). Saída completa em
`artifacts/esbmc-master-451f54c-2026-11-05/`, junto com a do `d520a903ae`, o ESBMC congelado que o pipeline usa
até o próximo congelamento. Quando o resultado no d520 é diferente do master, a coluna do ESBMC diz como é lá. Dos 15 que
ficaram de 03/11, nenhum mudou de veredito no `rodar.sh`; o gerador de pytest do 52 mudou (ver a seção dele).

| Arquivo | Construção | CPython | ESBMC `451f54c` | Issue |
|---|---|---|---|---|
| `20_kwargs.py` | `kw.get('error')` com `**kw` no `__init__` | `ZeroDivisionError` | `Object "kw" not found` | #9074 (aberta) |
| `24_numpy_shape_parametro.py` | `np.array(data).shape[1]` com `data: list[list[float]]` | `ZeroDivisionError` | recusa: `numpy.array() of a value that is not a numpy array or a list or tuple literal` | #9077 (fechada pelo #9141, que troca o erro por recusa explícita) |
| `31_strip_split_laco.py` | `nondet_str().strip().split("\n")` e `split` dentro do laço | executa | com `--unwind 5` termina só com `unwinding assertion` (laços 6 e 7), esperado para string de tamanho livre; com `--unwind 12` continua sem veredito em 300 s (em `c0813af` não terminava nem com `--unwind 5`) | nenhuma: escalonamento do solver com string nondet |
| `33_atributo_ausente_uniao.py` | `x.size` com `x: Union[A, B]` valendo `B()` | `AttributeError` | recusa: `storing or passing 'x', which holds an instance of A or B` | #8408 (aberta), mesma construção |
| `45_nondet_str_contraexemplo.py` | `assert s != "ab"` com `s = nondet_str()` | `AssertionError` com `"ab"` | FAILED, sem o valor de `s` no contraexemplo (o trace só tem o `State 1` da linha 5) | #9091 (fechada como "not planned": é apresentação, não verificação) |
| `48_atributo_aninhado_campo_none.py` | `current.prev.next = ...` com `prev` iniciado em `None` | `AttributeError` | `Cannot resolve nested attribute: next` | nenhuma (contorno no `verify/compat.py`) |
| `51_pytest_metodo.py` | gerador de pytest num método | ver seção abaixo | mesmo teste gerado de 22/10 | nenhuma |
| `52_pytest_varios_args.py` | gerador de pytest com vários argumentos | ver seção abaixo | teste gerado já reproduz (mudou sem issue; no d520, igual a 22/10) | nenhuma |
| `53_pytest_str.py` | gerador de pytest com `str` | ver seção abaixo | mesmo teste gerado de 22/10 | nenhuma |
| `57_global_nondet_str_lida_em_funcao.py` | função lê `len(s)` de um `s: str = nondet_str()` global | executa | aborta: `Unexpected index type in computer_pointer_offset` | nenhuma ainda |
| `58_alias_de_funcao_como_argumento.py` | `op = f; f(op(1))`: alias de função chamado dentro de argumento | executa | aborta: `type mismatch: expected code` e core dump | nenhuma (contorno no `verify/compat.py`, regra `compat_function_alias`, desde 04/11) |
| `60_lista_em_valor_de_dict.py` | `d['p'] = []; d['p'].append("x")` | executa | recusa: `List variable not found:` | #9837 (aberta; PR #9864 aberto, ver abaixo) |
| `63_getitem_tupla_em_atributo.py` | `fr.loc[0, 1]` com `__getitem__` na classe do atributo | executa | segfault no encoder (exit 139); com chave escalar, FAILED falso | #9839 (aberta; PR #9861 aberto, ver abaixo) |
| `65_parametro_reatribuido_dict_get.py` | parâmetro `k` reatribuído a `d.get(k)` | executa | `Member 'is_none' is not a field of pointer_struct` e `SMT solver failed` | rascunho: `issues/65_param_reassigned_optional.md` |
| `66_desempacotar_getitem_de_atributo.py` | `a, b = n.m[0]` com `__getitem__` na classe do atributo | executa | recusa: `Cannot unpack pointer` | rascunho: `issues/66_unpack_getitem_on_attribute.md` (contorno no `verify/compat.py`, regra `compat_attribute_item`, desde 04/11) |
| `70_tupla_opcional_len.py` | `len(value)` de um `Optional[tuple[int, int]]` atribuído num ramo, depois do `is not None` | executa | FAILED falso: o `len` vira `strlen` e dá 1; `for v in value` também dá 1 volta. d520: SUCCESSFUL (certo) | #9953 (aberta em 05/11) |
| `71_tupla_opcional_desempacotada.py` | `a, b = value` no mesmo caso do 70 | executa | recusa: `Cannot unpack non-tuple type: tag-Optional_struct` (também com `a, *rest`). d520: exceção do Bitwuzla (a #9843) | #9953 (aberta em 05/11) |
| `72_tupla_opcional_com_bool.py` | `value[1]` de um `Optional[tuple[bool, float]]` atribuído num ramo | executa | SIGSEGV no encoder (exit 139), igual no d520 | #9954 (aberta em 05/11) |

Os reprodutores 54 a 59 vieram da Tarefa 10, passo 2 (27/10): com o portão de fidelidade, o agente
manteve o corpo da função nos 5 casos, e os obstáculos que sobraram são do ESBMC. O 54, o 55 e o 59 foram
corrigidos no master até 03/11, e o 56 até 05/11.

Os reprodutores 60 a 66 vieram da triagem da Tarefa 10, passo 4 (28/10, 30 casos), reduzidos por três agentes.
No 60 o contorno teria de mudar a estrutura da função alvo; o 65 se contorna renomeando a variável
reatribuída (regra `compat_rebound_parameter` do `compat.py`, desde 03/11), e o 66 tem contorno que preserva o corpo.

Os reprodutores 70 a 72 vieram da conferência da correção da #9843 (05/11). O #9863 acertou o índice, o `in`
e o `==` sobre o `Optional[tuple]`, mas o 70 e o 71 pioraram em relação ao d520 (lá o `len`, o `for` e o
desempacotamento com `*` davam o certo). O 70 é o mais grave dos novos: FAILED falso. O 72 é a parte da #9843
que continua: tupla com `bool` junto de um tipo mais largo. Ficaram de fora dois achados da nossa revisão da
correção, porque no master não aparecem: `t: tuple[float, float] = (1.5, 2.5); t = (1, 2)` dá SUCCESSFUL
(e FAILED com o valor trocado) nos dois ESBMC, sem abortar o Bitwuzla.

## Issues abertas com PR em andamento (05/11)

- #9837 (60): o PR #9864, do mantenedor, tipa o valor do dicionário como lista quando toda gravação nele é uma
  lista literal. Não aplica mais sobre o master `451f54c` (conflito em `dict_type_resolution.cpp` com o #9745),
  então não foi medido. Mesmo depois de entrar, não cobre o caso real (`bip_ansible_16`): lá o mesmo
  dicionário guarda lista e `int` (`cpu_facts['processor_count'] = i`), e o PR mantém a regra antiga quando as
  gravações misturam tipos. Medido no master: `d['p'] = []; d['n'] = 1; d['p'].append("x")` continua
  recusado, no módulo e dentro de função.
- #9839 (63): o PR #9861, do mantenedor, aplicado sem conflito sobre o `451f54c` (só para medir, depois
  desfeito): o 63 dá SUCCESSFUL e FAILED com o valor trocado; chave escalar, fatia (`fr.loc[:, "All"]`) e o
  objeto vindo de parâmetro anotado (`def g(table: Frame)`) também dão o certo. Ele só vale quando a única
  gravação do atributo é `self.attr = C(...)` no `__init__` e nenhuma das classes tem subclasse.

## Rascunhos de issue

`issues/` guarda rascunhos em inglês, nada postado: ela avalia antes de abrir. Em 03/11 ela aprovou e foram
abertas #9835 a #9843 (47 com o 46, 56, 60, 61 com o 62, 63, 64, 67, 68 e 69); os rascunhos saíram da pasta.
Em 05/11 ela aprovou abrir os novos (nenhum PR cobria o caso): #9953 (70 e 71) e #9954 (72); os rascunhos
saíram da pasta. O 70 tem um contorno possível do lado do pipeline (trocar `len` pela aridade anotada e o
desempacotamento por índices), mas muda o código alvo, então não entra no `compat.py`.
Ficam o 65 e o 66, que têm contorno que preserva o comportamento (renomear a variável reatribuída; alias local
anotado). 57 e 58 não têm rascunho: têm contorno (driver e filtro). Os rascunhos das issues abertas antes
(#9073, #9074, #9077, #9091) também saíram da pasta.

## Corrigidos entre 03/11 e 05/11

Saíram da pasta. Conferido no master `451f54cab6` com a mesma regra de 03/11: o veredito certo no reprodutor e
FAILED com o valor trocado (`assert` de outro valor, ou `except` da exceção errada nos casos de exceção). Todos
continuam errados no `d520a903ae` (medido no mesmo dia), então afetam o pipeline até o próximo congelamento.

| Reprodutor | Issue | Correção (commit no master) | Situação no `451f54c` | Caso do dataset |
|---|---|---|---|---|
| 46 e 47 (`len(self)` sem `__len__`) | #9835 | #9846 (`b0cb337083`) | FAILED com `TypeError`, como o CPython; `except TypeError` dá SUCCESSFUL, `except AttributeError` dá FAILED. O PR #9849 (rascunho, aberto) estende para `self` com classe base | `nm_real_11` |
| 56 (atributo criado em outra instância) | #9836 | #9872 (`cc63c4f527`) | FAILED com `AttributeError`; `except AttributeError` dá SUCCESSFUL | `nm_real_12` |
| 61 e 62 (`or` com atributo inexistente) | #9838 | #9866 (`4cbfb304be`) | FAILED com `AttributeError` nos dois (o 61 também, porque `nondet_bool()` pode ser falso); `except AttributeError` dá SUCCESSFUL | `nm_real_25` |
| 64 (lambda em método) | #9840 | #9851 (`7aea1e0f64`) | SUCCESSFUL; com `== 3`, FAILED | `dz_real_02` |
| 67 (parâmetro float sem anotação) | #9841 | #9860 (`9e6919c513`) | SUCCESSFUL; com `== 2`, FAILED | PGENE601 `cps_mavproxy_1032` |
| 68 (`%.1f` com operando variável) | #9842 | #9850 (`90b9926cf1`) | SUCCESSFUL; com `"v 2.6"`, FAILED | PGENE601 `cps_mavproxy_1380` |
| 69 (`Optional[tuple[float, float]]` comparado) | #9843 | #9863 (`cd06228e88`) | SUCCESSFUL; com `< 1.0`, FAILED. Correção parcial: ver 70 a 72 | PGENE601 `cps_mavproxy_1380` |

Nosso patch da #9843 (worktree `~/esbmc-wt/issue-9843`) ficou obsoleto e foi descartado; a cópia está em
`~/mestrado/backup_llm_esbmc_2026-11-05/`.

## Corrigidos entre 27/10 e 03/11

Saíram da pasta, com os rascunhos de issue, que não chegaram a ser postados. Conferido com um `assert` do valor
esperado: SUCCESSFUL com o valor certo, FAILED com o valor trocado.

| Reprodutor | Issue | Situação no `0945ac9` |
|---|---|---|
| 54 (`g(1, **d)`) | | SUCCESSFUL, sem abortar |
| 55 (`g(**d)` com falso `TypeError`) | #9329 (de outra pessoa, fechada em 30/10) | SUCCESSFUL |
| 59 (alias de método sem anotação) | | SUCCESSFUL, sem o falso positivo no `assert` |

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
o master já não tem (25, 26, 39). Remedido em 04/11 no `d520a903ae` (`docs/experimentos/melhorias_2026-11-04/lote_C.md`):
saíram as guardas de `in`, comparação de ordem e aritmética (sondas aceitas e os mesmos vereditos nos 19 casos reais
medidos). Ficam a de atributo (o ESBMC ainda perde o `AttributeError` de método chamado no fim de uma cadeia de
campos, sonda nova `none_metodo_cadeia`; sem a guarda, 3 confirmações caem), a de índice e a de `len`/`int`/`float`.

## Casos do dataset afetados

| Reprodutor | Casos de `dataset/bugs_reais` |
|---|---|
| 20 | `vm_real_02` (schema, `Schema.validate`; o 19, do mesmo caso, já passa) |
| 24 | `dz_real_01` (matplotlib, `makeMappingArray`) |
| 31, 57 | `bip_thefuck_4` (aliases do fish; com o corpo preservado, o 57 aparece antes do 31) |
| 33 | `nm_real_25` (`s.method` com `s` de uma união de classes) |
| 48 | `nm_real_12` (`current_line.prev.next = ...`, com `prev` iniciado em `None`) |
| 58 | `bip_pandas_7` (`np.where(op(l, r) | ...)` com `op = operator.lt` ou `operator.le`) |
| 60 | `bip_ansible_16` (`cpu_facts['processor'].append(...)`) |
| 63 | `bip_pandas_162` (`table.loc[:, margins_name]`) |
| 65 | `av_real_01` (youtube-dl `cli_bool_option`: `param = params.get(param)`) |
| 66 | `dz_real_04` (nki-samples `interpolate_bilinear_2x_fwd`) |
| 70, 71, 72 | nenhum caso medido ainda; vieram da conferência da #9843 (o `click_pos` do `cps_mavproxy_1380` é `Optional[tuple[float, float]]`) |

## Gerador de pytest (medido no master `7da3564`, 22/10/2026; igual no `c0813af`)

`--generate-pytest-testcase --pytest-output-dir <pasta> --unwind 5`, com Bitwuzla. Formato de entrada da
documentação ([pytest-testgen](https://esbmc.github.io/docs/python/pytest-testgen/)): o `nondet_*` vai direto na
chamada, e a linha da chamada sai do programa antes de rodar o `pytest` (o `from prog import *` reexecuta o
módulo). O nome do arquivo precisa ser módulo Python válido (não pode começar com dígito).

| Arquivo | Teste gerado | Roda e reproduz? | Com ajuste |
|---|---|---|---|
| `51_pytest_metodo.py` | `media(n)`, sem o objeto | não: `NameError` | `--no-slice` piora: `Conta(ctor_self, n)`, `TypeError`. Sem ajuste no gerador |
| `52_pytest_varios_args.py` | só `c`: `f(c)` | não: `TypeError` (faltam `a`, `b`) | `--no-slice`: `f(a, b, c)`, reproduz o `ZeroDivisionError`. No master `451f54c` (05/11) já sai `f(arg0, arg1, arg2)` com `(0, 0, 0)` sem `--no-slice`, e o pytest reproduz; mudou sem issue, commit não identificado. O 51 e o 53 seguem iguais |
| `53_pytest_str.py` | `""` (pegou o `unwinding assertion` do `strlen`) | não | `--no-unwinding-assertions`: `"ab"`, reproduz o `ValueError` |

Também: guardar o `nondet` numa variável antes da chamada gera nomes internos (`k&0#1`) que não são Python.

Decisão para a Tarefa 7 do plano do harness de agente: **função livre com vários argumentos, sim** (com
`--no-slice` e o `nondet` direto na chamada); **método com receptor, não**: vai pela rota `free_function`
(`pytest_reproducer`). Pela regra das issues (só o que não dá para contornar), nenhum dos três vira issue por
enquanto: todos têm contorno do lado do pipeline. O 51 é o candidato mais forte se ela decidir reportar.
