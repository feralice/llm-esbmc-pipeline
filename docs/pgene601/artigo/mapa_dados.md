# De onde sai cada número do artigo

Só aponta onde estão os dados. O texto é da autora.

| Seção | Dado | Onde está |
|---|---|---|
| Conjunto de dados | 47 bugs, projeto, tipo de exceção | `dataset/disciplina_pgene601/README.md`, `manifest.json` |
| Pipeline | etapas e veredictos | `docs/projeto/` e `src/research_pipeline/verify/` |
| Linha mypy | 2/47 padrão, 5/47 `--check-untyped-defs` (3 com a mensagem certa) | `docs/pgene601/pgene601_sondas_e_mypy_2026-10-18.md` |
| Linha pytest | 10 diferenciais; 36 sem teste Python | `scripts/pgene601_tabela.py` |
| Resultado, rodada de 06/11 | 5 pela expressão, 8 pela função (única fora da amostra; detecção copiada da rodada de 05/11) | `artifacts/pgene601/congelado-c-2026-11-06/` |
| Resultado, rodada de 08/11 | 9 pela expressão, 14 pela função; 36/47 com hipótese certa | `artifacts/pgene601/rodada-final-2026-11-08/` (`resumo.md`, `funil.txt`, `tabela.md`) |
| Resultado, rodada de 09/11 | 9 pela expressão, 14 pela função; 37/47 com hipótese certa | `artifacts/pgene601/rodada-final-2026-11-09/` (`resumo.md`, `funil.txt`, `tabela.md`) |
| Resultado, rodada de 11/11 | 9 pela expressão, 15 pela função; 37/47 com hipótese certa; onde cada bug parou | `artifacts/pgene601/rodada-2026-11-11/` (`resumo.md`, `funil.txt`, `tabela.md`) |
| Rodada de 14/11 | parcial, parou no limite de uso (89 de 128 verificações); não vale | `artifacts/pgene601/ruido-2026-11-14-r1/` |
| Rodada com o pipeline congelado | em andamento desde 16/11; regras contra viés escritas antes | `artifacts/pgene601/congelado-2026-11-16-r1/`, `docs/experimentos/README.md` |
| Quais rodadas foram completas | só 08 e 09/11, 09/11 e 11/11; 06/11 e 07/11 reaproveitaram a detecção; 02/11 e 03/11 só têm a detecção | `docs/pgene601/artigo/tabela_experimentos.md` (seção "Tipo de cada rodada") |
| Critério de acerto | por função, em dois níveis, desde 14/11; linha e expressão só como apoio | `docs/projeto/REGRA_DE_ACERTO_2026-11-14.md`, `dataset/disciplina_pgene601/gabarito_funcoes.json` |
| Conjunto de dados | 47 bugs de 21 projetos, cada um de um pull request aceito | `docs/projeto/ORIGEM_DOS_47_BUGS.md`, `dataset/disciplina_pgene601/manifest.json` |
| Custo e reparo | 28,4 milhões de tokens na rodada de 14/11; regra que interrompe o reparo; simulação | `artifacts/pgene601/ruido-2026-11-14-r1/v2_checkpoint.json` (telemetria), commit `f55cc5a` |
| Discussão | por que param (bytearray, array.array, crashes) | `docs/projeto/possiveis_problemas/README.md` |
| Scan | pymodbus antes dos consertos, 3 bugs de referência | `artifacts/scan_pymodbus_2026-11-09/` |
| Scan, pymodbus | rodada Codex parcial e análise das hipóteses | `docs/pgene601/artigo/tabela_scans.md`, `docs/experimentos/scan_pymodbus_codex_2026-11-10.md`, `artifacts/scan_pymodbus_codex_2026-11-10/` |
| Scan, pyserial | resultado e análise das hipóteses | `docs/pgene601/artigo/tabela_scans.md`, `artifacts/scan_pyserial_2026-11-10/scan_summary.md`, `scan_report.json` |
| Scan, aws-cost-explorer-report | resultado | `docs/pgene601/artigo/tabela_scans.md`, `/mnt/e/scan_amazon/cost-explorer_2026-11-10/scan_summary.md`, `scan_report.json` |
| Scan, aws-glue-samples | resultado e análise das hipóteses | `docs/pgene601/artigo/tabela_scans.md`, `/mnt/e/scan_amazon/glue_haiku_lote1/scan_summary.md`, `scan_report.json` |
| Scan, aws-secrets-manager-rotation-lambdas | em andamento, sem resumo na conferência | `docs/pgene601/artigo/tabela_scans.md`, `/mnt/e/scan_amazon/rotation_haiku_lote1/` |
| Ameaças à validade | 47 usados para corrigir erros; só 06/11 é fora da amostra | `docs/experimentos/README.md` |
