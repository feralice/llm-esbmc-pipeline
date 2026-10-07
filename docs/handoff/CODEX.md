# Handoff para o Codex (continuação do trabalho do Claude Code)

Leia este arquivo inteiro antes de qualquer ação. Visão geral do que falta: `docs/ESTADO.md`. Depois leia `docs/experimentos/README.md`
(seções "Fase 9" e "Fase 10") e o ledger `.superpowers/sdd/2026-10-06-orquestrador-harness/progress.md`.

## Contexto da pesquisa

Mestrado da Fernanda (verificação de software, orientação Lucas Cordeiro). Pipeline: uma LLM procura
bugs em funções Python reais; o ESBMC-Python verifica formalmente; o CPython reexecuta o código
original para confirmar. **Objetivo dela: o ESBMC confirmar formalmente bugs reais.** Evidência só do
CPython (`FUZZ_FOUND`) é contada à parte e nunca somada a `CONFIRMED`.

Dataset: `dataset/bugs_reais/` (289 bugs; gabarito em `ground_truths.json`). Conjuntos fixos para medir
rápido: `dataset/bugs_reais/conjunto_dificil.json` (20 casos, mede o harness) e
`dataset/bugs_reais/amostra_deteccao.json` (50 bugs, mede o prompt de detecção).

## Onde trabalhar

- Diretório: `/mnt/c/Users/ferna/Documents/mestrado/llm_esbmc/.claude/worktrees/validacao-deteccao`
  (git worktree, branch `feat/validacao-deteccao`). Não trabalhe na pasta principal.
- `artifacts/` aqui é um link para `../../../artifacts` (resultados das rodadas, fora do git). Nunca
  faça `git add -A` nem `git add .`: adicione arquivos pelo nome (o link não pode entrar no git).
- Python: `/mnt/c/Users/ferna/Documents/mestrado/llm_esbmc/.venv/bin/python`. ESBMC:
  `/usr/local/bin/esbmc` (8.5.0).
- Testes: `timeout 590 python3 -m pytest tests/ -q` (cerca de 7 min; hoje 715+ passam). Um arquivo:
  `python3 -m pytest tests/<arquivo> -q`.

## Regras dela (obrigatórias)

- Responder em português, curto e com exemplo concreto do código real quando explicar algo.
- **Nunca usar travessão (—)** em texto, documento ou commit; usar dois-pontos ou reestruturar.
- Não deixar todo item de lista com a mesma estrutura gramatical.
- **Commit só com autorização dela**, nunca com coautoria de IA (sem `Co-Authored-By`). Mensagem em
  inglês: título imperativo curto, 2 a 4 linhas de corpo. Nunca squash, nunca force push.
- **Antes de qualquer coisa que gaste API paga, perguntar.** Assinaturas (Claude Code, Codex) estão ok.
- Sem Docker.
- Regras sempre gerais: nunca ajustar o pipeline para um caso específico do dataset.
- TDD: teste que falha primeiro, depois o código, depois a suíte inteira verde.
- Toda rodada vai para `docs/experimentos/README.md` (data, pasta, commit, comando, resultado) e é
  arquivada com `python3 scripts/archive_runs.py <pasta> --fase N` (adicione a pasta em `PHASES`).
- Ao relatar, dizer primeiro o efeito na métrica final (bugs do gabarito confirmados pelo ESBMC na
  linha), antes de métricas intermediárias. Hoje: **7**.

## Estado

- O `master` tem o código até o commit aff456c; os commits depois disso estão só no branch. Ela junta
  com `git -C /mnt/c/Users/ferna/Documents/mestrado/llm_esbmc merge --ff-only feat/validacao-deteccao`
  quando autorizar.
- Fase 9: validação dos vereditos (0 funções alteradas, 3 vazios) e prompts (A5 = A1+A2 é o melhor).
- Fase 10: orquestrador (`verify/routing.py`, `verify/orchestrator.py`, `verify/dynamic.py`,
  `scripts/v2_orchestrate.py`). Não aumentou as confirmações formais; a busca no CPython achou 5 bugs
  na linha só na versão com bug.

