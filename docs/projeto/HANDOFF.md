# Handoff (05/11/2026)

## PARADO AQUI: atualização mais recente (05/11, noite)

Fernanda vai continuar com o Codex. Ler antes o `CLAUDE.md` do repo. Regras: português, palavras simples, sem
travessão; commit só com pedido dela, sem coautoria de IA; push, tag, PR e issue só com ok dela; não adicionar
os dois PDFs da raiz; nenhuma chamada de API paga sem ok (rodadas usam a assinatura, `claude_cli`).

### Feito nesta sessão

- **Congelamento c:** tag `v2-congelado-2026-11c` (commit `578673c`; último commit de código `428454f`), ESBMC
  master `451f54cab68f22261aad0f53ea8236261d8384a5` em `~/esbmc-master/build-bw` (8.6.0). Suíte: 1599 passaram
  em seis pedaços (`ls tests/test_*.py | split -n r/6`, cada um com `timeout 10m .venv/bin/python -m pytest -q -p no:cacheprovider`).
  Registrado em `docs/experimentos/README.md`. Tag e branch **sem push**.
- **Extensão (`d553e97`):** em inglês, comando `/verify-repo` (era `/verificar-repo`); `/self-healing` removido
  porque o self-healing já roda dentro do fluxo (decisão dela). `scripts/add_repair.py` e `check_preserved.py` ficam.
- **Catálogo `possiveis_problemas`:** `rodar.sh ~/esbmc-master/esbmc.sh` (sem flags extras: o `esbmc.sh` já
  passa `--no-pointer-check --no-align-check`) deu o mesmo do README; nenhum caso corrigido.
- **Decisão dela (05/11):** ESBMC sempre o master mais novo, inclusive antes de cada rodada durante os
  experimentos (registrar o commit do ESBMC por rodada); issues continuam sendo abertas.

### Issues do ESBMC (conferido em 05/11)

- Fechadas pelo professor e já no binário: #9835, #9836, #9838, #9840 a #9843 (e quase todas de #9073 a #9093).
- Com PR do professor aberto: #9837 (PR #9864), #9839 (PR #9861). Não mexer.
- Sem PR e sem responsável: **#9074** (a nossa, abaixo), #9953, #9954 (worktree `~/esbmc-wt/issue-9953` só
  com cmake configurado, nada feito).

### PR da #9074: em andamento, abrir só com 100% testado (pedido dela)

Worktree `~/esbmc-wt/issue-9074`, branch `fix/issue-9074`, sobre master `451f54cab6`, **sem commit**:
`src/python-frontend/preprocessor/vararg_mixin.py`, `src/python-frontend/python_annotation/annotation_conversion.inl`
e 22 testes `regression/python/github_9074_*`. Título e descrição propostos:

```
[python] Lower **kwargs read through .get() in __init__

A constructor that reads its `**kwargs` was refused with `Object "kw" not found`.
The preprocessor now packs the keywords each construction passes into a dict and
rewrites `__init__` to take them, and `d.get(k)` on a `dict[K, int]` (or an
empty `{}` only read by `.get`) is typed `Optional[int]` so the stored attribute
compares against None. Shapes it cannot preserve (str/float/None values,
mutation of the dict, name collisions) are refused with a message instead of a
wrong verdict.

Fixes #9074
```
Label `python`. Já passou: `scripts/check_python_tests.sh github_9074`; clang-format 23.1.1 nas linhas novas
(`/tmp/t9074/cf/v/bin/clang-format`, só as linhas do diff: o arquivo tem violações antigas fora dele); YAPF 0.43
(`/tmp/t9074/cf/v/bin/yapf`) aplicado nos 22 testes. Revisão anterior sem bloqueio.

**Atualização (05/11, fim):** cobertura Mode B deu **PASS** (40/40 linhas C++ novas; `.inl` 80,62% para 80,97%;
a queda antiga era erro de medição). Os 24 `github_9074*` passaram com Bitwuzla e `--z3`.
`github_9074_empty_dict_fail/test.desc` ganhou `assertion !b->x\.is_none` (antes passava no master pelo motivo
errado). Revisão feita: achados de veredito errado testados e refutados; aplicadas duas correções em
`vararg_mixin.py` (classe nunca construída recusada com o motivo "the class is never constructed"; tirado o
default `calls=()`), com teste novo `github_9074_unused_unsupported`. **Falta recompilar**
(`ninja -C build/coverage-pr -j4 esbmc`) e rodar de novo os `github_9074*` (Bitwuzla e Z3) e o subconjunto
(`ctest -R ... -j2`). A troca `__esbmc_` para `_esbmc_` nos nomes gerados é proposital (name mangling dentro da
classe): citar no PR. O WSL travou 3 vezes por memória: usar `ulimit -v 6000000`, `ctest -j2`, `ninja -j4`.
Mode C ainda não feito.

