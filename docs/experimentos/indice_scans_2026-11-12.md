# Índice dos scans em repositórios reais (12/11/2026)

Índice único dos scans de hoje. Cada linha aponta para o registro completo e para a saída em `artifacts/`.
Resultados que ainda não estão no artigo ficam marcados como pendentes.

## Ciberfísicos (CLI `llm-esbmc scan`, assinatura Claude)

| Repositório | Commit | Estado | Funções (ok/erro) | Hipóteses verificadas | CONFIRMED | Avaliação | Saída | Registro |
|---|---|---|---|---|---|---|---|---|
| Adafruit_CircuitPython_GPS | c67a122 | concluído | 39 | 35 | 2 | os 2 não chegam ao usuário; achado real do LLM (GSA 17 campos, issue #132) | `artifacts/cps/gps/` | `scan_cps_gps_2026-11-12.md` |
| pynmea2 | d8240dc | em andamento | 93 | 14 até 20h48 | 2 | mesmo bug da PR #189 do repo | `artifacts/cps/pynmea2/` | pendente |
| pyserial (completo) | a5c48d4 | em andamento | 98 de 346 até 20h48 | 0 | - | pendente | `artifacts/cps/pyserial-full/` | pendente |
| paho.mqtt.python | e3eab73 | na fila 1 (30 funções) | - | - | - | pendente | `artifacts/cps/paho.mqtt.python/` | pendente |
| cantools | 2e4bbb8 | na fila 1 (30 funções) | - | - | - | pendente | `artifacts/cps/cantools/` | pendente |
| pymodbus | 7509a6b | na fila 2 (30 funções) | - | - | - | pendente | `artifacts/cps/pymodbus/` | pendente |
| gpiozero | 4e60a6a | na fila 2 (30 funções) | - | - | - | pendente | `artifacts/cps/gpiozero/` | pendente |
| python-can | 86e8579 | na fila 2 (30 funções) | - | - | - | pendente | `artifacts/cps/python-can/` | pendente |
| bleak | - | na fila 3 (30 funções) | - | - | - | pendente | `artifacts/cps/bleak/` | pendente |
| pyvisa | a5b56ab | na fila 3 (30 funções) | - | - | - | pendente | `artifacts/cps/pyvisa/` | pendente |

Filas: `artifacts/cps/fila.log`, `fila2.log`, `fila3.log`. Retomada de cota: `scripts/scan_com_retomada.sh`.

## Amazon (aws-samples), backend Codex

| Repositório | Estado | Funções (ok/erro) | Hipóteses | Vereditos | Avaliação | Saída | Registro |
|---|---|---|---|---|---|---|---|
| sam-python-crud-sample (piloto, 11/11) | concluído | 5 (4 ok, 1 erro) | 16 | 3 CONFIRMED, falsos positivos (API Gateway envia `httpMethod`) | nenhum bug | `artifacts/scan_amazon_2026-11-11/sam-python-crud-sample/` | `docs/projeto/nota_contexto_framework_scan_amazon_2026-11-11.md` |
| aws-secrets-manager-rotation-lambdas | concluído | 40 (39 ok, 1 erro) | 84 | 26 verificações: 3 CONFIRMED, 10 PIPELINE_ERROR, 4 ESBMC_TIMEOUT, 3 UNVALIDATED, 3 OTHER_FAILURE, 2 ESBMC_ERROR, 1 LLM_ONLY | os 3 CONFIRMED não são bugs reportáveis: 2 exigem segredo binário, fora do contrato documentado (`SecretString` em JSON); 1 exige item não-texto em `permissions`, entrada malformada | `artifacts/scan_aws_codex_2026-11-12/rotation/` | `docs/experimentos/scan_repos_aws_codex_2026-11-12.md` |
| aws-glue-samples | concluído parcialmente | 40 (36 ok, 4 erro) | 71; 12 verificadas | 11 PIPELINE_ERROR (timeout do Codex e `workspace routing discovery failed`), 1 LLM_ONLY | falha de infraestrutura do Codex, nenhum veredito sobre o código | `artifacts/scan_aws_glue_codex_2026-11-12/` | `docs/experimentos/scan_repos_aws_codex_2026-11-12.md` |

Problema conhecido: o `relatorio.md` do secrets rotation foi gerado durante uma falha do Codex e não foi refeito
depois da retomada. Não citar esse arquivo; refazer o relatório a partir do checkpoint.

## Achados classificados

| Achado | Repositório | Classificação | Ação |
|---|---|---|---|
| GSA de 17 campos perde o 12º satélite | Adafruit GPS | bug real, achado por leitura do LLM e confirmado à mão | issue #132 aberta |
| `ASH`/`TNLDG` levantam `IndexError` com sentença proprietária truncada | pynmea2 | bug real, contrato de `parse` violado | já reportado: PR #189 aberta, sem issue nova |
| `ValueError` em `_parse_float`/`_parse_int` | Adafruit GPS | não alcançável pelo caminho público, capturado em `_parse_data` | nenhuma |
| `httpMethod` ausente | sam-python-crud-sample | falso positivo, entrada que a plataforma não envia | nenhuma |
| `SecretString` ausente (MongoDB, RDS MariaDB) | secrets rotation | fora do contrato documentado (segredo binário) | talvez melhorar a mensagem de erro; não é bug |
| `permissions` com item não-texto | secrets rotation | entrada malformada | talvez validar; não é bug |

## Melhorias no pipeline identificadas hoje

1. **Contexto de exceções dos chamadores** (`fix/caller-exception-context`): evita `CONFIRMED` quando todo chamador captura a exceção. Pendente: variante A21 ainda não funciona com o prompt padrão.
2. **Tabela de roteamento de prompts** (`docs/projeto/tabela_roteamento_prompts_v1.md`): escolha de variantes por característica do AST. Não implementada; aguarda decisões.
3. **Pedido de alcance pela entrada pública** no prompt de detecção e no contrato da entrada (ex.: API Gateway, NMEA com checksum).
4. **Falhas de infraestrutura separadas no relatório**: `PIPELINE_ERROR` por timeout ou roteamento do Codex não deve aparecer como veredito sobre o código.
5. **Relatório refeito após retomada**: hoje o `relatorio.md` pode ficar com dados de uma falha antiga.
6. **Retomada de cota** na CLI: já existe `--resume` e `scripts/scan_com_retomada.sh`; falta usar nas filas.
7. **Limpeza de clones**: `mainframe-data-utilities` removido; GPS e sam mantidos por rastreabilidade.

## Pendências gerais

- Concluir os scans das filas e do pyserial completo, e registrar cada um aqui.
- Refazer o relatório do secrets rotation a partir do checkpoint.
- Decidir sobre comentar na PR #189 com os casos ASH e TNL (ação pública; precisa de OK).
- Investigar a falha de roteamento do Codex antes de repetir o Glue.
