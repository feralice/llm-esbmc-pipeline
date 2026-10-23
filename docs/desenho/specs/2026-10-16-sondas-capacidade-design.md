# Sondas de capacidade do ESBMC (self-healing): desenho

Data: 16/10/2026. Item 2 do `docs/historico/PLANO_GERAL_2026-10-15.md`.
Plano de implementação: `docs/desenho/planos/2026-10-16-sondas-capacidade.md`.

## Objetivo

O harness que o pipeline monta para o ESBMC-Python passa por reescritas. Parte delas existe só porque o
ESBMC recusa uma construção válida de Python ou a modela errado (por exemplo, não levanta
`AttributeError` ao ler atributo de `None`). Hoje essas reescritas estão fixas no código e continuam
ligadas mesmo quando o ESBMC instalado já trata a construção.

Este item dá a cada uma dessas regras um ou mais programas mínimos (sondas). Antes de um lote de
verificação, o pipeline roda as sondas no ESBMC configurado, guarda o resultado num cache por binário,
flags e versão, e liga só as regras cuja construção o ESBMC ainda não trata. Quando o ESBMC evoluir, a
sonda passa e a regra se desliga sozinha, sem editar código. Junto vai a aplicação do patch
`docs/historico/regras_pos_congelamento_2026-10-15.patch` (três regras novas e seus testes), e as duas
regras de reescrita que ele cria também ganham sondas.

Nenhuma medição de efeito na métrica entra aqui: rodar sondas faz parte do funcionamento, mas comparar
confirmações com e sem regras fica para o item 6.

## Inventário das regras de reescrita

Levantado no código em 16/10/2026 (números de linha antes do patch). Classes:

- **(a)** existe só porque o ESBMC recusa ou modela errado uma construção, e desligar a regra deixa um
  programa válido: ganha sonda.
- **(b)** necessária por outro motivo (fatiamento, stubs de bibliotecas ausentes, montagem do driver,
  desempenho): sem sonda.
- **(c)** contorna limitação do ESBMC, mas não tem caminho alternativo no código (desligar quebraria o
  harness) ou troca uma forma por outra equivalente: sem sonda neste item.
- **(d)** já se ajusta sozinha a partir do diagnóstico do próprio ESBMC (oráculo de conversão): sem sonda.

