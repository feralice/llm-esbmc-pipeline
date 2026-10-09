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

## 5. O que falta, em ordem (combinado em 08/10)

Para **terminar o pipeline**:

1. **Medir a entrada fixada** nos 20 casos difíceis (braço `pinned`, `verify/pinned.py`): o ESBMC
   prova só o caminho da entrada que a busca no CPython achou. Rodando.
2. **Prazo da passada aleatória** no executor do CPython (achado I1 da revisão): o teste já existe
   (`test_the_random_pass_gets_time_even_when_every_exhaustive_run_is_slow`), falta o código.
3. **Juntar o branch no `master`** (ela roda o comando de junção).
4. **Rodada final, uma vez**: `scripts/run_final.sh <data>`. Detecção com o prompt A5, harness nível 1,
   ESBMC, orquestrador sem agentes (busca no CPython e entrada fixada), controle nas versões
   corrigidas e validação. Dá os números da dissertação.
5. **Registrar os números finais** em `docs/experimentos/` (fase 11) e atualizar este arquivo.

Depois de terminar:

6. **Skill unificada e agente único**: as regras do harness numa pasta só do repo
   (`skills/esbmc-python-harness/`), e um único caminho "agente" no orquestrador em que a pessoa escolhe
   a LLM (Claude Code, Codex, Gemini CLI ou qualquer API). Especificação:
   `docs/superpowers/specs/2026-10-07-skill-unificada-design.md`.
7. **Grafo dentro do arquivo**: quem chama a função e com que contrato (falsos alarmes, falta de
   contexto).
8. **Harness para bugs de resultado errado** (`assert` da propriedade, validado pela versão corrigida).
9. **Grafo do repositório e modo scan**; caça de bugs novos.
10. **Virar ferramenta para bugs novos** (ideia de 08/10): primeiro um comando de terminal
    (`llm-esbmc scan <repositório>`), depois plugin de agente ou servidor MCP em cima da skill do
    item 6; extensão de editor e GitHub Action ficam por último. Precisa de varredura do repositório
    (grafo), relatório legível (linha, entrada que quebra, contraexemplo, script de reprodução) e de
    confiança sem versão corrigida (só ESBMC mais CPython). Antes disso, o método é validado nos bugs
    reais conhecidos (dissertação).

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
