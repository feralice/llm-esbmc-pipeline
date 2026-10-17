# Passo 1 do item 6: auditoria da rodada final (16/10/2026)

Rodada auditada: `artifacts/v2/final-2026-10-15-codex` (detecção Claude Sonnet, spec misto Sonnet/Codex,
ESBMC master 333d07cc8a). Nenhuma chamada de LLM nesta auditoria. Gabarito novo (Fase 17).

## 1. Funil por bug

Script: `scripts/v2_funnel.py artifacts/v2/final-2026-10-15-codex --out artifacts/v2/funil-2026-10-16`.
Cada bug fica na etapa mais avançada alcançada por uma hipótese **na linha do bug** (causa do patch ou
linha da quebra). Uma confirmação do orquestrador nessa linha conta como confirmada.

| Etapa onde parou | Exceção (111) | Resultado errado (178) | Total (289) |
|---|---|---|---|
| Fora da rodada (contexto de patch) | 0 | 12 | 12 |
| Sem hipótese (o LLM não achou bug) | 6 | 41 | 47 |
| Hipótese fora da linha do bug | 38 | 80 | 118 |
| Cortado pelo limite do LLM | 31 | 8 | 39 |
| Harness não montado | 0 | 1 | 1 |
| ESBMC recusou | 26 | 26 | 52 |
| ESBMC rodou sem confirmar | 5 | 8 | 13 |
| Confirmado | 5 | 2 | 7 |

"Exceção" soma excecao_local (59), excecao_modelavel (23), excecao_nao_modelavel (24) e incerto (5).

Leitura:
- Os bugs de resultado errado não tinham como ser confirmados nesta rodada (o oráculo de valor, item 5,
  veio depois). Os 2 "confirmados" (av_real_07, ip_real_22) quebraram com uma exceção que não é o bug do
  gabarito e não entram na métrica.
- Nos 111 bugs de exceção, as três perdas grandes têm tamanhos parecidos: 38 com a hipótese fora da linha
  (detecção), 31 nunca verificados por falta de limite do LLM (refazer na semana 4, sem mudar código) e
  26 recusados pelo ESBMC (alvo do piloto da semana 2).
- Contada por hipótese (564), a recusa do ESBMC parecia o gargalo (185 hipóteses). Contada por bug e na
  linha, ela é uma das três perdas, não a maior.

## 2. Os 71 vereditos do ESBMC sem confirmação

Só 18 das 71 hipóteses estão na linha do bug.

| Motivo | Hipóteses | Na linha | Bugs na linha |
|---|---|---|---|
| ESBMC: sem violação dentro do limite | 27 | 6 | av_real_14, bip_scrapy_15, bip_thefuck_19, bip_thefuck_25, bip_tornado_5 |
| ESBMC achou, Python quebrou com outro erro | 12 | 1 | bip_black_21 |
| ESBMC disse seguro, mas o Python quebra | 10 | 5 | bip_keras_25, bip_scrapy_21, bip_youtube_dl_43, ip_real_22 |
| ESBMC achou, replay indisponível | 9 | 2 | bip_keras_38, bip_youtube_dl_41 |
| ESBMC achou, Python não reproduziu | 6 | 1 | bip_thefuck_10 |
| ESBMC: só limite de laço curto | 4 | 3 | bip_thefuck_30, ip_real_07 |
| ESBMC achou outra exceção que o Python | 3 | 0 | |

Leitura:
- "ESBMC disse seguro, mas o Python quebra" é o caso mais informativo: o código original quebra com uma
  entrada concreta, e o ESBMC não vê. É lacuna de modelagem (do harness ou do ESBMC), candidata ao piloto e
  a issue.
- "Só limite de laço curto" pede limite maior, não técnica nova.

## 3. Auditoria das confirmações com a versão corrigida

Script: `scripts/v2_audit_control.py <v2_verify_report.json> --out artifacts/v2/auditoria-2026-10-16`. As 24
hipóteses CONFIRMED foram verificadas de novo no ESBMC v8.6 com os specs gravados (todas continuam
CONFIRMED), e a entrada que quebrou foi dada à versão corrigida da função.

Regra: a confirmação cai só se a versão corrigida levanta **a mesma exceção**. Outra exceção é mudança de
comportamento: a correção pode levantar um erro mais claro para a mesma entrada (dz_real_03 passa a
levantar `CroniterBadCronError("Bad range")`) ou usar um nome que o harness não montou (av_real_02 usa
`self.ws_connection`).

| | Vale | Correção muda o comportamento | Corrigida quebra igual | Sem controle |
|---|---|---|---|---|
| Na linha do bug (7) | 1 (av_real_01) | 4 (av_real_02, av_real_07, dz_real_03 ×2) | 1 (ip_real_22) | 1 (bip_scrapy_15) |
| Fora da linha (17) | 0 | 1 | 10 | 6 |

