# Proposta: o que "confirmado" deve significar (10/11/2026)

Proposta da IA para a Fernanda decidir. Nada foi implementado. Escolhas, riscos e medição ficam abertos.

## O problema, com dois exemplos do repositório

Hoje `CONFIRMED` quer dizer: o ESBMC achou a falha **e** o replay em CPython reproduziu a exceção. Os dois passos
rodam sobre o **programa gerado** (o harness), e não sobre o código real do projeto.

| Caso | O que o pipeline disse | O que o código real mostra |
|---|---|---|
| pyserial, `Serial.rfc2217_set_control` e `Serial.rfc2217_send_purge` | `CONFIRMED`: KeyError em `self._rfc2217_options['control']` | O `open()` (`serial/rfc2217.py`, linhas 449 a 453) sempre cria as chaves `'purge'` e `'control'`, e os dois métodos só rodam com a porta aberta. O harness montou um dict com chaves sorteadas, possivelmente vazio. O KeyError nunca acontece no uso real. |
| aws-cost-explorer-report, `CostExplorer.addReport` | `LLM_ONLY`: hipótese de `set_index('date')` com resultado vazio | Não confirmado por nada. A API devolve um período por mês, então a lista vazia é muito improvável. Não rodei o pandas para provar. |

O primeiro é um falso positivo marcado como confirmado. É o furo que importa para a dissertação, porque um revisor
vai perguntar: "confirmado onde?".

## Causa

O harness reconstrói o estado do objeto (atributos, dicts, listas) a partir de um JSON de tipos que a LLM escreve.
Esse estado não é checado contra o código que realmente prepara o objeto (`__init__`, `open()`, quem chama).
Então o ESBMC e o replay concordam entre si sobre um estado que o projeto talvez nunca produza.

## Opções

As opções podem ser combinadas. Ordem de custo, da menor para a maior.

### A. Mudar só o rótulo (menor custo)
- Separar `CONFIRMED` em dois níveis: `REPRODUZIDO_NO_HARNESS` (como hoje) e `CONFIRMADO_NO_PROJETO` (só quando
  o estado foi mostrado como alcançável, por B, C ou D).
- O relatório lista os dois em tabelas separadas e diz o que cada um permite afirmar.
- Mexe pouco no código (veredito e relatório). Não muda quantos bugs o pipeline acha, muda o que ele afirma.
- Risco: os números de "confirmados" caem. O artigo passa a reportar os dois valores.

### B. Checar alcançabilidade pelo grafo de chamadas
- Para cada atributo que o contraexemplo usa, procurar no grafo quem o inicializa e se essa escrita domina a
  chamada (por exemplo, `open()` roda antes de `rfc2217_set_control`).
- Se a inicialização que domina a chamada garante a chave, o contraexemplo é descartado ou marcado como
  "estado impossível".
- Já existe o grafo (`scan_graph.json`) e o campo `caller_guards` no contexto de cada hipótese. Falta usar a
  inicialização do objeto, não só os chamadores da função.
- Risco: análise estática erra nos dois sentidos. Pode descartar bug real se achar que um guarda existe e ele não
  cobre o caminho. Por isso o descarte deve ser "rebaixar para candidato", não "apagar".

### C. Replay no código real, sem harness
- Instanciar a classe real do projeto (importando o módulo, com as dependências pesadas trocadas por stubs mínimos),
  aplicar as entradas do contraexemplo e ver se a exceção ocorre.
- É a evidência mais forte: roda o código do projeto, e não um programa gerado.
- Custo alto: muitos projetos precisam de dependências, rede ou hardware (pyserial pede porta, rfc2217 pede
  socket). Pode valer só quando o replay real é possível, e cair em A quando não é.
- Risco: o objeto real exige um estado que o contraexemplo não descreve (falha por motivo errado).

### D. Estado inicial vindo do código, não do palpite da LLM
- Pedir à LLM só o que o código não informa. Chaves e tipos que o `__init__`/`open()` fixam entram no spec com a
  origem (arquivo e linha), e a LLM não pode contradizê-los.
- É a proposta que o Codex já registrou em `docs/experimentos/scan_pyserial_2026-11-10.md`.
- Risco: o `open()` real faz I/O e é difícil de ler como "estado". Funciona bem para atributos simples e mal para
  condições de sucesso.

## Recomendação (a decisão é sua)

Começar por **A**: é barato, honesto e não depende de acertar análise nenhuma. Depois testar **D** em atributos de
dict e lista (o caso do pyserial) e só então avaliar **C** para os repositórios em que o replay real cabe.
B fica por último, pelo risco de descartar bug verdadeiro.

## Como medir

- Casos negativos (devem cair de `CONFIRMED` para candidato): os 2 do pyserial acima.
- Casos positivos (não podem cair): os bugs que já foram confirmados com ground truth nos 47 da disciplina.
  Mudança que derruba um deles está errada ou precisa de justificativa.
- Reportar a métrica final primeiro: quantos bugs reais confirmados antes e depois, e só então quantos falsos
  positivos saíram.

## O que precisa de decisão

1. Mudar o significado de `CONFIRMED` (opção A) conta como mudança de critério. Declarar no artigo, e a decisão
   de aceitar é sua e do orientador.
2. O pipeline está congelado para a disciplina (tag e comando da rodada final registrados). Esta mudança entra
   depois da entrega, ou em uma branch de pesquisa separada?
3. O que vale mais para a dissertação: reduzir falso positivo (A, B, C) ou aumentar alcance (D)?

## Limites desta proposta

- Os dois exemplos vêm de rodadas pequenas (pyserial com 20 funções, cost-explorer com 7). Não provam a taxa de
  falso positivo do pipeline, só mostram que o furo existe.
- Não foi pesquisada a literatura sobre validação de contraexemplos em verificação com abstração (por exemplo,
  refinamento guiado por contraexemplo). Antes de escolher o desenho, vale ler e citar fontes verificadas.
