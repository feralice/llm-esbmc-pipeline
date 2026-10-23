# Base do item 6b: recusas do ESBMC na rodada final (19/10/2026)

Fonte: `artifacts/v2/final-2026-10-17/v2_verify_report.json` (ESBMC v8.6). Das 742 hipóteses, 288 terminaram
UNSUPPORTED (84 mensagens distintas depois de trocar nomes, números e arquivos por marcadores). Para a métrica
contam só as hipóteses **na linha do bug** (`v2_evaluator.at_bug_line`) de bugs ainda não confirmados:
**96 hipóteses em 73 bugs**. É a base do 6b.

| Bugs | Hipóteses | Recusa | Origem | Exemplos |
|---|---|---|---|---|
| 7 | 11 | a classe do alvo define `__new__`; o receptor não consegue herdar dela | harness | bip_pandas_106, 141, 143, 29 |
| 6 | 6 | `Could not resolve type of receiver in member call` | frontend | bip_keras_36, bip_thefuck_3, 4, ip_real_03 |
| 5 | 6 | arquivo não suportado (módulo ausente ou recurso não implementado) | frontend | bip_keras_33, bip_pandas_95, bip_spacy_1, bip_youtube_dl_5 |
| 4 | 6 | `Cannot infer type for class attribute` | frontend | bip_pandas_24, 25, 33, 52 |
| 3 | 5 | `NameError: name ... is not defined` | frontend | bip_ansible_16, ip_real_20, ip_real_23 |
| 3 | 6 | `Variable ... is not defined in function` | frontend | bip_keras_4, bip_luigi_21, tm_real_13 |
| 3 | 3 | `list indices must be integers or slices, not str` | frontend | nm_real_03, nm_real_23, oob_real_11 |
| 2 | 3 | `Cannot unpack empty` | frontend | bip_keras_40, bip_matplotlib_11 |
| 2 | 2 | tipo de entrada fora do subconjunto do harness | harness | bip_matplotlib_2, bip_pandas_166 |
| 2 | 2 | `'X' object is not subscriptable` | frontend | bip_pandas_115, dz_real_01 |
| 2 | 2 | `Type inference failed ... Variable func not found` | frontend | bip_pandas_152, 21 |
| 2 | 2 | `Cannot resolve nested attribute` | frontend | bip_pandas_160, tm_real_06 |
| 2 | 2 | oráculo de valor sem valor devolvido (construtor) | harness | bip_pandas_64, bip_scrapy_28 |
| 2 | 2 | `non-constant argument in str % formatting` | frontend | bip_scrapy_18, nm_real_04 |
| 2 | 2 | ponto de entrada `async` | harness | ip_real_11, ip_real_13 |
| 1 cada | | outras mensagens, uma por bug | | |

Leitura:
- A cauda é longa: as sete primeiras mensagens cobrem no máximo 31 dos 73 bugs (um bug pode aparecer em mais de uma). Nenhuma regra sozinha muda muito.
- Quatro linhas são do próprio harness (`__new__`, tipo de entrada, construtor no oráculo de valor, `async`),
  não do ESBMC: 13 bugs que se resolvem no pipeline, sem esperar o frontend.
- Pelo piloto (Fase 20), cada bug tem de 2 a 4 obstáculos em cadeia: tirar uma recusa costuma levar o bug
  ao obstáculo seguinte, não à confirmação. O ganho do 6b se mede em bugs que chegam a um veredito do
  ESBMC, além de bugs confirmados.
- Antes do 6b, a reverificação com o ESBMC master de 19/10 (`df93f12`) mostra quais dessas recusas o
  próprio ESBMC já resolveu; o 6b começa pelo que sobrar.
