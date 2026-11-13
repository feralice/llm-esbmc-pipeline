# Varredura do Adafruit CircuitPython GPS (12/11/2026)

Primeira varredura de um repositório ciberfísico real com o comando `llm-esbmc scan`, pela assinatura Claude.

## O que foi

- Alvo: `adafruit/Adafruit_CircuitPython_GPS`, commit `c67a122`, clone raso em `~/cps_scan/` (fora do projeto).
- Código do pipeline: `master` em `44ce2a8` (merge de `feat/workers`), com a CLI `llm-esbmc` (commit `da13a4d`).
- Comando:

```
llm-esbmc scan ~/cps_scan/Adafruit_CircuitPython_GPS --backend claude --yes --out artifacts/cps/gps
```

- Saída: `artifacts/cps/gps/` (fora do git). Relatório em `relatorio.md` e `scan_summary.md`. Testes gerados em `agent_cases/<id>/pytest/test_replay.py`.
- Início: 12/11/2026, por volta das 13h. Fim: 12/11/2026, antes das 16h33 (horário local).

## Números

- Grafo: 41 funções em 8 módulos. 71 de 276 chamadas resolvidas dentro do repo.
- Detecção: 39 funções analisadas, sem erro. 35 hipóteses foram ao ESBMC. 21 ficaram só com a LLM.
- Custo: detecção com custo equivalente de US$ 0,38 (valor que a API cobraria). Não cobrado, porque é assinatura. A verificação não tem total no relatório (`null`). Então o custo real da rodada é maior que o da detecção, e não consigo dar esse número.

Vereditos das 35 hipóteses verificadas:

| Veredito | Quantas |
|---|---:|
| CONFIRMED | 2 |
| REPRODUCED_CPYTHON | 4 |
| ESBMC_MISSED | 3 |
| NOT_CONFIRMED | 7 |
| NOT_CONFIRMED_VACUOUS | 1 |
| UNVALIDATED | 1 |
| UNSUPPORTED | 10 |
| BOUND_INCONCLUSIVE | 1 |
| AGENT_FAILED | 4 |
| ESBMC_ERROR | 2 |

## Resultados

**Confirmados pelo ESBMC (2).** Os dois são o mesmo padrão: `_parse_float` faz `float(nmea_data)` e `_parse_int` faz `int(nmea_data)`, e o ESBMC provou o `ValueError` para a entrada `'a'`. O alcance real é limitado: o driver valida o checksum antes de chegar a esses campos, então só uma sentença NMEA com checksum válido e texto onde deveria haver número chega lá. A função `_parse_time` do mesmo driver trata esse caso, e `_parse_float` não. É candidato a melhoria, não bug confirmado.

**Reproduzidos só no CPython (4).** O ESBMC não decidiu, mas o programa gerado levanta a exceção com entradas simples:
- `_read_deg_mins` e `_read_degrees`: `IndexError` em listas curtas, e `AttributeError` com um campo vazio.
- `GPS_GtopI2C.readline`: `TypeError` na comparação de prazo.

Isso é evidência de execução. Não prova que o estado é alcançável com dado real do receptor. Para cada um, falta uma sentença NMEA real que chegue a esse ponto.

**Suspeitas só da LLM (21).** Ficaram fora do ESBMC. A maioria é texto plausível sem verificação, e algumas leituras que conferi parecem erradas (por exemplo, a de `_parse_gsa` sobre o intervalo `data[2:-4]`). Não tratar como bug sem leitura manual.

## Falhas

- **AGENT_FAILED (4):** um agente não escreveu o `harness.py`; dois não acharam a expressão suspeita no corpo da função; um estourou o tempo (`TimeoutExpired`). Não investiguei cada caso a fundo.
- **ESBMC_ERROR (2):** SIGSEGV do próprio ESBMC, em dois harnesses. Pode ser bug do ESBMC. Antes de qualquer issue, precisa de reprodução mínima e de conferir se já há issue ou contorno, pela regra do projeto.
- **BOUND_INCONCLUSIVE (1):** a verificação parou no limite de laço (`unwinding assertion loop 3`). Não é prova de ausência de bug.

## Limites desta rodada

- Nada aqui foi lido à mão além dos casos citados. Achado do ESBMC não virou issue, e nenhuma issue foi aberta.
- O replay roda o programa gerado, não o projeto. "Reproduzido" significa só "o programa gerado levanta a exceção".
- A rodada usa a configuração padrão do scan, sem as flags novas (`--workers`, `--detection-cache`, `--heal-triage`).
- Custo da verificação não foi medido.

## Próximos passos sugeridos

1. Ler os 4 `REPRODUCED_CPYTHON` e os 2 `CONFIRMED` contra sentenças NMEA reais, para separar bug de alcance.
2. Investigar os 2 SIGSEGV do ESBMC com reprodução mínima.
3. Seguir a fila do plano de 19/10 (pynmea2, pynmeagps, pyrtcm, pyubx2, minimalmodbus e os drivers BME280 e LSM6DS), um repositório por vez, sempre com simulação antes.
