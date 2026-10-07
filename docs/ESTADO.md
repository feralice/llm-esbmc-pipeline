# Estado do pipeline e o que falta (07/10/2026)

Documento de trabalho: onde a pesquisa está, quais números valem hoje e tudo o que ainda falta, em
ordem. Serve para ela, para o Claude Code e para o Codex (`docs/handoff/CODEX.md` traz as regras de
trabalho e os passos técnicos de cada tarefa).

## 1. Objetivo

Uma LLM procura bugs em funções Python reais; o **ESBMC-Python confirma formalmente** no código
original; o CPython reexecuta para validar. A tese: a LLM ajuda bastante, e ferramentas híbridas
(LLM, verificação formal, execução) ajudam ainda mais.

Qualificação até fevereiro de 2027.

## 2. Números que valem hoje

| Métrica | Valor | Onde está |
|---|---|---|
| **Bugs do gabarito confirmados pelo ESBMC na linha** (métrica principal) | **7** | README de experimentos, "Resultado consolidado" |
| Detecção, rodada completa (277 bugs): função / linha | 178 (64%) / 82 (30%) | fase 8, `full-2026-10-04-sonnet` |
| Detecção na amostra de 50, prompt atual: função / linha | 34 / 15 a 17 | fase 9 |
| Detecção na amostra de 50, **prompt A5 (A1 + A2)** | **44 / 24** | fase 9 |
| Funções alteradas pela LLM nos vereditos | 0 de 23 | fase 9, validação |
| Vereditos "seguro" vazios (ESBMC não chega à linha) | 3 | fase 9, validação |
| Falsos alarmes conhecidos (dependem do chamador) | 2 (ir_real_03, bip_thefuck_11) | fase 8 |
| Bugs que o CPython quebra na linha só na versão com bug (evidência, não prova) | 5 | fase 10 |

Os 7 confirmados: av_real_01, oob_real_01, oob_real_02 (harness pelo código); bip_luigi_21,
bip_pandas_33, ip_real_14, nm_real_14 (agente).

## 3. O que já foi feito

- **Dataset:** 289 bugs reais com gabarito, tipo de falha (`failure_kind`) e linha da quebra.
- **Pipeline V2:** detecção sem categoria, triagem pela própria LLM (`verifiable`), harness pelo
  código (nível 1), agente Claude Code e agente via API (nível 2), reexecução no CPython.
- **Validação dos vereditos** (`scripts/v2_validate.py`): função preservada, vacuidade, controle nas
  versões corrigidas, mutantes.
- **Detecção:** modo só detecção, variantes do prompt (A1, A2, A3, A6), união de rodadas, amostra fixa
  de 50 bugs.
- **Harness:** conjunto fixo de 20 casos difíceis; orquestrador que escolhe o braço pelo motivo do
  travamento; busca no CPython nos casos travados.
- **Registro:** todas as rodadas em `docs/experimentos/` (fases 1 a 10).

## 4. Por que o ESBMC confirma pouco (diagnóstico)

Dos 229 resultados distintos da rodada completa, por que não houve veredito:

| Causa | Casos | Quem pode resolver |
|---|---|---|
| ESBMC-Python recusa o programa | 72 | só o próprio ESBMC (reprodutores já enviados ao professor) |
| falta contexto (módulo, classe, função de fora) | 64 | agente ou grafo de código |
| o harness por código não sabe montar (função aninhada, `*args`, decorador) | 51 | agente ou harness novo |
| o pipeline não acha a função ou a expressão | 17 | agente ou aterramento |
| harness com tipos ruins | 10 | agente |
| já têm veredito | 15 | nada a fazer |

Os casos de tempo esgotado não melhoram com mais tempo: com 900 s eles esgotam a memória. O limite é
o tamanho da fórmula (strings livres dentro de conjuntos).

## 5. O que falta, em ordem

### Curto prazo (fechar o pipeline)

1. **Juntar o branch no `master`.** O `master` está em aff456c; os commits seguintes (fase 10,
   correções da revisão, handoff, este arquivo) estão só em `feat/validacao-deteccao`. Ela roda:
   `git -C /mnt/c/Users/ferna/Documents/mestrado/llm_esbmc merge --ff-only feat/validacao-deteccao`.
