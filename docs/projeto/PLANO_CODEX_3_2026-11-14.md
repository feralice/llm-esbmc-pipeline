# Plano 3 para o Codex: fechar o congelamento e propor a limpeza do repositório (14/11/2026)

Quem executa: Codex. Quem decide: Fernanda. Continua `docs/projeto/PLANO_CODEX_2_2026-11-14.md` (P1, P2, P3 e P5 feitas, ver `docs/projeto/EXECUCAO_CODEX_2_2026-11-14.md`). A Fernanda quer parar de mexer em código e rodar os experimentos até 25/11/2026.

## 1. Regras que valem para tudo

- Nada pago: nenhuma chamada de LLM, scan ou rodada.
- **Nada destrutivo sem a Fernanda responder "sim" àquele item**: apagar arquivo, apagar branch, remover worktree, `git push`, `git commit`, tag, recompilar ou `git pull` no ESBMC. Cada um precisa de autorização própria; a de um não vale para outro.
- Prefira mover com `git mv` (reversível) a apagar. Nunca apague `dataset/`, `artifacts/`, `docs/` nem os alvos em `~/alvos`.
- Sem `Co-Authored-By`. Sem travessão em texto. Poucos comentários.
- Teste primeiro. Ao terminar, registre em `docs/projeto/EXECUCAO_CODEX_3_2026-11-14.md`, em palavras simples, com seção "Uso de IA".

## 2. Passos, em ordem (pare em cada PERGUNTAR)

### N1. Corrigir como a avaliação por função é apresentada (sem custo)
O relatório antigo deu 47 de 47 casos "apontados". Esse número **não tem poder de discriminação neste desenho**: cada arquivo de `dataset/disciplina_pgene601/funcao_com_bug` tem 1 função (no máximo 2; média 1,1), então a LLM não tem outra função para apontar. Faça:
1. No relatório de avaliação por função e em `docs/projeto/REGRA_DE_ACERTO_2026-11-14.md`, acrescente essa explicação junto ao nível "apontado", com os números de arquivos e funções por arquivo.
2. Deixe em destaque os níveis que discriminam: "apontado e reproduzido" (8 de 47 no relatório antigo), "confirmado pelo ESBMC" (5) e, quando existir, o juiz do conserto (`scripts/juiz_conserto.py`, 4).
3. Teste que garante que o texto de aviso aparece quando o nível 1 é 100% por construção.

### N2. Script da detecção nas funções corrigidas (escrever, **não executar**)
A rodada dos 47 só mostra funções com bug, então não mede falso positivo. Escreva `scripts/deteccao_corrigidas.sh`, modelo `scripts/run_detection_variants.sh`, que roda só a detecção (`--v2-stage detection`, perfil `congelado`) sobre `dataset/disciplina_pgene601/arquivo_corrigido` (as funções corrigidas), mesmo modelo e mesma variante dos 47. Registre o custo estimado (cerca de 53 chamadas, uns 80 mil tokens contados pelo CLI, que não conta o cache). Confira o que `funcao_com_bug` tem que `arquivo_corrigido` não tem (o recorte da função) para a entrada ser comparável. **Não execute.**

### N3. Atualizar o ESBMC
PERGUNTAR: "Posso rodar `scripts/atualizar_esbmc.sh`?" Só com "sim":
1. `git -C ~/esbmc-master pull --ff-only`.
2. Recompilar em `build-bw` com o comando dos logs `cmake-bw_2026-11-06.log` e `build-bw_2026-11-06b.log` (confirme o solver Bitwuzla e o Z3).
3. Testar em `cps_simpleio_43` (divisão por zero, já confirmado antes) e abortar se piorar.
4. Anotar a linha em `docs/experimentos/ESBMC_VERSOES.md`: data, commit, `--version`, hash do binário.
Lembrete: `esbmc --version` diz só `8.6.0`, sem commit. A prova de qual código gerou o binário é o hash do binário e a data, gravados pela procedência (`esbmc_provenance.py`). Rode **sempre** o script de atualização antes de uma rodada.

### N4. Suíte completa e `pylint`
Confira com `pgrep` que não há rodada ativa. Suíte completa com limite de 10 minutos. `pylint` não está instalado: instale, diga que instalou, rode nos arquivos alterados. Registre os resultados e **não corrija nada fora do que você mesmo alterou** sem avisar.

### N5. Limpeza (propor, não executar)
Escreva `docs/projeto/LIMPEZA_PROPOSTA_2026-11-14.md` com uma tabela por item: o que é, evidência, risco, ação sugerida. **Não execute nenhuma ação.** Levantamento do Claude Code em 14/11 (confirme cada número antes de repetir):

