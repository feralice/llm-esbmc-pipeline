# Spec com contexto dos chamadores (item 3 do plano geral)

Data: 16/10/2026. Plano de implementação: `docs/superpowers/plans/2026-10-16-spec-com-contexto.md`.
Item 3 de `docs/projeto/PLANO_GERAL_2026-10-15.md`. Sem experimento neste item: a medição fica para o
item 6 (rodada final e2e).

## Objetivo

O passo de spec pede a um LLM o JSON com os tipos das entradas da função alvo. Hoje o LLM vê só o
recorte do módulo e uma lista de membros usados, e por isso chuta tipo. Quando o chute contradiz o uso
(um parâmetro `int` em que o código chama `.groups()`, um `int` subscrito), o harness é gerado mesmo
assim e o ESBMC recusa a conversão, gastando uma chamada de ESBMC e uma tentativa de reparo com uma
mensagem que não aponta o tipo errado.

Este item faz duas coisas:

1. Acrescenta ao pedido de spec as **chamadas reais da função** (com algumas linhas em volta), as
   **referências sem chamada** (a função passada como valor, por exemplo `partial(f, ...)`) e **fatos
   estáticos** de cada entrada (tipo do valor padrão, tipos literais que os chamadores passam, se a
   função subscreve, itera ou chama `len()` na entrada).
2. Acrescenta uma **checagem de consistência** que rejeita, antes do ESBMC, um tipo contrariado pelo
   uso dentro da função, e devolve o motivo ao LLM pelo laço de reparo que já existe.

Métrica que o item quer mover (medida só no item 6): bugs do gabarito confirmados na linha. Meta
intermediária, também medida só no item 6: menos recusas do ESBMC por tipo errado e menos `SPEC_FAILED`.

## Como o código está hoje

As linhas citadas são do commit `ffc40ef`. O item 2 está mexendo em `loop.py` ao mesmo tempo (parâmetro
`rules` em `precheck`, `verify_hypothesis` e `render_program`), então os números podem andar uma ou duas
linhas; o plano usa trechos de texto como âncora, não números.

- **Montagem do pedido.** `src/research_pipeline/verify/loop.py:35` lê o prompt de sistema
  `src/research_pipeline/prompts/input_spec_prompt.txt`. `_user_prompt` (`loop.py:69-90`) monta o
  pedido: função, expressão suspeita, hipótese, entradas sem tipo, stubs, membros usados nas entradas
  (`loop.py:83-85`, vindo de `Grounded.object_members`) e o recorte do módulo, limitado por
  `_bound_untrusted` (`src/research_pipeline/verify/llm_client.py:33-42`, 32.000 caracteres).
- **Validação.** `parse_spec` (`src/research_pipeline/verify/spec.py:107-124`) lê o JSON;
  `shape_unpacked` (`spec.py:211-232`) alarga escalar desempacotado para tupla; `spec_problems`
  (`spec.py:235-270`) rejeita tipo ausente, tipo fora do subconjunto, desempacotamento com aridade
  errada e suposição mal formada. Nenhuma regra compara o tipo com o uso.
- **Reparo.** `verify_hypothesis` (`loop.py:140-207`) faz até `1 + max_repairs` chamadas. Com
  problemas, o motivo vira `feedback` (`loop.py:174-178`) e volta no pedido seguinte quando
  `--spec-strategy repair`; com `resample` (`loop.py:163`) o pedido seguinte não mostra o erro. Ao
  esgotar, todos os problemas com "unsupported type" dão `UNSUPPORTED`, o resto `SPEC_FAILED`
  (`loop.py:204-207`).
- **Atenção:** `render_program` também chama `spec_problems` (`src/research_pipeline/verify/render.py:417-419`),
  e `precheck` renderiza um spec provisório com tudo `int` (`loop.py:93-97`, `loop.py:125`). Uma regra
  de uso colocada dentro de `spec_problems` faria esse spec provisório falhar e mandaria casos para
  `UNSUPPORTED` antes de qualquer chamada ao LLM. Por isso a checagem nova fica fora de `spec_problems`.
