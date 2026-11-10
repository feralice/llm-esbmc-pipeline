# ESBMC-Python: construções que o ESBMC ainda não reproduz

Cada arquivo é um reprodutor mínimo de um caso em que o ESBMC-Python erra, trava ou recusa código Python
válido. Os casos vieram da verificação dos bugs reais de `dataset/bugs_reais` (setembro e outubro de 2026). A
pasta guarda só o que ainda dá problema no master; o que foi corrigido sai, e continua no histórico do git
(a versão completa do README, com todas as medições de 30/09 a 22/10, está no commit anterior a esta limpeza).

Rodar com `./rodar.sh /caminho/do/esbmc "--no-pointer-check --no-align-check"`. Flags do motor verify:
`--unwind 5 --multi-property`. As duas flags extras desligam as checagens de memória dos modelos em C;
`--no-bounds-check` não pode entrar, porque troca o `IndexError` do Python por `out-of-bounds read in list`.

## Situação no master `822227ff96` (08/11/2026)

ESBMC 8.6.0 (build Bitwuzla em `~/esbmc-master/build-bw`, master `822227ff96`, compilado em 07/11), o mesmo que o
pipeline usa agora. 95 commits depois do `451f54c`. Saída completa em
`artifacts/esbmc-master-822227ff96-2026-11-08/saida.txt`, gerada com
`./rodar.sh <esbmc> "--no-pointer-check --no-align-check"`. Para os que passaram a dar SUCCESSFUL, conferi também
com o valor do `assert` trocado (60: `== 2`; 63: `== 1`; 70: `len == 3`; 71: `b == 3`; 72: `== 3.5`): os cinco dão
FAILED, então o SUCCESSFUL é o veredito certo e não um erro que passa batido. Das 18 linhas da tabela de 05/11,
5 mudaram para melhor e 13 ficaram iguais; nenhuma piorou.

| Arquivo | Veredito em `822227ff96` | Desde `451f54c` | Issue |
|---|---|---|---|
| `20_kwargs.py` | `Object "kw" not found` | igual | #9074 (aberta) |
| `24_numpy_shape_parametro.py` | recusa: `numpy.array() of a value that is not a numpy array or a list or tuple literal` | igual | #9077 (fechada pelo #9141, já era recusa explícita) |
| `31_strip_split_laco.py` | só `unwinding assertion` (laços 6 e 7) | igual | nenhuma |
| `33_atributo_ausente_uniao.py` | recusa: `storing or passing 'x', which holds an instance of A or B` | igual | #8408 (aberta) |
| `45_nondet_str_contraexemplo.py` | FAILED (`return_value$_strcmp$1 != 0`), sem o valor de `s` | igual | #9091 (fechada, "not planned") |
| `48_atributo_aninhado_campo_none.py` | `Cannot resolve nested attribute: next` | igual | nenhuma |
| `51_pytest_metodo.py` | FAILED (`ZeroDivisionError`) | igual (gerador de pytest não remedido hoje) | nenhuma |
| `52_pytest_varios_args.py` | FAILED (`ZeroDivisionError`) | igual (idem) | nenhuma |
| `53_pytest_str.py` | FAILED (`ValueError`; `unwinding assertion` laço 2) | igual (idem) | nenhuma |
| `57_global_nondet_str_lida_em_funcao.py` | aborta: `Unexpected index type in computer_pointer_offset` | igual | nenhuma ainda |
| `58_alias_de_funcao_como_argumento.py` | aborta: `type mismatch: expected code` | igual | nenhuma (contorno no `compat.py`) |
| `60_lista_em_valor_de_dict.py` | SUCCESSFUL | **corrigido** (era recusa `List variable not found`) | #9837 (fechada em 07/11, PR #9864) |
| `63_getitem_tupla_em_atributo.py` | SUCCESSFUL | **corrigido** (era segfault) | #9839 (fechada em 06/11, PR #9861) |
| `65_parametro_reatribuido_dict_get.py` | `Member 'is_none' is not a field of pointer_struct` | igual | rascunho em `issues/` |
| `66_desempacotar_getitem_de_atributo.py` | recusa: `Cannot unpack pointer` | igual | rascunho em `issues/` |
| `70_tupla_opcional_len.py` | SUCCESSFUL | **corrigido** (era FAILED falso) | #9953 (fechada em 06/11, PR #10000) |
| `71_tupla_opcional_desempacotada.py` | SUCCESSFUL | **corrigido** (era recusa) | #9953 (PR #10000) |
| `72_tupla_opcional_com_bool.py` | SUCCESSFUL | **corrigido** (era SIGSEGV) | #9954 (fechada em 07/11, PR #10020) |

