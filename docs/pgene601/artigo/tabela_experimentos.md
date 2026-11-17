# Experimentos com o conjunto da disciplina

Organização de registros existentes, preparada com apoio do Codex. As contagens são de **bugs**, não de hipóteses, salvo indicação. Expressão significa confirmação na expressão equivalente à do gabarito; função significa confirmação na função com bug, que pode ocorrer em outra expressão. Hipótese certa é o apontamento do detector na expressão equivalente, antes da confirmação. Os resultados de mypy e pytest medem coisas diferentes e não são confirmações do ESBMC. «Não conferido» inclui dado ausente ou ainda não apurado; não significa zero.

| Rodada | Data | Modelo / backend | Commit do pipeline | ESBMC | Bugs pela expressão | Bugs pela função | Bugs com hipótese certa | Amostra | Resultado |
|---|---|---|---|---|---:|---:|---:|---|---|
| mypy padrão | 03/11/2026 | não se aplica; mypy 2.1.0 | `6c13902` | não se aplica | não se aplica | não se aplica | não se aplica | não se aplica: linha de base | `artifacts/pgene601/mypy-2026-11-03/` |
| mypy `--check-untyped-defs` | 03/11/2026 | não se aplica; mypy 2.1.0 | `6c13902` | não se aplica | não se aplica | não se aplica | não se aplica | não se aplica: linha de base | `artifacts/pgene601/mypy-2026-11-03/` |
| pytest dos testes das PRs | 03/11/2026 | não se aplica | não conferido | não se aplica | não se aplica | não se aplica | não se aplica | não se aplica: testes das PRs | `artifacts/pgene601/pytest-2026-11-03/` |
| Claude inicial | 02/11/2026 | `claude-sonnet-5-5` / `claude_cli` | `6c13902` | versão não conferida; commit `d520a903ae` no comando | não conferido | não conferido | 36 | não conferido | `artifacts/pgene601/e2e-2026-11-02/` |
| GPT mini, tentativa | 02/11/2026 | `gpt-5.4-mini-2026-03-17` / backend não conferido | `6c13902` | não conferido | não conferido | não conferido | não conferido | não conferido | `artifacts/pgene601/gpt-5.4-mini-2026-11-02/` |
| Codex | 03/11/2026 | `gpt-6.1-sol` / backend não conferido | não conferido | não conferido | não conferido | não conferido | 39 | não conferido | `artifacts/pgene601/codex-2026-11-03/` |
| Codex piloto, um arquivo | 03/11/2026 | `gpt-6.1-sol` / `codex` | não conferido | 8.6.0 | não conferido | não conferido | não conferido | não conferido | `artifacts/pgene601/codex-pilot-2026-11-03/` |
| Congelamento c, perdida | 05/11/2026 | `claude-sonnet-5-5` / `claude_cli` | `d553e97` | 8.6.0; indisponível na verificação | inválido | inválido | 38, detecção reutilizada em 06/11 | ver nota | `artifacts/pgene601/congelado-c-2026-11-05/` |
| Congelamento c | 06/11/2026 | `claude-sonnet-5-5` / `claude_cli` | `d553e97` | 8.6.0, `39590bbd26` | 5 | 8 | 38 | fora da amostra, conforme registro | `artifacts/pgene601/congelado-c-2026-11-06/` |
| Ajustes | 07/11/2026 | `claude-sonnet-5-5` / `claude_cli` | `d553e97` + alterações registradas | 8.6.0, `822227ff96` | 5 | 8 | 38 | dentro | `artifacts/pgene601/ajustes-2026-11-07/` |
| Replay, subconjunto | 08/11/2026 | `claude-sonnet-5-5` / `claude_cli` | não conferido | não conferido | não conferido | não conferido | não conferido | dentro | `artifacts/pgene601/replay-2026-11-08/` |
| Async e stub, subconjunto | 08/11/2026 | `claude-sonnet-5-5` / `claude_cli` | não conferido | não conferido | não conferido | não conferido | não conferido | dentro | `artifacts/pgene601/async-stub-2026-11-08/` |
| Logger e reparo, subconjunto | 08/11/2026 | `claude-sonnet-5-5` / `claude_cli` | não conferido | não conferido | não conferido | não conferido | não conferido | dentro | `artifacts/pgene601/logger-heal-2026-11-08/` |
| Prompt A2, só detecção | 08/11/2026 | `claude-sonnet-5-5` / `claude_cli` | não conferido | não se aplica | não se aplica | não se aplica | não conferido | dentro | `artifacts/pgene601/prompt-a2-2026-11-08/` |
| Prompt A2b, só detecção | 08/11/2026 | `claude-sonnet-5-5` / `claude_cli` | não conferido | não se aplica | não se aplica | não se aplica | não conferido | dentro | `artifacts/pgene601/prompt-a2b-2026-11-08/` |
| Rodada parcial interrompida | 08/11/2026 | modelo e backend não conferidos | `d553e97` + alterações registradas | não conferido | não conferido | não conferido | não conferido | dentro | `artifacts/pgene601/rodada-2026-11-08/` |
| Rodada final | 08/11/2026, terminou em 09/11 | `claude-sonnet-5-5` / `claude_cli` | `8579920` | 8.6.0; commit `95f025adf4` segundo o registro | 9 | 14 | 36 | dentro | `artifacts/pgene601/rodada-final-2026-11-08/` |
| Subconjunto | 09/11/2026 | `claude-sonnet-5-5` / `claude_cli`, conforme comando | `a347d3d` + alterações registradas | 8.6.0 | não conferido | não conferido | não conferido | dentro | `artifacts/pgene601/rodada-subconjunto-2026-11-09/` |
| Rodada final | 09/11/2026 | `claude-sonnet-5-5` / `claude_cli` | `a347d3d` + alterações registradas | 8.6.0; commit `b76980aaa0` segundo o registro | 9 | 14 | 37 | dentro | `artifacts/pgene601/rodada-final-2026-11-09/` |
| Rodada | 11/11/2026 | `claude-sonnet-5-5` / `claude_cli` | `63c9e42` (tag `v2-congelado-2026-11d`) | 8.6.0; commit exato não registrado na pasta | 9 | 15 | 37 | dentro | `artifacts/pgene601/rodada-2026-11-11/` |
| Medição de ruído, parcial | 14/11/2026 | `claude-sonnet-5-5` / `claude_cli` | `e346b00` | 8.6.0 | interrompida | interrompida | interrompida | dentro | `artifacts/pgene601/ruido-2026-11-14-r1/`; parou no limite de uso com a detecção pronta e 89 de 128 verificações; não vale |
| Rodada com o pipeline congelado | 16/11/2026, em andamento | `claude-sonnet-5-5` / `claude_cli` | `f086e22` (código da tag `v2-congelado-2026-11f`) | 8.6.0; commit `de72a905e0` | em andamento | em andamento | em andamento | dentro | `artifacts/pgene601/congelado-2026-11-16-r1/`; regras contra viés em `docs/experimentos/README.md` |

