# Semana 3 do item 6: recorte pelo caminho e correções do harness

Origem: piloto da semana 2 (`docs/historico/piloto_semana2_2026-10-16.md`). Dos 84 obstáculos em 19 bugs, as
correções A (recorte) e B (erros do harness) apareceram em 10 e 5 bugs e são do próprio pipeline, sem LLM.
Esta spec escolhe as regras dessas duas correções que são seguras (não mudam o que o CPython faria) e
baratas, mais a parte trivial de C (aliases de builtin).

## Objetivo

Menos recusas causadas por código que o caminho do bug não visita e por defeitos do próprio harness, sem
mudar o comportamento do código original. Critério de sucesso: medido nos 19 bugs do piloto e nos 9 de
reserva, com os specs gravados e sem LLM, aumentar o número de hipóteses na linha do bug que chegam a um
veredito do ESBMC, sem perder nenhuma confirmação atual.

## Regras

Todas preservam a numeração das linhas do módulo (o gabarito, os spans e o replay dependem dela).

**R1. Guardas mortas no Python 3.** Antes do recorte, um teste de `if`/`elif` que o Python 3 decide
estaticamente vira `False` ou `True`, e o corpo morto vira `pass`, com linhas em branco no lugar do resto:
- `TYPE_CHECKING` (nome importado de `typing`) é falso;
- comparação de `sys.version_info` (ou `sys.version_info[0]`/`.major`) com tupla ou inteiro literal, avaliada
  para a versão 3.12;
- em `and`/`or`, um operando decidido decide o todo quando cabe (`False and x` é falso, `True or x` é
  verdadeiro).
Motivo: bip_keras_33 (`unicode` só no ramo Python 2), bip_pandas_33 (`TYPE_CHECKING`). Os nomes do ramo morto
deixam de puxar dependências e de contar como indefinidos.

**R2. Métodos especiais sem gatilho.** Na classe do receptor, um método especial que o alvo não alcança é
removido quando nada do módulo o dispara: `__enter__`/`__exit__` sem `with`; `__copy__`, `__deepcopy__`,
`__reduce__`, `__reduce_ex__`, `__getstate__`, `__setstate__` sem `copy`/`pickle`; `__array__`,
`__array_ufunc__`, `__array_function__`, `__array_wrap__` sem `numpy`/`np`. Os demais métodos especiais
ficam (podem ser chamados implicitamente). Motivo: bip_youtube_dl_30 (`__enter__`/`__exit__` puxando
`cookiejar`), bip_pandas_33 (`__array_ufunc__` com `**kwargs`).

**R3. Sem chamada órfã.** Um método que um método especial mantido chama (`self.x()`) continua na classe,
mesmo fora do alcance do alvo. Motivo: ip_real_14 (`__getitem__` mantido desempacota o resultado de
`_empty_batch`, que tinha sido removido: "Cannot unpack empty").

**R4. Atributo de classe sem uso.** Na classe do receptor, uma atribuição no corpo da classe cujo nome não
aparece em mais nenhum lugar do módulo (nem como atributo `.nome`, nem como nome) é removida. Motivo:
bip_pandas_133 (`_internal_names_set = set(...)` matava todos os caminhos com `--unwind 5`), av_real_03
(`hist = pandas_plotting.hist_series`, alias de stub `None`).

**R5. Anotação `None`.** Um tipo `None` do spec vira a anotação `None`, não `none`. Defeito em
`render._annotation` achado no bip_luigi_21 (`worker_scheduler_factory: none=None`).

**R6. Anotação em texto.** Anotações que são texto (`data: "DataFrame"`, `-> "Report"`) são removidas do
módulo verificado; o render então põe o tipo do spec onde houver. O CPython ignora anotações, então o
comportamento não muda. Motivo: ip_real_16 e bip_black_16 (`NameError` do nome só importado sob
`TYPE_CHECKING`, repetido nas 3 tentativas do LLM).

**R7. Alias de builtin do youtube-dl.** Um nome externo `compat_chr` ou `compat_str` é o builtin no Python 3
(`chr`, `str`; definido em `except NameError: compat_chr = chr`) e é ligado a ele, não a um stub de valor
livre. `compat_ord` fica de fora: não é `ord` (devolve um `int` recebido sem mudar). Motivo: ip_real_07 (o stub de `compat_chr` apagava o `ValueError` real de `chr()`). 25 arquivos do
dataset usam `compat_*`.

## Fora do escopo

Reescritas mecânicas do frontend (grupo D do piloto), modelos de biblioteca (grupo C semântico), limite de
laço maior (já há escalada no `check()`), recorte do corpo de funções alcançáveis pelo nome mas fora do
caminho (av_real_03, bip_luigi_21: exige análise de caminho) e as falhas do ESBMC (issues).

## Testes

Cada regra tem um teste que falha antes: programa mínimo tirado do caso do piloto, mais um teste de
preservação de linhas. A medição final usa `scripts/v2_replay_specs.py` nos 28 bugs (ids sem repetição, um
diretório por pedaço) e `scripts/v2_audit_control.py` nas confirmações.

## Decisões tomadas sem a Fernanda

- Escolha das regras: só A e B do piloto, mais R7. D e C semântico ficam para depois (cada reescrita do D
  vira regra com sonda). Custo se errado: o ganho medido é pequeno e a semana 4 roda com menos melhorias.
- R2 lista fechada de métodos especiais removíveis, em vez de remover todos os não alcançados: remover um
  `__len__` ou `__eq__` chamado implicitamente mudaria o comportamento. Custo se errado: sobra código
  irrelevante em outros casos.
- R4 só na classe do receptor e só quando o nome não aparece em nenhum outro lugar do módulo (inclui
  `getattr` com texto, por busca do nome). Custo se errado: um acesso dinâmico por nome montado
  (`getattr(self, "_" + x)`) quebraria; o replay no original continua decisivo.
- R1 avalia `sys.version_info` para 3.12 (a versão do replay). Custo se errado: nenhum para Python 3.
- Sem chamada de LLM e sem commit; a medição é com specs gravados.
