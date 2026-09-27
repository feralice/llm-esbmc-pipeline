# Evidência de código real versus abstração Implementation Plan

> **Status (2026-09-27): concluído.** A avaliação, o resumo da CLI, a
> documentação e os testes distinguem `scalar` de `native`, `real_body` e
> `driver`. Evidência: testes focados e suíte completa passando.

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Separar, nas métricas e na documentação do V2, confirmações executadas no código original de confirmações obtidas apenas em harnesses escalares abstratos.

**Architecture:** O pipeline de síntese continuará produzindo os mesmos ScanCaseResult e mantendo o fallback escalar. A camada de avaliação usará harness_tier como fonte de força da evidência: tiers native, real_body e driver podem contribuir para confirmação end-to-end; tier scalar será reportado separadamente como confirmação da abstração. O resumo da CLI e a documentação refletirão as duas contagens.

**Tech Stack:** Python 3.9+, biblioteca padrão, pytest, JSON e Markdown.

**Spec:** docs/superpowers/specs/2026-09-25-evidence-real-body-design.md

## Global Constraints

- O fallback escalar permanece disponível e não será removido.
- Somente tiers native, real_body e driver podem contar como confirmação do código real.
- Um resultado sem harness_tier não será promovido silenciosamente a evidência do corpo real.
- Nenhum ground truth será enviado à LLM, ao harness ou ao ESBMC.
- Não alterar flags nem o comportamento interno do ESBMC-Python.
- Não commitar alterações sem pedido explícito da usuária.

## Review Focus

- Confirmação escalar correta: deve aparecer como abstração e não aumentar end_to_end.tp; teste na Task 1.
- Confirmação escalar de falso positivo: não deve aumentar end_to_end.fp; teste na Task 1.
- Confirmação em native, real_body e driver: deve ser contada uma vez na métrica principal; teste na Task 1.
- Resultado antigo sem tier: deve permanecer visível, mas não provar o corpo real; teste na Task 1.
- Resumo por categoria: confirmed deve representar corpo real e um contador separado deve representar abstração; teste na Task 2.

---

### Task 1: Separar a métrica de confirmação por tier de evidência

**Files:**
- Modify: src/research_pipeline/v2_evaluator.py:120-205
- Modify: tests/test_v2_evaluator.py
- Test: tests/test_v2_evaluator.py

**Interfaces:**
- Consumes: objetos ScanCaseResult já produzidos pelo pipeline, especialmente classification e harness_tier.
- Produces: evaluate_v2_results(...) -> dict com synthesis_given_correct_detection.confirmed_on_real_body, confirmed_on_abstraction, unknown_evidence, abstraction_only_rate, e end_to_end calculado apenas com evidência real.

- [ ] **Step 1: Atualizar os testes existentes para declarar o tier da evidência**

Nos casos que hoje criam ScanCaseResult(correct, "confirmed_on_abstraction", ...), definir explicitamente harness_tier="scalar". Nos casos de confirmação do corpo real, usar os tiers correspondentes: native, real_body ou driver. Isso torna os testes compatíveis com a regra de não inferir evidência a partir apenas da classificação.

- [ ] **Step 2: Escrever o teste de regressão para confirmação escalar**

Adicionar um teste que crie uma detecção correta com classification="confirmed_on_abstraction" e harness_tier="scalar", além de uma hipótese falsa com o mesmo tier. Verificar que:

    assert metrics["synthesis_given_correct_detection"]["confirmed_on_abstraction"] == 1
    assert metrics["end_to_end"]["tp"] == 0
    assert metrics["end_to_end"]["fp"] == 0
    assert metrics["pipeline_stage_losses"]["by_stage"]["abstraction_only"] == 1

- [ ] **Step 3: Rodar o teste e confirmar que ele falha com a semântica atual**

Run: python -m pytest tests/test_v2_evaluator.py -q

Expected: FAIL porque a implementação atual conta confirmed_on_abstraction dentro de end_to_end.

- [ ] **Step 4: Escrever testes para os tiers que executam código real**

Adicionar um teste parametrizado para harness_tier in {"native", "real_body", "driver"}, usando classificação de confirmação compatível (confirmed_native para native, confirmed_driver para os outros dois). Verificar que cada caso correto aumenta confirmed_on_real_body e end_to_end.tp exatamente uma vez.

Adicionar também uma hipótese falsa confirmada por um tier real e verificar que ela entra em end_to_end.fp.

- [ ] **Step 5: Escrever o teste de compatibilidade com relatório sem tier**

Criar um ScanCaseResult com classification="confirmed_on_abstraction" e sem harness_tier explícito. Verificar que o resultado aparece em unknown_evidence, não em confirmed_on_real_body, não em confirmed_on_abstraction e não aumenta end_to_end.tp.

- [ ] **Step 6: Implementar os predicados de evidência e a agregação**

Em src/research_pipeline/v2_evaluator.py, adicionar predicados internos ou públicos com contratos explícitos:

    def is_real_body_confirmation(result) -> bool:
        ...

    def is_scalar_abstraction_confirmation(result) -> bool:
        ...

is_real_body_confirmation() deve exigir uma classificação de confirmação operacional e harness_tier em {"native", "real_body", "driver"}. is_scalar_abstraction_confirmation() deve exigir classification == "confirmed_on_abstraction" e harness_tier == "scalar".

Refatorar a contagem atual para:

