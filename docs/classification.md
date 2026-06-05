# Classificações do Pipeline

## Diagrama de decisão

```mermaid
flowchart TD
    A[finding_type] --> B{out_of_scope_finding?}
    B -- sim --> OOS[out_of_scope_finding]
    B -- não --> C{llm_false_positive?}
    C -- sim --> FP[llm_false_positive]
    C -- não --> D{smell_heuristic?}
    D -- sim --> SMELL[heuristic_smell_only]
    D -- não --> E{esbmc_result.status}
    E -- skipped --> F{harness disponível?}
    F -- não --> SKIP[skipped_not_verifiable]
    F -- sim --> G{status harness}
    G -- reproduced --> REPR[runtime_reproduced_by_harness]
    G -- not_reproduced / wrong_exc --> NR[runtime_not_reproduced]
    G -- unsafe / timeout / error --> RI[runtime_inconclusive]
    E -- violation_found --> CONF[llm_confirmed_by_esbmc]
    E -- no_violation_found --> NC[not_confirmed_within_bound]
    E -- tool_error / inconclusive --> INC[esbmc_inconclusive]
    E -- skipped --> K{Flow A\nviolation_found?}
    K -- sim --> NATIVE[esbmc_native_bug]
    K -- não --> SKIP2[skipped_not_verifiable]
```

## Tabela de classificações

### Trilha formal (ESBMC)

| Classificação | Significado | Peso na dissertação |
|---|---|---|
| `llm_confirmed_by_esbmc` | LLM identificou e ESBMC confirmou formalmente via BMC | **Principal** — prova formal |
| `not_confirmed_within_bound` | ESBMC verificou mas não encontrou violação no bound | Resultado negativo formal |
| `esbmc_inconclusive` | ESBMC retornou erro, timeout ou resultado ambíguo | Limitação da ferramenta |
| `esbmc_native_bug` | Flow A detectou violação sem depender da LLM | ESBMC > LLM |
| `llm_missed_esbmc_bug` | Flow A encontrou bug que a LLM não apontou | Falso negativo da LLM |

### Trilha runtime (harness)

| Classificação | Significado | Peso na dissertação |
|---|---|---|
| `runtime_reproduced_by_harness` | LLM identificou e execução runtime reproduziu a exceção | **Auxiliar** — não é prova formal |
| `runtime_not_reproduced` | Harness executou sem levantar a exceção esperada | Não confirmado em runtime |
| `runtime_inconclusive` | Harness rejeitado por segurança, timeout ou erro | Inconclusivo |

> **Importante:** `runtime_reproduced_by_harness` NÃO equivale a `llm_confirmed_by_esbmc`. O ESBMC usa verificação formal por BMC (explora todos os inputs simbólicos dentro do bound). O harness executa com uma entrada concreta específica. São formas de validação com pesos científicos diferentes.

### Rejeição / heurística

| Classificação | Significado |
|---|---|
| `llm_false_positive` | LLM citou operação que não existe no código executável (alucinação) |
| `heuristic_smell_only` | Smell de qualidade de código — sem verificação formal |
| `skipped_not_verifiable` | Achado não pôde ser verificado no Flow B atual |
| `out_of_scope_finding` | Categoria fora das 5 aceitas pelo MVP |

### Flow A — ESBMC-only

O Flow A roda ESBMC com `--function <funcao>` para cada função detectada pelo AST, sem usar achados ou categorias da LLM.

| Status | Significado |
|---|---|
| `violation_found` | ESBMC encontrou violação com ponto de entrada disponível |
| `no_violation_found` | ESBMC verificou e não encontrou violação no bound |
| `skipped` | Nenhuma função candidata ou ESBMC indisponível |
| `tool_error` | Erro interno do ESBMC (tipo não suportado, annotation ausente) |
| `unsupported_case` | Módulo Python não suportado pelo ESBMC (numpy, pandas, etc.) |
| `timeout` | Execução excedeu o tempo limite configurado |

## Separação formal vs. auxiliar na dissertação

```
Resultados formais (ESBMC):
  llm_confirmed_by_esbmc       → TP da trilha formal
  not_confirmed_within_bound   → FP ou limitação do bound
  esbmc_native_bug             → ESBMC superior à LLM

Resultados auxiliares (harness):
  runtime_reproduced_by_harness → evidência de runtime, não prova formal
  runtime_not_reproduced        → bug não reproduzível com os inputs testados

Falsos positivos da LLM:
  llm_false_positive            → alucinação detectada pelo AST
```

Nas métricas do benchmark, calcule F1 **separadamente** para cada trilha. Não some `llm_confirmed_by_esbmc` com `runtime_reproduced_by_harness` em um único TP.
