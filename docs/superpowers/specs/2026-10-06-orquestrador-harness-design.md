# Orquestrador de harness, braço dinâmico e agente via API

Data: 2026-10-06. Parte do roteiro pós-validação (depois da Tarefa 12 do plano de validação e detecção).

## Objetivo

Tirar mais vereditos dos casos em que o nível 1 trava, gastando o braço caro só onde ele tem chance. Três peças:

1. **Medir o agente via API** nos mesmos casos travados em que o agente Claude Code já rodou, para saber se ele serve como degrau intermediário.
2. **Braço dinâmico (fuzzing com Hypothesis):** procura uma entrada que quebre a função original no CPython, sem prova formal. Barato, e a entrada achada vira semente para o ESBMC ou evidência à parte.
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

## Peça 2: braço dinâmico

- **Entrada:** o JSON de tipos que a LLM já devolve no nível 1 (`params`, `stubs`) e o recorte do arquivo original.
- **O que faz:** gera entradas com Hypothesis a partir dos tipos (int, str, list, Optional, dict...), chama a função original no CPython com o mesmo ambiente do `concrete_replay`, e para na primeira exceção da classe esperada na linha da hipótese.
- **Orçamento:** número fixo de exemplos e tempo máximo por caso (padrão 200 exemplos, 60 s).
- **Saídas novas:**
  - `FUZZ_FOUND`: o CPython quebrou na linha da hipótese, com a entrada registrada. **Não é CONFIRMED**: é evidência dinâmica, contada à parte na dissertação.
  - Quando o ESBMC ainda puder rodar, a entrada vira semente (`counterexample_seeds`) e o caso volta ao ESBMC; se ele confirmar, o veredito é CONFIRMED normal.
  - `FUZZ_NOTHING`: nada achado no orçamento (não prova ausência de bug).
- **Controle:** rodar também nas versões corrigidas; um `FUZZ_FOUND` na linha do bug na versão corrigida é falso alarme e entra na tabela.
- **Dependência nova:** `hypothesis` no `.venv` (não está instalado hoje).

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
- Linha de comando: `--orchestrate` no modo `end-to-end`, substituindo `--agent-fallback` quando ligado.

## Como medir

1. Aplicar `route` aos vereditos já gravados (sem rodar nada) e contar quantos casos iriam para cada braço: estima quanto tempo de agente o orquestrador economiza.
2. Peça 1 nos casos travados; Peça 2 em todos os travados e nas versões corrigidas.
3. Rodada completa com `--orchestrate` e comparação com `nível 1 + agente` (a rodada `agent-2026-10-06-e2e`): bugs do gabarito confirmados na linha, FUZZ_FOUND na linha, falsos alarmes no controle, tempo total.

Métrica principal: bugs do gabarito confirmados na linha (formal) e, separado, achados dinâmicos na linha. Nunca somar os dois num número só.

## Fora do escopo

- O grafo (parte 1 do roteiro) e o harness híbrido (parte 2) têm especificação própria; o orquestrador ganha uma rota nova quando eles existirem.
- Trocar de solver como braço.
- Fuzzing guiado por cobertura (Atheris): Hypothesis basta para a primeira medição.

## Decisões em aberto

- Se o achado dinâmico entra na mesma tabela da dissertação ou num capítulo à parte.
- Instalar `hypothesis` no `.venv` (pequeno, sem custo).