| Transformação reportada | Onde | Classe | Motivo |
|---|---|---|---|
| `compat_percent_format` | `compat.py:183-227`, `:263`, `:274` | (a) | `%` com argumento não constante recusado no 8.5 (reprodutor 17) |
| `compat_method_alias` | `compat.py:242-255`, `:276` | (a) | 8.5 recusa `__repr__ = __str__` ("Variable __str__ not found", `compat.py:243`) |
| `builtin_named_methods_renamed` | `compat.py:553-623` | (a) | método do usuário chamado `append`/`get` vai para o modelo de list/dict (reprodutor 27, comentário em `compat.py:553-555`) |
| `none_guards` | `compat.py:405-550` | (a) | master não levanta a exceção do CPython em valor `None` (`compat.py:405`; reprodutores 01 a 04, 10, 25, 26, 39) |
| `properties_as_attributes` | `slicing.py:94-119` (`:117-118`), `grounding.py:121-126`, `:532` | (a) | "ESBMC 8.5 has no `property`" (`grounding.py:122`) |
| `project_decorators_removed` | patch, `compat.py` novo `drop_project_decorators` | (a) | ESBMC recusa o wrapper `*args, **kwargs` que o decorador devolve |
| `conditional_assignments_split` | patch, `compat.py` novo `split_conditional_assignments` | (a) | ESBMC não tipa expressão condicional cujos ramos são funções |
| `unused_definitions_removed` | `compat.py:326-349`; `grounding.py:544` | (b) | fatiamento: tira código morto (o ESBMC poderia recusar qualquer coisa ali, não uma construção) |
| `cut_after_suspect` | `compat.py:366-402` | (b) | sub-aproximação de caminho, por desempenho |
| `decorators_removed` | `grounding.py:355-367`, `:525` | (b) | verificar o corpo da função alvo |
| `nested_entry_hoisted` | `grounding.py:434-469`, `:486` | (b) | o driver não alcança função aninhada |
| `inherited_members_inlined` | `grounding.py:211-238`, `:519-520` | (b) | a casca do receptor precisa dos membros herdados |
| `receiver_init_replaced`/`_added`, `receiver_new_removed`, `unreachable_methods_removed`, `receiver_subclass` | `slicing.py:111-116`; `grounding.py:533-541` | (b) | casca do receptor e fatiamento |
| `stubbed_imports` | `slicing.py:423-441`; lista `MODELED_MODULES` em `slicing.py:15-18` | (b) | bibliotecas sem modelo; a lista de módulos é corrigida pelo oráculo (`loop.py:115-133`) |
| `external_spread_arguments_named`, `external_decorators_removed` | `slicing.py:375-396`, `:362-372` | (b) | formato fixo de stub |
| `esbmc_refused_members_stubbed`, `member_models` | `slicing.py:316-353`, `:451-464`; `oracle.py` | (d) | já vêm do diagnóstico do ESBMC a cada lote |
| `external_result_members_flattened` | `slicing.py:398-420` | (c) | ESBMC não tipa atributo do resultado de stub; sem plano alternativo de stub |
| `external_chains_flattened` | `slicing.py:280-313`; problema em `:243-245` | (c) | ESBMC não resolve stub de dois níveis; idem |
| `builtin_exceptions_stubbed` | `render.py:284-335`, `:438-444` | (c) | lista por nome das exceções modeladas; sonda por nome fica para depois |
| `opaque_values`, `typing_import_added` | `render.py:433-435`, `:445-447` | (b) | montagem do harness |
| (não reportada) `Optional` por `if` em vez de ternário | `render.py:109-116` | (c) | forma equivalente (reprodutor 11); nada a ganhar ao desligar |
| (não reportada) stub `-> bytes` com `nondet_bytes(2)` | `render.py:191-193` | (c) | forma equivalente (#7902, reprodutor 23) |
| (não reportada) `sys.exit` como fim de caminho | `slicing.py:21-31` | (c) | modelo fixo de membro |
| (não reportada) contêiner com no máximo dois itens | `render.py:87-89` | (b) | desempenho |
| (não reportada) subconjunto de tipos da spec | `spec.py:11-12`, `:87-89` | (c) | linguagem da spec, não reescrita |
| (patch) `remove_unused` ignora autorreferência | patch, `_unused_definitions` | (b) | correção de fatiamento, não regra |

## Regras cobertas

`none_guards` vira seis regras, uma por tipo de construção, porque o master já trata parte delas
(reprodutores 01, 03, 04 e 10 dão a exceção certa) e não outras (25, 26, 39). O nome da transformação no
relatório continua `none_guards:N`. A coluna "Previsão" vem do README de `possiveis_problemas` (master
333d07cc8a, mesmas flags do wrapper) e serve só para conferir as sondas, não é medição deste item.

| Regra (id) | Sondas | Esperado | Previsão |
|---|---|---|---|
| `compat_percent_format` | `percent_valor`, `percent_violacao` (do 17) | seguro; `AssertionError` | não medido |
| `compat_method_alias` | `alias_de_metodo` | `ZeroDivisionError` | não medido |
| `builtin_named_methods_renamed` | `metodo_append` (27), `metodo_get` (variante do 27) | `ZeroDivisionError` | fica ligada (27 dá SUCCESSFUL) |
| `properties_as_attributes` | `property_decorador`, `property_funcao` | `ZeroDivisionError` | não medido (05 já passa no master) |
| `project_decorators_removed` | `decorador_do_projeto` | `ZeroDivisionError` | não medido |
| `conditional_assignments_split` | `condicional_de_funcoes` | `ZeroDivisionError` | não medido |
| `none_guards_attribute` | `none_atributo_local` (01), `none_atributo_campo` (25) | `AttributeError` | fica ligada (25) |
| `none_guards_subscript` | `none_indice_local`, `none_indice_campo` | `TypeError` | não medido |
| `none_guards_call` | `none_len_local`, `none_int_local` (39), `none_float_local`, `none_int_campo` | `TypeError` | fica ligada (39) |
| `none_guards_membership` | `none_in_dict_local` (04), `none_in_lista_local`, `none_in_str_local` (26), `none_in_str_campo` | `TypeError` | fica ligada (26) |
| `none_guards_ordering` | `none_ordem_local` (03), `none_ordem_campo` | `TypeError` | não medido no campo |
| `none_guards_arithmetic` | `none_soma_local` (10), `none_produto_local` (02), `none_soma_campo` | `TypeError` | não medido no campo |

São 12 regras e 26 sondas.

## Desenho

### Formato da sonda

Cada sonda é um arquivo `.py` pequeno, autocontido, com `main()` chamado no fim, no estilo dos
reprodutores de `docs/projeto/possiveis_problemas/`. A primeira linha é um comentário com a regra e a
origem (o reprodutor copiado ou "sonda nova"). O catálogo, em Python, associa a sonda à regra e declara
o resultado esperado:

- `exception`: o nome da exceção que o CPython levanta e que um ESBMC correto deve relatar; ou `None`
  quando o programa é seguro e o ESBMC correto diz SUCCESSFUL;
- `cpython`: valores que cada `nondet_*` devolve na checagem com o CPython (padrão: `False`, `0`, `""`).

O resultado de uma execução é um destes três:

- **aceita**: o ESBMC fez o que o CPython faz (relatou pelo nome a exceção esperada, ou nenhuma violação
  quando o esperado é seguro);
- **recusa**: o ESBMC recusou o programa, deu SUCCESSFUL onde devia achar a exceção, achou outra coisa,
  ou só deu artefato (unwinding);
- **indeterminada**: não deu para saber (timeout, ESBMC ausente, erro sem veredito, exceção no próprio
  mecanismo das sondas).

A exceção só conta quando o ESBMC a nomeia (`uncaught exception: X`, propriedade que começa com o nome,
`assertion` para `AssertionError`, `division by zero` para `ZeroDivisionError`). Mensagens do modelo de
memória (`NULL pointer`, `out-of-bounds`) não contam, mesmo que `outcome.py` as traduza para
`AttributeError`/`TypeError`/`IndexError` na leitura normal: sem `--no-pointer-check` o master acusa
`dereference failure: NULL pointer` no reprodutor 25, e isso desligaria a guarda de atributo por engano.

`compat_percent_format` usa um par de sondas: uma afirma que o resultado é `"ab 7"` (esperado seguro) e
a outra que não é (esperado `AssertionError`). Só um modelo que calcula a formatação passa nas duas; um
modelo que devolve string arbitrária falha a primeira.

### Onde ficam

- `src/research_pipeline/verify/rules.py`: os ids das regras (iguais ao prefixo da transformação
  reportada, menos as seis de `none_guards`), `ALL_RULES` e `NONE_GUARD_KINDS`.
- `src/research_pipeline/verify/probes/*.py`: os 26 programas. São cópias, não leituras de `docs/`, para
  que mexer na documentação nunca mude o comportamento do pipeline.
- `src/research_pipeline/verify/capabilities.py`: catálogo (`Probe`, `PROBES`), execução e
  classificação, cache e a função `resolve_rules` que o modo v2 chama.

### Como uma regra é ligada

As funções que aplicam as regras recebem o conjunto de regras ativas, com padrão `ALL_RULES` (o
comportamento de hoje):

- `rewrite_compat(..., rules=ALL_RULES)` pula `%` e alias quando a regra está fora;
- `none_guards(..., kinds=NONE_GUARD_KINDS)` filtra as guardas pelo tipo de construção;
- `render_program(grounded, spec, rules=ALL_RULES)` pula decoradores do projeto, separação de
  condicional e renomeação de métodos, e passa `rules & NONE_GUARD_KINDS` às guardas;
- `ground(h, source, refused, rules=ALL_RULES)` deixa `property` como está quando a regra está fora;
- `precheck` e `verify_hypothesis` repassam `rules`; `run_verify` já repassa `**kwargs`.

Uma regra fica **desligada só quando todas as suas sondas deram aceita**. Recusa, indeterminada ou
resultado ausente mantêm a regra ligada.

### Cache

Chave: sha256 de um JSON com

- o comando completo (binário e flags, por exemplo `esbmc.sh` com `--no-pointer-check --no-align-check`);
- a saída de `<comando> --version`;
- o sha256 do executável e, quando ele é um script (começa com `#!` e tem até 64 KiB), o sha256 de cada
  arquivo existente cujo caminho absoluto aparece no script; assim recompilar o ESBMC atrás do mesmo
  `esbmc.sh` muda a chave;
- o digest do catálogo (nome, regra, esperado, valores do CPython e texto de cada sonda).

Arquivo: `<cache_dir>/<chave>.json`, com `cache_dir` padrão `artifacts/esbmc_capabilities` (já fora do
git por `/artifacts/`) e opção `--capability-cache`. Só aceita e recusa entram no cache; uma sonda
indeterminada roda de novo no próximo lote. Cache ilegível ou corrompido é ignorado.

### Quando roda

Uma vez por lote, no início de `_mode_v2_verify` (`src/main.py`), antes de `run_verify`. As sondas rodam
em sequência pelo mesmo `check()` do motor (`esbmc_run.py:39-71`: `--unwind 5 --multi-property`, aumento
do limite se só faltou desenrolar, troca de solver em timeout), com 60 s por execução. Com o cache
quente, o custo é o hash do binário e uma chamada de `--version`.

O relatório das sondas (motivo, chave, identidade, regras ativas e desligadas, resultado de cada sonda)
vai para o checkpoint (`capabilities`) e para `config.capabilities` do `v2_verify_report.json`. Na
retomada (`--resume`) o conjunto gravado no checkpoint é reaproveitado sem rodar nada, para que as duas
metades de um lote usem as mesmas regras. Um checkpoint antigo, que já tem resultados de verificação mas
nenhum registro de sondas (o caso do lote pausado em `artifacts/v2/final-2026-10-15-codex`), segue com
todas as regras ligadas.

`--no-capability-probes` desliga as sondas e mantém todas as regras, para reproduzir uma rodada
congelada.

### Fail-safe

Nada nas sondas pode desligar uma regra por acidente nem parar o lote. Toda falha resulta em regra ligada:

| Situação | Comportamento |
|---|---|
| sonda dá timeout, crash sem veredito ou o ESBMC não existe | indeterminada, regra ligada, não vai ao cache |
| ESBMC recusa a sonda, dá SUCCESSFUL, artefato ou outra exceção | recusa, regra ligada, vai ao cache |
| exceção Python ao rodar uma sonda | indeterminada |
| exceção ao calcular a identidade ou ao montar o relatório | `resolve_rules` devolve todas as regras ligadas com o motivo |
| cache ilegível | ignorado; as sondas rodam |
| falha ao gravar o cache | ignorada; o lote segue com o resultado medido agora |
| sem `--esbmc-command` e sem `/usr/local/bin/esbmc` | todas ligadas, motivo "sem comando ESBMC" |

## Testes

Nenhum teste da suíte rápida roda o ESBMC real:

- regras: cada função de reescrita com a regra fora devolve o programa sem aquela edição, e com o padrão
  continua igual a hoje (os testes atuais seguem valendo sem mudança);
- catálogo: toda regra de `ALL_RULES` tem sonda, toda sonda tem regra conhecida e arquivo, nomes únicos;
- validade das sondas: cada sonda roda no CPython com os valores declarados e levanta exatamente a
  exceção esperada (ou nenhuma); um `__ESBMC_assume` falso no CPython falha o teste;
- classificação com um executor falso: exceção nomeada é aceita; `NULL pointer` não é; seguro, recusa de
  conversão, timeout, ESBMC ausente e exceção do executor caem em recusa ou indeterminada;
- `active_rules`: regra sai só com todas as sondas aceitas;
- cache: segunda chamada não roda sondas; indeterminada roda de novo; cache corrompido é ignorado; a chave
  muda com o binário apontado por um wrapper, com as flags e com o catálogo;
- `resolve_rules`: desligado, retomada, sem ESBMC e falha interna dão todas as regras;
- `main`: o conjunto ativo chega a `run_verify`, fica no checkpoint e no relatório, e a retomada não
  sonda de novo.

Um teste opcional de integração, em `tests/test_verify_esbmc_integration.py` (fora da suíte rápida),
roda as sondas no wrapper do master e confere que as regras das lacunas conhecidas (25 e 27) ficam
ligadas.

Um `tests/conftest.py` com fixture automática troca `main.resolve_rules` por "todas ligadas" nos testes
que importam `main`, para que nenhum teste antigo rode o ESBMC instalado.

## Fora do escopo

- Rodar as sondas como experimento, comparar confirmações com e sem regras ou rodar e2e: item 6.
- Sondas para as regras (c): stubs de dois níveis e de atributo de resultado precisariam de um plano de
  stub alternativo; a lista de exceções modeladas pede sonda por nome.
- Ligar as sondas no modo scan, nos scripts avulsos (`scripts/v2_*.py`) e no braço do agente: seguem com
  todas as regras ligadas (padrão `ALL_RULES`). O scan entra no item 7.
- Ligar e desligar a renomeação por nome de método (`get`, `pop`...): a regra é uma só.
- Atualizar `ESBMC_PYTHON_NOTES.md` do agente ou a pasta `docs/projeto/possiveis_problemas/`.
- Rodar sondas em paralelo.

## Decisões tomadas sem a Fernanda

1. O "esperado" da sonda é a exceção do CPython (ou "seguro"), e o resultado tem três valores (aceita,
   recusa, indeterminada), em vez de só "converte ou não converte": várias regras existem porque o ESBMC
   aceita o programa mas erra o veredito.
2. A regra só desliga quando todas as suas sondas dão aceita.
3. `none_guards` foi dividida em seis regras por tipo de construção; o nome no relatório não muda.
4. Cada tipo de guarda de `None` tem sonda com variável local e com campo de objeto, porque o harness
   gera os dois casos (parâmetro e atributo do receptor).
5. Operadores sem sonda própria (`-`, `/`, `//`, `**`, `<`, `<=`, `>`) são tratados como os
   representativos (`+`, `*`, `>=`). Se o ESBMC tratar um e não o outro, a guarda some para os dois.
6. `%` usa par de sondas (valor certo e violação) contra modelo que devolve string arbitrária.
7. Só conta exceção que o ESBMC nomeia; mensagens de memória não contam.
8. As sondas são cópias em `src/research_pipeline/verify/probes/`, com comentário de origem.
9. A chave do cache inclui comando com flags, `--version`, hash do executável e dos arquivos que um
   wrapper nomeia, e o digest do catálogo; o cache fica em `artifacts/esbmc_capabilities/`.
10. Resultado indeterminado não vai para o cache.
11. As sondas usam o `check()` do motor, com limite 5 e 60 s por execução, em sequência.
12. As sondas rodam uma vez por lote, no início do modo v2; o resultado fica no checkpoint e no relatório.
13. A retomada reaproveita o conjunto gravado; checkpoint antigo com resultados e sem registro segue com
    tudo ligado.
14. As sondas vêm ligadas por padrão; `--no-capability-probes` existe para rodadas congeladas.
15. As funções de reescrita recebem `rules` com padrão `ALL_RULES`, para que scripts, braço do agente e
    testes atuais não mudem.
16. Modo scan e scripts avulsos ficam fora deste item.
17. `tests/conftest.py` com fixture automática impede que testes antigos de `main` rodem o ESBMC.
18. Regras (c) e (d) ficam sem sonda e documentadas no inventário.
19. O patch entra como está (`git apply`), primeiro só a parte de testes, para vê-los falhar.
20. `docs/projeto/possiveis_problemas/` não é alterada.

## Emendas de 16/10

Depois da revisão final da implementação, a Fernanda aprovou estas mudanças. Onde o texto acima diverge
delas, valem as emendas.

1. **Gêmeo seguro para cada sonda de `None`** (emenda as decisões 1, 2 e 4). Cada uma das 17 sondas
   `none_*` que esperam exceção ganhou um par `<nome>_seguro`: o mesmo programa com
   `__ESBMC_assume(<valor> is not None)` antes do uso e resultado esperado "seguro". Como a regra só
   desliga com todas as suas sondas aceitas, uma guarda de `None` sai só quando o ESBMC acusa a exceção
   no ramo `None` e não acusa nada no ramo não `None`. Isso barra um modelo que erra em todo valor
   `Optional`.
2. **Mensagem de limitação do frontend não conta como exceção** (emenda a decisão 7). Uma propriedade
   que casa com algum padrão de limitação de `diagnose.py` (por exemplo
   `TypeError: object of this type has no len()`) não vale como exceção nomeada. A lista é a mesma
   que o diagnóstico de conversão usa, agora exposta pela função `limitation`.
3. **Catálogo de `%` ampliado** (emenda a decisão 6). Além do par original (`"%s %d"` com str e int),
   entram seis formas, cada uma com par de valor certo (seguro) e violação (`AssertionError`): `%s` de
   float, `%d` de float (trunca), `%d` de bool, `%%`, operando único fora de tupla e `%r` de str
   constante. Um teste confere que a própria regra reescreve cada sonda de `%`, para que o catálogo
   cubra o que a regra de fato faz.
4. **Alias pelo caso documentado** (emenda a tabela de regras). `compat_method_alias` ganhou
   `alias_repr_divisao` (`__repr__ = __str__` alcançado por `repr()`, espera `ZeroDivisionError`) e
   `alias_repr_valor` (o mesmo caso, espera seguro). A sonda `alias_de_metodo` continua.
5. **Retomada liga regra desconhecida.** O conjunto usado num lote é `ALL_RULES` menos as regras que o
   relatório gravado desligou, e não a lista de regras ativas. Assim, uma regra criada depois do
   checkpoint fica ligada na retomada.
6. **Cache gravado por arquivo temporário próprio.** Cada gravação usa um temporário com nome único na
   pasta do cache, e dois lotes que dividem o cache não escrevem no mesmo arquivo.

Com isso são 12 regras e 57 sondas. Rodadas no wrapper do master 333d07cc8a
(`artifacts/v2/final-2026-10-15/esbmc.sh`) em 16/10, as sondas desligam só `none_guards_arithmetic` e
`none_guards_ordering`. As outras dez regras ficam ligadas:

- `compat_percent_format`: `%d` de float e `%r` são recusados ("non-constant argument in str %
  formatting");
- `compat_method_alias`: o caso `repr()` é recusado;
- `none_guards_subscript` e `none_guards_call`: os casos de `len` e de índice no campo agora contam como
  limitação do frontend.
