# Handoff (05/11/2026, fim da sessão)

Para outra IA continuar. Leia antes o CLAUDE.md do repo e a memória em
`~/.claude/projects/-home-fernanda-mestrado-llm-esbmc/memory/` (em especial `feedback_esbmc_always_newest.md`,
`feedback_auto_lessons.md`, `feedback_issue_only_without_pr.md`, `project_improvements_2026-11-04.md`).
`docs/projeto/HANDOFF_2026-11-04_PIPELINE.md` (sessão do Codex de 04/11) está superado por este arquivo.

## Regras que valem sempre

- Commit só com pedido dela (nesta sessão ela pediu para commitar as melhorias). Push, tag e PR só com pedido.
  Sem coautoria de IA. Não adicionar os dois PDFs da raiz.
- Nenhuma chamada de API paga sem ok dela.
- ESBMC: **sempre o master mais novo** ao congelar ou rodar experimentos (decisão dela, 05/11).
- Issue do ESBMC: só trabalhar (ou abrir) se **não existir PR** para ela, e só se for fácil.
- Português, palavras simples, nunca travessão. Branch do repo: `feat/harness-de-agente`.
- Backups desta sessão: `~/mestrado/backup_llm_esbmc_2026-11-05/`; binário antigo: `~/esbmc-bin/esbmc-d520a903ae`.

## O que já está feito (commitado, sem push)

9 commits sobre `dc64068`, de `793cc12` a `f1e480b`: as 25 melhorias (lotes A a E), `--heal` no fingerprint do
hybrid, item 17b (`async def` via `asyncio.run`), catálogo `possiveis_problemas` medido no master `451f54cab6`,
docs (PLANO, README de experimentos). Suíte: **1546 passaram, 0 falharam** (rodar em pedaços de até 10 min:
`ls tests/test_*.py | split -n r/6`, cada pedaço com `timeout 10m .venv/bin/python -m pytest -q -p no:cacheprovider`).
Issues abertas por nós em 05/11: #9953 e #9954 (Optional[tuple], sem PR, paradas por falta de tokens).

## Estado no fim da sessão (05/11, noite)

- **#9074:** primeira versão pronta no worktree `~/esbmc-wt/issue-9074` (build em `build/`), mas a revisão
  achou bloqueios: **C1** `d.get(k)` em `dict[str,str]` virou falso FAILED (`annotation_conversion.inl`
  ~3649-3674 tipa todo `dict[K,V]` como `Optional[V]`; só int/float/bool ficam certos); **M1** `**kw` com
  valor str/None/lista/float virou falso FAILED em vez de recusa (restringir a reescrita em `vararg_mixin.py`
  a valores int/float/bool); **M2** recusa e mensagem devem vir do pré-processador, com teste do caso
  `def __init__(self, error, **kw)` + `Box(error=1)`. Probes em
  `/tmp/claude-1000/-home-fernanda-mestrado-llm-esbmc/e749d686-0c8c-42ab-8b15-f7fd382644e5/scratchpad/{p,q,r,s,t,u}/`
  (temporário). Um subagente estava corrigindo; conferir o worktree, rodar `github_9074*` (Bitwuzla e
  `--z3`), o subconjunto `regression/python/.*(dict|get|kwarg|vararg|9073|9074|optional|class|init|attr|none)`,
  depois `code-reviewer` de novo e `esbmc-coverage-pr` Mode B (o portão foi parado antes de medir).
- **#9074, autorização dela (05/11):** se a revisão (`code-reviewer`) não achar bloqueio e o portão de
  cobertura (`esbmc-coverage-pr` Mode B) der PASS, commitar no worktree (`[python] ...`, `Fixes #9074`, sem
  coautoria), dar push da branch `fix/issue-9074` e abrir o PR no esbmc/esbmc com label `python`.
