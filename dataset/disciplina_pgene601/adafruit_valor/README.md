# Bugs de valor errado em drivers de sensores da Adafruit (PGENE601)

Subconjunto do dataset da disciplina para testar a hipótese da especificação: usar o requisito do
datasheet como propriedade de verificação. Os 47 bugs da pasta acima levantam exceção; estes quatro não
levantam nada, o driver só devolve um número errado. Cada item traz um bloco `datasheet` com o requisito,
a pré-condição que mantém a leitura fisicamente válida, a pós-condição que o driver tem que cumprir e a
fonte. O formato é o mesmo da pasta acima, com `failure_kind = resultado_errado`.

| id | PR | função | bug | propriedade do datasheet |
|---|---|---|---|---|
| `ada_shtc3_5` | [SHTC3#5](https://github.com/adafruit/Adafruit_CircuitPython_SHTC3/pull/5) | `SHTC3.measurements` | valor cru lido com sinal (`">h"`); acima de 42,5 °C a temperatura sai negativa | com `1873 <= S_T <= 63663` e CRC certo, `-40 <= temperature <= 125` |
| `ada_max31855_11` | [MAX31855#11](https://github.com/adafruit/Adafruit_CircuitPython_MAX31855/pull/11) | `MAX31855.reference_temperature` | fator 0,625 em vez de 0,0625 °C por LSB | com a junção fria de 12 bits em `-640..2000` e sem falha, `-40 <= reference_temperature <= 125` |
| `ada_tsl2591_6` | [TSL2591#6](https://github.com/adafruit/Adafruit_CircuitPython_TSL2591/pull/6) | `TSL2591.lux` | saturação testada só em 65535; com 100 ms o canal satura em 36863 | se `lux` devolve valor com 100 ms, `channel_0 < 36863` e `channel_1 < 36863` |
| `ada_tsl2591_34` | [TSL2591#34](https://github.com/adafruit/Adafruit_CircuitPython_TSL2591/pull/34) | `TSL2591.visible` | luz visível montada como 32 bits juntando os dois canais | com `channel_1 <= channel_0`, `0 <= visible <= 65535` |

Fontes dos requisitos: datasheet do SHTC3 (Sensirion), do MAX31855 (Analog Devices) e do TSL2591 (ams),
com os links no campo `datasheet.source` de cada item. Os limites foram conferidos nessas fontes em
18/10/2026.

## Fora do subconjunto

- **MCP9808#5** (bit de sinal lido ao contrário, temperatura negativa sai positiva): `MCP9808.temperature`
  tem getter e setter com o mesmo nome, e nem o construtor nem o aterramento do pipeline sabem qual dos
  dois é o alvo. Além disso, a faixa de -40 a 125 °C não pega esse bug (`256 - x` fica entre 0 e 40 °C); a
  propriedade teria que usar o bit de sinal do registrador.
- **BME680#14** (compensação de pressão) e **BME680#24** (`filter_size`): o primeiro depende dos coeficientes
  de calibração gravados no chip, e o segundo levanta exceção, que é o caso da pasta acima.

## Como foi montado e conferido

`scripts/build_pgene601_adafruit.py` baixa as duas versões de cada arquivo, recorta a função e confere que a
expressão existe na função com bug e que o patch a altera. `scripts/pgene601_check_datasheet_props.py`
roda as duas versões no CPython, com o hardware trocado por leituras de registrador, e varre as entradas
permitidas pela pré-condição (o SHTC3 e o MAX31855 inteiros; os canais do TSL2591 numa grade de 424 valores,
bordas incluídas):

| id | violações com bug | violações na corrigida |
|---|---|---|
| `ada_shtc3_5` | 30896 | 0 |
| `ada_max31855_11` | 2376 | 0 |
| `ada_tsl2591_6` | 122760 | 0 |
| `ada_tsl2591_34` | 89676 | 0 |

## O que falta para o pipeline usar

Hoje o oráculo de valor (variante A15) pede à LLM a pós-condição. Para testar a hipótese, o pipeline
precisa receber a pós-condição e a pré-condição do campo `datasheet`, e o harness precisa montar o
registrador como bytes livres sob a pré-condição. Fica para depois da rodada final da dissertação, porque
mexe no código compartilhado. As sondas de 18/10 (`docs/pgene601/pgene601_sondas_e_mypy_2026-10-18.md`)
mostram que `struct.unpack` e `unpack_from` são recusados pelo ESBMC v8.6, o que afeta o SHTC3 e o
MAX31855.