- **Fontes da verificação.** `run_verify` (`loop.py:238-268`) lê o arquivo de
  `verification_source` (`loop.py:229-235`): o arquivo de mesmo nome em `--verification-sources`
  (ex.: `dataset/bugs_reais/arquivo_com_bug`, que é o arquivo inteiro do projeto) ou, sem ele, o
  arquivo da detecção. O texto chega a `verify_hypothesis` como `source`. `--context-sources`
  (`src/main.py:296-300`, `src/research_pipeline/llm/prompts.py:167-178`) só alimenta a variante A11 da
  detecção; o motor verify não o usa.
- **Contexto dos chamadores no modo scan.** `build_callgraph` (`src/research_pipeline/scan/callgraph.py:163-181`)
  só aceita um diretório (usa `python_files`, `callgraph.py:128-137`). `CallGraph.callers`
  (`callgraph.py:94-95`) devolve os `CallSite` (arquivo, linha, linha final e o texto da função chamada
  encurtado por `_shorten`, `callgraph.py:301-303`). `caller_context` (`src/research_pipeline/scan/context.py:14-31`)
  formata até 8 chamadas em até 3.000 caracteres, recortando sempre dentro da função chamadora
  (`context.py:34-51`), e troca o nome da função por `target_function` (`context.py:31`), o que serve à
  detecção mas não ao spec, que mostra o nome real. A resolução é conservadora: `obj.metodo()` com `obj`
  de tipo desconhecido fica sem destino; `self.metodo()`, `Classe.metodo()` e chamadas de função do
  mesmo módulo são resolvidas.
- **Reuso num arquivo só.** O `_Builder` (`callgraph.py:184-205`) recebe um dicionário de módulos já
  lidos; basta montar um `_Module` a partir do texto da fonte de verificação para ter o grafo de um
  arquivo, sem diretório. `caller_context` funciona igual sobre esse grafo.
- **Modo scan e verify.** `execute_scan` repassa `**verify_kwargs` a `run_verify`
  (`src/research_pipeline/scan/pipeline.py:180`), e `run_verify` repassa `**kwargs` a
  `verify_hypothesis` (`loop.py:241`, `loop.py:260`). Um argumento novo de `verify_hypothesis` chega
  dos dois modos sem mudar `run_verify`.
- **Retomada.** `_v2_fingerprint` (`src/main.py:489-503`) guarda o `config` da rodada e o hash do
  arquivo de prompt do spec (`main.py:500-502`). O texto montado por `_user_prompt` não entra no hash.
- **Reaplicação de specs.** `scripts/v2_replay_specs.py:88` e `scripts/v2_verify_smoke.py:75` chamam
  `verify_hypothesis` direto, com LLM falso. Precisam continuar iguais.

## Desenho

```
fonte de verificação (arquivo inteiro) ──┐
grafo do repositório (só no modo scan) ──┼─> collect_facts ─> CallerFacts ─┬─> render_section ─> pedido de spec
Grounded (params, attrs, object_members)┘                                  └─> usage_problems ─> feedback do reparo
```

Módulo novo `src/research_pipeline/verify/caller_facts.py`, só AST, sem LLM nem ESBMC:

- `collect_facts(h, grounded, source, *, graph=None) -> CallerFacts`. Sem `graph`, monta o grafo do
  arquivo `source` sozinho (`build_source_callgraph`, novo em `callgraph.py`). Com `graph` (modo scan),
  usa o grafo do repositório e acha chamadas em outros arquivos. Localiza a função por
  `function_key(graph, h.file, h.function)`; função ausente ou definida mais de uma vez no arquivo fica
  sem chamadores (nunca mostra os chamadores da função errada).
- `render_section(facts, grounded) -> str`: o bloco que entra no pedido.
- `usage_problems(spec, grounded, facts) -> list[str]`: a checagem de consistência.

`verify_hypothesis` ganha `spec_context: str = "none"` e `graph: CallGraph | None = None`. Com
`"callers"`, calcula os fatos uma vez por hipótese (depois do `precheck`, antes da primeira chamada ao
LLM), acrescenta o bloco a todo pedido e roda `usage_problems` quando `spec_problems` não acha nada.
O padrão da função é `"none"` para os scripts de reaplicação e os testes antigos não mudarem; a CLI
passa `--spec-context`, com padrão `callers`, nos modos V2 e scan. O modo scan passa também
`graph=plan.graph`.

## Dados que entram no prompt

O bloco vem depois do recorte do módulo e antes da tentativa anterior. Formato:

