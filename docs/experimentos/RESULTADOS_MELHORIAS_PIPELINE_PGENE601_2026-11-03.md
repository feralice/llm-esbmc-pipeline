# Resultados parciais das melhorias do pipeline — PGENE601

**Data:** 03/11/2026

**Fonte:** checkpoint parcial da rodada Codex PGENE601, copiado para
`artifacts/pgene601/melhorias-2026-11-03/baseline_checkpoint.json`.
O arquivo original tinha 36 verificações concluídas de 232 hipóteses distintas e ainda estava marcado como `running`.
O SHA-256 e o commit usado estão em `baseline_snapshot.json`, na mesma pasta.
Havia alterações locais nos módulos de verificação antes desta rodada; o commit sozinho não reproduz todo o estado de código.

## Timeout: três hipóteses do GPS

Copiei os três programas já gerados e executei o mesmo ESBMC 8.6.0 (`d520a903aef7f9585355e07e1fb92cb16982c588`),
com o mesmo bound 5, solver padrão Bitwuzla e demais opções do baseline. Só o limite de cada chamada mudou
de 180 para 300 s. Os logs e o comando de cada execução estão em `timeout-300/results.json`.

| Hipótese | Antes, 180 s | Depois, 300 s | Tempo da nova execução | Leitura |
| --- | --- | --- | ---: | --- |
| `67e38056f77f`, `int(raw[0])` | `ESBMC_TIMEOUT` | `violation_found` | não registrado¹ | `ValueError` em `int(raw[0])`; não é o defeito oficial |
| `0f099ccc2b47`, `raw[1][:4]` | `ESBMC_TIMEOUT` | `violation_found` | 247,065 s | Inclui `IndexError` em `raw[1]`, ligado ao defeito oficial |
| `ea8f3d26e5fe`, `int(f'{raw[1][:4]:0<4}')` | `ESBMC_TIMEOUT` | `violation_found` | 236,489 s | Inclui `IndexError` em `raw[1]`, ligado ao defeito oficial |

¹ O primeiro comando concluiu e salvou o log bruto, mas o script que registrava a duração falhou logo depois.
Seu log mostra 193,763 s de tempo total do procedimento de decisão do solver; esse número não é a duração completa da execução.

No código original com bug, `_parse_degrees('123')` produz `IndexError: list index out of range` e
`_parse_degrees('abc')` produz `ValueError`. Essas chamadas demonstram as falhas no código original,
mas o log do ESBMC não forneceu uma string concreta para afirmar que são os mesmos contraexemplos simbólicos.
Os três logs também contêm falhas de *unwinding* nas bibliotecas; portanto, o resultado não é uma prova
de todas as propriedades do programa. Dois harnesses chegaram à exceção rotulada; ambos pertencem ao mesmo bug GPS.
Como todos produziram um resultado antes de 300 s, não executei a etapa opcional de 600 s.

## Redução de hipóteses: análise sem LLM

O script `artifacts/pgene601/melhorias-2026-11-03/offline_analysis.py` lê a ordem original dos candidatos.
Ele agrupa somente candidatos do mesmo arquivo e função cuja expressão tem a mesma árvore sintática.
O gabarito é consultado apenas depois da seleção, para medir quantos bugs permanecem apontados.

| Seleção | Hipóteses | Bugs apontados na linha | Precisão retrospectiva |
| --- | ---: | ---: | ---: |
| Todas as hipóteses distintas | 232 | 39 | 54/232 = 23,3% |
| Primeira por função | 48 | 18 | 19/48 = 39,6% |
| Duas primeiras por função | 88 | 23 | 31/88 = 35,2% |
| Três primeiras por função | 117 | 26 | 37/117 = 31,6% |
| Até 12 por função | 222 | 39 | 54/222 = 24,3% |

Os 253 candidatos brutos viraram os mesmos 232 itens distintos já registrados; a normalização sintática
não reduziu mais a fila. O limite de 12 poupa 10 verificações nesta amostra sem perder os 39 bugs apontados,
mas foi escolhido após observar a cobertura retrospectiva. Precisa ser testado em outra amostra antes de
ser usado como regra operacional. Não houve nova síntese por LLM nem execução formal dessa fila reduzida;
economia de tempo e de chamadas ainda não foi medida.

## Obstáculos do ESBMC e papel da LLM

As hipóteses MAVProxy `c5fed455c120` e `e61ea670930d` pararam na recusa
`unsupported: non-constant argument in str % formatting`. A tentativa inicial de self-healing no sandbox
falhou antes de obter resposta do modelo porque o Codex CLI não conseguiu iniciar ali. A nova tentativa
fora do sandbox foi interrompida quando Fernanda esclareceu a regra: a LLM deve somente apontar o possível erro.
Não há resultado novo de reparo para esses dois casos. Os artefatos das tentativas interrompidas ficaram
em pastas separadas e não entram na comparação.

O pipeline já começa com bound 5 e aumenta o *unwind* quando o ESBMC relata apenas limite insuficiente;
ele também tenta outros solvers após timeout. Estes resultados apoiam testar 300 s nos casos GPS que
excederam 180 s, mas não justificam mudar o bound global. A preparação do código para o verificador
precisa ser determinística e conferir que preserva a expressão suspeita e o comportamento original.

Um terceiro caso MAVProxy (`945a54672935`) produziu uma falha interna do ESBMC/solver com uma tupla
opcional. Reproduzi a falha com 18 linhas em `artifacts/pgene601/melhorias-2026-11-03/esbmc_issue_repro.py`.
O rascunho para uma issue está em `docs/experimentos/ISSUE_ESBMC_OPTIONAL_TUPLE_DRAFT.md`.
**Nenhuma issue foi aberta.**

**Uso de IA neste registro:** Codex auxiliou a executar comandos, conferir logs, calcular as tabelas e redigir
este registro técnico. As propostas de configuração e interpretação exigem avaliação da autora antes de
integrarem o método ou as conclusões da pesquisa.
