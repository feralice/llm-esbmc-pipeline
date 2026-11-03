# Funções aninhadas no pipeline: entrada pela função de fora e levantamento

Data: 02/11/2026. Item "Funções aninhadas em 3 níveis ou mais" da seção Depois do `docs/projeto/PLANO_2026-10-19.md`,
puxado para antes do congelamento por decisão da Fernanda, nas formas (a) e (b).

## Por quê

Bug dentro de função interna (definida dentro de outra função) só existe quando a de fora roda. Hoje:

- o motor já levanta a interna para o módulo (`_hoist_nested` em `verify/grounding.py`, desde `bc36afb`, 15/10),
  em qualquer profundidade: `f.g.h` e `A.f.g.h.i` passam (sonda de 02/11);
- o motor **recusa** a interna que usa `nonlocal` e a classe interna que captura variável da função de fora;
- a validação **nunca reconhece** a interna: `target_preserved` dá `False` mesmo com o código idêntico
  (`verify/validation.py:50`), porque `find_function` desiste com 3 partes ou mais (`verify/astutil.py:26`);
  o mesmo vale para `program_for_result` (sonda de alcançabilidade do S1, replay, oráculo de valor);
- o scan nunca seleciona a interna: `FunctionNode.verifiable` exige `not nested` (`scan/callgraph.py:48`);
- o levantamento troca as variáveis capturadas por parâmetros livres, que o ESBMC preenche com qualquer valor,
  inclusive valores que a função de fora nunca passaria. Contraexemplo assim pode ser espúrio.

Medição de 02/11: 0 casos nas amostras de 48 e 30 e nos 47 da disciplina; 1 de 289 na amostra completa
(tm_real_06, `ContractsManager._clean_req.eb_wrapper`, callback); 44 de 1832 funções no PyAthena, quase todas
dentro de código async. O valor está no scan de repos reais, não nas métricas atuais.

## Objetivos

1. **(a) Entrada pela função de fora.** Quando cada elo da cadeia chama o próximo dentro do próprio corpo,
   o harness chama a função de fora mais externa que o motor localiza (função do módulo ou método), e a linha do
   bug continua dentro da interna. As capturas recebem os valores que o código real calcula; nada é reescrito.
2. **(b) Levantamento.** Sem chamada direta (callback, função devolvida, guardada em atributo), vale o
   levantamento que já existe: a interna é copiada para o fim do módulo, corpo intacto, capturas como parâmetros
   só-nomeados (lambda lifting, Johnsson, FPCA 1985, DOI 10.1007/3-540-15975-4_37, conferido no Crossref).
3. **Validação que enxerga a interna**: localizar a definição pelo caminho do nome no original e, no programa
   verificado, pelo mesmo caminho ou pelo nome levantado; comparar só o corpo (a assinatura levantada ganha
   parâmetros).
4. **Scan** passa a selecionar funções internas não async.
5. **Braço de agente** recebe no prompt onde a função está definida e as duas saídas permitidas.

## Fora do escopo

- Interna async, lambda, função dentro de compreensão.
- Levantar interna com `nonlocal` ou classe interna com captura: continuam recusadas no (b), porque o
  levantamento mudaria o comportamento no caminho do bug. Pelo (a) elas passam a ser alcançáveis.
- Rodada nova com LLM: a medição deste item é offline (ver "Como medir").

## O que não pode acontecer

- Corpo da interna alterado em qualquer caminho.
- Confirmação vinda do levantamento contada como se fosse pela entrada real: o veredito registra por qual
  caminho entrou (`nested_entry_via_outer:` ou `nested_entry_hoisted:` em `transforms`) e o relatório mostra.
- Regressão nas funções de 1 e 2 partes: `find_function` mantém o comportamento atual (o `ground` depende do
  `None` dele para tentar o levantamento).

## Decisões de desenho

- Ordem no motor: (a) primeiro quando aplicável, porque não reescreve nada; se o grounding pela de fora falhar,
  cai no (b); se o (b) também não servir, a falha de hoje continua.
- "Chama o próximo": dentro do corpo da função do elo (fora de definições internas a ela) existe uma chamada
  `nome(...)`; para elo classe, `Classe(...)` seguido de `.metodo(...)` no mesmo corpo, ou o método chamado sobre
  instância dessa classe. Chamada condicional conta: se a linha não for alcançável, o portão do S1 já marca
  `NOT_CONFIRMED_VACUOUS`.
- Localizar pelo caminho: helper novo em `verify/astutil.py` que resolve `A.f.g.h` atravessando classes e
  funções (a lógica de `_definitions_in` e `_nested_chain` sai de `grounding.py` para lá e é reaproveitada).
  `find_function` não muda; validação e `agent_arm._target` passam a usar o helper novo.
- Scan: `verifiable` aceita interna não async e não ambígua; a contagem de excluídos ganha a razão `nested_async`
  e o resumo diz quantas internas entraram.

## O que fica para quem implementa

- Nomes dos helpers e onde exatamente o (a) entra no `ground` (antes ou depois da checagem de async).
- Texto exato da linha nova no prompt do agente.
- Testes: um por forma da sonda de 02/11 (3 e 4 níveis, `nonlocal`, classe interna, callback) nos dois caminhos,
  mais `target_preserved` verdadeiro para interna intacta e falso para interna alterada; cada teste mostrado
  falhando antes da mudança.

## Como medir

Sem LLM, no PyAthena (`~/alvos/PyAthena-limpo`): para cada função interna não async do grafo, uma hipótese
sintética na primeira expressão arriscada do corpo; contar quantas fazem grounding por (a), por (b) e quantas
falham, antes e depois. Registrar em `docs/experimentos/README.md`. Suíte inteira passando antes da nova tag
`v2-congelado-2026-11b`.