- contar confirmações reais e escalares separadamente entre true_positive_results;
- contar confirmações reais entre false_hypothesis_results para end_to_end.fp;
- contar resultados de confirmação sem tier reconhecido em unknown_evidence;
- calcular abstraction_only_rate como confirmações escalares corretas divididas por len(true_positive_results), ou None quando o denominador for zero;
- adicionar cada confirmação escalar correta a pipeline_stage_losses.by_stage["abstraction_only"];
- manter end_to_end.fn = expected - end_to_end.tp e recalcular precisão, recall e F1 com o novo TP/FP.

Preservar as chaves históricas que ainda forem úteis, mas documentar no próprio retorno que confirmed_on_abstraction agora significa confirmação escalar explicitamente identificada.

- [ ] **Step 7: Rodar os testes focados**

Run: python -m pytest tests/test_v2_evaluator.py -q

Expected: PASS.

---

### Task 2: Refletir a distinção no resumo da CLI e na documentação

**Files:**
- Modify: src/main.py:1421-1466
- Modify: tests/test_main_v2.py:221-238
- Modify: docs/v2/harness_synthesis.md:190-245
- Modify: docs/projeto/complemento_apresentacao_2026-09-23.md:100-125,230-265

**Interfaces:**
- Consumes: is_real_body_confirmation(), is_scalar_abstraction_confirmation() e os campos atuais de ScanCaseResult.
- Produces: resumo CLI com confirmação real separada da confirmação na abstração; documentação que não chama uma confirmação escalar de prova do código original.

- [ ] **Step 1: Escrever o teste do resumo por categoria**

Atualizar test_scan_summary_counts_harness_tiers para incluir uma confirmação escalar com harness_tier="scalar" e uma confirmação real. Verificar que o dicionário por categoria contém contadores separados, por exemplo:

    assert summary["by_category"]["division_by_zero"]["confirmed"] == 1
    assert summary["by_category"]["division_by_zero"]["abstraction_only"] == 1

A expectativa deve refletir que confirmed conta somente evidência real.

- [ ] **Step 2: Rodar o teste e confirmar a falha da expectativa nova**

Run: python -m pytest tests/test_main_v2.py::test_scan_summary_counts_harness_tiers -q

Expected: FAIL porque o resumo atual coloca confirmed_on_abstraction em confirmed e não expõe abstraction_only.

- [ ] **Step 3: Implementar o resumo sem duplicar a regra metodológica**

Em src/main.py, ajustar _scan_summary() para usar os predicados da avaliação ou a mesma regra centralizada, evitando que a CLI tenha uma definição diferente da avaliação JSON. Para cada categoria, manter total, confirmed, native, driver e unverified, acrescentando abstraction_only. A impressão textual deve nomear explicitamente a contagem escalar como “abstração”, sem chamá-la de confirmação do código real.

- [ ] **Step 4: Atualizar a documentação técnica**

Em docs/v2/harness_synthesis.md, atualizar as tabelas e o texto para distinguir:

- confirmação no código original por native, real_body ou driver;
- confirmação somente no harness escalar;
- resultado seguro ou inconclusivo em cada nível.

Preservar a explicação de que um harness sintetizado pode ser uma abstração e incluir a regra de que a métrica end-to-end não usa o tier escalar.

- [ ] **Step 5: Atualizar o complemento da apresentação**

Em docs/projeto/complemento_apresentacao_2026-09-23.md, revisar os trechos de resultado e de dúvidas metodológicas para dizer que:

- o harness escalar não executa necessariamente o código real;
- suas confirmações devem ser reportadas como confirmações da abstração;
- apenas os tiers que preservam/executam o corpo original sustentam a confirmação final.

Não inventar novos números nesta etapa; se os números dos slides precisarem ser recalculados depois da implementação, marcar a necessidade de uma nova rodada de avaliação.

- [ ] **Step 6: Rodar os testes focados do resumo**

Run: python -m pytest tests/test_main_v2.py::test_scan_summary_counts_harness_tiers -q

Expected: PASS.

---

### Task 3: Verificação integrada e consistência dos relatórios

**Files:**
- Modify: nenhum arquivo de produção inicialmente
- Test: tests/test_v2_evaluator.py, tests/test_main_v2.py, suíte completa

**Interfaces:**
- Consumes: implementação das Tasks 1 e 2.
- Produces: evidência de que os relatórios JSON, o resumo da CLI e os testes usam a mesma semântica de evidência.

- [ ] **Step 1: Rodar todos os testes relacionados ao V2**

Run: python -m pytest tests/test_v2_evaluator.py tests/test_main_v2.py tests/test_scan_pipeline.py tests/test_scan_driver.py tests/test_scan_real_body.py -q

Expected: PASS.

- [ ] **Step 2: Rodar a suíte completa**

Run: python -m pytest -q

Expected: PASS sem falhas ou erros.

- [ ] **Step 3: Inspecionar um relatório serializado representativo**

Usar um relatório existente ou uma execução de teste para confirmar que cada resultado ainda preserva classification, verification_target, abstraction_level e harness_tier, e que o bloco evaluation contém as métricas separadas.

- [ ] **Step 4: Verificar a consistência textual**

Pesquisar por usos da expressão “confirmação formal” em README.md, docs/v2/harness_synthesis.md e docs/projeto/complemento_apresentacao_2026-09-23.md. Corrigir apenas os trechos que tratam confirmação escalar como prova do código real; não alterar histórico experimental sem recalcular os números.

- [ ] **Step 5: Registrar o resultado para a próxima etapa**

Documentar, no handoff da próxima sessão ou no comentário da tarefa, os testes executados e se os números históricos precisam de uma nova rodada de benchmark. Não fazer commit sem pedido explícito.
