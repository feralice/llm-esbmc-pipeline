# De onde sai cada número do artigo

Só aponta onde estão os dados. O texto é da autora.

| Seção | Dado | Onde está |
|---|---|---|
| Conjunto de dados | 47 bugs, projeto, tipo de exceção | `dataset/disciplina_pgene601/README.md`, `manifest.json` |
| Pipeline | etapas e veredictos | `docs/projeto/` e `src/research_pipeline/verify/` |
| Linha mypy | 2/47 padrão, 5/47 `--check-untyped-defs` (3 com a mensagem certa) | `docs/pgene601/pgene601_sondas_e_mypy_2026-10-18.md` |
| Linha pytest | 10 diferenciais; 36 sem teste Python | `scripts/pgene601_tabela.py` |
| Resultado, rodada de 06/11 | 5 pela expressão, 8 pela função (única fora da amostra) | `artifacts/pgene601/congelado-c-2026-11-06/` |
| Resultado, rodada de 08/11 | 9 pela expressão, 14 pela função; 36/47 com hipótese certa | `artifacts/pgene601/rodada-final-2026-11-08/` (`resumo.md`, `funil.txt`, `tabela.md`) |
| Resultado, rodada de 09/11 | a preencher quando fechar | `artifacts/pgene601/rodada-final-2026-11-09/` |
| Discussão | por que param (bytearray, array.array, crashes) | `docs/projeto/possiveis_problemas/README.md` |
| Scan | pymodbus antes dos consertos, 3 bugs de referência | `artifacts/scan_pymodbus_2026-11-09/` |
| Ameaças à validade | 47 usados para corrigir erros; só 06/11 é fora da amostra | `docs/experimentos/README.md` |
