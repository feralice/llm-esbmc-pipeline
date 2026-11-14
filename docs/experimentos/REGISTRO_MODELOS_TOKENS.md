# Modelos e tokens de cada rodada

Gerado por scripts/registro_rodadas.py a partir dos relatórios gravados. Backend claude_cli usa a assinatura: o custo em dólar não existe, só tokens.

| Pasta | Data | Tipo | Modelo | Backend | Variantes | Hipóteses | Tokens detecção | Tokens síntese/spec |
|---|---|---|---|---|---|---:|---:|---:|
| exp-2026-09-29-oracle-fixed | 2026-09-29 | dataset | gpt-4o-mini | openai |  | 125 | n/d | 188517 |
| exp-2026-09-29-oracle-repair | 2026-09-29 | dataset | gpt-4o-mini | openai |  | 125 | n/d | 345539 |
| exp-2026-09-29-oracle-resample | 2026-09-29 | dataset | gpt-4o-mini | openai |  | 125 | n/d | 354061 |
| exp-oracle-fixed-cobertura | 2026-09-29 | dataset | gpt-4o-mini | openai |  | 125 | n/d | 239637 |
| exp-oracle-repair-cobertura | 2026-09-29 | dataset | gpt-4o-mini | openai |  | 125 | n/d | 417197 |
| exp-oracle-repair-rep2 | 2026-09-29 | dataset | gpt-4o-mini | openai |  | 125 | n/d | 356258 |
| exp-oracle-repair-rep3 | 2026-09-29 | dataset | gpt-4o-mini | openai |  | 125 | n/d | 363836 |
| exp-oracle-resample-rep2 | 2026-09-29 | dataset | gpt-4o-mini | openai |  | 125 | n/d | 344815 |
| exp-oracle-resample-rep3 | 2026-09-29 | dataset | gpt-4o-mini | openai |  | 125 | n/d | 350732 |
| verify-2026-09-29-gpt-4o-mini-e2e | 2026-09-29 | dataset | gpt-4o-mini | openai |  | 138 | 257717 | 790843 |
| verify-2026-09-29-gpt-4o-mini-oracle-r5 | 2026-09-29 | dataset | gpt-4o-mini | openai |  | 125 | n/d | 261491 |
| engine-2026-10-01 | 2026-10-01 | dataset | n/d | n/d |  | n/d | n/d | n/d |
| engine-fixed-2026-10-01 | 2026-10-01 | dataset | n/d | n/d |  | n/d | n/d | n/d |
| triage-2026-10-04-sonnet-20 | 2026-10-04 | dataset | claude-sonnet-5-5 | claude_cli |  | 5 | 19973 | 2337 |
| triage-2026-10-04-sonnet-20-prompt2 | 2026-10-04 | dataset | claude-sonnet-5-5 | claude_cli |  | 11 | 18635 | 4149 |
| full-2026-10-04-sonnet | 2026-10-05 | dataset | claude-sonnet-5-5 | claude_cli |  | 232 | 327607 | 124380 |
| det-2026-10-06-amostra-A0-r2 | 2026-10-06 | dataset | claude-sonnet-5-5 | claude_cli |  | 53 | 53645 | n/d |
| det-2026-10-06-amostra-A1 | 2026-10-06 | dataset | claude-sonnet-5-5 | claude_cli | A1 | 71 | 64098 | n/d |
| det-2026-10-06-amostra-A1,A2 | 2026-10-06 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2 | 85 | 68330 | n/d |
| det-2026-10-06-amostra-A2 | 2026-10-06 | dataset | claude-sonnet-5-5 | claude_cli | A2 | 67 | 61906 | n/d |
| det-2026-10-06-amostra-A3 | 2026-10-06 | dataset | claude-sonnet-5-5 | claude_cli | A3 | 42 | 56168 | n/d |
| det-2026-10-06-amostra-A6 | 2026-10-06 | dataset | claude-sonnet-5-5 | claude_cli | A6 | 44 | 54095 | n/d |
| full-2026-10-05-regrounded | 2026-10-06 | dataset | claude-sonnet-5-5 | claude_cli |  | 232 | 327607 | 153969 |
| det-2026-10-12-amostra-A1,A2,A10 | 2026-10-12 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2,A10 | 99 | 70964 | n/d |
| det-2026-10-12-amostra-A1,A2,A11 | 2026-10-12 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2,A11 | 92 | 75867 | n/d |
| det-2026-10-12-amostra-A1,A2,A7 | 2026-10-12 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2,A7 | 89 | 89421 | n/d |
| det-2026-10-12-amostra-A1,A2,A8 | 2026-10-12 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2,A8 | 87 | 66272 | n/d |
| det-2026-10-12-amostra-A1,A2,A9 | 2026-10-12 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2,A9 | 136 | 75277 | n/d |
| final-2026-10-15 | 2026-10-15 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2 | 564 | 506345 | 336011 |
| final-2026-10-15-codex | 2026-10-15 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2 | 564 | 506345 | 3498545 |
| det-2026-10-17-amostra-A1,A2 | 2026-10-17 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2 | 97 | 66877 | n/d |
| det-2026-10-17-amostra-A1,A2,A13 | 2026-10-17 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2,A13 | 85 | 87411 | n/d |
| det-2026-10-17-amostra-A1,A2,A14 | 2026-10-17 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2,A14 | 71 | 71060 | n/d |
| det-2026-10-17-amostra-A1,A2,A9 | 2026-10-17 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2,A9 | 163 | 76618 | n/d |
| final-2026-10-17 | 2026-10-19 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2,A15 | 742 | 475804 | 816222 |
| det-2026-10-20-amostra-A1,A2,A12 | 2026-10-20 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2,A12 | 74 | 75354 | n/d |
| det-2026-10-20-sc1-A1,A2 | 2026-10-20 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2 | 94 | 72842 | n/d |
| det-2026-10-20-sc2-A1,A2 | 2026-10-20 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2 | 96 | 67924 | n/d |
| det-2026-10-20-sc3-A1,A2 | 2026-10-20 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2 | 100 | 75826 | n/d |
| det-2026-10-20b-amostra-A1,A2,A16 | 2026-10-20 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2,A16 | 89 | 75530 | n/d |
| det-2026-10-31-en-r1-A1,A2 | 2026-10-31 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2 | 84 | 71906 | n/d |
| det-2026-10-31-en-r2-A1,A2 | 2026-10-31 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2 | 94 | 71262 | n/d |
| pyathena-limpo-r1 | 2026-10-31 | scan |  | n/d | A1,A2,A12 | 1 | 3765 | n/d |
| pyathena-limpo-r2 | 2026-10-31 | scan |  | n/d | A1,A2,A12 | 0 | 0 | n/d |
| pyathena-semeado-r1 | 2026-10-31 | scan |  | n/d | A1,A2,A12 | 3 | 3353 | n/d |
| pyathena-semeado-r2 | 2026-10-31 | scan |  | n/d | A1,A2,A12 | 0 | 0 | n/d |
| codex-pilot-2026-11-03 | 2026-11-03 | dataset | gpt-6.1-sol | codex | A1,A2 | 2 | 17955 | 36093 |
| e2e-2026-11-02 | 2026-11-03 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2 | 121 | 75963 | 23613 |
| congelado-c-2026-11-05 | 2026-11-06 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2 | 123 | 82700 | 81143 |
| congelado-c-2026-11-06 | 2026-11-06 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2 | 123 | 82700 | 648680 |
| ajustes-2026-11-07 | 2026-11-08 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2 | 123 | 82700 | 512594 |
| async-stub-2026-11-08 | 2026-11-08 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2 | 11 | 7777 | 163956 |
| logger-heal-2026-11-08 | 2026-11-08 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2 | 14 | 7341 | 100823 |
| prompt-a2-2026-11-08 | 2026-11-08 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2 | 34 | 21131 | n/d |
| prompt-a2b-2026-11-08 | 2026-11-08 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2 | 36 | 23711 | n/d |
| replay-2026-11-08 | 2026-11-08 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2 | 6 | 3745 | 5702 |
| rodada-final-2026-11-08 | 2026-11-09 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2 | 119 | 79923 | 562031 |
| rodada-final-2026-11-09 | 2026-11-09 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2 | 109 | 68191 | 670003 |
| scan_pyserial_2026-11-08 | 2026-11-09 | scan | claude-sonnet-5-5 | n/d | A1,A2,A12 | 30 | 0 | 45619 |
| cost-explorer_2026-11-10 | 2026-11-10 | scan |  | n/d | A1,A2,A12 | 6 | 6337 | 16642 |
| glue_haiku_lote1 | 2026-11-10 | scan | haiku | n/d | A1,A2,A12 | 16 | 74322 | 66922 |
| rotation_haiku_lote1 | 2026-11-10 | scan | haiku | n/d | A1,A2,A12 | 33 | 102352 | 155730 |
| scan_pyserial_2026-11-10 | 2026-11-10 | scan |  | n/d | A1,A2,A12 | 32 | 27464 | 49029 |
| sam-python-crud-sample | 2026-11-11 | scan | gpt-6.1-sol | n/d | A1,A2,A12 | 16 | 281762 | 638452 |
| sdk_examples_lote1 | 2026-11-11 | scan | haiku | n/d | A1,A2,A12 | 12 | 0 | 48185 |
| bedrock-access-gateway_2026-11-12 | 2026-11-12 | scan | haiku | n/d | A1,A2,A12 | 16 | 1000375 | 1963974 |
| gps | 2026-11-12 | scan |  | n/d | A1,A2,A12 | 35 | 3267781 | n/d |
| rodada-2026-11-11 | 2026-11-12 | dataset | claude-sonnet-5-5 | claude_cli | A1,A2 | 116 | 3371854 | 44751885 |
| rotation | 2026-11-12 | scan |  | n/d | A1,A2,A12 | 0 | 0 | n/d |
| PyAthena-upstream_2026-11-13 | 2026-11-13 | scan | haiku | n/d | A1,A2,A12,A22 | 12 | 1289816 | 1070821 |
| boto3-upstream_2026-11-13 | 2026-11-13 | scan | haiku | n/d | A1,A2,A12,A22 | 10 | 1240685 | 723457 |
| botocore-upstream_2026-11-13 | 2026-11-13 | scan | haiku | n/d | A1,A2,A12,A22 | 12 | 1177757 | 1373893 |
| hardeneks_2026-11-12 | 2026-11-13 | scan | haiku | n/d | A1,A2,A12 | 23 | 1298922 | 2193275 |
| service-screener-v2_2026-11-13 | 2026-11-13 | scan | haiku | n/d | A1,A2,A12,A22 | 17 | 1254979 | 2041571 |
