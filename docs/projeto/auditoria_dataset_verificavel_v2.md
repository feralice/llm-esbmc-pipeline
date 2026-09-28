# Auditoria do dataset V2: subconjunto verificável pelo ESBMC-Python

Data: 28/09/2026  
Verificador: ESBMC 8.5.0, `--z3 --unwind 6 --timeout 20s` (flags por caso na primeira linha de `bugs/<id>_fixed.py`)  
Dataset: `dataset/v2_real_world` (corpus completo preservado) e `dataset/v2_real_world_eligible` (subconjunto gerado)

## Resumo

Esta tabela mostra o estado da **referência ESBMC**, não a validade dos bugs. Os
120 casos têm validação externa e `detection/` mapeado ao trecho pré-fix; 18
também já têm harness de referência confirmado ponta a ponta pelo ESBMC. Os
102 restantes continuam no corpus e ainda não têm essa confirmação completa.

| Classificação | Casos |
|---|---:|
| Prontos para baseline ESBMC | 18 |
| Precisam de revisão | 18 |
| Não suportados pelo ESBMC 8.5.0 | 23 |
| Ainda não prontos para baseline | 61 |
| Total | 120 |

Categorias no conjunto pronto para baseline: out_of_bounds (8), invalid_precondition (4), division_by_zero (3), none_misuse (3), variable_misuse (1), type_mismatch (1). Dois casos mantêm duas categorias (`dz_real_03` e `dz_real_04`), porque o fix traz evidência independente de precondição de entrada. Os 18 não são o limite do dataset: são somente os casos cuja referência ESBMC já está pronta para comparação.

Validação externa: os 120 casos têm bug confirmado por terceiros. 87 vêm do BugsInPy, com commits conferidos contra o `bug.info`; os outros 33 têm o fix no branch principal do repositório oficial ou em PR mergeado. O gargalo não é a proveniência, e sim a fidelidade do harness e o suporte do ESBMC.

## Critérios

Um caso é **pronto para o baseline ESBMC** somente se passa em todos os portões, verificados por `scripts/build_v2_eligible.py` (que se recusa a gerar o subconjunto se algum falhar) e por `tests/test_v2_eligibility.py`. Isso não define a validade do bug nem remove o caso do corpus: os 120 casos continuam sendo bugs reais validados externamente. O subconjunto `v2_real_world_eligible/` é apenas uma amostra conveniente de casos cujo harness de referência já está pronto para comparação.

1. Bug validado por terceiros, com `repo_url` e evidência de origem. Quando existe um commit do fix, ele é guardado em `patches/<id>.diff` como evidência auxiliar; o fix não é requisito para incluir o bug no corpus.
2. Categoria entre as oito formais e presente nos rótulos originais.
3. O arquivo de `detection/` é um snippet fiel do código **anterior** ao fix, comparado com o patch quando há um patch disponível. O snippet é a entrada do LLM; não precisa ser o arquivo completo do projeto.
4. O harness bugado dá FAILED numa checagem nativa do ESBMC (`esbmc_property`); `unwinding_assertion` e falhas internas do modelo (`model_check`) não contam.
5. O sintoma é compatível com cada categoria mantida (tabela `symptoms_for_category` em `eligibility.json`).
6. Quando existe `bugs/<id>_fixed.py`, ele é usado somente para validar o harness de referência; essa comparação não define se o bug é real nem se ele pertence ao corpus.

Categoria e sintoma são coisas diferentes: o ESBMC só informa o sintoma (a linha após `Violated property:`), e a categoria descreve a causa. `invalid_precondition` e `variable_misuse` não têm mensagem própria e só são confirmadas pela consequência nativa.

## Achados principais

- **Código corrigido no `detection/`**: `dz_real_02`, `ip_real_19` e `ip_real_21` mostravam ao LLM a versão já consertada. Os três foram restaurados para a versão bugada do commit, e a expressão do `ip_real_21` foi corrigida no GT e no manifesto.
- **Snippets de detection**: os 120 arquivos de `detection/` agora contêm o trecho pré-fix correspondente à evidência disponível. Eles são recortes para a entrada do LLM, não cópias completas dos repositórios de produção.
- **Duplicata**: `vm_real_09` e `nm_real_09` são o mesmo commit do tqdm, contado duas vezes com categorias diferentes.
- **Proveniência errada**: `oob_real_06` tinha `bugsinpy_id: 1513`, mas é o issue 1513 do PyBugHive; `tm_real_11` aponta para uma função que o fix não altera (o patch muda o chamador).
- **Harness artificial**: cerca de 35 harnesses reduziam o bug a `assert not flag`, e o ESBMC só escolhia um booleano. Outros 40 usavam `assert buggy == correct`, que na prática mede resultado incorreto. A auditoria de 09/09 contou esses casos como confirmados.
- **Falhas do modelo contadas como bug**: 12 FAILED anteriores eram `unwinding assertion` dentro do modelo de string ou asserts internos (`chr`, `int`, `list.pop`), e não a propriedade do bug.
- **Harness infiel**: `ip_real_21` usava dicionários de tamanhos diferentes, que o código real descarta antes do acesso; foi reescrito com mesmo tamanho e chaves diferentes.
- **Arquivos órfãos**: `ip_real_27`, `nm_real_26` e `tm_real_14` foram removidos de `bugs/` e `detection/`; eram as duplicatas que o commit `29a144a` tirou do GT e ainda entravam no scan.
- **Checagem final de mapeamento**: 120/120 entradas têm `detection/` e passam pela verificação de correspondência com o trecho pré-fix; nenhum caso foi removido por falha do ESBMC.

## Limitações do ESBMC-Python 8.5.0 medidas nesta auditoria

| Construção | Resultado | Efeito |
|---|---|---|
| `/` e `%` por zero (int e float) | `ZeroDivisionError` nativo | assert manual removido de `dz_real_02/03/04` |
| atributo de objeto em `None` | `dereference failure: NULL pointer` | detectado |
| atributo inexistente | `AttributeError` nativo | detectado (dentro de `in` precisa de leitura prévia) |
| método em `None`, `len(None)`, `int >= None`, `float("abc")`, chamar string | SUCCESSFUL | falso negativo |
| `isinstance` em variável `bool \| None`; `is None` em `Optional[str]` | FAILED indevido ou guard ignorado | falso positivo / falso negativo (issue aberta) |
| `None * int` | erro do Z3 | não verificável |
| `in` sobre `None` | exceção interna (`irep2_cast_error`) | não verificável |
| `getattr(obj, nome, default)`, `%` com argumento variável, `re.sub`, `re.findall` | não suportado | não verificável |
| `chr()` fora da faixa, `list.pop()` fora da faixa | assert interno, não exceção capturável | fix com `except` não verificável |
| `UnboundLocalError` | não modelado | valor arbitrário |
| `len(lst[0])` com `lst: list` sem tipo do elemento | tratado como `strlen` | resolvido anotando `list[list[int]]` |

## Prontos para baseline ESBMC (18)