## Tarefas pendentes, em ordem

### 1. (Feita) 5 casos de tempo esgotado com 900 s

Resultado em `docs/experimentos/README.md` (fase 10, `timeout900-2026-10-07`): mais tempo não
confirmou nada no gabarito; ip_real_22 e oob_real_12 passaram a esgotar a memória. Por isso a tarefa 2.

### 2. Entrada fixada ("saída 2", aprovada por ela)

Para os casos que estouram tempo ou memória ( ip_real_22 `91509f265939` e oob_real_12
`a9cdf5adabac`), a busca no CPython já achou uma entrada que quebra na linha do bug
(`artifacts/v2/orq-2026-10-06-dyn-all/orchestrated.json`). A ideia: rodar o ESBMC **com essa entrada
fixada**, para ele provar só aquele caminho. Se der `VERIFICATION FAILED` na linha do bug e o CPython
reproduzir, é confirmação formal (prova que existe entrada válida que viola a propriedade).

Passos sugeridos (TDD em cada um):
1. Guardar a entrada que quebrou. Hoje `ReplayVerdict` (`verify/replay.py`) descarta `inputs`, e o
   worker (`verify/replay_worker.py`) grava índices na passada exaustiva (`vector`) e valores na
   aleatória. Faça o `_Chooser` guardar os **valores** escolhidos e o `ReplayVerdict` carregá-los.
2. Gerar o programa fixado: as chamadas `nondet_*` acontecem em ordem de execução; uma forma geral é
   trocar cada chamada `nondet_X()` do driver por uma que devolve o próximo valor gravado, ou
   acrescentar `__ESBMC_assume(var == valor)` logo depois de cada atribuição de `nondet_*` no driver.
   Verifique primeiro, com um programa pequeno, qual das duas o ESBMC-Python aceita.
3. Rodar o ESBMC (`verify/esbmc_run.check`) e o CPython (`concrete_replay` com essa entrada) e ler o
   veredito com `verify/outcome.final_verdict`.
4. Plugar como braço `pinned` no orquestrador para resultados `ESBMC_TIMEOUT` com `FUZZ_FOUND`, medir
   nos 20 casos difíceis e no controle das versões corrigidas
   (`artifacts/v2/control-fixed-2026-10-06/report_0of1.json`, `--verification-sources dataset/bugs_reais/arquivo_corrigido`).

Proibido: `--no-unwinding-assertions`.

### 3. Achado I1 da revisão: prazo da passada aleatória

Em `verify/replay_worker.py`, a passada exaustiva e a aleatória dividem um único `deadline`, e a
exaustiva roda primeiro (até 400 execuções de 0,5 s), então a aleatória quase nunca roda. Reserve uma
parte do prazo para cada passada. Teste: alvo lento com 5 `nondet_int` em que só valores grandes
quebram; com `timeout_seconds=8` e `random_runs=300` deve dar `reproduced`.

### 4. Skill unificada no repo

Especificação: `docs/superpowers/specs/2026-10-07-skill-unificada-design.md` (ela aprovou a direção).
Criar `skills/esbmc-python-harness/` (SKILL.md, references, examples **inventados**, nunca casos do
dataset para não contaminar a medição), fazer `verify/agent_arm.py` ler a skill em vez das strings
`_PROMPT`/`_API_SYSTEM`, e acrescentar backends `codex exec` e `gemini -p`. Escreva o plano antes e
mostre a ela.

### 5. Rodada completa com o prompt A5

Só no fim, uma vez: `--v2-variants A1,A2` na rodada completa (ver "Comando base" no README), e depois
validação e orquestrador em cima. Confirmar com ela antes (leva horas).

## Pendências menores (não fazer sem pedido)

Lista em `.superpowers/sdd/2026-10-06-orquestrador-harness/progress.md` (linhas "minor (deferred)").