Falta, nesta ordem:
1. **Cobertura (esbmc-coverage-pr Mode B):** estava rodando no fim da sessão. A primeira tentativa travou o WSL
   (falta de memória: 23 GiB, 16 núcleos): usar `ninja -j6` e `ctest -j4` no máximo. Bars: 100% das linhas
   adicionadas, nenhum arquivo tocado caindo, total do repo não caindo. Uma medição antiga deu 30,03% para
   29,95% em `annotation_conversion.inl` com avisos de "hash mismatch" (provável mistura de perfis de binários
   diferentes): medir com pasta de perfil limpa. `~/esbmc-master/build-cov` existe; conferir de que commit é.
2. Regressão: todos `github_9074*` com Bitwuzla e com `--z3`, e o subconjunto
   `regression/python/.*(dict|get|kwarg|vararg|9073|9074|optional|class|init|attr|none)` (cada ctest até 10 min).
3. Mode C-Live nos ramos novos do C++ (Bitwuzla e Z3). Da outra vez ficou inconclusivo: o ESBMC não lê o
   cabeçalho de JSON do frontend. Se travar de novo, perguntar a ela se aceita como prova que cada ramo novo é
   executado por um teste (medido na cobertura).
4. Revisão de código do diff final.
5. Mostrar a ela título, descrição e diff; com o ok: commit (sem coautoria), push e PR no esbmc/esbmc.

### Depois do PR

- Ver se há algo a melhorar no pipeline (pedido dela).
- Rodada PGENE601 pronta, **não rodada**: `artifacts/pgene601/congelado-c-2026-11-05/run.sh` (igual a
  `e2e-2026-11-02`, só muda a pasta; `commit.txt` gravado). Em 02/11 foram 226 chamadas (73 detecção, 153
  síntese). Antes: atualizar o ESBMC se houver master novo. Não rodar junto com build pesado. Registrar no README.
- Push da branch `feat/harness-de-agente` e das tags, com ok dela.
- Rascunho `docs/projeto/possiveis_problemas/issues/73_pytest_argumentos_extras.md`: conferir contra a #7188 e
  PRs antes de propor issue.
- Testar `/verify-repo` num repositório pequeno. Depois: item 14, smells 200, 8a/8b/8c, 13, porte Codex.

## Histórico da sessão anterior

O texto abaixo preserva decisões e contexto anteriores. Onde houver conflito, a atualização PARADO AQUI acima prevalece.

### Handoff anterior

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

## PARADO AQUI (05/11, 16:20, tokens acabando; tudo parado por pedido dela)

- **ESBMC novo compilado:** `~/esbmc-master/build-bw` = master `451f54cab6` (8.6.0); d520 guardado em
  `~/esbmc-bin/esbmc-d520a903ae`. Passo 3 da ordem (compilar) feito.
- **Com o binário novo, 2 testes falham** em `tests/test_verify_esbmc_integration.py`
  (`test_confirmed_free_function_gets_a_pytest_reproducer_from_esbmc`, `test_a_coroutine_is_verified_through_asyncio_run`):
  o pytest que o ESBMC gera chama a função com aridade errada (`TypeError: inverse() takes...`; o master agora
  gera `f(arg0, arg1, ...)`, ver reproducer 52). Um subagente começou a adaptar `verify/pytest_gen.py` e foi
  parado no meio: conferir `git diff` (pode haver edição parcial em `pytest_gen.py`/testes), terminar ou
  descartar, e se o formato novo for bug do ESBMC, marcar 'invalid' com motivo e rascunhar issue (só se não
  houver PR). Depois rodar a suíte em 6 pedaços e só então congelar (tag `v2-congelado-2026-11c`, push com ok).
- **#9074:** subagente parado no meio do conserto dos achados C1/M1/M2 (último passo dele: "CPython check,
  formatting e subset"). Worktree `~/esbmc-wt/issue-9074`: +195/−46 em 2 arquivos, binário recompilado 16:10,
  testes novos `github_9074_{str_get,str_get_fail,str_value_unsupported,mutated_unsupported,collision_unsupported}`.
  Falta: rodar todos `github_9074*` (Bitwuzla e `--z3`), `scripts/check_python_tests.sh github_9074`, subconjunto
  `regression/python/.*(dict|get|kwarg|vararg|9073|9074|optional|class|init|attr|none)`, clang-format 23.1.1,
  `code-reviewer` e `esbmc-coverage-pr` Mode B. Se passar: ela autorizou abrir o PR (ver acima).
- Depois: rever `possiveis_problemas` com o binário novo (`rodar.sh`, checagem de assert trocado).

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