- **AST menos restrita (pedido dela, 05/11):** `target_preserved`/`_as_original` em `verify/validation.py:49`
  exige corpo idêntico. Decisão: afrouxar só o que não muda o caminho do bug (anotações, docstring, `pass`,
  contornos do `compat.py`, renomeação consistente de locais); continuar recusando linha removida ou fora de
  ordem, condição/operador/constante trocados, `raise`/`assert` removidos, chamada trocada por valor. Medir antes
  e depois nos `artifacts/`. Um subagente estava nisso no checkout principal, sem commit: conferir `git diff`,
  rodar a suíte em pedaços e commitar. **Feito e commitado em 05/11** (73 para 52 recusas no agente, 86 para 6 no motor).
- **Lições automáticas do self-healing:** feito e commitado (`764fe85`).

## O que falta, NESTA ORDEM (ordem dela)

1. **Terminar a #9074** (`**kwargs` no `__init__`, sem PR). Worktree `~/esbmc-wt/issue-9074`, branch
   `fix/issue-9074`, WIP `daacfa453e` aplicado sem commit. Falta: o falso FAILED de `Box(error=1)` +
   `b._error == 1` (atributo de `kw.get('error')` sem default fica `void *`), testes `regression/python/github_9074*`
   com pares `_fail`, `scripts/check_python_tests.sh github_9074`, subconjunto ctest (vararg, kwargs, 9073,
   9002, 8497, 9341, 9304, 9539), clang-format 23.1.1, Mode C (Bitwuzla e Z3), `code-reviewer`,
   `esbmc-coverage-pr` Mode B. Um subagente estava nisso; conferir o estado do worktree. Mostrar a ela antes
   de abrir PR (label `python`, título `[python] ...`, `Fixes #9074`).
2. **Ajustar o self-healing: lições automáticas** (decisão dela). Toda correção do harness que passa nas
   checagens de candidata (`scripts/v2_repair_candidates.py`; sem `STUB_INDUCED`, sem mudar o comportamento
   da função) entra no caderno na hora, com origem "automatica", data, rodada, caso e mensagem do ESBMC;
   sem duplicatas; `notebook_version` por caso; flag `--no-auto-lessons` (entra no fingerprint do hybrid e do
   scan); entrada no `docs/experimentos/README.md` avisando que o resultado passa a depender da ordem dos casos.
   **Feito em 05/11** (commit logo após `f1e480b`; suíte 1566 passaram). Lições ficam em
   `verify/skills/reparos-aprendidos/SKILL.md`, que é rastreado no git: rodadas normais vão deixá-lo modificado.
3. **Compilar o ESBMC mais novo e conferir:** `~/esbmc-master` já está no código `451f54cab6` (o `pull` foi
   feito), mas o binário `build-bw` ainda é o antigo (build interrompido). Fazer `git -C ~/esbmc-master pull
   --ff-only origin master`, `ninja -C ~/esbmc-master/build-bw esbmc`, `--version`, e rodar
   `tests/test_verify_esbmc_integration.py` (as sondas de capacidade podem ligar ou desligar regras com o
   binário novo; ajustar testes só se a mudança for esperada e explicada).
4. **Trocar o pipeline para o ESBMC novo e congelar:** o pipeline já usa `~/esbmc-master/esbmc.sh`, então basta o
   binário novo. Registrar no `docs/experimentos/README.md` o commit do pipeline e do ESBMC; criar tag
   `v2-congelado-2026-11c` e fazer push só com o ok dela.
5. **Rever `docs/projeto/possiveis_problemas/`** com o binário novo: rodar `rodar.sh`, fazer a checagem de
   trocar o valor do assert nos que passarem, tirar os corrigidos (como em 03/11 e 05/11), anotar o resto.

## Depois disso

Experimentos (ela quer começar logo): 47 bugs da disciplina PGENE601 (prazo 08/12), item 14 (bug semeado),
smells 200. Depois, na ordem dela: 8a, 8b, 8c, 13 (grafo para o agente), 12 (extensão), porte para o Codex
(`docs/superpowers/specs/2026-11-03-esbmc-codex-port-design.md`); cada frente com brainstorming e plano antes.
Atenção: o fingerprint novo recusa `--resume` de checkpoints antigos (ex.: `artifacts/pgene601/codex-2026-11-03`).