````
Call sites (real code that calls this function, verbatim; evidence for the types callers pass):
```python
# chamada em Fish.get_aliases, bip_thefuck_4.py, linha 60:
   57 |     def get_aliases(self):
   ...
   60 |         raw_aliases = _get_aliases(overridden)
```

The function is also used as a value here:
```python
  845 | self._type_conversions[group] = partial(date_convert, ymd=n + 1,
```

Facts read from the code (computed, not guessed):
- ymd: default is None; callers pass int (1x)
- rows: iterated; passed to len()
````

1. **Chamadas.** Saída de `caller_context(..., rename=False)`: até `MAX_SITES = 5` chamadas, cada uma
   com 3 linhas antes e 1 depois, recortadas dentro da função chamadora, com a linha da assinatura
   dela. Sem chamada, o bloco diz `# none found in the verification source`, que também é informação
   (qualquer entrada compatível com a assinatura pode chegar).
2. **Referências sem chamada.** Linhas do arquivo da função em que ela aparece como valor
   (`partial(date_convert, ...)`, callback, registro em dicionário). Para método, só
   `self.m`, `cls.m` ou `Classe.m` sem chamada. Até `MAX_REFERENCES = 3` linhas, cada uma cortada em 160
   caracteres. Só no arquivo da função, também no modo scan.
3. **Fatos por entrada** (parâmetros na ordem da assinatura, depois `self.<attr>`), só quando há algo
   a dizer:
   - `default is T`: tipo literal do valor padrão (`None`, `int`, `str`, `tuple`...).
   - `callers pass T (Nx)`: tipo literal de cada argumento ligado ao parâmetro, contado por chamada.
     Ligação posicional pela ordem de `Grounded.params` (sem `self`), parando no primeiro `*args`;
     ligação por nome pelos `keywords`. Em `Classe.metodo(obj, x)` as posições não batem (o receptor
     vem primeiro), então só os nomeados contam. Argumento que não é literal (nome, chamada,
     expressão) não gera fato: o trecho da chamada já aparece no item 1.
   - `subscripted`, `iterated`, `passed to len()`: uso direto da entrada no corpo da função alvo.
   - Os membros usados (`.groups()`) já aparecem na linha "Members used on inputs" que existe hoje
     (`loop.py:83-85`) e não se repetem.

Entradas que a função reatribui (`tz = groups[tz]`), apaga, sombreia num `lambda` ou função interna, ou
testa com `isinstance`, `hasattr`, `getattr`, `type` ou `callable` ficam marcadas como `unchecked` e não
geram fato de uso: depois da reatribuição, o uso já não diz nada sobre o tipo de entrada. O caso real
que motivou a regra é o `tz` de `ip_real_32` (linhas 488-500 do arquivo com bug), subscrito e com
`.strip()` só depois de virar texto.

Nada aqui depende do gabarito, do patch nem de hipóteses de outros casos.

## Limite de tamanho

| Parte | Limite | Constante |
|---|---|---|
| Chamadas | 5 chamadas e 2.000 caracteres, mais a linha `# [+N chamada(s) omitida(s)]` | `MAX_SITES`, `MAX_CALLER_CHARS` |
| Referências | 3 linhas de até 160 caracteres | `MAX_REFERENCES`, `MAX_LINE_CHARS` |
| Fatos | 1.200 caracteres, depois `[...]` | `MAX_FACT_CHARS` |

O bloco inteiro fica abaixo de cerca de 3.800 caracteres (perto de 1.000 tokens) por pedido, e o pedido
se repete em até 3 chamadas por hipótese. O tamanho de cada bloco fica gravado no resultado
(`spec_context.chars`), junto com `call_sites` e `references`, para o item 6 medir o custo.

## Checagem de consistência

`usage_problems(spec, grounded, facts)` roda depois de `spec_problems` e só quando ele não achou nada
(tipo inválido primeiro; depois, tipo válido mas contrariado). Para cada entrada com membros em
`grounded.object_members` ou com fato de uso, inclusive membros aninhados tipados em `stubs`
(`self.cron.RANGES`):

| Uso no código | Tipos rejeitados |
|---|---|
| membro lido ou chamado que o tipo não tem (`dir()` do tipo embutido) | qualquer tipo que não seja `object` |
| subscrito (`x[...]`) | `int`, `float`, `bool`, `None`, `set`, `frozenset` |
| iterado ou passado a `len()` | `int`, `float`, `bool`, `None` |

