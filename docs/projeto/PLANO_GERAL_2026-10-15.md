# Plano geral (15/10/2026, revisto em 16/10)

Um item por vez. Nenhum experimento ou medição antes do item 6. Um item só termina quando o critério "Pronto quando" estiver cumprido e registrado em
`docs/experimentos/README.md`. Ideia nova no meio de um item vai para "Depois", no fim deste arquivo, e
não é começada. Rodada e2e só no item 6, depois de todas as melhorias.

Métrica principal: **bugs distintos** do gabarito confirmados na linha (ESBMC acha, replay do código
original levanta a mesma exceção na linha), contados por bug e não por hipótese. **Hoje: 14.** Na última
rodada completa: 19 de 230 bugs exercitados tiveram alguma confirmação (8,3%), nem todas na linha.

## Estado

| # | Item | Estado |
|---|---|---|
| 1 | Corrigir o gabarito | pronto (aplicado em 16/10) |
| 2 | Sondas de capacidade do ESBMC (harness auto-adaptativo) | pronto; revisto num bug real (dz_real_03) |
| 3 | Spec com contexto dos chamadores | pronto; barraria 46 de 708 specs gravados |
| 4 | Variantes de prompt | pronto (A13, A14); comparação no item 6 |
| 5 | Oráculo de valor errado no harness | pronto; av_real_07 VALUE_CONFIRMED com propriedade à mão |
| 5b | Texto escondido no contraexemplo (`nondet_str`) e ESBMC v8.6 como padrão | pronto (commit a1fccb4) |
| 6a | Backend `gemini_cli` | cancelado: a Fernanda decidiu usar o Claude (16/10). Em 16/10 o login pessoal do Gemini CLI falhava (IneligibleTierError) |
| 6 | Diagnóstico, intervenções e rodada final (4 semanas, abaixo) | semanas 1 a 3 feitas (Fase 20 do README); semana 4 (rodada com LLM) espera a Fernanda |
| 6b | Harness que aprende com o repositório do ESBMC, automático (regras de reescrita guiadas pelos testes de regressão, com sonda; stubs fiéis; issues ao Lucas) | novembro, depois do número final do item 6; spec e plano com superpowers antes, com aprovação da Fernanda |
| 7 | Modo scan num repositório real | depois da qualificação |
| 8 | Plugin/extensão (MCP + skill) com escolha de LLM | depois da qualificação |

## Plano revisado (16/10), a partir da segunda opinião

Ideia central: não perseguir os 62 tipos de recusa nem técnicas novas de LLM. Descobrir, num grupo pequeno
de bugs, o que separa uma hipótese promissora de um bug confirmado, atacar só 2 ou 3 obstáculos e medir.
Prompt da consulta: `docs/projeto/prompt_segunda_opiniao.md`.

Perguntas de pesquisa:
- **QP1:** quantos bugs reais o LLM detecta na linha certa?
- **QP2:** quanto da detecção a verificação formal confirma, e o que impede o resto (funil por bug)?
- **QP3:** que intervenções no harness aumentam essa fração, e quanto o ESBMC acrescenta à busca dinâmica
  com as mesmas hipóteses?

Item 6 em 4 semanas:

| Semana | O quê | LLM? |
|---|---|---|
| 1 | Auditar os 19 bugs confirmados (entrada admissível, controle na versão corrigida também para exceções); abrir os 71 "veredito sem confirmação" por motivo real; funil por bug, explicando os 59 bugs fora da rodada e os 114 cortados por cota | não |
| 2 | **Piloto do harness que aprende com o repositório do ESBMC**, feito à mão em ~20 bugs travados, por causa e projeto: para cada recusa, buscar nos testes de regressão do ESBMC (`regression/python/`, 5.671 programas) a forma que ele aceita e destravar com ela, anotar o próximo obstáculo até testemunha e replay; separar candidatos a correção no frontend do ESBMC (`IOError`, `enumerate` aninhado, `*args`) para o Lucas | não |
| 3 | Implementar só as 2 intervenções de maior ganho por dia que o piloto mostrar, com teste (se o piloto confirmar bugs, uma delas é automatizar o passo da semana 2: o LLM reescreve a linha recusada guiado pelos testes do ESBMC, validado por testes diferenciais, e o caso fica guardado para virar regra com sonda); reservar bugs não usados no desenvolvimento | não |
| 4 | Rodada congelada: Claude pela assinatura (`--backend claude_cli`, retomando quando o limite acabar), ESBMC v8.6, comparação de prompts (amostra de 50) e rodada final; comparação com o braço dinâmico por bug, tempo e contribuição exclusiva; registrar positivos e negativos | sim |

Comandos da semana 4 (rodam só com a Fernanda; usam o limite da assinatura do Claude):

```bash
# 1. Prompts na amostra de 50 (detecção só; cada variante retoma sozinha depois de um limite)
BACKEND=claude_cli MODEL=claude-sonnet-5-5 scripts/run_detection_variants.sh 2026-11-XX-amostra \
  dataset/bugs_reais/amostra_deteccao.json A1,A2 A1,A2,A9 A1,A2,A13 A1,A2,A14
# 2. Rodada final do zero com a vencedora (<V>), ESBMC v8.6, oráculo de valor e controle
PYTHONPATH=src .venv/bin/python -W ignore::SyntaxWarning src/main.py --mode hybrid --v2-stage end-to-end \
  --input dataset/bugs_reais/funcao_com_bug --ground-truth dataset/bugs_reais/ground_truths.json \
  --verification-sources dataset/bugs_reais/arquivo_com_bug --fixed-sources dataset/bugs_reais/arquivo_corrigido \
  --v2-variants <V>,A15 --backend claude_cli --model claude-sonnet-5-5 \
  --synth-backend claude_cli --synth-model claude-sonnet-5-5 \
  --esbmc-command ~/esbmc-releases/v8.6/esbmc.sh --bound 5 --timeout 180 --output-dir artifacts/v2/final-2026-11-XX
# (repetir com --resume quando o limite acabar)
# 3. Funil e controle da rodada
PYTHONPATH=src .venv/bin/python scripts/v2_funnel.py artifacts/v2/final-2026-11-XX --out artifacts/v2/final-2026-11-XX/funil
PYTHONPATH=src .venv/bin/python scripts/v2_audit_control.py artifacts/v2/final-2026-11-XX/v2_verify_report.json \
  --out artifacts/v2/final-2026-11-XX/controle
```

