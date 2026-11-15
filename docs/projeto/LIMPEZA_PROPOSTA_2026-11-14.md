# Proposta de limpeza do repositório (14/11/2026)

**Nada deste documento foi executado.** Cada ação precisa de um "sim" da Fernanda, item por item. Levantamento feito só por leitura; os comandos para conferir cada número estão na coluna "Como conferir".

## O que NÃO é código sem uso (não remover)

| Item | Por quê |
|---|---|
| 52 arquivos `src/research_pipeline/verify/probes/*.py` | Sem `import`, mas o `capabilities.py` os lê por caminho (`PROBE_DIR`). São as sondas que dizem quais regras do harness o ESBMC instalado ainda precisa |
| `verify/differential_worker.py` e `verify/pytest_worker.py` | Rodam como subprocesso, chamados por `differential.py` e `pytest_gen.py` |
| Scripts de `scripts/` sem referência em `src/` ou `tests/` | São ferramentas de linha de comando usadas à mão. Referência ausente não prova falta de uso |
| `scripts/build_*` e `scripts/pgene601_*` (4 deles nenhum documento cita) | Constroem os datasets: servem à reprodutibilidade dos dados |

## Candidatos reais, do mais seguro ao que exige decisão

| # | Item | Evidência | Risco | Ação sugerida | Como conferir |
|---|---|---|---|---|---|
| 1 | **14 branches locais já mescladas** em `master`: `dataset/v1-seed-python`, `feat/harness-de-agente`, `feat/roteamento-automatico`, `feat/v2-scan-mode`, `feat/validacao-deteccao`, `feat/verify-esbmc-rewrites`, `feat/workers`, `fix/caller-exception-context`, `refactor/code-quality-audit` e 5 `worktree-agent-*` | `git branch --merged master` | Nenhum commit se perde: tudo já está em `master` | `git branch -d <nome>` (o `-d` recusa se não estiver mesclada). Uma branch que uma worktree está usando (`feat/validacao-deteccao` e as `worktree-agent-*`) só sai depois do item 2 | `git branch --merged master` |
| 2 | **Worktrees de sessões antigas**: 5 em `.claude/worktrees/agent-*` (676 MB no total), `~/.codex/worktrees/2a3c`, `/mnt/c/Users/ferna/Documents/mestrado/llm_esbmc-rules` e `/mnt/c/.../llm_esbmc/.claude/worktrees/validacao-deteccao` | Os 5 commits das pontas (`7917192`, `dc64068`, `63c9e42`, `88ad57a`, `951fb08`) estão todos contidos em `master` (`git merge-base --is-ancestor`) | Baixo. **Antes de remover, olhe se há arquivos soltos (não commitados) em cada pasta**: um commit mesclado não garante que não haja trabalho não salvo dentro dela | `git worktree remove <pasta>` (recusa se houver alteração) e depois `git worktree prune` | `git worktree list` |
| 3 | `reports/` e `logs/` do V1 | `reports/` tem 1035 arquivos versionados (4,5 MB), quase todos `json/v1_benchmark`; `logs/` tem 8 (benchmark V1 e uma rodada V2 de setembro). Só o `README.md` da raiz cita `reports/` | Baixo | `git mv reports archive/v1_reports` e `git mv logs archive/v1_logs`. Não apagar | `git ls-files reports \| wc -l` |
| 4 | PDFs e nota na raiz: `kbs2026.pdf` (9,7 MB), `UFAM-2026-Cordeiro.pdf`, `Diretrizes para o Uso de LLMs na Escrita da Dissertação_vfinal.pdf`, `analise-verificao-formal.md` | São material de referência. O PDF das diretrizes é fonte das regras de escrita da Fernanda | Médio: algum documento ou skill pode apontar para o caminho atual | Conferir referências ao caminho e só então `git mv` para `docs/referencias/`. Não apagar | `grep -rn "Diretrizes" CLAUDE.md docs/escrita` |
| 5 | `extension/` (3 arquivos: extensão `/verify-repo` do Claude Code) | Não consegui saber se a Fernanda ainda usa | Depende dela | Perguntar. Se não usa, `git mv` para `archive/` | `git ls-files extension` |

## Duas branches que NÃO estão mescladas (não mexer sem decidir)

- `feat/gemini-cli-backend` e `ise2026-artifacts`. Existem também no GitHub (`origin`). Apagar a local não apaga a remota, mas elas têm commits que `master` não tem.

## Correção a uma informação anterior

Em 14/11 afirmei que `feat/validacao-deteccao` não estava mesclada. **Estava errado**: o levantamento de `git branch --merged master` a lista como mesclada, e o commit da worktree dela (`951fb08`) está em `master`.

## Fora do repositório (a Fernanda decide)

| Item | Tamanho | Observação |
|---|---|---|
| `artifacts/` | 2,2 GB | Não versionado (`.gitignore`). Não apague: contém as rodadas citadas nos documentos e no registro de modelos e tokens |
| `outputs/` | 13 MB | Não versionado |
| `~/alvos/PyAthena` | 37 MB | **Cópia com bug semeado. Não varrer.** Candidata a apagar se não for mais usada |
| `~/alvos/PyAthena-limpo` | 21 MB | Cópia antiga |
| `~/alvos/pymodbus-antes` | n/d | Cópia antiga (conferir o tamanho) |
| `~/alvos/pybughive_dados` | 17 MB | Metadados do PyBugHive. Pode servir ao conjunto novo e limpo |
| `/mnt/e/scan_amazon/` | n/d | Resultados dos scans da Amazon, citados no registro de modelos e tokens |

Em 13/11 a Fernanda pediu para tirar as cópias que não serão mais usadas; falta ela dizer quais.

## Ordem sugerida, se ela aprovar

1. Itens 1 e 2 (branches e worktrees mesclados): economiza 676 MB e confusão, sem perder commit.
2. Item 3 (V1 para `archive/`).
3. Itens 4 e 5 só depois de conferir as referências e de ela responder.

Não faça nenhuma destas ações antes do commit de congelamento e da tag: a limpeza muda o repositório e não deve entrar no commit que os experimentos citam.