`Optional[T]` é checado pelo `T`. Nunca é questionado:

- tipo `object` (o harness gera a classe com os membros);
- anotação declarada no código (o LLM não pode mudá-la; rejeitar daria `SPEC_FAILED` certo);
- entrada `unchecked` (reatribuída, sombreada ou testada com `isinstance` e afins).

Mensagem, em inglês como o resto do pedido, apontando a correção:

```
input 'match': typed 'int', but the code uses .groups() on it, which int does not have; type it object and give each member under stubs
input 'rows': typed 'int', but the code subscripts it (rows[...])
input 'b': typed 'Optional[float]', but the code iterates it or passes it to len()
```

Os problemas entram em `record["problems"]` e no `feedback` exatamente como os de `spec_problems`, e o
reparo e a reamostragem seguem iguais. Nenhuma mensagem contém "unsupported type", então esgotar as
tentativas por uso contrariado dá `SPEC_FAILED`, não `UNSUPPORTED`.

## Erros e casos de borda

- Fonte que não faz parse no `collect_facts`: devolve `CallerFacts()` vazio, o bloco diz que não achou
  chamada e a checagem só vê os membros. Nunca derruba o caso.
- Função não encontrada pelo nome (entrada aninhada içada, herança embutida): fatos de uso e padrões
  vazios; chamadas vazias.
- Função definida duas vezes no arquivo (variantes py2/py3): sem chamadores, porque o grafo a marca
  como ambígua.
- Texto das chamadas é código não confiável dentro de bloco cercado, como o recorte do módulo hoje.
- `--spec-context` com valor fora de `none`/`callers` em `verify_hypothesis`: `ValueError`, como
  `strategy`.

## Retomada e fingerprint

- Mudar `input_spec_prompt.txt` muda `fingerprint["spec_prompt"]` (`main.py:500-502`), e o `config`
  ganha `spec_context`. Uma rodada V2 começada antes deste item **não pode ser retomada** com o código
  novo, nem com `--spec-context none`. Isso inclui o checkpoint pausado em
  `artifacts/v2/final-2026-10-15-codex` (470 de 564): o item 6 refaz a rodada do zero, ou retoma com o
  código do commit anterior a este item e não ganha a melhoria.
- O modo scan tem fingerprint próprio (`scan/pipeline.py:127-130`, raiz, variantes, modelo e alvos) que
  não inclui o prompt do spec nem `spec_context`. Retomar um scan depois deste item reaproveita os
  vereditos já gravados e faz os pendentes com o pedido novo. Fica anotado; não muda neste item.

## Testes

Todos com AST e LLM falso, sem ESBMC real (os testes do laço trocam `run_esbmc_direct` e
`concrete_replay` por falsos, como `tests/test_verify_loop.py` já faz).

- Grafo de um arquivo: acha chamadas sem diretório, nome do arquivo sem pasta, `SyntaxError` em fonte
  quebrada; `caller_context(rename=False)` mantém o nome real.
- Fatos: tipos literais (constantes, negativos, f-string, contêineres; nome e expressão não contam);
  chamada, padrões, referência via `partial`; subscrito, iteração, `len()`; reatribuição, sombra em
  `lambda` e `isinstance` viram `unchecked` e somem dos fatos de uso; `Classe.m(obj, 5, y=0)` só liga o
  nomeado; função duplicada sem chamadores; grafo do repositório acha chamada em outro arquivo; fonte
  quebrada dá fatos vazios; bloco limitado e com "none found".
- Checagem: `int` com `.groups()` rejeitado com o membro na mensagem; `object` e `Optional[str]` com
  `.strip()` passam; escalar subscrito ou iterado rejeitado; `set` subscrito rejeitado; anotação
  declarada nunca questionada; reatribuída ou testada nunca questionada; atributo do receptor e membro
  aninhado em `stubs` checados.
- Laço: o bloco aparece em todo pedido e o resultado grava `spec_context`; com `"none"` o pedido é
  idêntico ao de hoje; spec contrariado volta com o motivo e a segunda tentativa confirma; três
  rejeições por uso dão `SPEC_FAILED`; `spec_context` desconhecido dá `ValueError`.
- CLI: padrão `callers`; `spec_context` entra no `config` do fingerprint; com `callers` o resultado traz
  `spec_context`, com `none` não; no modo scan, `spec_context` e o grafo chegam a `run_verify`.

## Fora do escopo