2. **Entrada fixada** (tarefa 2 do handoff). A busca no CPython acha a entrada que quebra, e o ESBMC
   prova só aquele caminho, o que dá confirmação formal onde hoje estoura tempo ou memória.
   Candidatos: ip_real_22, oob_real_12. É a próxima chance concreta de subir a métrica principal.
3. **Prazo da passada aleatória** (tarefa 3 do handoff, achado I1 da revisão). Correção pequena em
   `verify/replay_worker.py`.
4. **Refazer a validação com mutantes** usando a busca melhorada. Na fase 9 os mutantes deram
   inconclusivo porque a busca no CPython era fraca.
5. **Agentes nos 68 casos que a rota nova manda para eles** (harness por código e aterramento).
   A rota foi corrigida depois da rodada da fase 10, então esses casos ainda não passaram pelo
   agente com a rota certa. Medir primeiro nos que estão entre os 20 difíceis.

### Médio prazo (melhorar o harness e a independência de ferramenta)

6. **Skill unificada no repo** (tarefa 4 do handoff, especificação
   `docs/superpowers/specs/2026-10-07-skill-unificada-design.md`). Tudo o que o agente precisa numa
   pasta só, sem depender do plugin instalado na máquina; backends para Codex e Gemini CLI.
7. **Comparar agentes** (Claude Code, Codex, Gemini) nos mesmos 20 casos, com a mesma skill.
8. **Harness híbrido** (parte 2 do roteiro): a LLM escreve só o driver com `assume` e `assert`; o código
   faz recorte e stubs. Permite verificar bugs de **resultado errado** com `assert` da propriedade,
   validado pela versão corrigida. Hoje esses bugs (178 de 289) quase não chegam ao ESBMC.
9. **Grafo dentro do arquivo** (parte 1 do roteiro): quem chama a função e com que contrato. Ataca os
   falsos alarmes (ir_real_03, bip_thefuck_11) e parte da falta de contexto.

### Fechamento dos números (uma vez, no fim)

10. **Rodada completa com o prompt A5** (`--v2-variants A1,A2`), seguida da validação e do
    orquestrador em cima. Leva horas; confirmar com ela antes. Dá o número final de detecção e de
    confirmação da dissertação.
11. **Controle nas versões corrigidas** para tudo o que essa rodada confirmar.

### Longo prazo (depois da qualificação, ou se sobrar tempo)

12. **Grafo do repositório e modo scan** (parte 4 do roteiro): apontar para um repositório, a LLM
    varre, o pipeline confirma. Alvo: código pouco auditado de organizações conhecidas.
13. **Caça de bugs novos:** parsers e desserializadores que leem entrada de fora (exemplo:
    CVE-2026-104020 no ion-python, recursão sem limite, creditado a Weiqi Wang e Lucas Cordeiro).
    Vale perguntar ao professor como foi achado.

## 6. Pendências pequenas (fazer só se atrapalharem)

Achados menores das revisões de código, adiados (lista completa nos ledgers
`.superpowers/sdd/2026-10-06-*/progress.md`):

- a retomada não percebe mudança no texto das variantes do prompt;
- a checagem de alcance não reaproveita o solver da rodada original;
- mutantes em linhas com duas instruções saem quebrados;
- o script de união não confere se as rodadas têm a mesma configuração;
- a rota quebra se o motivo vier como `None`; um braço sem `verdict` derruba a rodada;
- o braço dinâmico não guarda a entrada que quebrou (a tarefa 2 resolve);
- a configuração do orquestrador não inclui todas as opções.

## 7. Para a dissertação: o que já dá para afirmar

- A LLM acha a função do bug em cerca de dois terços dos casos e a linha em cerca de um terço; com o
  prompt A5 a linha sobe cerca de 50% na amostra.
- A LLM não altera a função verificada (0 em 23), e o controle nas versões corrigidas separa bug real
  de falso alarme.
- O gargalo da confirmação formal é o próprio ESBMC-Python e a montagem do harness, não a detecção:
  a LLM entrega a linha certa em dezenas de casos que não chegam a veredito.
- A execução no CPython acha quebras onde o ESBMC trava, o que motiva a combinação das ferramentas
  (entrada fixada).

Limitações a declarar: a função é verificada sem o contrato de quem a chama; os mutantes ainda não
mediram nada; 50 bugs só mostram diferenças grandes entre prompts.