Ressalva sobre o 60: o reprodutor mínimo passa, mas o caso real (`bip_ansible_16`) mistura lista e `int` no mesmo
dicionário, e esse continua recusado: `d['p'] = []; d['n'] = 1; d['p'].append("x")` dá `List variable not found:`
no `822227ff96`. Então o 60 está corrigido, mas o `bip_ansible_16` não.

Sobram 13 reprodutores. Dos 13, 2 têm issue aberta (20 e 33), 2 têm rascunho em `issues/` (65 e 66), 3 são do
gerador de pytest e os outros 6 não têm issue (31, 45, 48, 57, 58 e o 24, que já é recusa explícita).

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

Atualização de 08/11: os dois PRs abaixo foram aceitos (#9861 em 06/11, #9864 em 07/11) e as issues #9837 e #9839
estão fechadas. O texto abaixo é a medição de 05/11 e fica como histórico. A única issue desta pasta que segue aberta
no GitHub é a #9074 (20), mais a #8408 (33). O PR #9849 (estender o `len(self)` para classe base) foi fechado sem merge.

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

## Corrigidos entre 05/11 e 08/11

Conferidos no `822227ff96` com a regra de sempre: veredito certo no reprodutor e FAILED com o valor trocado. O
reprodutor continua na pasta (fica como teste de regressão do que mudou) e na tabela acima; o histórico dele está
na seção do `451f54c`.

| Reprodutor | Issue | Correção (commit no master) | Situação no `822227ff96` | Caso do dataset |
|---|---|---|---|---|
| 60 (lista em valor de `dict`) | #9837 | #9864 (`4129f25d35`) | SUCCESSFUL; com `== 2`, FAILED. Só o caso de lista pura; o caso real mistura `int` e continua recusado | `bip_ansible_16` (ainda não) |
| 63 (`__getitem__` com tupla em atributo) | #9839 | #9861 (`b9ebba04ac`) | SUCCESSFUL; com `== 1`, FAILED | `bip_pandas_162` |
| 70 e 71 (`len`, `for` e desempacotar `Optional[tuple]`) | #9953 | #10000 (`39590bbd26`) | SUCCESSFUL nos dois; com o valor trocado, FAILED | nenhum medido |
| 72 (`Optional[tuple[bool, float]]`) | #9954 | #10020 (`519a101a7b`) | SUCCESSFUL; com `== 3.5`, FAILED | nenhum medido |

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

## Onde os bugs da disciplina param antes do ESBMC (rodada de 08/11/2026)

Medido em `artifacts/pgene601/ajustes-2026-11-07` (ESBMC master `822227ff96`, 47 bugs). O detector acerta a
expressão de 38 dos 47. Desses 38, só 17 chegam a um veredito do ESBMC e 5 viram `CONFIRMED`. Os outros 18 ficam em
`LLM_ONLY` por recusa do ESBMC ou por recusa prévia do pipeline. Os motivos, por bug:

| Motivo | Bugs | Causa | Contorno possível |
|---|---|---|---|
| `async` como ponto de entrada | `cps_opcua_1131`, `cps_opcua_1826` | recusa prévia do pipeline, sem tentar o ESBMC | gerar a versão síncrona do corpo (`await x` vira `x`) |
| `array.array` chamado e lido | `cps_pymavlink_1058`, `cps_pymavlink_1259` | recusa prévia do pipeline | stub tipado de `array.array` |
| `bytearray` não suportado | `cps_minimqtt_5`, `cps_pythoncan_225` | recusa do ESBMC | `bytes` onde só lê; lista de inteiros onde escreve |
| `str %` com argumento não constante | `cps_mavproxy_1380`, `cps_mavproxy_1447` | recusa do ESBMC (`%f`, `%s` com valor livre) | já há regra `compat_percent_format` para `%s`, `%d` e `%u`; falta o caso com argumento não constante |
| classe do stub definida 2 vezes | `cps_mavproxy_989` (`_TimeStub`); `cps_pyspartn_4` (`_HexBytesStub`) tem o mesmo defeito em uma hipótese, mas conta em `SPEC_FAILED` | defeito do renderizador do pipeline, não do ESBMC | dar nome único ao stub ou emitir uma vez só |
| tipo do receptor não resolvido | `cps_cantools_595` (`.attrib.get()`), `cps_mavproxy_741` (`__python_dict__.get()`), `cps_pymavlink_1217` (`_instances` em `Subscript`) | recusa do ESBMC | variável local com anotação antes da cadeia |
| atributo de classe sem tipo ou não definido | `cps_piouart_6` (`Parity`), `cps_udsoncan_291` (`C@AsciiCodec`) | recusa do ESBMC | mesma família do contorno de 07/11 (constante como campo de instância), agora para classe do próprio código |
| outros | `cps_cantools_804`, `cps_pymodbus_2921`, `cps_pythoncan_1811`, `cps_ros2cli_1112` | tipos de stub, numpy, método sem definição convertida, `os.environ` | caso a caso |

Em 14 dos 18 o self-healing tentou 3 vezes, mas só mudou o JSON de tipos do LLM, nunca o programa. Nos 4 de recusa
prévia ele nem rodou. Ordem de ataque proposta: (1) os 2 defeitos do renderizador, (2) recusa prévia de `async` e
`array.array`, (3) `bytearray`, (4) `str %`, (5) receptor e atributo de classe.

Dos 20 restantes, 5 viram `CONFIRMED` e 15 param assim: 4 `UNVALIDATED` (o CPython não reproduz o contraexemplo), 3
`SPEC_FAILED` (não chegam ao ESBMC), 2 `ESBMC_TIMEOUT` (`cps_gps_127`, `cps_pymodbus_2977`), 2 `ESBMC_ERROR` (`cps_mavproxy_1032` com
SIGSEGV, `cps_ros2cli_370` com `irep2_cast_error`), 2 `OTHER_FAILURE`, 1 `ESBMC_MISSED` e 1 `NOT_CONFIRMED`.

## Candidatos a issue (08/11/2026, nada foi aberto)

Reduzidos de quatro programas da rodada dos 47. Conferido contra o CPython e contra as 851 issues com o rótulo `python` (título). Rascunhos em `issues/74` a `issues/77`.

| Arquivo | Construção | ESBMC `822227ff96` | Issue parecida | Contorno |
|---|---|---|---|---|
| `74_float_variavel_passada_por_self.py` | `int(tnow - 1.5)` em parâmetro sem anotação, chamado por `self` com uma variável `float` | SIGSEGV interno | #9841 (fechada pela #9860, que cobre só o argumento literal) | anotar o parâmetro |
| `75_staticmethod_dict_aninhado_irep2.py` | `@staticmethod` que devolve `dict[str, dict[str, str]]`, lido com `.items()` e `.get()` | `irep2_cast_error` | nenhuma igual (a #10121, aberta, é anotação entre aspas) | só parcial: sem a classe some, mas aparece um falso negativo à parte |
| `76_bytes_vazio_indice_falso_negativo.py` | `d[0] == b"P"` com `d = b""` | 0 VCC, `SUCCESSFUL` (falso negativo) | nenhuma | `len(d) > 0 and d[0] == b"P"` |
| `77_bytearray_nao_suportado.py` | `bytearray()` e `.append` | recusa: `bytearray is not supported` | nenhuma (a #5515 deu a mensagem clara) | nenhum fiel |

Também medido e descartado: `'Click %.1f m' % (x,)` com `len(...) > 0` dava FAILED só por `--unwind 5` curto (o `strlen` precisa de mais voltas); com `--unwind 20` dá SUCCESSFUL, então não é defeito.
O `array.array` já tem a #8222 (aberta, o Lucas comentou o modelo em classe).
Nota: o reprodutor do subagente para o 76 usava `nondet_bool()` e não roda no CPython; esta versão foi trocada por `f(b"")`, que reproduz nos dois.

## 09/11/2026: bytearray e bytes(lista)

- **Regra nova `compat_bytearray`** (compat.py): `bytearray()`, `bytearray(b"..")`, `bytearray([..])` e `bytearray(n)` com `n` inteiro (literal ou parâmetro `int`) viram lista de inteiros. Atinge as hipóteses que paravam em "bytearray is not supported" (21 na rodada final; bugs minimqtt_5, piouart_6, pythoncan_225, mavproxy_1572, umqtt_1149). Ainda **não medida** em rodada: precisa de LLM para a especificação.
- **Limite da regra:** um byte maior que 255 deixa de dar ValueError; o replay em CPython pega isso e o veredito vira UNVALIDATED, não confirmação falsa.
- **Candidato a issue 78 (não postado):** `bytes(buf)` com `buf` lista em variável tem tamanho errado no ESBMC (falso alarme). Reprodutor `78_bytes_de_lista_variavel.py`. Por isso a regra não reescreve um buffer que passa por `bytes(...)` no mesmo código.

## Candidatos novos da rodada de 09/11/2026 (parcial, 66 de 109 hipóteses; sem reprodutor, nada aberto)

Vêm das recusas `LLM_ONLY` do `v2_verify_report`/checkpoint da rodada final. Falta reduzir cada um a um arquivo pequeno e conferir no ESBMC mais novo e no GitHub antes de virar rascunho.

| Nº provisório | Mensagem do ESBMC | Casos da rodada | Observação |
|---|---|---|---|
| 79 | `uncaught exception [N6type2t18symbolic_type_excpE]` | mavproxy_741 e mavproxy_989 (`LogModule.log_status`) | crash interno; aparecia também em pyspartn_4 e pymodbus_2977 em rodadas anteriores |
| 80 | `attribute '_sock' holds a '_Obj_self__sock' and is assigned ...` | minimqtt_5 (`MQTT.connect`) | atributo recebe objeto de outra classe |
| 81 | `unsupported: non-constant argument in str % formatting` | mavproxy_1380, mavproxy_1447, mavproxy_1572 | formato com `%u`/`%.2f` e valores de atributo; a regra `compat_percent_format` só cobre argumento constante |
| 82 | `Cannot unpack symbol/empty - only tuples and arrays can be unpacked` | gps_60 (`GPS.update`), pymavlink_1058 (`init_arrays_fast`) | desempacotar valor que o ESBMC não vê como tupla |
| 83 | `class '_OsModule' is defined 2 times ... ESBMC keys a class` | mavproxy_989, piouart_6 | o harness define a mesma classe de stub duas vezes: provável defeito do nosso render, conferir antes de culpar o ESBMC |

Fora da lista de issues, um caso nosso: em piouart_6 a regra `compat_bytearray` não disparou (o `n` é parâmetro reatribuído). Conserto pequeno possível depois da entrega.

## Issues abertas em 09/11/2026

Autorizado pela Fernanda no mesmo dia. Conferido antes: nenhuma issue nem PR igual entre as issues e PRs com rótulo `python` (por título); reprodutores rodados no ESBMC `b76980aaa0` (o master estava 12 commits à frente, nenhum sobre essas construções pelo título; não recompilado). O 74 cita a #9841.

| Rascunho | Issue |
|---|---|
| 74 float em variável passada por `self` (SIGSEGV) | esbmc/esbmc#10204 |
| 75 staticmethod com dict aninhado (`irep2_cast_error`) | esbmc/esbmc#10205 |
| 76 `d[0] == b"P"` com `bytes` vazio (falso negativo) | esbmc/esbmc#10206 |
| 77 suporte a `bytearray` (pedido de recurso) | esbmc/esbmc#10207 |
| 78 `bytes(lista_em_variavel)` com tamanho errado | esbmc/esbmc#10208 |

Os candidatos 79 a 83 acima continuam sem reprodutor e sem issue.
