# Orquestrador de harness, braço dinâmico e agente via API

Data: 2026-10-06. Parte do roteiro pós-validação (depois da Tarefa 12 do plano de validação e detecção).

## Objetivo

Tirar mais vereditos dos casos em que o nível 1 trava, gastando o braço caro só onde ele tem chance. Três peças:

1. **Medir o agente via API** nos mesmos casos travados em que o agente Claude Code já rodou, para saber se ele serve como degrau intermediário.
2. **Braço dinâmico (busca no CPython):** procura uma entrada que quebre a função original no CPython, sem prova formal. Barato, e a entrada achada vira semente para o ESBMC ou evidência à parte.
3. **Orquestrador por motivo:** lê por que o nível 1 travou e escolhe o próximo braço (ou nenhum).

A tese que isso sustenta: cada ferramenta entra onde ajuda; LLM, verificação formal e teste dinâmico juntos confirmam mais do que qualquer uma sozinha.

## Ponto de partida (rodada `full-2026-10-05-regrounded`, 236 vereditos)

| Veredito do nível 1 | Casos |
|---|---|
| UNSUPPORTED | 115 |
| MISSING_DEPENDENCY | 57 |
| GROUNDING_FAILED | 19 |
| ESBMC_ERROR / ESBMC_TIMEOUT | 9 / 5 |
| OTHER_FAILURE, SPEC_FAILED, UNVALIDATED | 5, 4, 3 |
| CONFIRMED / NOT_CONFIRMED / ESBMC_MISSED | 6 / 8 / 1 |

O agente Claude Code rodou em 28 travados (05/10) e confirmou 4; a rodada `agent-2026-10-06-e2e` cobre 156. O agente via API (`agent_arm.api_agent`) só rodou num caso.

## Peça 1: agente via API nos mesmos casos

- Mesmos casos e mesmo orçamento de verificação da rodada `agent-2026-10-06-e2e` (o que for medido primeiro: os 28 de 05/10, depois os 156).
- Dois modelos: Claude via `claude_cli` (sem custo de API, assinatura) e um modelo local via Ollama (reprodutível). Modelo pago só com confirmação dela antes.
- Mesmas checagens finais dos outros braços: ESBMC de novo, CPython, função preservada (`target_preserved`), alcance da linha.
- Saída: tabela por caso, braço × veredito, e o tempo gasto.

## Peça 2: braço dinâmico (busca no CPython)

Revisão de 06/10: o pipeline já tem o executor que a peça precisa. `concrete_replay` roda o programa
gerado no CPython, numa caixa sem rede, trocando cada `nondet_*` por valores de uma lista pequena
(int 0, 1, -1, 2; str "" e "a"; listas de até 2 itens). Hoje ele só roda depois que o ESBMC dá um
veredito: 141 travados da rodada `full-2026-10-05-regrounded` têm programa pronto e nunca passaram
por ele. Por isso o braço dinâmico não usa Hypothesis (sem dependência nova):

- **Busca aleatória:** depois da passada exaustiva atual, o executor faz uma passada aleatória com
  semente fixa e valores mais variados (inteiros de borda e sorteados, strings com espaço, ponto,
  sinal, acento e barra, listas de até 5 itens). Orçamento padrão: 300 execuções ou 60 s por caso.
- **Entrada:** o programa pré-reescrita do veredito (o mesmo que a validação V1 lê), com as
  restrições `assume` que a LLM pôs: só entradas que a especificação aceita.
- **Saídas:** `FUZZ_FOUND` quando o CPython levanta exceção na linha da hipótese dentro da função;
  `FUZZ_OTHER` quando quebra em outro lugar; `FUZZ_NOTHING` quando nada quebrou no orçamento;
  `FUZZ_UNAVAILABLE` quando não há programa executável. `FUZZ_FOUND` não é CONFIRMED.
- **Sem volta ao ESBMC por enquanto:** os travados são casos em que o ESBMC recusa o programa, e uma
  semente não muda isso. Fica para quando houver caso de tempo esgotado que se beneficie.
- **Controle:** a mesma busca nas versões corrigidas (`control-fixed-2026-10-06`).

## Peça 3: orquestrador por motivo

Uma função pura `route(result) -> list[braço]` que lê o veredito e o motivo do nível 1 e devolve a sequência de braços a tentar. Regras gerais, escritas por classe de motivo, nunca por bug do dataset.

| Motivo do nível 1 (exemplos reais) | Sequência |
|---|---|
| Falta contexto: `MISSING_DEPENDENCY` (`Module 'layers' not found`, `Function "opfunc" not found`, `Base class not found`) | agente Claude Code → dinâmico |
| Tipos ou especificação ruins: `SPEC_FAILED`, `UNVALIDATED`, `TypeError: __init__() takes...` | agente API → agente Claude Code → dinâmico |
| Limite do ESBMC-Python: `UNSUPPORTED` com `Unsupported expression Starred`, `non-constant argument in str % formatting`, `*args/**kwargs`, exceção interna (`irep2_cast_error`, `symbolic_type_excp`) | dinâmico (os agentes não resolvem) |
| Aterramento: `GROUNDING_FAILED`, entrada aninhada em função | dinâmico |
| Solver: `ESBMC_TIMEOUT`, `ESBMC_ERROR` inconclusivo | dinâmico |
| Já tem veredito: CONFIRMED, NOT_CONFIRMED, ESBMC_MISSED | nenhum |

- A tabela fica num arquivo de dados (padrões de texto → classe), testada caso a caso com os motivos reais acima.
- Um braço que chega a veredito encerra a sequência; FUZZ_FOUND não encerra se ainda há braço formal na lista.
- Primeiro como script sobre um relatório pronto (`scripts/v2_orchestrate.py`), medido nos 20 casos
  difíceis; a opção `--orchestrate` no `main.py` só entra se o script mostrar ganho.

## Como medir

1. Aplicar `route` aos vereditos já gravados (sem rodar nada) e contar quantos casos iriam para cada braço: estima quanto tempo de agente o orquestrador economiza.
2. Peça 1 nos casos travados; Peça 2 em todos os travados e nas versões corrigidas.
3. Rodada completa com `--orchestrate` e comparação com `nível 1 + agente` (a rodada `agent-2026-10-06-e2e`): bugs do gabarito confirmados na linha, FUZZ_FOUND na linha, falsos alarmes no controle, tempo total.

Métrica principal: bugs do gabarito confirmados na linha (formal) e, separado, achados dinâmicos na linha. Nunca somar os dois num número só.

## Fora do escopo

- O grafo (parte 1 do roteiro) e o harness híbrido (parte 2) têm especificação própria; o orquestrador ganha uma rota nova quando eles existirem.
- Trocar de solver como braço.
- Fuzzing guiado por cobertura (Atheris) ou Hypothesis: a busca aleatória do executor basta para a primeira medição.

## Decisões em aberto

- Se o achado dinâmico entra na mesma tabela da dissertação ou num capítulo à parte.
