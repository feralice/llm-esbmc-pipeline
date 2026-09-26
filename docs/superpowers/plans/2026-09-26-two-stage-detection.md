# Detecção em duas etapas Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:executing-plans (recommended) or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Adicionar uma estratégia opt-in que localiza hipóteses de bug e classifica suas categorias em chamadas LLM separadas.

**Architecture:** Criar contratos estruturados específicos para localização e classificação, um wrapper que combina as duas respostas em Findings existentes e suporte de estágio nos backends atuais. A estratégia single permanecerá padrão; two_stage será selecionável pela CLI e ficará registrada na configuração/telemetria.

**Tech Stack:** Python 3.9+, JSON Schema, urllib/subprocess existentes, pytest.

**Spec:** docs/superpowers/specs/2026-09-26-two-stage-detection-design.md

## Global Constraints

- single permanece o padrão e não muda seu contrato.
- two_stage não recebe ground truth, caminho do arquivo ou rótulos do dataset.
- O limitador MAX_PROMPT_SOURCE_CHARS é usado nas duas etapas.
- Smells não entram na estratégia two_stage.
- Chamadas reais ficam fora dos testes padrão.
- Não commitar sem pedido explícito.

## Review Focus

- Localização sem candidato: não chamar a segunda etapa e retornar lista vazia.
- Classificação de categoria inválida: rejeitar sem fabricar Finding verificável.
- Candidato localizado com expressão não executável: deixar o grounding existente rejeitar.
- Falha na segunda chamada: propagar erro para checkpoint, sem resultado parcial enganoso.
- Contexto truncado: ambas as etapas devem receber o marcador de truncamento.

---

### Task 1: Schemas, modelos e prompts das duas etapas

**Files:**
- Create: src/research_pipeline/llm/staged.py
- Modify: src/research_pipeline/llm/prompts.py
- Modify: src/research_pipeline/llm/schema.py
- Test: tests/test_prompt_surface_consistency.py
- Create: tests/test_llm_staged.py

- [ ] Definir dataclasses LocationCandidate e ClassificationResult com tipos explícitos.
- [ ] Definir LOCALIZATION_JSON_SCHEMA e CLASSIFICATION_JSON_SCHEMA sem adicionar categorias falsas ao enum global.
- [ ] Adicionar load_system_prompt(stage=...) e build_user_prompt(stage=..., candidates=...) reutilizando o mesmo limitador.
- [ ] Escrever testes para schema, presença de marcadores de dados não confiáveis, ausência de ground truth e truncamento nas duas etapas.
- [ ] Rodar os testes novos e observar a falha antes da implementação.
- [ ] Implementar parsing estrito, rejeitando candidate_id inexistente, categoria fora das oito formais e payloads sem a chave esperada.
- [ ] Rodar os testes da Task 1 e verificar PASS.

### Task 2: Suporte de estágio nos backends e wrapper

**Files:**
- Modify: src/research_pipeline/llm/protocols.py
- Modify: src/research_pipeline/llm/backends/openai.py
- Modify: src/research_pipeline/llm/backends/chat_completions.py
- Modify: src/research_pipeline/llm/backends/codex.py
- Modify: src/research_pipeline/llm/backends/anthropic.py
- Modify: src/research_pipeline/llm/backends/claude_cli.py
- Modify: src/research_pipeline/llm/backends/factory.py
- Modify: src/research_pipeline/llm/staged.py
- Create: tests/test_two_stage_analyzer.py

- [ ] Escrever testes com backend falso verificando duas chamadas na ordem localização -> classificação.
- [ ] Escrever teste de zero candidatos verificando que a classificação não é chamada.
- [ ] Escrever teste de erro na classificação verificando que a exceção é preservada.
- [ ] Implementar analyze_stage em cada backend, mantendo analyze(unit) compatível.
- [ ] Implementar TwoStageAnalyzer para combinar candidatos e classificações, normalizar Findings e agregar telemetria sem copiar uma confiança global para cada finding.
- [ ] Verificar que o wrapper não chama a etapa de classificação quando a localização é vazia.
- [ ] Rodar os testes novos e os testes atuais dos backends.

### Task 3: Configuração CLI, pipeline e relatório

**Files:**
- Modify: src/main.py
- Modify: src/research_pipeline/llm/backends/factory.py
- Modify: src/research_pipeline/pipeline.py
- Modify: tests/test_main_v2.py
- Modify: tests/test_llm_backends.py
- Modify: tests/test_research_pipeline.py

- [ ] Escrever teste de parser para --detection-strategy single/two_stage e default single.
- [ ] Escrever teste de factory verificando que two_stage retorna wrapper e single retorna backend normal.
- [ ] Implementar a passagem da estratégia para V2 e para os modos de detecção existentes sem alterar o default.
- [ ] Registrar detection_strategy, localization_calls e classification_calls na configuração/telemetria do relatório.
- [ ] Confirmar que checkpoints continuam retomáveis e que uma falha por unidade não descarta as demais.
- [ ] Rodar os testes focados e verificar PASS.

### Task 4: Avaliação determinística e documentação experimental

**Files:**
- Modify: README.md
- Modify: docs/projeto/complemento_apresentacao_2026-09-23.md
- Create: docs/projeto/two_stage_detection_experiment.md
- Test: tests/test_two_stage_analyzer.py

- [ ] Documentar o comando opt-in e o aumento esperado de chamadas/custo.
- [ ] Documentar que a comparação exige múltiplas rodadas, positivos e negativos por categoria e armazenamento dos resultados brutos.
- [ ] Registrar que os resultados two_stage não devem ser apresentados como melhoria sem rodada experimental controlada.
- [ ] Rodar a suíte completa com python3 -m pytest -q.
- [ ] Não executar chamadas LLM reais como parte dos testes padrão.