Cuidados registrados:
- Não chamar as sondas de "self-healing" sem diferenciar: o termo já é usado no ESBMC-AI (LLM corrige o
  programa com o contraexemplo do ESBMC), do grupo do Lucas. Aqui é o harness que se calibra ao verificador.
- Auditar as regras que podem mudar o comportamento (decoradores removidos, `@property` como atributo,
  proteções de `None`): o replay no original protege a confirmação, mas a regra pode esconder um bug.
- Conclusão restrita: limites do pipeline com ESBMC-Python neste corpus, não da verificação formal de
  Python em geral.
- Referências só depois de conferidas (trabalhos próximos: ESBMC-Python, Shivaji et al., PyVeritas,
  ESBMC-AI, Evident).

Cronograma até a qualificação (fevereiro de 2027): item 6 nos próximos dias (rodada final em andamento); item 6b em novembro (semanas 1-2 regras de reescrita com sonda, semana 3 stubs fiéis, semana 4 medição sem LLM e issues); texto em dezembro; revisão em janeiro.

## 1. Corrigir o gabarito

Spec `docs/superpowers/specs/2026-10-15-linha-da-quebra-design.md`, plano
`docs/superpowers/plans/2026-10-15-linha-da-quebra.md`.

- [x] Script e testes (`scripts/propose_crash_lines.py`, 24 testes; suíte 817).
- [x] Causa pelo patch, sem LLM, para os 289 bugs (convenção da área: linhas que a correção muda).
- [x] Avaliação aceita causa antiga, causas do patch e linhas da quebra.
- [x] Causas gravadas para os 289 (213 claras, 41 ambíguas, 33 só inserção, 2 sem casamento).
- [x] Claude propôs a linha da quebra dos 84 bugs de exceção.
- [x] Conferência por revisores (143 casos): quebra 57 aceitas, 14 corrigidas, 5 rejeitadas, 8 dúvidas; causa 96 aceitas, 47 corrigidas.
- [x] Revisão da Fernanda na tabela `docs/projeto/revisao_linha_da_quebra_2026-10-15.md`.
- [x] Aplicado no gabarito (289 com causa, 58 com quebra própria; Fase 17 do README).

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

Comparar variantes do prompt de detecção no gabarito já corrigido, medidas com o Claude pela assinatura.

**Pronto quando:** variantes implementadas e testadas; a comparação roda no item 6.

- [x] Spec `docs/superpowers/specs/2026-10-16-variantes-prompt-design.md`, plano `docs/superpowers/plans/2026-10-16-variantes-prompt.md`.
- [x] A13 (exemplos reais por similaridade, sem o projeto do bug) e A14 (linha citada e condição de disparo), com testes.
- [x] `scripts/print_detection_prompt.py` (prompts sem LLM) e `BACKEND`/`MODEL` em `run_detection_variants.sh`.
- Para o item 6: comparar A5, A5+A9, A5+A13, A5+A14 com `BACKEND=claude_cli`.

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

Em 4 semanas (tabela do plano revisado acima). A rodada final começa do zero: o checkpoint
`artifacts/v2/final-2026-10-15-codex` não retoma com o código atual.

**Pronto quando:** número final registrado no README e tag de congelamento criada.

Decisões da Fernanda (16/10): LLM = Claude pela assinatura (`--backend claude_cli`), no lugar do Gemini; ESBMC = release oficial v8.6
(`~/esbmc-releases/v8.6`), com `--no-pointer-check --no-align-check` como nas rodadas anteriores.

## 7. Modo scan e 8. Plugin

Depois do número final. Primeira rodada real do scan num repositório pequeno; plugin com MCP + skill e
escolha de LLM (com fallback quando um limite acaba).

## Depois (ideias anotadas, não começar)

- Fallback automático entre LLMs.
- Rascunhos de issue para o Lucas a partir dos reprodutores 19 a 44.
- 47 bugs da disciplina PGENE601.
- Harness de desenvolvimento no Claude Code (skills/agentes do próprio projeto).
- Issue do `nondet_str()` sem valor no contraexemplo: rascunho pronto em `docs/projeto/rascunho_issue_nondet_str.md` (reprodutor 45, confirmado na v8.6), a Fernanda vai falar com o Lucas. O pipeline contorna com o witness do `--generate-pytest-testcase`.
- Reescrita da linha recusada por LLM, guiada pelos testes de regressão do ESBMC e validada por testes
  diferenciais (antigo "2b"/nível 1): só se o piloto da semana 2 mostrar que vale.
- Modelos de operações de biblioteca gerados por LLM (nível 2): só para operações compartilhadas por vários bugs.
- Skill `/nova-regra`: transformar reescritas repetidas em regra com sonda, com aprovação humana.
- Code smells como camada da ferramenta (só LLM, sem verificação formal), junto do item 8.
- Fine-tuning (trabalho futuro): precisa de dataset maior e modelo aberto em GPU maior; few-shot (item 4) cobre parte do ganho.
