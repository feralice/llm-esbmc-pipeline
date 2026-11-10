# Varredura de projeto com equilíbrio entre custo e recall (proposta de 09/11/2026)

Proposta da IA a partir da conversa com a Fernanda. Nada implementado. As escolhas abaixo são sugestões para ela
avaliar. Só entra em código depois da entrega da disciplina (10/11, 16h).

## Objetivo

Varrer um repositório Python atrás de bugs de runtime gastando pouco token e pouco tempo, sem perder os bugs que o
pipeline já sabe achar. Uso diário: rápido. Uso na pesquisa: completo.

## Funil

1. **Triagem sem LLM.** Placar de risco por função: PageRank e número de chamadores (já existem em `scan/`), mais
   padrões de risco na AST (índice ou chave sem checagem, `int()`, divisão, atributo de valor que pode ser `None`,
   desempacotar, `bytes` e `struct`). Funções de risco baixo não gastam LLM.
2. **Passada 1, barata.** Uma variante do detector nas N melhores funções (N entre 40 e 100), com os chamadores no
   contexto. Saída: hipótese com confiança.
3. **Passada 2, só para confiança média ou alta.** Harness e ESBMC. Se o ESBMC recusa duas vezes pelo mesmo motivo,
   para o self-healing e registra o motivo.
4. **Replay em CPython** antes de qualquer relatório, para cortar falso positivo.
5. **Relatório em duas listas:** confirmados (com prova) e candidatos só da LLM, ordenados por confiança.

## Dois modos

| | `--rapido` | `--completo` |
|---|---|---|
| Variantes do detector | 1 | A1 + A2 |
| Bound e timeout | 3 e curto | 5 e 180 s, escada inteira |
| Self-healing | para na recusa fixa | como hoje |
| Uso | dia a dia | artigo e comparações |

## Como medir

- Pymodbus antes dos consertos (commit `5e0816c04^`), bugs 2921, 2977 e 2980: posição no ranking, token e tempo nos
  dois modos.
- Bug plantado num repositório limpo (item 14 do plano) como controle.
- Critério de equilíbrio: o modo rápido acha os mesmos bugs com cerca de metade do custo do completo.
  Número de partida, não promessa.

## Antes de implementar

- Ler a literatura de priorização de funções e de detecção com LLM (fonte junto da proposta, citações conferidas).
- Medir quanto do custo atual está na detecção, no spec, no reparo e no ESBMC, para cortar onde pesa de verdade.
- Perguntar ao orientador: vale confirmar por execução em CPython quando o ESBMC recusa (caminho 3)?

## Riscos

- O placar de risco pode esconder bugs em funções "sem padrão". O modo completo existe para checar isso.
- Parar o reparo cedo pode perder confirmações que o self-healing salvaria. Medir com a rodada dos 47.
