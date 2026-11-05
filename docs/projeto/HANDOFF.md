# Handoff (05/11/2026, manhã)

Para outra IA continuar. Leia antes o CLAUDE.md do repo e a memória em
`~/.claude/projects/-home-fernanda-mestrado-llm-esbmc/memory/` (em especial `project_improvements_2026-11-04.md`).
Existe também `docs/projeto/HANDOFF_2026-11-04_PIPELINE.md`, escrito pela sessão do Codex dela em 04/11:
o estado descrito lá foi superado por este arquivo (a junção parcial que ele cita foi desfeita e refeita).

## Regras que valem sempre

- Nenhum commit, push, tag ou PR sem pedido explícito dela. Sem coautoria de IA.
- Nenhuma chamada de API paga sem o ok dela.
- ESBMC congelado do pipeline: `~/esbmc-master` (build-bw, d520a903ae). Não mexer nesse checkout
  (`verify/esbmc_knowledge.py` lê o git dele).
- Português, palavras simples, nunca travessão. Branch: `feat/harness-de-agente`.
- Backups desta sessão: `~/mestrado/backup_llm_esbmc_2026-11-05/` (junção parcial do Codex, skill V1, patch 9843).

## Estado

1. **25 melhorias (lotes A a E) juntadas no checkout principal, sem commit.** Patches aplicados com
   `git apply --3way` a partir dos worktrees `.claude/worktrees/agent-*` (ainda existem; podem ser apagados
   depois do commit). 7 conflitos resolvidos mantendo os dois lados. Relatórios por lote em
   `docs/experimentos/melhorias_2026-11-04/lote_{A..E}.md`. Skill V2 copiada para
   `.claude/skills/llm-esbmc-pipeline/skill.md`.
   - Suíte inteira rodando em duas metades (logs no scratchpad da sessão, `merge/h1.log`, `h2.log`).
     Conferir que passa antes de qualquer commit. `pylint` não está instalado; os lotes usaram `ruff`.
   - Não feitos por limite do ESBMC: itens 4 (57, 61/62), 10; item 17 parcial (async medido, nada reabilitado);
     item 12 sem veredito novo medido (máquina carregada).
2. **Decisões pendentes dela** (propostas padrão entre parênteses):
   `.patch/.diff` sem conversão de fim de linha (sim); Codex como assinatura (sim); `--heal` no fingerprint
   do hybrid (sim, ainda não implementado); checkpoint `artifacts/pgene601/codex-2026-11-03` não retoma com
   o fingerprint novo (preservar, refazer se precisar); harness com `asyncio.run` (depois); hipótese de valor
   no agente, item 7 (feito); `Optional[tuple]` item 10 (esperar ESBMC novo).
3. **Ela quer congelar de novo.** Falta: suíte verde, revisão do diff junto, registro no
   `docs/experimentos/README.md`, decidir se o novo congelamento usa ESBMC master novo (o professor corrigiu
   #9835, #9836, #9838, #9840 a #9843 em 04 e 05/11) ou continua no d520, commit e tag com o ok dela.
4. **ESBMC:** abertas só #9837 e #9839. Nossa correção da #9843 ficou sem uso (o professor fez o PR #9863).
   Um subagente está atualizando `docs/projeto/possiveis_problemas/` contra o master novo, com checagem de
   assert trocado, e vendo se dá para ajudar nas abertas; ele usa `~/esbmc-wt/issue-9843` atualizado para o
   master. Achados F1/F2/F3 da revisão da 9843 (padding de tupla em `in`, desempacotar, `len`; int em tupla
   de float) entram como candidatos no catálogo se ainda falharem.

## Atualização 05/11 (tarde)

- **Suíte com as 25 melhorias juntas: 1531 passaram, 0 falharam** (5 pedaços; um teste de integração foi
  atualizado porque o lote C manteve a guarda de atributo `None` de propósito). Depois disso entrou
  `"heal": args.heal` no config do fingerprint do hybrid (`src/main.py`, teste
  `test_a_resume_under_another_heal_mode_is_refused`).
- **Rodando quando esta nota foi escrita:** subagente do item 17b (harness chama `async def` com
  `asyncio.run`, escreve no checkout principal e anexa seção ao `lote_B.md`) e subagente da **#9074** no
  worktree `~/esbmc-wt/issue-9074` (WIP `daacfa453e` aplicado; falta o falso FAILED de `kw.get('error')`
  sem default tipado `void *`, testes, Mode C, revisão, cobertura). Sem commit, sem PR.
- **`possiveis_problemas` atualizado** contra o master `451f54cab6` (saíram 46, 47, 56, 61, 62, 64, 67, 68,
  69; entraram 70, 71, 72). Issues novas abertas com o ok dela: **#9953** (70/71) e **#9954** (72).
  Ela decidiu: issue que já tem PR não se mexe (#9837 tem #9864, #9839 tem #9861); #9953 e #9954 ficam
  paradas por falta de tokens (avaliar antes se são fáceis; worktree `~/esbmc-wt/issue-9953` pode ter build
  pela metade).
- **Pedido dela para fechar:** depois da #9074, rever `possiveis_problemas` e as melhorias e **commitar tudo**
  (autorizado): commits separados por lote (A, B, C, D, E, item 17b, heal no fingerprint, catálogo),
  sem coautoria de IA, sem os dois PDFs da raiz. Antes: rodar a suíte de novo (em pedaços de até 10 min),
  registrar no `docs/experimentos/README.md`. Push e tag só com pedido dela; congelamento novo ainda
  depende de ela escolher o ESBMC (master novo, recomendado, ou d520).

## Depois do congelamento

Ordem dela: 8a, 8b, 8c, 13 (grafo para o agente), 12 (extensão), porte para o Codex
(`docs/superpowers/specs/2026-11-03-esbmc-codex-port-design.md`). Cada frente: brainstorming e plano antes,
base na literatura. Depois os experimentos (47 da disciplina PGENE601, prazo 08/12).
