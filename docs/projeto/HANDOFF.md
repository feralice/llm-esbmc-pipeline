# Handoff (05/11/2026)

## PARADO AQUI: atualização mais recente

Fernanda pediu para **parar e esquecer o PR da #9074** e focar no pipeline. Não retomar essa issue nem abrir PR sem novo pedido. O worktree `~/esbmc-wt/issue-9074` permanece com alterações e testes sem commit. As instruções antigas abaixo para retomar a #9074 estão superadas.

O ESBMC `~/esbmc-master/build-bw` foi compilado no master `451f54cab68f22261aad0f53ea8236261d8384a5`, versão 8.6.0. O master remoto foi consultado e estava nesse commit; `ninja -C build-bw esbmc` terminou com sucesso. Antes de congelar ou rodar experimentos, conferir novamente o master mais recente. O binário anterior está em `~/esbmc-bin/esbmc-d520a903ae`.

### Próximos passos do pipeline

1. Rever `docs/projeto/possiveis_problemas/` com o ESBMC atualizado: executar `rodar.sh`, trocar o valor das asserções nos casos que passarem, conferir e registrar os resultados. Explicar o que foi observado para Fernanda avaliar.
2. Revisar as alterações sem commit e, para congelar, registrar em `docs/experimentos/README.md` os commits do pipeline e do ESBMC. A tag planejada é `v2-congelado-2026-11c`; commit, tag e push só com pedido explícito dela.
3. Depois, os experimentos escolhidos são os 47 bugs da disciplina PGENE601 (prazo registrado: 08/12), o item 14 (bug semeado) e 200 smells. Os demais itens continuam na seção histórica abaixo.

### Estado local e verificações

- As 25 melhorias do pipeline, as lições automáticas do self-healing (`764fe85`) e a comparação de AST menos restrita (`c74c900`) foram concluídas e commitadas localmente, sem push.
- `src/research_pipeline/verify/pytest_gen.py` está sem commit: chamadas geradas pelo ESBMC com quantidade incorreta de argumentos são identificadas como inválidas. `tests/test_verify_esbmc_integration.py` e `tests/test_verify_pytest_gen.py` também foram alterados, com teste específico da contagem e expectativas adaptadas. Revisar os diffs antes de congelar.
- Os 12 testes diretamente relacionados ao gerador e às duas integrações passaram. A suíte completa passou em seis grupos: **1.599 testes** (230, 233, 211, 381, 160 e 384). O terceiro grupo precisou ser repetido com acesso ao cache em `~/.cache/llm_esbmc`.
- `docs/projeto/possiveis_problemas/issues/73_pytest_argumentos_extras.md` é um rascunho sem commit. O defeito foi reproduzido isoladamente: o ESBMC gerou `inverse(arg0, arg1)` para uma função de um argumento, e o pytest terminou com `TypeError`. A issue fechada #7188 também relata argumentos incorretos; conferir se é a mesma causa e verificar PRs antes de propor uma nova issue.
- Os dois PDFs não rastreados na raiz não devem ser adicionados ao Git. A branch `feat/harness-de-agente` estava 23 commits à frente da origem, sem push, nesta atualização.

### Registro da #9074, suspensa por pedido de Fernanda

A sessão corrigiu uma colisão de nomes gerados. Passaram 285 testes relacionados, 24 casos específicos com Z3 e os novos pares com Bitwuzla; a checagem dos exemplos Python também passou. A revisão refeita não encontrou outro bloqueio concreto. O portão de cobertura **não passou**: as 40 linhas executáveis adicionadas foram alcançadas, mas uma campanha ampliada mostrou queda local de 30,03% para 29,95% e avisos de incompatibilidade de hash. Mode C-Live ficou inconclusivo porque o parser do ESBMC não analisou o cabeçalho real. A investigação foi interrompida por pedido dela. Não retomar sem novo pedido.

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