- Qualquer rodada com LLM ou ESBMC, e qualquer medição: tudo no item 6.
- "Could not resolve type of receiver" em cadeias de atributos e stubs (`bip_pandas_133`
  `cls._AXIS_ALIASES.get`, `bip_thefuck_4` `proc.stdout.read()`): o tipo que falta é de membro de
  biblioteca ou de atributo de classe, não de parâmetro, e o contexto dos chamadores quase não ajuda.
  Continua na Tarefa 3 de `docs/projeto/PLANO_CONTINUACAO_2026-10-15.md`.
- `Optional[tuple[...]]` para entrada desempacotada sob guarda `is not None` (`d_m_y` de `ip_real_32`,
  que hoje para em `spec_problems`, `spec.py:259-263`): é regra de desempacotamento, não de contexto.
- Inferência de tipo entre funções (seguir o valor do chamador até a origem), tipos de argumentos não
  literais e chamadas por `partial` ligadas a parâmetros.
- Hipótese cujo bug é o próprio `AttributeError` por tipo errado: a checagem empurra para `object`, e o
  harness não modela esse erro hoje.
- `--context-sources` no motor verify: os fatos vêm sempre do arquivo que o ESBMC verifica.
- Mudar o fingerprint do modo scan.

## O que a sondagem por AST mostrou (sem LLM, sem ESBMC)

Rodei `collect_facts` e `render_section` numa cópia do código no rascunho, sobre
`dataset/bugs_reais/arquivo_com_bug/`, só para conferir o desenho:

- `ip_real_32` (`date_convert`): nenhuma chamada direta; três referências por `partial(date_convert,
  ymd=n + 1, ...)` (linhas 845, 852, 859), que mostram que `ymd`/`dmy`/`mdy` são índices inteiros;
  bloco de 668 caracteres; `match: int` é rejeitado com `.groups()` na mensagem. Na rodada final do
  Codex o LLM já tipava `match` como `object`; o bloqueio atual desse caso é o `d_m_y` (fora do escopo).
- `bip_thefuck_4` (`_get_aliases`): uma chamada (`Fish.get_aliases`, linha 60); 419 caracteres.
- `bip_pandas_133` (`NDFrame.interpolate`): nenhuma chamada no arquivo; só padrões; 392 caracteres.
- `oob_real_13` (`tokenize`): `string` subscrito e passado a `len()`; 239 caracteres.

## Decisões tomadas sem a Fernanda

1. **Checagem fora de `spec_problems`.** Dentro dela, o spec provisório todo `int` do `precheck`
   quebraria e casos virariam `UNSUPPORTED` antes do LLM.
2. **Padrão `callers` na CLI e `none` na função.** A CLI liga a melhoria; scripts de reaplicação de spec
   e testes antigos ficam idênticos. `--spec-context none` existe como linha de base para o item 6.
3. **`none` desliga também a checagem.** A linha de base é o comportamento de hoje inteiro, para a
   comparação do item 6 isolar o efeito do item.
4. **Uma regra nova no prompt de sistema**, sabendo que isso impede retomar rodadas antigas, inclusive a
   final pausada (ver "Retomada e fingerprint"). O plano geral já previa refazer a rodada no item 6.
5. **Fonte dos chamadores = arquivo que o ESBMC verifica** (`--verification-sources`, ou o da detecção),
   não `--context-sources`. Em `arquivo_com_bug` cada arquivo é de um projeto diferente; montar o grafo
   da pasta inteira misturaria projetos sem ganho.
6. **Referências sem chamada entram**, porque no caso que motivou o item (`ip_real_32`) a função só é
   usada via `partial`.
7. **Limites menores que os da detecção** (5 chamadas e 2.000 caracteres, contra 8 e 3.000): o pedido de
   spec se repete até 3 vezes por hipótese.
8. **Rótulos das chamadas em português** (`# chamada em ..., linha N:`), reaproveitando
   `caller_context` sem duplicar o formatador, dentro de um pedido em inglês.
9. **Reatribuição, sombra e teste de tipo desligam a checagem daquela entrada**, preferindo deixar passar
   um tipo errado a rejeitar um certo.
10. **Tipos permitidos por `dir()` do tipo embutido do CPython**, não pelo que o ESBMC modela: a checagem
    só pega contradição com Python; o que o ESBMC não modela continua com as sondas do item 2.
