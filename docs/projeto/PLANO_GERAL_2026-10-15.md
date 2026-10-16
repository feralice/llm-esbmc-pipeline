# Plano geral (15/10/2026)

Um item por vez. Nenhum experimento ou medição antes do item 6. Um item só termina quando o critério "Pronto quando" estiver cumprido e registrado em
`docs/experimentos/README.md`. Ideia nova no meio de um item vai para "Depois", no fim deste arquivo, e
não é começada. Rodada e2e só no item 6, depois de todas as melhorias.

Métrica principal: bugs do gabarito confirmados na linha (ESBMC acha, replay do código original levanta
a mesma exceção na linha). **Hoje: 14.**

## Estado

| # | Item | Estado |
|---|---|---|
| 1 | Corrigir o gabarito | esperando revisão da Fernanda |
| 2 | Sondas de capacidade do ESBMC (self-healing) | pronto, sem medição (mede no item 6) |
| 3 | Spec com contexto dos chamadores | pronto, sem medição (mede no item 6) |
| 4 | Variantes de prompt | pronto (A13, A14); comparação no item 6 |
| 5 | Oráculo de valor errado no harness | pronto (A15), sem medição (mede no item 6) |
| 6 | Rodada final e2e e métrica para a dissertação | a fazer |
| 7 | Modo scan num repositório real | a fazer |
| 8 | Plugin (MCP + skill) com escolha de LLM | a fazer |

## 1. Corrigir o gabarito

Spec `docs/superpowers/specs/2026-10-15-linha-da-quebra-design.md`, plano
`docs/superpowers/plans/2026-10-15-linha-da-quebra.md`.

- [x] Script e testes (`scripts/propose_crash_lines.py`, 24 testes; suíte 817).
- [x] Causa pelo patch, sem LLM, para os 289 bugs (convenção da área: linhas que a correção muda).
- [x] Avaliação aceita causa antiga, causas do patch e linhas da quebra.
- [x] Causas gravadas para os 289 (213 claras, 41 ambíguas, 33 só inserção, 2 sem casamento).
- [x] Claude propôs a linha da quebra dos 84 bugs de exceção.
- [x] Conferência por revisores (143 casos): quebra 57 aceitas, 14 corrigidas, 5 rejeitadas, 8 dúvidas; causa 96 aceitas, 47 corrigidas.
- [ ] Revisão da Fernanda na tabela `docs/projeto/revisao_linha_da_quebra_2026-10-15.md` (esperando).
- [ ] Aplicar no gabarito.

**Pronto quando:** tabela revisada e gabarito aplicado. Sem medição agora: todos os experimentos ficam para o item 6.

## 2. Sondas de capacidade do ESBMC

Cada regra do harness ganha um programa mínimo que testa se o ESBMC instalado aceita a construção; a
regra só liga quando o ESBMC recusa. Os reprodutores de `docs/projeto/possiveis_problemas/` viram as
sondas. Inclui aplicar o patch `docs/projeto/regras_pos_congelamento_2026-10-15.patch`.

**Pronto quando:** spec e plano aprovados, sondas rodando antes de cada verificação, testes passando.

## 3. Spec com contexto dos chamadores

Os tipos e guardas que os chamadores usam (grafo de chamadas do modo scan) entram no pedido de spec ao
LLM, para reduzir recusas do ESBMC por tipo errado (ex.: ip_real_32, `int` usado com `.groups()`).

**Pronto quando:** spec e plano aprovados, implementado com testes.

- [x] Spec `docs/superpowers/specs/2026-10-16-spec-com-contexto-design.md`, plano
  `docs/superpowers/plans/2026-10-16-spec-com-contexto.md`.
- [x] `--spec-context callers` (padrão) mostra chamadas, referências e fatos de uso ao LLM do spec e
  rejeita tipo contrariado pelo uso; `--spec-context none` é a linha de base para o item 6.
- Retomada: o prompt de sistema do spec não mudou, mas `spec_context` entrou no `config` do fingerprint,
  então rodadas V2 anteriores não retomam com este código.

## 4. Variantes de prompt

Comparar variantes do prompt de detecção no gabarito já corrigido, medidas com Gemini (sem custo).

**Pronto quando:** variantes implementadas e testadas; a comparação roda no item 6.

- [x] Spec `docs/superpowers/specs/2026-10-16-variantes-prompt-design.md`, plano `docs/superpowers/plans/2026-10-16-variantes-prompt.md`.
- [x] A13 (exemplos reais por similaridade, sem o projeto do bug) e A14 (linha citada e condição de disparo), com testes.
- [x] `scripts/print_detection_prompt.py` (prompts sem LLM) e `BACKEND`/`MODEL` em `run_detection_variants.sh`.
- Para o item 6: comparar A5, A5+A9, A5+A13, A5+A14 com `BACKEND=google MODEL=gemini-2.5-flash`.

## 5. Oráculo de valor errado no harness

O LLM escreve a propriedade esperada; o harness a coloca como `assert`; o ESBMC procura violação; o replay
confirma no código original; a versão corrigida não pode violar (controle). Abre os 178 bugs de valor
errado para a métrica de confirmação.

**Pronto quando:** spec e plano aprovados, implementado com testes; a medição roda no item 6.

- [x] Spec `docs/superpowers/specs/2026-10-16-oraculo-valor-design.md`, plano
  `docs/superpowers/plans/2026-10-16-oraculo-valor.md`.
- [x] Variante A15 (`metadata.failure_mode`), propriedade na etapa de spec, `assert` no driver, replay e
  controle com a versão corrigida; vereditos `VALUE_CONFIRMED`, `VALUE_VIOLATION`, `PROPERTY_REJECTED`;
  métrica à parte (`value_confirmed_at_bug`, `confirmed_at_bug_with_value`).
- Para o item 6: detecção com `--v2-variants A15` (junto das outras) e verify com
  `--fixed-sources dataset/bugs_reais/arquivo_corrigido`.

## 6. Rodada final e2e

Todos os experimentos: comparação de prompts, gabarito novo e rodada final, com tudo congelado. Retomar ou refazer a rodada final (checkpoint atual em
`artifacts/v2/final-2026-10-15-codex`, pausado em 470/564), rodar o orquestrador e contar a métrica.

**Pronto quando:** número final registrado no README e tag de congelamento criada.

## 7. Modo scan e 8. Plugin

Depois do número final. Primeira rodada real do scan num repositório pequeno; plugin com MCP + skill e
escolha de LLM (com fallback quando um limite acaba).

## Depois (ideias anotadas, não começar)

- Fallback automático entre LLMs.
- Rascunhos de issue para o Lucas a partir dos reprodutores 19 a 44.
- 47 bugs da disciplina PGENE601.
- Harness de desenvolvimento no Claude Code (skills/agentes do próprio projeto).
- Fine-tuning (trabalho futuro): precisa de dataset maior e modelo aberto em GPU maior; few-shot (item 4) cobre parte do ganho.