| Caso | Projeto | Categorias (original → mantidas) | Evidência | Validação | ESBMC bugado | ESBMC corrigido | Motivo |
|---|---|---|---|---|---|---|---|
| `dz_real_02` | dateparser | division_by_zero, invalid_precondition → division_by_zero | [fix 7098f635](https://github.com/scrapinghub/dateparser/commit/7098f6359033294c605ce4f8cbdb89a1d6d42055) | fix mergeado upstream | FAILED ZeroDivisionError | SUCCESSFUL | Divisão real por num_substrings == 0; fix protege a divisão. invalid_precondition removida no elegível: não há evidência independente (o fix é um guard local, não validação de entrada). |
| `dz_real_03` | croniter | division_by_zero, invalid_precondition | [fix 7d319c51](https://github.com/kiorky/croniter/commit/7d319c510b863827073d42ecee787f3c5a046f7c) | fix mergeado upstream | FAILED ZeroDivisionError | SUCCESSFUL | Módulo por zero real; o fix valida a faixa e lança CroniterBadCronError, o que é evidência independente de precondição de entrada. |
| `dz_real_04` | nki-samples | division_by_zero, invalid_precondition | [fix d631c881](https://github.com/aws-neuron/nki-samples/commit/d631c8815da107186164d5bfd62c7ed0825eca90), [pr](https://github.com/aws-neuron/nki-samples/pull/126), [issue](https://github.com/aws-neuron/nki-samples/issues/125) | fix mergeado upstream | FAILED ZeroDivisionError | SUCCESSFUL | Divisão por step_size == 0; o fix (PR #126) acrescenta assert chunk_size >= 2 na entrada, evidência independente de precondição. |
| `ip_real_17` | scrapy | invalid_precondition, none_misuse → none_misuse | [BugsInPy scrapy/17](https://github.com/soarsmu/BugsInPy/tree/master/projects/scrapy/bugs/17), [fix 65c7c050](https://github.com/scrapy/scrapy/commit/65c7c05060fd2d1fc161d4904243d5e0b31e202b) | BugsInPy | FAILED TypeError | SUCCESSFUL | TypeError real: dict.get sem default devolve None para to_native_str. invalid_precondition removida no elegível: mesma evidência da none_misuse. |
| `ip_real_21` | sortedcontainers | invalid_precondition | [fix a04f4a68](https://github.com/grantjenks/python-sortedcontainers/commit/a04f4a68188fea6797fe3e5f16f388086e405e62) | fix mergeado upstream | FAILED KeyError | SUCCESSFUL | KeyError nativo com dicts de mesmo tamanho e chaves diferentes (harness corrigido: o anterior tinha tamanhos diferentes, que o código real curto-circuita). |
| `ip_real_28` | tornado | invalid_precondition | [BugsInPy tornado/14](https://github.com/soarsmu/BugsInPy/tree/master/projects/tornado/bugs/14), [fix 1d02ed60](https://github.com/tornadoweb/tornado/commit/1d02ed606f1c52636462633d009bdcbaac644331) | BugsInPy | FAILED RuntimeError | SUCCESSFUL | RuntimeError real lançado com condição invertida em entrada válida; fix inverte o teste. |
| `nm_real_12` | ansible | none_misuse | [BugsInPy ansible/10](https://github.com/soarsmu/BugsInPy/tree/master/projects/ansible/bugs/10), [fix a4b59d02](https://github.com/ansible/ansible/commit/a4b59d021368285490f7cda50c11ac4f7a8030b5) | BugsInPy | FAILED null_dereference | SUCCESSFUL | NULL dereference nativo ao acessar current_line.next.prev com next None; fix adiciona o guard. |
| `nm_real_21` | jmespath.py | none_misuse | [fix 8f14a303](https://github.com/jmespath/jmespath.py/commit/8f14a303bf9c953e1762c116c446542d68e1ab5d) | fix mergeado upstream | FAILED missing_return | SUCCESSFUL | Missing return nativo: caminho sem return devolve None; fix sempre retorna a lista. |
| `oob_real_04` | thefuck | out_of_bounds | [BugsInPy thefuck/22](https://github.com/soarsmu/BugsInPy/tree/master/projects/thefuck/bugs/22), [fix e2e8b6fc](https://github.com/nvbn/thefuck/commit/e2e8b6fc865452b4cfc1bed70e5b9b49807258ae) | BugsInPy | FAILED IndexError | SUCCESSFUL | IndexError nativo na operação real; o patch do commit elimina a falha com a mesma main. |
| `oob_real_05` | black | out_of_bounds | [BugsInPy black/17](https://github.com/soarsmu/BugsInPy/tree/master/projects/black/bugs/17), [fix 7fc6ce99](https://github.com/psf/black/commit/7fc6ce990669464f5172b63fafa3724f5f308be3) | BugsInPy | FAILED IndexError | SUCCESSFUL | IndexError nativo na operação real; o patch do commit elimina a falha com a mesma main. |
| `oob_real_09` | dateutil | out_of_bounds | [fix 6222418b](https://github.com/dateutil/dateutil/commit/6222418b231461f73ff97a84c6739fa33d2aca4b) | fix mergeado upstream | FAILED IndexError | SUCCESSFUL | IndexError nativo na operação real; o patch do commit elimina a falha com a mesma main. |
| `oob_real_10` | python-tabulate | out_of_bounds | [fix 20c6370d](https://github.com/astanin/python-tabulate/commit/20c6370d5da2dae89b305bfb6c7f12a0f8b7236c) | fix mergeado upstream | FAILED IndexError | SUCCESSFUL | IndexError nativo na operação real; o patch do commit elimina a falha com a mesma main. |
| `oob_real_11` | wcwidth | out_of_bounds | [fix 4c914039](https://github.com/jquast/wcwidth/commit/4c914039ba6c70ea2508420b591e3319683d5185) | fix mergeado upstream | FAILED IndexError | SUCCESSFUL | IndexError nativo na operação real; o patch do commit elimina a falha com a mesma main. |
| `oob_real_12` | natsort | out_of_bounds | [fix 441d1a74](https://github.com/SethMMorton/natsort/commit/441d1a74093ba3aaa48e4d88a0eb457bac0e05b3) | fix mergeado upstream | FAILED IndexError | SUCCESSFUL | IndexError nativo na operação real; o patch do commit elimina a falha com a mesma main. |
| `oob_real_13` | emoji | out_of_bounds | [fix 14a3a162](https://github.com/carpedm20/emoji/commit/14a3a1621673a9e98f8b8976dfc6d99038bbe267) | fix mergeado upstream | FAILED IndexError | SUCCESSFUL | IndexError nativo na operação real; o patch do commit elimina a falha com a mesma main. |
| `oob_real_14` | distro | out_of_bounds | [fix d3e91941](https://github.com/python-distro/distro/commit/d3e919410b5a759de554eb73c959e16f3fd481ad) | fix mergeado upstream | FAILED IndexError | SUCCESSFUL | IndexError nativo na operação real; o patch do commit elimina a falha com a mesma main. |
| `tm_real_10` | luigi | variable_misuse | [BugsInPy luigi/1](https://github.com/soarsmu/BugsInPy/tree/master/projects/luigi/bugs/1), [fix aec5dc2e](https://github.com/spotify/luigi/commit/aec5dc2ed8db53fc282a0bd24aabe59031b6d1ba) | BugsInPy | FAILED AttributeError | SUCCESSFUL | AttributeError nativo: método chamado no objeto errado; fix chama no coletor. |
| `tm_real_13` | scrapy | type_mismatch | [BugsInPy scrapy/22](https://github.com/soarsmu/BugsInPy/tree/master/projects/scrapy/bugs/22), [fix bb2cf7c0](https://github.com/scrapy/scrapy/commit/bb2cf7c0d7199fffe0aa100e5c8a51c6b4b82fc2) | BugsInPy | FAILED AttributeError | SUCCESSFUL | AttributeError nativo: .decode() em valor int; fix converte com str(). |

## Precisam de revisão (18)

| Caso | Projeto | Categorias (original → mantidas) | Evidência | Validação | ESBMC bugado | ESBMC corrigido | Motivo |
|---|---|---|---|---|---|---|---|
| `av_real_02` | tornado | assertion_violation | [BugsInPy tornado/1](https://github.com/soarsmu/BugsInPy/tree/master/projects/tornado/bugs/1), [fix 4677c54c](https://github.com/tornadoweb/tornado/commit/4677c54cc18bbfbdf0f4dadf11610fab6203fd63) | BugsInPy | FAILED assertion | sem fixed | Bug real dispara o assert do próprio código (AssertionError), mas o harness só testa flags booleanas; reescrever com o objeto real. |
| `ip_real_11` | fastapi | invalid_precondition | [BugsInPy fastapi/12](https://github.com/soarsmu/BugsInPy/tree/master/projects/fastapi/bugs/12), [fix d262f6e9](https://github.com/tiangolo/fastapi/commit/d262f6e9296993e528e2327f0a73f7bf5514e7c6) | BugsInPy | FAILED assertion | sem fixed | Exceção real (HTTPException) lançada com auto_error=False; harness diferencial, reescrever como ip_real_28. |
| `ip_real_19` | python-semver | invalid_precondition | [fix f332326e](https://github.com/python-semver/python-semver/commit/f332326e54a5582092b50c8fa113d11bbdf1a9e6) | fix mergeado upstream | FAILED assertion | sem fixed | Com patch == 0, filter(None) descarta a parte e o código lança IndexError; harness atual é diferencial. |
| `ip_real_32` | parse | invalid_precondition | [fix 4cf2b44b](https://github.com/r1chardj0n3s/parse/commit/4cf2b44bcb22c1d6a4d693694f7d5ecff5ff84d7) | fix mergeado upstream | FAILED assertion | sem fixed | hour == 24 faz datetime lançar ValueError no código real; harness codifica o contrato do datetime com assert. |
| `nm_real_04` | scrapy | none_misuse | [BugsInPy scrapy/1](https://github.com/soarsmu/BugsInPy/tree/master/projects/scrapy/bugs/1), [fix 9d9dea0d](https://github.com/scrapy/scrapy/commit/9d9dea0d69709ef0f7aef67ddba1bd7bda25d273) | BugsInPy | FAILED assertion | sem fixed | Bug real lança exceção, mas o harness só testa uma flag booleana; precisa ser reescrito com a operação real e medido no ESBMC. |
| `nm_real_07` | tornado | none_misuse | [BugsInPy tornado/9](https://github.com/soarsmu/BugsInPy/tree/master/projects/tornado/bugs/9), [fix 86cc31f5](https://github.com/tornadoweb/tornado/commit/86cc31f52992fb9d11f92de6fd5496842fea2265) | BugsInPy | FAILED assertion | sem fixed | Bug real lança exceção, mas o harness só testa uma flag booleana; precisa ser reescrito com a operação real e medido no ESBMC. |
| `nm_real_08` | sanic | none_misuse | [BugsInPy sanic/4](https://github.com/soarsmu/BugsInPy/tree/master/projects/sanic/bugs/4), [fix e81a8ce0](https://github.com/sanic-org/sanic/commit/e81a8ce07329e95d3d0899b1d774f21759c28e0e) | BugsInPy | FAILED AttributeError | SUCCESSFUL | Par confirmado (AttributeError / SUCCESSFUL), mas o bug é atributo inexistente, não None; categoria none_misuse questionável. Leitura do atributo foi separada do `in` para contornar falso negativo do ESBMC. |
| `nm_real_13` | tornado | none_misuse, invalid_precondition | [BugsInPy tornado/3](https://github.com/soarsmu/BugsInPy/tree/master/projects/tornado/bugs/3), [fix aa622e72](https://github.com/tornadoweb/tornado/commit/aa622e724f80e0f7fcee369f75d69d1db13d72f2) | BugsInPy | FAILED assertion | sem fixed | Bug real lança exceção, mas o harness só testa uma flag booleana; precisa ser reescrito com a operação real e medido no ESBMC. |
| `nm_real_17` | python-tabulate | none_misuse | [fix 3b356a8b](https://github.com/astanin/python-tabulate/commit/3b356a8beca036fac7fd5ede951062c580b4fca1) | fix mergeado upstream | FAILED assertion | sem fixed | Bug real lança exceção, mas o harness só testa uma flag booleana; precisa ser reescrito com a operação real e medido no ESBMC. |
| `nm_real_22` | python-dotenv | none_misuse | [fix bc439674](https://github.com/theskumar/python-dotenv/commit/bc439674fe718bcff3039e3239602de3c23e42e4) | fix mergeado upstream | FAILED assertion | sem fixed | Bug real lança exceção, mas o harness só testa uma flag booleana; precisa ser reescrito com a operação real e medido no ESBMC. |
| `oob_real_01` | thefuck | out_of_bounds | [BugsInPy thefuck/1](https://github.com/soarsmu/BugsInPy/tree/master/projects/thefuck/bugs/1), [fix 444908ce](https://github.com/nvbn/thefuck/commit/444908ce1c17767ef4aaf9e0b4950497914f7f63) | BugsInPy | FAILED IndexError | sem fixed | IndexError nativo, mas a causa é a regex de re.findall, que o ESBMC não modela; o fix muda só a regex e não é representável. |
| `oob_real_06` | cookiecutter | out_of_bounds | [fix cc92e3cc](https://github.com/cookiecutter/cookiecutter/commit/cc92e3cc00a3d2acd1ef6d38cf5731478dade3cb), PyBugHive #1513 | fix mergeado upstream | FAILED assertion | sem fixed | KeyError real em default[k], mas o harness é `assert default_has_key`; reescrever com o merge recursivo. Além disso, o detection é uma reconstrução sintética (com main própria), não o código real de cookiecutter/config.py. |
| `oob_real_15` | youtube-dl | out_of_bounds | [BugsInPy youtube-dl/6](https://github.com/soarsmu/BugsInPy/tree/master/projects/youtube-dl/bugs/6), [fix d631d5f9](https://github.com/ytdl-org/youtube-dl/commit/d631d5f9f27f93767226192e4288990413fa9dbd) | BugsInPy | FAILED KeyError | SUCCESSFUL | Par buggy/fixed confirmado (KeyError / SUCCESSFUL), mas out_of_bounds é definido no pipeline como IndexError em subscrito; decidir se KeyError conta. |
| `tm_real_01` | spacy | type_mismatch | [BugsInPy spacy/4](https://github.com/soarsmu/BugsInPy/tree/master/projects/spacy/bugs/4), [fix 9fa9d7f2](https://github.com/explosion/spaCy/commit/9fa9d7f2cb52ce6a70c264d4e57c7f190d7686bf) | BugsInPy | FAILED model_check | SUCCESSFUL | Fixed confirma, mas o sintoma é ValueError de int('_') (checagem interna do modelo), não type_mismatch. |
| `tm_real_08` | python-tabulate | type_mismatch, none_misuse | [fix 41a6db29](https://github.com/astanin/python-tabulate/commit/41a6db29b666f0c0eedec40efb5bc3af4f411a56) | fix mergeado upstream | FAILED assertion | sem fixed | Bug real lança exceção, mas o harness só testa uma flag booleana; precisa ser reescrito com a operação real e medido no ESBMC. |
| `vm_real_03` | spacy | variable_misuse | [BugsInPy spacy/5](https://github.com/soarsmu/BugsInPy/tree/master/projects/spacy/bugs/5), [fix 3bd15055](https://github.com/explosion/spaCy/commit/3bd15055ce74b04dcaf3b9abe2adeb01fb595776) | BugsInPy | FAILED assertion | sem fixed | Bug real lança exceção, mas o harness só testa uma flag booleana; precisa ser reescrito com a operação real e medido no ESBMC. |
| `vm_real_06` | scrapy | variable_misuse | [BugsInPy scrapy/32](https://github.com/soarsmu/BugsInPy/tree/master/projects/scrapy/bugs/32), [fix aa6a7270](https://github.com/scrapy/scrapy/commit/aa6a72707daabfb6217f52e4774f2ff038f83dcc) | BugsInPy | FAILED assertion | sem fixed | Bug real lança exceção, mas o harness só testa uma flag booleana; precisa ser reescrito com a operação real e medido no ESBMC. |
| `vm_real_08` | PySnooper | variable_misuse | [BugsInPy PySnooper/3](https://github.com/soarsmu/BugsInPy/tree/master/projects/PySnooper/bugs/3), [fix 15555ed7](https://github.com/cool-RR/PySnooper/commit/15555ed760000b049aff8fecc79d29339c1224c3) | BugsInPy | FAILED assertion | sem fixed | Bug real lança exceção, mas o harness só testa uma flag booleana; precisa ser reescrito com a operação real e medido no ESBMC. |

## Não suportados pelo ESBMC 8.5.0 (23)

| Caso | Projeto | Categorias (original → mantidas) | Evidência | Validação | ESBMC bugado | ESBMC corrigido | Motivo |
|---|---|---|---|---|---|---|---|
| `av_real_01` | youtube-dl | assertion_violation | [BugsInPy youtube-dl/17](https://github.com/soarsmu/BugsInPy/tree/master/projects/youtube-dl/bugs/17), [fix 5b232f46](https://github.com/ytdl-org/youtube-dl/commit/5b232f46dcbdc805507c02edd4fd598f31d544d5) | BugsInPy | FAILED assertion | FAILED assertion | ESBMC acusa isinstance(param, bool) mesmo com param=True (falso positivo em variável bool\|None); o fix também falha. |
| `ip_real_07` | youtube-dl | invalid_precondition | [BugsInPy youtube-dl/28](https://github.com/soarsmu/BugsInPy/tree/master/projects/youtube-dl/bugs/28), [fix 7aefc49c](https://github.com/ytdl-org/youtube-dl/commit/7aefc49c4013efb5056b2c1237e22c52cb5d3c49) | BugsInPy | FAILED model_check | sem fixed | chr() fora da faixa vira assert interno do modelo, não ValueError capturável; o modelo também rejeita surrogates que o CPython aceita. |
| `nm_real_01` | httpie | none_misuse | [BugsInPy httpie/3](https://github.com/soarsmu/BugsInPy/tree/master/projects/httpie/bugs/3), [fix 58988793](https://github.com/httpie/httpie/commit/589887939507ff26d36ec74bd2c045819cfa3d56) | BugsInPy | FAILED assertion | sem fixed | Chamada de método em None dá SUCCESSFUL no ESBMC 8.5.0 (falso negativo medido). |
| `nm_real_02` | tqdm | none_misuse | [BugsInPy tqdm/4](https://github.com/soarsmu/BugsInPy/tree/master/projects/tqdm/bugs/4), [fix 964dee63](https://github.com/tqdm/tqdm/commit/964dee631d0ed30e2f799b42fc58ba5e73795a08) | BugsInPy | FAILED assertion | sem fixed | None * int derruba o Z3 ('ast is not an expression'). |
| `nm_real_03` | youtube-dl | none_misuse | [BugsInPy youtube-dl/39](https://github.com/soarsmu/BugsInPy/tree/master/projects/youtube-dl/bugs/39), [fix a020a0dc](https://github.com/ytdl-org/youtube-dl/commit/a020a0dc20ced6468ec46214c394f6f360735b1d) | BugsInPy | timeout | timeout | Bugado confirma, mas o fixed não termina em 850s (modelo de string). |
| `nm_real_05` | scrapy | none_misuse | [BugsInPy scrapy/5](https://github.com/soarsmu/BugsInPy/tree/master/projects/scrapy/bugs/5), [fix acd2b8d4](https://github.com/scrapy/scrapy/commit/acd2b8d43b5ebec7ffd364b6f335427041a0b98d) | BugsInPy | FAILED assertion | sem fixed | Depende de urllib.parse / os.path, não modelados. |
| `nm_real_09` | tqdm | none_misuse | [BugsInPy tqdm/6](https://github.com/soarsmu/BugsInPy/tree/master/projects/tqdm/bugs/6), [fix 6dad2e89](https://github.com/tqdm/tqdm/commit/6dad2e89019317e875c46d5a3a82a811ad6de2f9) | BugsInPy | FAILED assertion | sem fixed | O fix usa getattr(obj, nome, default), que o ESBMC não suporta. |
| `nm_real_10` | luigi | none_misuse | [BugsInPy luigi/4](https://github.com/soarsmu/BugsInPy/tree/master/projects/luigi/bugs/4), [fix 8501e5db](https://github.com/spotify/luigi/commit/8501e5dbb8d3040453a89bb0d3562526086d51e5) | BugsInPy | FAILED assertion | sem fixed | len(None) dá SUCCESSFUL no ESBMC 8.5.0 (falso negativo medido). |
| `nm_real_11` | scrapy | none_misuse | [BugsInPy scrapy/2](https://github.com/soarsmu/BugsInPy/tree/master/projects/scrapy/bugs/2), [fix 439a3e59](https://github.com/scrapy/scrapy/commit/439a3e59b8e858441f8d97dbc32f398db392330d) | BugsInPy | FAILED assertion | sem fixed | Comparação int >= None dá SUCCESSFUL no ESBMC 8.5.0 (falso negativo medido). |
| `nm_real_14` | scrapy | none_misuse | [BugsInPy scrapy/29](https://github.com/soarsmu/BugsInPy/tree/master/projects/scrapy/bugs/29), [fix 8d45b3c4](https://github.com/scrapy/scrapy/commit/8d45b3c4810cb5304ba1193b45697a0df1157326) | BugsInPy | SUCCESSFUL | SUCCESSFUL | CPython lança TypeError, mas o ESBMC dá SUCCESSFUL no bugado: falso negativo com Optional[str] (issue aberta pela autora). |
| `nm_real_18` | tenacity | none_misuse | [fix 213446e8](https://github.com/jd/tenacity/commit/213446e8f5f73ca0d20e22ec8ee38b1f75a45434) | fix mergeado upstream | FAILED assertion | sem fixed | Formatação % com argumento não constante não é suportada. |
| `nm_real_19` | voluptuous | none_misuse | [fix 3c5ea7f3](https://github.com/alecthomas/voluptuous/commit/3c5ea7f329f1b346b39a30fbf79b23fe42478065) | fix mergeado upstream | FAILED assertion | sem fixed | Depende de urllib.parse / os.path, não modelados. |
| `nm_real_20` | inflect | none_misuse | [fix f799157f](https://github.com/jaraco/inflect/commit/f799157f68d5e7e1c59b5f8ecd51530c4b6e20a5) | fix mergeado upstream | FAILED null_dereference | FAILED null_dereference | Fixed continua acusando NULL deref depois de `if decimal is None: return`: falso positivo com Optional[str]. |
| `nm_real_23` | python-markdown2 | none_misuse | [fix 3c53c6ae](https://github.com/trentm/python-markdown2/commit/3c53c6aed381ac284d3fb25945ce709a99c83195) | fix mergeado upstream | FAILED assertion | sem fixed | `in` sobre None derruba o ESBMC (irep2_cast_error). |
| `nm_real_24` | black | none_misuse | [BugsInPy black/1](https://github.com/soarsmu/BugsInPy/tree/master/projects/black/bugs/1), [fix c0a7582e](https://github.com/psf/black/commit/c0a7582e3d4cc8bec3b7f5a6c52b36880dcb57d7) | BugsInPy | FAILED assertion | sem fixed | Chamada de método em None dá SUCCESSFUL no ESBMC 8.5.0 (falso negativo medido). |
| `nm_real_25` | tornado | none_misuse | [BugsInPy tornado/13](https://github.com/soarsmu/BugsInPy/tree/master/projects/tornado/bugs/13), [fix 34903f9e](https://github.com/tornadoweb/tornado/commit/34903f9e1a99441b2729bbe6f1d65d46cf352ea7) | BugsInPy | FAILED assertion | sem fixed | O fix usa getattr(obj, nome, default), que o ESBMC não suporta. |
| `oob_real_02` | thefuck | out_of_bounds | [BugsInPy thefuck/21](https://github.com/soarsmu/BugsInPy/tree/master/projects/thefuck/bugs/21), [fix 213791d3](https://github.com/nvbn/thefuck/commit/213791d3c2af379ffa37a140735998736b41912e) | BugsInPy | FAILED IndexError | timeout | Bugado confirma, mas o fixed não termina em 850s (modelo de string). |
| `oob_real_03` | thefuck | out_of_bounds | [BugsInPy thefuck/9](https://github.com/soarsmu/BugsInPy/tree/master/projects/thefuck/bugs/9), [fix feb36ede](https://github.com/nvbn/thefuck/commit/feb36ede5c518fdc3b6eddf945b2d8b1e2294d15) | BugsInPy | FAILED model_check | FAILED model_check | list.pop fora da faixa vira assert interno (list.c), não IndexError capturável pelo except do fix. |
| `tm_real_04` | youtube-dl | type_mismatch | [BugsInPy youtube-dl/11](https://github.com/soarsmu/BugsInPy/tree/master/projects/youtube-dl/bugs/11), [fix 348c6bf1](https://github.com/ytdl-org/youtube-dl/commit/348c6bf1c1a00eec323d6e21ff7b9b12699afe04) | BugsInPy | FAILED assertion | sem fixed | Depende de re.sub, não suportado pelo modelo de re. |
| `tm_real_09` | python-tabulate | type_mismatch | [fix c59a5ff3](https://github.com/astanin/python-tabulate/commit/c59a5ff3ef898464df25f8bb97a611c9c4ff5013) | fix mergeado upstream | FAILED assertion | sem fixed | float('abc') dá SUCCESSFUL no ESBMC 8.5.0 (falso negativo medido). |
| `tm_real_12` | luigi | type_mismatch | [BugsInPy luigi/25](https://github.com/soarsmu/BugsInPy/tree/master/projects/luigi/bugs/25), [fix 040bbc9e](https://github.com/spotify/luigi/commit/040bbc9ef8d1703b64d13c60f271fded63e13601) | BugsInPy | FAILED assertion | sem fixed | Chamar uma string (propriedade chamada como método) dá SUCCESSFUL (falso negativo medido). |
| `vm_real_02` | schema | variable_misuse | [fix 92fad7dc](https://github.com/keleshev/schema/commit/92fad7dc00825c60e8c1c0862f818c54165b3558) | fix mergeado upstream | FAILED assertion | sem fixed | UnboundLocalError não é modelado: variável não ligada vira valor arbitrário. |
| `vm_real_05` | luigi | variable_misuse | [BugsInPy luigi/13](https://github.com/soarsmu/BugsInPy/tree/master/projects/luigi/bugs/13), [fix a8e64fe7](https://github.com/spotify/luigi/commit/a8e64fe7f83d69702166a44c7e8cb9470ff31040) | BugsInPy | erro | SUCCESSFUL | Frontend recusa self.fs.mkdir(): 'Could not resolve type of receiver'. |

## Ainda não prontos para baseline (61)

| Caso | Projeto | Categorias (original → mantidas) | Evidência | Validação | ESBMC bugado | ESBMC corrigido | Motivo |
|---|---|---|---|---|---|---|---|
| `av_real_03` | pandas | assertion_violation | [BugsInPy pandas/3](https://github.com/soarsmu/BugsInPy/tree/master/projects/pandas/bugs/3), [fix d3a6a3a5](https://github.com/pandas-dev/pandas/commit/d3a6a3a58e1a6eb68b8b8399ff252b8f4501950e) | BugsInPy | FAILED assertion | sem fixed | O fix só troca AssertionError por TypeError: o código corrigido continua lançando exceção na mesma entrada. |
| `av_real_04` | luigi | incorrect_result | [BugsInPy luigi/9](https://github.com/soarsmu/BugsInPy/tree/master/projects/luigi/bugs/9), [fix b7115974](https://github.com/spotify/luigi/commit/b7115974c3deadf77113686248b39567cb67e38f) | BugsInPy | FAILED assertion | sem fixed | Categoria incorrect_result não é formal. |
| `av_real_05` | tqdm | none_misuse | [BugsInPy tqdm/5](https://github.com/soarsmu/BugsInPy/tree/master/projects/tqdm/bugs/5), [fix 4f340697](https://github.com/tqdm/tqdm/commit/4f340697af69b71850aad496387c9c5aa1904136) | BugsInPy | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `av_real_06` | thefuck | assertion_violation | [BugsInPy thefuck/31](https://github.com/soarsmu/BugsInPy/tree/master/projects/thefuck/bugs/31), [fix 12853033](https://github.com/nvbn/thefuck/commit/1285303363bc420bd7606bd5f808e3f2b4f0e83f) | BugsInPy | timeout | sem fixed | Resultado de string errado (incorrect_result de fato) e bugado não termina no ESBMC. |
| `av_real_07` | thefuck | assertion_violation | [BugsInPy thefuck/32](https://github.com/soarsmu/BugsInPy/tree/master/projects/thefuck/bugs/32), [fix 25cc98a2](https://github.com/nvbn/thefuck/commit/25cc98a21a3450a046caf418f08713c82a290805) | BugsInPy | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `av_real_08` | thefuck | assertion_violation | [BugsInPy thefuck/29](https://github.com/soarsmu/BugsInPy/tree/master/projects/thefuck/bugs/29), [fix 88831c42](https://github.com/nvbn/thefuck/commit/88831c424f569e6a55fc98883d3eeecc7d425b18) | BugsInPy | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `av_real_09` | matplotlib | incorrect_result | [BugsInPy matplotlib/24](https://github.com/soarsmu/BugsInPy/tree/master/projects/matplotlib/bugs/24), [fix 407a9fe7](https://github.com/matplotlib/matplotlib/commit/407a9fe71a4c0a8ba4914b8f54f21d32d6dd2d74) | BugsInPy | FAILED assertion | sem fixed | Categoria incorrect_result não é formal. |
| `av_real_10` | black | incorrect_result | [BugsInPy black/10](https://github.com/soarsmu/BugsInPy/tree/master/projects/black/bugs/10), [fix 66aa6762](https://github.com/psf/black/commit/66aa676278948368dff251dffd58c850cb8b889e) | BugsInPy | FAILED assertion | sem fixed | Categoria incorrect_result não é formal. |
| `av_real_11` | tornado | assertion_violation | [BugsInPy tornado/11](https://github.com/soarsmu/BugsInPy/tree/master/projects/tornado/bugs/11), [fix 1131c9b5](https://github.com/tornadoweb/tornado/commit/1131c9b50a6a4c0868d0d6fa5e0be077cf8fd1ca) | BugsInPy | FAILED unwinding_assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `av_real_12` | thefuck | assertion_violation | [BugsInPy thefuck/7](https://github.com/soarsmu/BugsInPy/tree/master/projects/thefuck/bugs/7), [fix 75d2c439](https://github.com/nvbn/thefuck/commit/75d2c43997ca703150cbdb4c46ed7b2e2e71fd11) | BugsInPy | FAILED unwinding_assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `av_real_13` | thefuck | assertion_violation | [BugsInPy thefuck/5](https://github.com/soarsmu/BugsInPy/tree/master/projects/thefuck/bugs/5), [fix c205683a](https://github.com/nvbn/thefuck/commit/c205683a8df8a57e2db1e9816a5a7ce3255b08fc) | BugsInPy | FAILED unwinding_assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `av_real_14` | thefuck | assertion_violation | [BugsInPy thefuck/27](https://github.com/soarsmu/BugsInPy/tree/master/projects/thefuck/bugs/27), [fix 1becd92b](https://github.com/nvbn/thefuck/commit/1becd92b126a368d6e7d93aa8eea209414ce4aa2) | BugsInPy | timeout | sem fixed | Resultado de string errado (incorrect_result de fato) e bugado não termina no ESBMC. |
| `av_real_15` | scrapy | assertion_violation | [BugsInPy scrapy/11](https://github.com/soarsmu/BugsInPy/tree/master/projects/scrapy/bugs/11), [fix 9de6f1ca](https://github.com/scrapy/scrapy/commit/9de6f1ca757b7f200d15e94840c9d431cf202276) | BugsInPy | FAILED unwinding_assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `av_real_17` | youtube-dl | assertion_violation, none_misuse | [BugsInPy youtube-dl/29](https://github.com/soarsmu/BugsInPy/tree/master/projects/youtube-dl/bugs/29), [fix 6a750402](https://github.com/ytdl-org/youtube-dl/commit/6a750402787dfc1f39a9ad347f2d78ae1c94c52c) | BugsInPy | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `av_real_19` | matplotlib | incorrect_result | [BugsInPy matplotlib/24](https://github.com/soarsmu/BugsInPy/tree/master/projects/matplotlib/bugs/24), [fix 407a9fe7](https://github.com/matplotlib/matplotlib/commit/407a9fe71a4c0a8ba4914b8f54f21d32d6dd2d74) | BugsInPy | FAILED assertion | sem fixed | Categoria incorrect_result não é formal. |
| `av_real_20` | black | incorrect_result | [BugsInPy black/10](https://github.com/soarsmu/BugsInPy/tree/master/projects/black/bugs/10), [fix 66aa6762](https://github.com/psf/black/commit/66aa676278948368dff251dffd58c850cb8b889e) | BugsInPy | FAILED assertion | sem fixed | Categoria incorrect_result não é formal. |
| `av_real_21` | youtube-dl | assertion_violation | [BugsInPy youtube-dl/18](https://github.com/soarsmu/BugsInPy/tree/master/projects/youtube-dl/bugs/18), [fix 0396806f](https://github.com/ytdl-org/youtube-dl/commit/0396806f671e5828c2abdeb8048acf8b654507b6) | BugsInPy | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `dz_real_01` | matplotlib | division_by_zero | [BugsInPy matplotlib/30](https://github.com/soarsmu/BugsInPy/tree/master/projects/matplotlib/bugs/30), [fix d4de838f](https://github.com/matplotlib/matplotlib/commit/d4de838fe7b38abb02f061540fd93962cc063fc4) | BugsInPy | FAILED assertion | sem fixed | O patch trata N == 1; o harness modela x duplicado (que o fix não cobre) e a divisão NumPy real dá nan, não exceção. |
| `io_real_01` | matplotlib | integer_overflow | [BugsInPy matplotlib/16/17](https://github.com/soarsmu/BugsInPy/tree/master/projects/matplotlib/bugs/16), [fix 5d99e151](https://github.com/matplotlib/matplotlib/commit/5d99e151be80bcb0b3b6d081fd3038330f573d94) | BugsInPy | FAILED assertion | sem fixed | Overflow depende de int8 do NumPy, codificado à mão no harness. |
| `io_real_02` | consensus-specs | integer_overflow | [fix f82a3af9](https://github.com/ethereum/consensus-specs/commit/f82a3af97852867e8922b57ccc6815f9659c209a), [pr](https://github.com/ethereum/consensus-specs/pull/3600) | fix mergeado upstream | FAILED assertion | sem fixed | Overflow depende do uint64 da remerkleable, reduzido a 255 e codificado com assert. |
| `ip_real_01` | scrapy | invalid_precondition | [BugsInPy scrapy/37](https://github.com/soarsmu/BugsInPy/tree/master/projects/scrapy/bugs/37), [fix f701f5b0](https://github.com/scrapy/scrapy/commit/f701f5b0db10faef08e4ed9a21b98fd72f9cfc9a) | BugsInPy | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `ip_real_03` | scrapy | invalid_precondition | [BugsInPy scrapy/12](https://github.com/soarsmu/BugsInPy/tree/master/projects/scrapy/bugs/12), [fix 2c9a38d1](https://github.com/scrapy/scrapy/commit/2c9a38d1f54a12c33d7c9a19e021c840c4a32dee) | BugsInPy | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `ip_real_04` | tornado | invalid_precondition | [BugsInPy tornado/2](https://github.com/soarsmu/BugsInPy/tree/master/projects/tornado/bugs/2), [fix 4f486a4a](https://github.com/tornadoweb/tornado/commit/4f486a4aec746e9d66441600ee3b0743228b061c) | BugsInPy | FAILED unwinding_assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `ip_real_05` | ansible | invalid_precondition | [BugsInPy ansible/2](https://github.com/soarsmu/BugsInPy/tree/master/projects/ansible/bugs/2), [fix 5b9418c0](https://github.com/ansible/ansible/commit/5b9418c06ca6d51507468124250bb58046886be6) | BugsInPy | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. Além disso, o detection não reproduz o trecho bugado do commit. |
| `ip_real_06` | pandas | invalid_precondition | [BugsInPy pandas/38](https://github.com/soarsmu/BugsInPy/tree/master/projects/pandas/bugs/38), [fix e7ee418f](https://github.com/pandas-dev/pandas/commit/e7ee418fa7a519225203fef23481c5fa35834dc3) | BugsInPy | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `ip_real_08` | sanic | incorrect_result | [BugsInPy sanic/3](https://github.com/soarsmu/BugsInPy/tree/master/projects/sanic/bugs/3), [fix 861e8734](https://github.com/sanic-org/sanic/commit/861e87347a2d373d6ffa387965a6887c83af632c) | BugsInPy | FAILED assertion | sem fixed | Categoria incorrect_result não é formal. |
| `ip_real_09` | ansible | incorrect_result | [BugsInPy ansible/7](https://github.com/soarsmu/BugsInPy/tree/master/projects/ansible/bugs/7), [fix 4ec14372](https://github.com/ansible/ansible/commit/4ec1437212b2fb3c313e44ed5a76b105f2151622) | BugsInPy | FAILED assertion | sem fixed | Categoria incorrect_result não é formal. |
| `ip_real_10` | scrapy | invalid_precondition | [BugsInPy scrapy/35](https://github.com/soarsmu/BugsInPy/tree/master/projects/scrapy/bugs/35), [fix c3d3a949](https://github.com/scrapy/scrapy/commit/c3d3a9491412d2a91b0927a05908593dcd329e4a) | BugsInPy | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `ip_real_12` | ansible | incorrect_result | [BugsInPy ansible/15](https://github.com/soarsmu/BugsInPy/tree/master/projects/ansible/bugs/15), [fix 68de1825](https://github.com/ansible/ansible/commit/68de182555b185737353e780882159a3d213908c) | BugsInPy | FAILED assertion | sem fixed | Categoria incorrect_result não é formal. |
| `ip_real_13` | tornado | invalid_precondition | [BugsInPy tornado/4](https://github.com/soarsmu/BugsInPy/tree/master/projects/tornado/bugs/4), [fix db529031](https://github.com/tornadoweb/tornado/commit/db529031a1e1a6e951826aba0b7d0b18f05cd4c7) | BugsInPy | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `ip_real_14` | keras | invalid_precondition | [BugsInPy keras/28](https://github.com/soarsmu/BugsInPy/tree/master/projects/keras/bugs/28), [fix 5422fdd3](https://github.com/keras-team/keras/commit/5422fdd38baad36730cb6aeb946e17eeae6a551c) | BugsInPy | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `ip_real_15` | black | invalid_precondition | [BugsInPy black/4](https://github.com/soarsmu/BugsInPy/tree/master/projects/black/bugs/4), [fix c7495b9a](https://github.com/psf/black/commit/c7495b9aa098ef7a358fc74556359d21c6a4ba11) | BugsInPy | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. Além disso, o detection não reproduz o trecho bugado do commit. |
| `ip_real_16` | pandas | invalid_precondition, none_misuse | [BugsInPy pandas/86](https://github.com/soarsmu/BugsInPy/tree/master/projects/pandas/bugs/86), [fix f792d8c5](https://github.com/pandas-dev/pandas/commit/f792d8c50ee456aa8aa2ae406d8e6b8843f45614) | BugsInPy | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `ip_real_18` | croniter | invalid_precondition | [fix f3299642](https://github.com/kiorky/croniter/commit/f329964223eeb29e7788b1a9d615b525148fec96) | fix mergeado upstream | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `ip_real_20` | watchdog | incorrect_result | [fix dc345245](https://github.com/gorakhargosh/watchdog/commit/dc345245a3c82afc4a0cdd197068fb5a32545033) | fix mergeado upstream | FAILED unwinding_assertion | sem fixed | Categoria incorrect_result não é formal. |
| `ip_real_22` | thefuck | invalid_precondition | [BugsInPy thefuck/18](https://github.com/soarsmu/BugsInPy/tree/master/projects/thefuck/bugs/18), [fix c3b1ba76](https://github.com/nvbn/thefuck/commit/c3b1ba763708b8faaaf55717c436c4cd4c57a7ea) | BugsInPy | FAILED unwinding_assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `ip_real_23` | luigi | invalid_precondition | [BugsInPy luigi/20](https://github.com/soarsmu/BugsInPy/tree/master/projects/luigi/bugs/20), [fix c3d685e2](https://github.com/spotify/luigi/commit/c3d685e2b03369aab6f4d86ed1c95169c1c2c217) | BugsInPy | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `ip_real_24` | luigi | invalid_precondition | [BugsInPy luigi/31](https://github.com/soarsmu/BugsInPy/tree/master/projects/luigi/bugs/31), [fix c0857e9e](https://github.com/spotify/luigi/commit/c0857e9e06012b696017e0a353ae74f4f621d066) | BugsInPy | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `ip_real_25` | luigi | invalid_precondition | [BugsInPy luigi/15](https://github.com/soarsmu/BugsInPy/tree/master/projects/luigi/bugs/15), [fix 736c0f13](https://github.com/spotify/luigi/commit/736c0f1352463c20ece84f2f651bcd37fd2b88ae) | BugsInPy | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `ip_real_26` | luigi | invalid_precondition | [BugsInPy luigi/7](https://github.com/soarsmu/BugsInPy/tree/master/projects/luigi/bugs/7), [fix daf9ce99](https://github.com/spotify/luigi/commit/daf9ce99a3a7ed4227d1564570c5fce8848357e5) | BugsInPy | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `ip_real_31` | matplotlib | incorrect_result | [BugsInPy matplotlib/26](https://github.com/soarsmu/BugsInPy/tree/master/projects/matplotlib/bugs/26), [fix 557375ff](https://github.com/matplotlib/matplotlib/commit/557375ff91f64c1b827f6014da2d369513a69316) | BugsInPy | FAILED assertion | sem fixed | Categoria incorrect_result não é formal. |
| `ip_real_33` | send2trash | invalid_precondition | [fix 4b9bc4bc](https://github.com/arsenetar/send2trash/commit/4b9bc4bc31c0269d92ed0373824e4e3dca1c3fa4) | fix mergeado upstream | FAILED assertion | sem fixed | Falha depende da API de lixeira do Windows, não isolável. |
| `ip_real_34` | cookiecutter | invalid_precondition | [BugsInPy cookiecutter/2](https://github.com/soarsmu/BugsInPy/tree/master/projects/cookiecutter/bugs/2), [fix 90434ff4](https://github.com/cookiecutter/cookiecutter/commit/90434ff4ea4477941444f1e83313beb414838535) | BugsInPy | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `ir_real_01` | esbmc | incorrect_result | [fix d432ae5d](https://github.com/esbmc/esbmc/commit/d432ae5ddf5ece697b51610aa9f677412ef7aee1) | fix mergeado upstream | FAILED unwinding_assertion | sem fixed | Categoria incorrect_result não é formal. |
| `ir_real_02` | esbmc | incorrect_result | [fix 2e99e3c8](https://github.com/esbmc/esbmc/commit/2e99e3c8bdaf8e1bfbdcf923ee1e6253f00fc3d6) | fix mergeado upstream | FAILED assertion | sem fixed | Categoria incorrect_result não é formal. |
| `ir_real_03` | esbmc | incorrect_result | [fix d8ad5349](https://github.com/esbmc/esbmc/commit/d8ad5349c15f6a13f6ff05b08d62c1bb2f0d88ff) | fix mergeado upstream | FAILED assertion | sem fixed | Categoria incorrect_result não é formal. |
| `ir_real_05` | shortuuid | incorrect_result | [fix 496cddf1](https://github.com/skorokithakis/shortuuid/commit/496cddf186b6598ebebe7be5c99c0715e7fc5ab5) | fix mergeado upstream | FAILED assertion | sem fixed | Categoria incorrect_result não é formal. |
| `nm_real_06` | scrapy | none_misuse | [BugsInPy scrapy/36](https://github.com/soarsmu/BugsInPy/tree/master/projects/scrapy/bugs/36), [fix cf9be534](https://github.com/scrapy/scrapy/commit/cf9be5344a89dd8e14f8241ec69de9c984ec1e05) | BugsInPy | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `nm_real_15` | fastapi | incorrect_result | [BugsInPy fastapi/13](https://github.com/soarsmu/BugsInPy/tree/master/projects/fastapi/bugs/13), [fix c8df3ae5](https://github.com/tiangolo/fastapi/commit/c8df3ae57c57e119d115dd3c1f44efa78de1022a) | BugsInPy | FAILED assertion | sem fixed | Categoria incorrect_result não é formal. |
| `nm_real_16` | matplotlib | incorrect_result | [BugsInPy matplotlib/5](https://github.com/soarsmu/BugsInPy/tree/master/projects/matplotlib/bugs/5), [fix 66289c4f](https://github.com/matplotlib/matplotlib/commit/66289c4f1895b8c65ca92a03d92f6b1cfa552267) | BugsInPy | FAILED assertion | sem fixed | Categoria incorrect_result não é formal. |
| `oob_real_16` | boltons | out_of_bounds, invalid_precondition | [fix d0a284fc](https://github.com/mahmoud/boltons/commit/d0a284fc7ef1aebceb54798600d73be4eeb76ed8) | fix mergeado upstream | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `tm_real_02` | luigi | type_mismatch | [BugsInPy luigi/28](https://github.com/soarsmu/BugsInPy/tree/master/projects/luigi/bugs/28), [fix e2be9712](https://github.com/spotify/luigi/commit/e2be971226c34a193d7029c51206e488b6a037cd) | BugsInPy | FAILED unwinding_assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `tm_real_03` | youtube-dl | type_mismatch | [BugsInPy youtube-dl/1](https://github.com/soarsmu/BugsInPy/tree/master/projects/youtube-dl/bugs/1), [fix 1cc47c66](https://github.com/ytdl-org/youtube-dl/commit/1cc47c667419e0eadc0a6989256ab7b276852adf) | BugsInPy | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `tm_real_05` | scrapy | type_mismatch | [BugsInPy scrapy/9](https://github.com/soarsmu/BugsInPy/tree/master/projects/scrapy/bugs/9), [fix ff3aec66](https://github.com/scrapy/scrapy/commit/ff3aec661355a82a6f77355a95e1f391fa586c2b) | BugsInPy | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `tm_real_06` | scrapy | type_mismatch | [BugsInPy scrapy/4](https://github.com/soarsmu/BugsInPy/tree/master/projects/scrapy/bugs/4), [fix 16dad817](https://github.com/scrapy/scrapy/commit/16dad81715d3970149c0cf7a318e73a0d84be1ff) | BugsInPy | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `tm_real_07` | matplotlib | type_mismatch | [BugsInPy matplotlib/3](https://github.com/soarsmu/BugsInPy/tree/master/projects/matplotlib/bugs/3), [fix 2a3707d9](https://github.com/matplotlib/matplotlib/commit/2a3707d9c3472b1a010492322b6946388d4989ae) | BugsInPy | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `tm_real_11` | scrapy | type_mismatch | [BugsInPy scrapy/20](https://github.com/soarsmu/BugsInPy/tree/master/projects/scrapy/bugs/20), [fix 25c56159](https://github.com/scrapy/scrapy/commit/25c56159b86288311630cc0cf6db9d755aeeff1e) | BugsInPy | FAILED assertion | sem fixed | O fix (BugsInPy scrapy/20) altera o chamador em scrapy/spiders/sitemap.py; o detection mostra uma função que o patch não toca. |
| `vm_real_01` | tqdm | variable_misuse | [BugsInPy tqdm/8](https://github.com/soarsmu/BugsInPy/tree/master/projects/tqdm/bugs/8), [fix cae9d139](https://github.com/tqdm/tqdm/commit/cae9d139c6df5614be3bf6e25ccbd600ee3286dc) | BugsInPy | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. Além disso, o detection não reproduz o trecho bugado do commit. |
| `vm_real_04` | youtube-dl | variable_misuse | [BugsInPy youtube-dl/12](https://github.com/soarsmu/BugsInPy/tree/master/projects/youtube-dl/bugs/12), [fix e118a879](https://github.com/ytdl-org/youtube-dl/commit/e118a8794ffe5a3a414afd489726f34d753b0b23) | BugsInPy | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `vm_real_07` | keras | variable_misuse | [BugsInPy keras/13](https://github.com/soarsmu/BugsInPy/tree/master/projects/keras/bugs/13), [fix a07253d8](https://github.com/keras-team/keras/commit/a07253d8269e1b750f0a64767cc9a07da8a3b7ea) | BugsInPy | FAILED assertion | sem fixed | O bug real produz valor/decisão errada sem falha de runtime; o harness só detecta via oráculo diferencial ou flag, o que na prática é incorrect_result. |
| `vm_real_09` | tqdm | variable_misuse | [fix 6dad2e89](https://github.com/tqdm/tqdm/commit/6dad2e89019317e875c46d5a3a82a811ad6de2f9), PyBugHive #539 | fix mergeado upstream | FAILED assertion | sem fixed | Duplicata de nm_real_09: mesmo commit do tqdm (a4b9c86 -> 6dad2e8). Além disso, o detection não reproduz o trecho bugado do commit. |

## Apêndice: expressão bugada e linha do fix por caso

| Caso | Expressão bugada (detection) | Primeira linha adicionada pelo fix |
|---|---|---|
| `av_real_01` | `assert isinstance(param, bool)` | `if param is None:` |
| `av_real_02` | `assert self.stream is not None` | `assert self.ws_connection is not None` |
| `av_real_03` | `assert isinstance(self.index, PeriodIndex)` | `if not isinstance(self.index, PeriodIndex):` |
| `av_real_04` | `set_tasks["failed"] = {task for (task, status, ext) in task_history if status == 'FAILED'}` | `set_tasks["ever_failed"] = {task for (task, status, ext) in task_history if status == 'FAI` |
| `av_real_05` | `self.iterable = iterable` | `if total is None and iterable is not None:` |
| `av_real_06` | `return '{} --staged'.format(command.script)` | `return command.script.replace(' diff', ' diff --staged')` |
| `av_real_07` | `'ls' in command.script and not ('ls -' in command.script)` | `return (command.script == 'ls'` |
| `av_real_08` | `conf.update(kwargs)` | `"""` |
| `av_real_09` | `setter(self, max(vmin, vmax, oldmax), min(vmin, vmax, oldmin),                        ignore=True)` | `setter(self, max(vmin, vmax, oldmin), min(vmin, vmax, oldmax),` |
| `av_real_10` | `current_column += 4` | `elif char in ' \t':` |
| `av_real_11` | `headers.get("Transfer-Encoding") == "chunked"` | `if headers.get("Transfer-Encoding", "").lower() == "chunked":` |
| `av_real_12` | `"php -s" in command.script` | `return " -s " in command.script` |
| `av_real_13` | `'set-upstream' in command.output` | `and 'git push --set-upstream' in command.output)` |
| `av_real_14` | `'open http://' + command.script[5:]` | `return command.script.replace('open ', 'open http://')` |
| `av_real_15` | `output += f.extrabuf` | `output += f.extrabuf[-f.extrasize:]` |
| `av_real_17` | `return compat_str(upload_date)` | `if upload_date is not None:` |
| `av_real_19` | `setter(self, max(vmin, vmax, oldmax), min(vmin, vmax, oldmin),                        ignore=True)` | `setter(self, max(vmin, vmax, oldmin), min(vmin, vmax, oldmax),` |
| `av_real_20` | `current_column += 4` | `elif char in ' \t':` |
| `av_real_21` | `del force_properties[f]` | `for f in ('_type', 'url', 'id', 'extractor', 'extractor_key', 'ie_key'):` |
| `dz_real_01` | `(xind[1:-1] - x[ind - 1]) / (x[ind] - x[ind - 1])` | `if N == 1:` |
| `dz_real_02` | `float(not_parsed)/float(num_substrings)` | `rating.append([` |
| `dz_real_03` | `(crc >> idx) % (range_end - range_begin + 1)` | `rng = range_end - range_begin + 1` |
| `dz_real_04` | `(h_src - wdw_size) / step_size` | `assert chunk_size >= 2, "chunk_size must be >= 2 (step_size = chunk_size - 1 must be posit` |
| `io_real_01` | `maxabsvalue = max(abs(vmin), abs(vmax))` | `vmin, vmax = map(float, [vmin, vmax])` |
| `io_real_02` | `y = (x + 1) // 2` | `\| `MAX_UINT_64` \| `uint64(2**64 - 1)` \|` |
| `ip_real_01` | `':' not in self._url` | `if ('://' not in self._url) and (not self._url.startswith('data:')):` |
| `ip_real_03` | `text = response.text` | `if not(response is None or text is None):` |
| `ip_real_04` | `"Transfer-Encoding" not in headers` | `and (` |
| `ip_real_05` | `return not self.__lt__(other)` | `def __gt__(self, other):` |
| `ip_real_06` | `clocs` | `if not rlocs:` |
| `ip_real_07` | `compat_chr(int(numstr, base))` | `try:` |
| `ip_real_08` | `netloc = self.config.get("SERVER_NAME", "")` | `host = uri.find("/")` |
| `ip_real_09` | `commands.append("no {0}".format(key))` | `for key in to_remove:` |
| `ip_real_10` | `settings.get('SPIDER_MANAGER_CLASS')` | `cls_path = settings.get('SPIDER_MANAGER_CLASS',` |
| `ip_real_11` | `scheme.lower() != "bearer"` | `if self.auto_error:` |
| `ip_real_12` | `needs_update('state') and not needs_update('vrf')` | `if needs_update('state'):` |
| `ip_real_13` | `(start is not None and start >= size) or end == 0` | `if start is not None and start < 0:` |
| `ip_real_14` | `self.end_index - self.start_index` | `if self.start_index > self.end_index:` |
| `ip_real_15` | `before = min(before, max_allowed)` | `before = (` |
| `ip_real_16` | `columns` | `if columns is None:` |
| `ip_real_17` | `http.RESPONSES.get(int(status))` | `return '%s %s' % (status, to_native_str(http.RESPONSES.get(int(status), "Unknown Status"))` |
| `ip_real_18` | `return dt.month % step` | `return ((dt.month - 1) % step) + 1` |
| `ip_real_19` | `self.to_tuple()[index]` | `and (index.start is not None and index.start < 0)` |
| `ip_real_20` | `src_dir_path + full_path[len(dest_dir_path):] if src_dir_path else ""` | `renamed_path = src_dir_path + full_path[len(dest_dir_path):] if src_dir_path else ""` |
| `ip_real_21` | `len(self._dict) == len(that) and all((self[key] == that[key] for key in self))` | `and all((key in that) and (self[key] == that[key])` |
| `ip_real_22` | `pattern.lower() in command.stderr.lower()` | `if command.script_parts and command.script_parts[0] == 'sudo':` |
| `ip_real_23` | `params[param_name].significant` | `params_str[param_name] = params[param_name].serialize(param_value)` |
| `ip_real_24` | `in_workers = assistant or worker in task.workers` | `in_workers = (assistant and task.workers) or worker in task.workers` |
| `ip_real_25` | `necessary_tasks` | `if task.status not in (DONE, DISABLED, UNKNOWN) or \` |
| `ip_real_26` | `worker is not None` | `if not (task.status in (RUNNING, BATCH_RUNNING) and (status not in (DONE, FAILED, RUNNING)` |
| `ip_real_28` | `IOLoop.current(instance=False) is None` | `if IOLoop.current(instance=False) is not None:` |
| `ip_real_31` | `max(vmin, vmax, oldmax)` | `setter(self, max(vmin, vmax, oldmin), min(vmin, vmax, oldmax),` |
| `ip_real_32` | `H += 12` | `- 1.6.3 handle repeated instances of named fields, fix bug in PM time` |
| `ip_real_33` | `SHFileOperationW(byref(fileop))` | `if not paths:` |
| `ip_real_34` | `return os.path.abspath(os.path.join(hooks_dir, hook_file))` | `scripts = []` |
| `ir_real_01` | `sqrt(2.0 * pi_const) * pow(t, z + 0.5) * exp(0.0 - t) * a` | `return sqrt(2.0 * pi) * pow(t, z + 0.5) * exp(0.0 - t) * a` |
| `ir_real_02` | `pi: float = 3.14153` | `pi: float = 3.141592653589793` |
| `ir_real_03` | `pattern_len != 7` | `if pattern_len != 6:` |
| `ir_real_05` | `alpha_len = len(alphabet)` | `alpha_len = len(alphabet_index)` |
| `nm_real_01` | `value = value.decode('utf8')` | `if value is None:` |
| `nm_real_02` | `total *= unit_scale` | `if total:` |
| `nm_real_03` | `len(video_title) > 80 + 3` | `limit_length,` |
| `nm_real_04` | `url_pattern.match(domain)` | `domains = []` |
| `nm_real_05` | `url = self.urljoin(url)` | `elif url is None:` |
| `nm_real_06` | `return objcls.from_crawler(crawler, *args, **kwargs)` | `Raises ``TypeError`` if the resulting instance is ``None`` (e.g. if an` |
| `nm_real_07` | `isinstance(args, dict)` | `if args is None:` |
| `nm_real_08` | `"//" in self.app.config.SERVER_NAME` | `try:` |
| `nm_real_09` | `self.total if self.iterable is None else self.iterable.shape[0] if hasattr(self.iterable, "shape") e` | `else getattr(self, "total", None))` |
| `nm_real_10` | `len(self.columns)` | `if self.columns and len(self.columns) > 0:` |
| `nm_real_11` | `len(self) >= self.limit` | `if self.limit:` |
| `nm_real_12` | `current_line.next.prev = current_line.prev` | `self.prev = None` |
| `nm_real_13` | `self._instance_cache.get(self.io_loop) is not self` | `cached_val = self._instance_cache.pop(self.io_loop, None)` |
| `nm_real_14` | `to_bytes(parsed.hostname)` | `s += b"Host: " + to_bytes(parsed.hostname or b'') + b"\r\n"` |
| `nm_real_15` | `responses = {**responses, **route.responses}` | `if responses is None:` |
| `nm_real_16` | `linewidths = rcParams['lines.linewidth']` | `if linewidths is None:` |
| `nm_real_17` | `_isint(string)` | `if string is None:` |
| `nm_real_18` | `sec_format % retry_state.seconds_since_start` | `secs = retry_state.seconds_since_start` |
| `nm_real_19` | `return os.path.isfile(v)` | `>>> with raises(FileInvalid, 'Not a file'):` |
| `nm_real_20` | `first = not num.endswith(decimal)` | `if decimal is None:` |
| `nm_real_21` | `if matches:             return self.__class__(matches)` | `return self.__class__(matches)` |
| `nm_real_22` | `dotenv_as_dict = dotenv_values(file)` | `from .compat import IS_TYPE_CHECKING, to_env` |
| `nm_real_23` | `tag in html_classes_from_tag` | `if isinstance(html_classes_from_tag, dict):` |
| `nm_real_24` | `executor.shutdown()` | `try:` |
| `nm_real_25` | `start_line.method in ("HEAD", "GET")` | `or getattr(start_line, 'method', None) in ("HEAD", "GET")):` |
| `oob_real_01` | `re.findall(r'ERROR: unknown command \"([a-z]+)\"',                             command.output)[0]` | `broken_cmd = re.findall(r'ERROR: unknown command "([^"]+)"',` |
| `oob_real_02` | `command.script.split()[1]` | `splited_script = command.script.split()` |
| `oob_real_03` | `command.script_parts.pop(upstream_option_index)` | `try:` |
| `oob_real_04` | `self._cached[0]` | `if self._cached:` |
| `oob_real_05` | `src_txt[-1]` | `if not lines:` |
| `oob_real_06` | `default[k]` | `new_config[k] = merge_configs(default.get(k, {}), v)` |
| `oob_real_09` | `l[i + 4]` | `if i+4 < len_l and l[i+3] == ':':` |
| `oob_real_10` | `list_of_lists[0]` | `if len(list_of_lists):` |
| `oob_real_11` | `pwcs[idx]` | `end = len(pwcs) if n is None else min(n, len(pwcs))` |
| `oob_real_12` | `x[0]` | `if not x:` |
| `oob_real_13` | `result[-1]` | `elif char == _ZWJ and result and result[-1].chars in EMOJI_DATA and i > 0 and string[i - 1` |
| `oob_real_14` | `lines[0]` | `if not lines:` |
| `oob_real_15` | `para.attrib['begin']` | `return` |
| `oob_real_16` | `self.item_list[real_index]` | `if index < 0 or index >= len(self):` |
| `tm_real_01` | `head = (int(head) - 1) if head != "0" else id_` | `head = (int(head) - 1) if head not in ["0", "_"] else id_` |
| `tm_real_02` | `return stdout and table in stdout` | `return stdout and table.lower() in stdout` |
| `tm_real_03` | `UNARY_OPERATORS = {'': lambda v: v is not None, '!': lambda v: v is None}` | `'': lambda v: (v is True) if isinstance(v, bool) else (v is not None),` |
| `tm_real_04` | `if int_str is None:         return None` | `if not isinstance(int_str, compat_str):` |
| `tm_real_05` | `msg['To'] = COMMASPACE.join(to)` | `from .utils.misc import arg_to_iter` |
| `tm_real_06` | `exc_info = failure.value, failure.type, failure.getTracebackObject()` | `exc_info = failure.type, failure.value, failure.getTracebackObject()` |
| `tm_real_07` | `self._filled = True` | `self._filled = self._fillstyle != 'none'` |
| `tm_real_08` | `TableFormat(None, None, None, None, headerrow=None, datarow=DataRow('', separator, ''), padding=0, w` | `headerrow=DataRow('', separator, ''),` |
| `tm_real_09` | `formatted_val = format(float(raw_val), floatfmt)` | `try:` |
| `tm_real_10` | `metrics.configure_http_handler(self)` | `metrics_collector = self._scheduler._state._metrics_collector` |
| `tm_real_11` | `line.lstrip().startswith('Sitemap:')` | `for url in sitemap_urls_from_robots(response.text):` |
| `tm_real_12` | `path = self.s3_load_path()` | `path = self.s3_load_path` |
| `tm_real_13` | `self._xg_characters(serialized_value)` | `elif isinstance(serialized_value, six.text_type):` |
| `vm_real_01` | `return l_bar + r_bar` | `l_bar, r_bar = l_bar_user.format(**bar_args), r_bar_user.format(**bar_args)` |
| `vm_real_02` | `type(skey) is not Optional` | `skey = None` |
| `vm_real_03` | `docs = _pipe(pipe, docs, kwargs)` | `docs = _pipe(docs, pipe, kwargs)` |
| `vm_real_04` | `op = lambda attr, value: not str_op` | `op = lambda attr, value: not str_op(attr, value)` |
| `vm_real_05` | `self.fs.mkdir(d)` | `self.mkdir(d)` |
| `vm_real_06` | `configure_logging(settings)` | `configure_logging(self.settings)` |
| `vm_real_07` | `val_enqueuer_gen = iter_sequence_infinite(generator)` | `val_enqueuer_gen = iter_sequence_infinite(val_data)` |
| `vm_real_08` | `with open(output_path, 'a') as output_file:` | `with open(output, 'a') as output_file:` |
| `vm_real_09` | `self.total` | `else getattr(self, "total", None))` |

## Como reproduzir

```bash
python scripts/audit_v2_buggy_fixed.py --jobs 4   # ESBMC em todos os pares; grava esbmc_audit.json
python scripts/build_v2_eligible.py                # valida os portões e gera dataset/v2_real_world_eligible/
pytest -q tests/test_v2_eligibility.py
```

Para rodar o E2E só no elegível:

```bash
python src/main.py --mode v2 --input dataset/v2_real_world_eligible/detection \
    --ground-truth dataset/v2_real_world_eligible/ground_truths.json ...
```

Com mais de 4 processos em paralelo, o mypy embutido no ESBMC falha por falta de memória (`OSError: Cannot allocate memory`), e o resultado sai como `erro`.

## Próximos passos

- Reescrever com a operação real os 18 casos `needs_review`, conferindo cada par no CPython e no ESBMC como foi feito aqui; isso melhora o baseline de comparação, mas não remove os casos do corpus.
- Reavaliar os 23 `unsupported_by_esbmc` com o binário da PR e registrar o resultado separado em `esbmc_audit_pr.json`; a primeira rodada confirmou pares completos adicionais em `nm_real_14` e `nm_real_20`, ainda pendentes de revisão dos portões.
- Para aumentar o volume sem abstração manual, sondar o RunBugRun (subconjunto Python com erro de runtime), em trilha separada do V2.