O mypy apontou linhas selecionadas em 2 casos no modo padrão e em 5 com a opção, segundo `docs/experimentos/README.md`. Nos testes das PRs, o registro conta 10 casos cujo teste falhou por comportamento ligado ao defeito e passou na versão corrigida, entre 11 casos com teste Python; não conta uma falha causada pelo ambiente. Essas medidas não preenchem as colunas de confirmação do pipeline.

A rodada perdida de 05/11 e a de 06/11 compartilham a detecção: o README diz que a segunda copiou o checkpoint da primeira e refez a verificação. O README chama a rodada de 06/11 de única fora da amostra e declara que os consertos posteriores vieram da análise desses casos. Há uma divergência no próprio histórico: a seção de 07/11 diz que o caderno foi mantido sem lições para preservar o teste fora da amostra, enquanto a seção posterior de 08/11 classifica somente 06/11 como fora da amostra. O commit `8579920` registra a ressalva em seu título. Isso não comprova, por si só, que nenhuma pessoa olhou os casos antes de 06/11; além disso, há registros anteriores com o mesmo conjunto. Por isso, a classificação das rodadas anteriores fica não conferida, em vez de presumir que sejam dentro ou fora. As linhas de base não usam o mesmo critério de ajuste do pipeline.

## Tipo de cada rodada (conferido nos checkpoints em 16/11/2026)

Só as rodadas de **08 e 09/11**, **09/11** e **11/11** foram completas, de ponta a ponta: detecção e verificação do começo ao fim, a partir de pasta vazia. As demais:

- **02/11, Claude inicial:** só a detecção vale. 118 das 121 verificações terminaram em `PIPELINE_ERROR` (`claude -p saiu com código 1`).
- **03/11, Codex:** a rodada não terminou (checkpoint em estado `running`, 36 verificações). Só a detecção serve.
- **06/11 e 07/11:** a verificação foi refeita e a detecção foi copiada da rodada anterior (05/11 e 06/11, respectivamente), segundo o `run.sh` de cada pasta.
- **14/11:** parou no limite de uso da assinatura e não vale.

A contagem por bug de 11/11 (9 pela expressão, 15 pela função, 37 com hipótese certa) vem do `resumo.md` e do `funil.txt` da própria pasta.

## Critério de acerto

Até 13/11 o acerto era contado pela linha ou expressão do rótulo (colunas "pela expressão"). Em 14/11 passou a valer a regra por função, em dois níveis, escrita antes de qualquer rodada nova e descrita em `docs/projeto/REGRA_DE_ACERTO_2026-11-14.md`. Motivo: em 13 dos 47 rótulos a linha é a vizinha do guarda inserido pelo patch, e o que os mantenedores validaram foi a função corrigida. As colunas "pela expressão" e "pela função" desta tabela continuam lado a lado.

## Pendências para fechar

- Apurar as contagens por bug nas rodadas parciais, nos subconjuntos e nos prompts a partir dos checkpoints e relatórios, com o mesmo critério das rodadas finais. Algumas não têm relatório final.
- Confirmar commits e versões ausentes, e o backend da tentativa GPT mini. O arquivo de orçamento registra erro de requisição; não comprova uma rodada concluída.
- Esclarecer o histórico das rodadas anteriores a 06/11 e o sentido exato de «antes de olhar os 47». O README confirma a classificação metodológica da rodada de 06/11, mas os registros anteriores exigem distinção mais precisa.
- Verificar se outras sondas e reexecuções em `artifacts/pgene601/melhorias-2026-11-03/`, `synth-gabarito-2026-11-03/` e `smoke-2026-11-05/` devem ser contabilizadas como experimentos comparáveis. São registros técnicos distintos das rodadas acima.
- Fontes principais: `docs/experimentos/README.md`, `artifacts/pgene601/tabela-comparacao-parcial.md`, os arquivos `commit.txt`, `esbmc_version.txt`, `llm_telemetry.json`, `run.sh`, `resumo.md` e `funil.txt` das respectivas pastas. A rodada parcial de 08/11 não deve ser apresentada como resultado final, conforme seu `LEIA-ME.md`.