Leitura:
- Nenhuma confirmação da métrica cai. ip_real_22 quebra igual na corrigida, mas não contava (gabarito de
  resultado errado).
- Fora da linha, 10 de 17 confirmações quebram igual na versão corrigida: entradas que quebram até o código
  consertado. O controle separa esses casos, e a métrica final deve exigi-lo.
- "Sem controle" vem de a função corrigida não caber no programa de replay (6) ou de a entrada ter mais
  valores que o programa usou (bip_scrapy_15). Melhorar isso é candidato à semana 3.
- dz_real_02 (da métrica) veio do braço `pinned` do orquestrador e não está entre as 24; fica para a
  auditoria da semana 4.

## 4. Candidatos ao piloto da semana 2

31 bugs de exceção chegaram ao ESBMC na linha do bug e não confirmaram, com 22 causas diferentes. O piloto
pega um bug por causa (20), sem as duas causas de ambiente (resultado inconclusivo em bip_pandas_142,
tempo esgotado em bip_scrapy_18).

| # | Bug | O que travou |
|---|---|---|
| 1 | bip_keras_23 | dependência: `Function "layer" not found` |
| 2 | bip_keras_33 | nome do Python 2 ausente: `unicode` |
| 3 | bip_youtube_dl_30 | dependência: `Object "m" not found` |
| 4 | av_real_03 | `Type inference failed ... Variable func not found` |
| 5 | bip_black_16 | `yield from is not supported for generator inlining` |
| 6 | bip_luigi_21 | função que se referencia (`setup_interface_logging`) |
| 7 | bip_pandas_104 | chamada externa que não vira stub (`base.OutputKey(...)`) |
| 8 | bip_pandas_133 | tipo do receptor sem resolução (`._AXIS_ALIASES.get()`) |
| 9 | bip_pandas_160 | atributo aninhado (`name`) |
| 10 | bip_pandas_33 | tipo de atributo de classe (`na_value`) |
| 11 | bip_pandas_34 | classe não definida no ponto de uso (`C@Grouper`) |
| 12 | bip_pandas_7 | classe com `__new__` próprio |
| 13 | bip_scrapy_40 | `**kwargs` dentro de método (`kwargs` não definido) |
| 14 | ip_real_11 | função `async` |
| 15 | ip_real_14 | desempacotamento de vazio |
| 16 | ip_real_16 | `DataFrame` não definido |
| 17 | ip_real_17 | `%` com argumento não constante |
| 18 | ip_real_32 | indexação avançada (`fancy indexing`) |
| 19 | bip_keras_25 | ESBMC diz seguro, o Python quebra |
| 20 | ip_real_07 | só limite de laço curto |

Os outros 9 (bip_matplotlib_28, bip_pandas_162, bip_youtube_dl_4, bip_pandas_152, bip_thefuck_4,
ip_real_21, bip_scrapy_21, bip_black_21, bip_keras_38) repetem causas da lista e ficam como reserva, sem
uso no desenvolvimento, para testar se as intervenções da semana 3 generalizam.

Observação: bip_luigi_21, bip_pandas_33 e ip_real_14 já estão na métrica (confirmados pelo agente em
rodadas anteriores), mas o motor normal recusa. O piloto mostra o que o agente fez que o motor não faz.

## 5. O que a troca para o ESBMC v8.6 mudou nos 20 do piloto (sem LLM)

`scripts/v2_replay_specs.py` com os specs gravados, saída em `artifacts/v2/piloto-86/`:
- **ip_real_17**: UNSUPPORTED → **CONFIRMED** na linha do bug (`TypeError` em
  `to_native_str(http.RESPONSES.get(int(status)))`, sem tipos preenchidos). A correção acrescenta o padrão
  `"Unknown Status"`. O controle com a versão corrigida dá `NameError` (o harness não roda a corrigida), então
  é "correção muda o comportamento", não controle limpo. Candidato novo à métrica.
- **ip_real_07**: NOT_CONFIRMED → UNVALIDATED (o ESBMC passa a achar os erros de `int()`; o replay ainda não
  reproduz na linha).
- **bip_pandas_33**: o "aceito na v8.6" desta rodada não se sustenta. A lista de hipóteses tinha ids
  repetidos e dois pedaços gravaram no mesmo arquivo de programa; o programa em disco é recusado
  (`piloto_semana2_2026-10-16.md`).
- Os outros 17 continuam com a mesma recusa.

Observação para a semana 3: "correção muda o comportamento" junta casos legítimos (dz_real_03 levanta um
erro novo de propósito) e casos em que o harness não roda a versão corrigida (av_real_02, ip_real_17). Fazer
o controle rodar a corrigida com fidelidade é candidato a intervenção.