**Não são código morto (não remover):**
- 54 módulos de `src/` sem `import` direto. 52 deles são `src/research_pipeline/verify/probes/*.py`, que o `capabilities.py` lê **por caminho** (`PROBE_DIR`). `differential_worker.py` e `pytest_worker.py` são executados como subprocesso por `differential.py` e `pytest_gen.py`. Nenhum é sem uso.
- Scripts em `scripts/` sem referência em `src/` ou `tests/`: são ferramentas de linha de comando usadas à mão, não módulos. Referência ausente **não prova** falta de uso. Os 4 que nenhum documento cita (`build_code_smell_dataset.py`, `build_disciplina_pgene601.py`, `build_pgene601_adafruit.py`, `pgene601_check_datasheet_props.py`) constroem datasets: servem à reprodutibilidade dos dados, então mantenha.

**Candidatos reais, em ordem de segurança:**
1. **Branches já mescladas.** 17 branches locais, 15 já contidas em `master` (`git branch --merged master`). Apagar branch mesclada não perde commit. Liste os nomes e peça autorização.
2. **Worktrees velhas.** `git worktree list` mostra 5 em `.claude/worktrees/agent-*` (de sessões anteriores), 1 do Codex (`~/.codex/worktrees/2a3c`, desanexada) e 2 em `/mnt/c/Users/ferna/Documents/mestrado/` (`llm_esbmc-rules`, `validacao-deteccao`). Para cada uma, diga se o commit dela está em `master` (`git branch --contains`) antes de propor remover. A do `validacao-deteccao` tem branch própria `feat/validacao-deteccao`, que **não** aparece como mesclada: não remova sem a Fernanda decidir.
3. **`reports/` e `logs/` do V1.** `reports/` tem 1035 arquivos versionados (4,5 MB), quase todos de `v1_benchmark`; `logs/` tem 8 (logs do benchmark V1 e de uma rodada V2 de setembro). Só o `README.md` do repositório menciona `reports/`. A V1 está arquivada (`archive/v1_verificacao_formal`). Sugestão: `git mv` para dentro de `archive/`, não apagar.
4. **PDFs na raiz:** `kbs2026.pdf` (9,7 MB), `UFAM-2026-Cordeiro.pdf`, `Diretrizes para o Uso de LLMs na Escrita da Dissertação_vfinal.pdf` e `analise-verificao-formal.md`. São material de referência. Sugestão: `git mv` para `docs/referencias/` e **não** apague (o PDF de diretrizes é fonte das regras de escrita da Fernanda). Confira se algum arquivo do repositório aponta para o caminho atual antes de mover.
5. **`teste.py`** na raiz: 4 linhas de rascunho, já ignorado pelo `.gitignore` (linha 39). Não é versionado; só informe.
6. **`extension/`** (3 arquivos: `README.md`, `commands/verify-repo.md`, `.claude-plugin/plugin.json`): é a extensão do Claude Code do projeto. Pergunte à Fernanda se ainda usa antes de propor mover.

**Fora do repositório, só informar (a Fernanda decide):**
- `artifacts/` tem 2,2 GB e não é versionado (`.gitignore`). `outputs/` tem 13 MB, também ignorado.
- Em `~/alvos`: `PyAthena` (cópia com bug semeado, 37 MB, **não varrer**), `PyAthena-limpo` (21 MB), `pymodbus` e `pymodbus-antes`, `pybughive_dados` (17 MB). Em 13/11 ela pediu para tirar as cópias que não serão mais usadas; falta ela dizer quais.

### N6. Commit e tag
PERGUNTAR: "Posso commitar tudo?" Agrupe em commits por assunto (M1 a M3, P1 a P5, scripts de análise e documentos de 14/11), com mensagem curta e sem coautoria. Depois PERGUNTAR: "Posso criar a tag `v2-congelado-2026-11d`?", com o commit do ESBMC e o hash do binário na mensagem. Depois da tag, nenhum código do pipeline muda.

## 3. O que a Fernanda faz depois (não é do Codex)

Rodar, com `--profile congelado`, a rodada dos 47 (r1 e r2, pasta nova; a de 14/11 não vale porque o ESBMC mudou), e se ela quiser, `scripts/deteccao_corrigidas.sh`. As análises sem custo (mypy e pytest nos 47, juiz do conserto, avaliação por função, ruído entre r1 e r2) saem dos resultados gravados.

## 4. Perguntas deixadas para a Fernanda

N1 e N2 implementadas. Registro: `docs/projeto/EXECUCAO_CODEX_3_2026-11-14.md`. A execução parou antes de N3, sem antecipar N4, N5 ou N6.

Autorizações pendentes, separadas conforme a seção 1:

- Executar `git -C ~/esbmc-master pull --ff-only` pelo atualizador?
- Recompilar em `build-bw` e executar o teste de regressão de `cps_simpleio_43` antes e depois, pelo atualizador?

O comando preparado é `bash scripts/atualizar_esbmc.sh --execute`. Ele só poderá ser iniciado depois de autorizar as duas ações. Não houve execução paga nem limpeza.
