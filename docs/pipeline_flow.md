# Fluxo Detalhado do Pipeline

## Modo `full` (Flow A + Flow B)

```mermaid
sequenceDiagram
    participant CLI as main.py
    participant FA as Flow A (ESBMC-only)
    participant PP as Preprocess
    participant LLM as LLM Analyzer
    participant ESBMC as ESBMC
    participant HV as Harness Validator
    participant RPT as Full Report

    CLI->>PP: preprocess_file(arquivo)
    PP-->>CLI: list[CodeUnit]
    CLI->>FA: run_esbmc_function_baseline(arquivo, funcoes)
    FA-->>CLI: ESBMCDirectResult agregado

    loop Para cada CodeUnit
        CLI->>LLM: analyzer.analyze(unit)
        LLM-->>CLI: list[Finding]

        loop Para cada Finding
            alt verifiable=true e categoria no escopo
                CLI->>ESBMC: run_esbmc_on_function(arquivo, unit.name)
                ESBMC-->>CLI: ESBMCResult
                alt ESBMC skipped + harness disponível
                    CLI->>HV: validate_harness(source, harness)
                    HV-->>CLI: HarnessValidationResult
                end
            end
            CLI->>CLI: consolidate_result(...)
        end
    end

    CLI->>RPT: build_full_report(results)
    RPT-->>CLI: JSON hierárquico
```

## Modo `esbmc-direct` (Flow A puro)

```mermaid
flowchart LR
    A[arquivo.py] --> B[preprocess_file]
    B --> C[funções candidatas]
    C --> D[esbmc --function em cada função]
    D --> E{Saída agregada}
    E -- alguma VERIFICATION FAILED --> VF[violation_found]
    E -- todas sem falha --> NV[no_violation_found]
    E -- erro/timeout --> TE[tool_error / inconclusive]
    E -- nenhuma função --> SK[skipped]
```

**Observação:** o Flow A atual evita o problema de 0 VCCs em arquivos com apenas definições de função porque chama o ESBMC com `--function` para cada função candidata.

## Modo `llm-first` (Flow B puro)

Igual ao Flow B do modo `full`, mas sem o Flow A precedente. O campo `esbmc_direct` fica `null` no relatório.

## Modo `benchmark`

```mermaid
flowchart TD
    A[ground_truths/bugs/] --> B[load_ground_truth_cases]
    B --> C[Para cada arquivo + expected_findings]
    C --> D[preprocess_file + analyzer.analyze]
    D --> E[run_esbmc_function_baseline + run_esbmc_on_function]
    E --> F[match findings vs expected]
    F --> G[EvalCounts: TP, FP, FN]
    G --> H[prf: Precision, Recall, F1]
```

## Fluxo de normalização do finding (detalhe)

```mermaid
flowchart TD
    A[Finding da LLM] --> B{Categoria\nno escopo MVP?}
    B -- não --> OOS[out_of_scope_finding]
    B -- sim --> C{verifiable=true?}
    C -- não --> SMELL[smell_heuristic\npassar ao consolidate]
    C -- sim --> D{assertion_violation?}
    D -- sim --> AV[verifica se assert/raise\nexiste no source]
    D -- não --> E{AST encontra\noperação por kind?}
    E -- sim --> SB1[suspected_bug\nenriquece linha e guarda]
    E -- não --> F{Expressão existe\ncomo nó executável?}
    F -- sim --> SB2[suspected_bug\nast_unrecognized=true]
    F -- não --> FP[llm_false_positive]
    AV -- existe --> SB3[suspected_bug]
    AV -- não existe --> FP
```
