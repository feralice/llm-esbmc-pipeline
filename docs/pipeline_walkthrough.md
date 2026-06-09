# Pipeline Walkthrough — Cada Arquivo, Cada Passo

> Guia de leitura para quem quer entender o pipeline de dentro para fora.
> Para referência de métricas e fórmulas, veja [`benchmark_v1_reference.md`](benchmark_v1_reference.md).

---

## Fluxo Completo em 1 Linha

```
arquivo.py → preprocess → prompt → LLM → validação AST → ESBMC → matching GT → métricas
```

**Exemplo concreto para `dz_01.py`:**

```
dz_01.py
  → preprocess.py      extrai função "compute_ratio" → CodeUnit
  → prompts.py         monta prompt (raw mode, sem path)
  → anthropic.py       envia para Claude → JSON com finding
  → findings.py        valida "total // count" no AST → suspected_bug
  → esbmc_runner.py    roda ESBMC --function compute_ratio → FAILED (div/0 encontrado)
  → evaluator.py       compara com GT [category=division_by_zero, function=compute_ratio] → TP
  → EvalCounts         hybrid_bug_tp += 1, llm_confirmed_by_esbmc += 1
```

---

## Passo 0 — `src/main.py` (Ponto de Entrada CLI)

Quando você roda:
```bash
python src/main.py --mode benchmark --model gpt-4o --prompt-mode raw ...
```

O `main.py`:
1. Lê os argumentos (`--model`, `--bound`, `--prompt-mode`, `--report`, etc.)
2. Detecta o backend pelo nome do modelo:
   - nome com `claude` → Anthropic
   - nome com `gpt`, `o1`, `o3`, `o4` → OpenAI
   - qualquer outro → Ollama (inferência local)
3. Chama `evaluate_model()` do `evaluator.py` com todos os 70 arquivos
4. Imprime tabela de métricas no terminal com CIs de 95%
5. Salva JSON de relatório se `--report` foi passado

---

## Passo 1 — `research_pipeline/preprocess.py`

**O que faz:** parseia o arquivo Python com `ast` e extrai cada função como um `CodeUnit`.

**Por que existe:** o ESBMC roda com `--function <nome>` para analisar funções isoladas. O preprocess garante que sabemos o nome, parâmetros e código de cada função.

**O que produz por função (`CodeUnit`):**

| Campo | Conteúdo | Exemplo |
|---|---|---|
| `source` | código-fonte da função | `"def compute_ratio(total, count):\n    return total // count"` |
| `qualname` | nome da função | `"compute_ratio"` |
| `parameters` | lista de parâmetros | `["total", "count"]` |
| `type_hints` | tipos declarados | `{"total": "int", "count": "int", "return": "int"}` |
| `operations` | operações detectadas | `[Operation(kind="floor_div", expression="total // count", line=2)]` |
| `guards` | condições if/assert presentes | `["count != 0"]` se existir |
| `metrics` | contagens | `{"line_count": 2, "parameter_count": 2}` |

---

## Passo 2 — `research_pipeline/llm/prompts.py`

**O que faz:** `build_user_prompt(unit, prompt_mode)` monta o texto que vai para a LLM.

### `raw` mode (padrão, obrigatório para avaliações)

```
Analise a função 'compute_ratio' para o pipeline LLM + ESBMC.

CÓDIGO DA FUNÇÃO:
```python
def compute_ratio(total: int, count: int) -> int:
    return total // count
```

METADADOS DA FUNÇÃO:
{
  "start_line": 1,
  "end_line": 2,
  "parameters": ["total", "count"],
  "type_hints": {"total": "int", "count": "int", "return": "int"},
  "metrics": {"line_count": 2, "parameter_count": 2}
}
```

**Por que o `path` foi removido:** o arquivo está em `dataset/labeled/ok/bugs/division_by_zero/dz_01.py`. Com o path no prompt, a LLM veria `division_by_zero` no diretório e "adivinharia" a categoria — isso mede leitura de label, não inteligência. O path foi removido em 2026-06-07.

### `ast_hints` mode (só ablação)

Inclui operações pré-extraídas pelo AST (divisões encontradas, subscripts, etc.). Não usar em avaliações principais — entrega o tipo de operação como dica, inflando artificialmente as métricas.

---

## Passo 2b — `research_pipeline/prompts/system_prompt.txt`

**O que faz:** instrui a LLM sobre papel, taxonomia e raciocínio antes de gerar o JSON.

**Estratégia:** role + Chain-of-Thought próprio do projeto. Substituiu um prompt de 8 passos procedurais que sobrecarregava modelos 7B. Referência conceitual: Tamberg & Bahsi (IEEE Access 2025).

**Conteúdo:**
1. **Role:** especialista em segurança Python em pipeline híbrido LLM+ESBMC
2. **Taxonomia:** bugs formais (`verifiable=true`) vs. code smells (`verifiable=false`)
3. **4 perguntas CoT** a aplicar antes de gerar o JSON:
   - O operando é controlado por parâmetro livre?
   - Existe guarda que bloqueia EXATAMENTE o valor problemático em TODOS os caminhos?
   - A exceção é capturada por try/except?
   - Existe valor concreto que passa pela guarda E causa a falha?
4. **Spec de output:** JSON sem markdown, `true`/`false` minúsculos

---

## Passo 3 — `research_pipeline/llm/backends/`

Três backends com a mesma interface: `analyze(unit) -> list[Finding]`.

### `openai.py` — OpenAIResponsesAnalyzer

Usa a Responses API da OpenAI. Funciona com `gpt-4o`, `o3`, `o4-mini`, etc.

### `anthropic.py` — AnthropicAnalyzer

Usa a Messages API da Anthropic. Funciona com `claude-sonnet-4-6`, etc.

### `chat_completions.py` — ChatCompletionsAnalyzer

Formato OpenAI-compat. Usado para Ollama local: `deepseek-r1:7b`, `qwen2.5-coder:7b`, etc.

**Limitação:** Ollama usa `json_object` (sem schema enforcement). GPT-4o usa `strict json_schema`. Modelos locais podem gerar campos fora do schema — o parser normaliza com defaults.

**Timeout:** modelos de raciocínio como DeepSeek-R1 podem levar vários minutos por função. Use `--llm-timeout 600`. `TimeoutError` é capturado e re-tentado até 3 vezes antes de pular o arquivo.

### `factory.py` — build_analyzer()

```python
build_analyzer(backend="anthropic", llm_model="claude-sonnet-4-6", prompt_mode="raw")
```

Detecta o backend automaticamente pelo nome do modelo e retorna o objeto correto.

**Todos os backends:**
- `temperature=0` — respostas determinísticas, reproduzíveis
- Retry com backoff exponencial em 429/500/502/503/504

**Schema de output (5 campos obrigatórios):**
```json
{
  "findings": [
    {
      "finding_type": "suspected_bug",
      "category": "division_by_zero",
      "explanation": "count pode ser zero se passado como parâmetro livre",
      "verifiable": true,
      "metadata": {"expression": "total // count"}
    }
  ]
}
```

Campos opcionais (`id`, `title`, `evidence`, `confidence`) são aceitos com defaults se ausentes. O schema foi simplificado de 12 para 5 campos obrigatórios para reduzir carga cognitiva em modelos 7B.

**`strip_markdown_json` (em `findings.py`):** trata três problemas comuns antes de parsear:
1. Remove blocos `<think>...</think>` de reasoning models (DeepSeek-R1)
2. Substitui literais Python (`True`/`False`/`None`) por JSON válido (`true`/`false`/`null`)
3. Remove fences markdown e usa `raw_decode()` para descartar texto após o JSON

---

## Passo 4 — `research_pipeline/llm/findings.py`

**O que faz:** `normalize_findings(unit, findings)` valida cada finding da LLM contra o código real.

### Fase 1 — Categoria suportada?

Se `category` não está em `SUPPORTED_CATEGORIES` → `out_of_scope_finding` (descartado).

### Fase 2 — A expressão existe no código?

Para `division_by_zero` com `expression = "total // count"`:
- Busca operações de divisão no AST da função com `ast.walk()`
- **Encontrou** `total // count` → `suspected_bug` (vai para o ESBMC)
- **Não encontrou** → `llm_false_positive` (alucinação — LLM inventou expressão que não existe)

Para `assertion_violation` com `expression = "result > 0"`:
- Busca nós `ast.Assert` na árvore
- Compara via `ast.dump()` para normalizar variações de formatação

### Fase 3 — Guarda protege a operação?

Ex: se o código tem `if count != 0: return total // count`, o denominador `count` aparece na guarda. Isso fica registrado como `has_guard = "true"` mas **não cancela** o finding — o ESBMC ainda verifica.

### O que é uma alucinação

A LLM disse que `"total // count"` existe no código, mas o AST não encontrou essa expressão em nenhum nó executável (não em strings, não em comentários, não em código não-executável). Isso é alucinação → `hallucination_count += 1`.

---

## Passo 5 — `research_pipeline/verification/esbmc_runner.py`

**O que faz:** roda o ESBMC em modo verificador formal para confirmar ou refutar a hipótese da LLM.

### Flow B (híbrido): `run_esbmc_on_function()`

```bash
esbmc dz_01.py \
  --function compute_ratio \
  --no-bounds-check \
  --unwind 5 \
  --timeout 30
```

**Por que `--function` é central:** sem ele, ESBMC analisa o módulo como `main()` e não testa funções isoladas com parâmetros livres. Com `--function compute_ratio`, o ESBMC trata `total` e `count` como valores **simbólicos** (qualquer inteiro possível) e prova: _"existe algum valor que causa a violação?"_

**Flags por categoria:**

| Categoria | Flags | Por quê |
|---|---|---|
| `division_by_zero` | `--no-bounds-check` | Desliga verificação OOB para não gerar ruído |
| `out_of_bounds` | `--no-div-by-zero-check --assign-param-nondet` | `--assign-param-nondet` inicializa parâmetros de lista como simbólicos |
| `assertion_violation` | _(sem flags extras)_ | ESBMC já verifica asserts por padrão |

**O que o ESBMC retorna:**
- `"VERIFICATION FAILED"` → encontrou violação → `llm_confirmed_by_esbmc`
- `"VERIFICATION SUCCESSFUL"` → provou que não há violação dentro do bound → `not_confirmed_within_bound`
- Timeout / erro → `esbmc_inconclusive`

### Flow A (baseline): `run_esbmc_function_baseline()`

Mesmo mecanismo, mas sem hipótese da LLM. Roda `--function` em todas as funções do dataset sem flags de categoria. Mede o que o ESBMC consegue encontrar sozinho.

---

## Passo 6 — `research_pipeline/evaluator.py`

**O que faz:** orquestra tudo, compara com o ground truth e calcula métricas.

### Matching com Ground Truth

```python
# GT para dz_01.py:
{"expected_category": "division_by_zero", "function": "compute_ratio"}

# Finding da LLM confirmado pelo ESBMC:
{"category": "division_by_zero", "function": "compute_ratio"}

# Matching: category == expected_category E function == function → TP
```

**Regra estrita:** se a LLM acerta a categoria mas aponta para função errada = FN + FP. Sem "acertos por sorte".

### `EvalCounts` — Contadores por arquivo

Cada arquivo produz um `EvalCounts` individual. No final, todos são somados:

```
Flow C (LLM puro):  bug_tp, bug_fp, bug_fn
Flow B (híbrido):   hybrid_bug_tp, hybrid_bug_fp, hybrid_bug_fn
Flow A (ESBMC):     esbmc_direct_tp, esbmc_direct_fp, esbmc_direct_fn
Nível de função:    bug_func_tp/fp/fn/tn  (para MCC)
Eventos:            hallucination_count, llm_confirmed_by_esbmc, etc.
```

### Retry por arquivo

Cada arquivo tem até 3 tentativas (`_MAX_RETRIES = 3`). Se todas falharem por timeout/rede, o arquivo é pulado com aviso `WARN` no terminal. O benchmark continua — sem crash por arquivo problemático.

### Bootstrap 95% CIs

Com os 70 `EvalCounts` individuais (um por arquivo):
1. Reamostrar 70 casos com reposição (alguns arquivos aparecem mais de uma vez, outros não aparecem)
2. Somar os `EvalCounts` reamostrados → calcular a métrica
3. Repetir 2000 vezes → distribuição empírica da métrica
4. Percentis 2.5% e 97.5% = intervalo de confiança de 95%

Isso quantifica: "com n=70, uma diferença de 5pp entre dois modelos — é real ou ruído?"

---

## Passo 7 — `research_pipeline/report.py`

**O que faz:** `consolidate_result()` decide a classificação final de cada arquivo.

| O que aconteceu | Classificação |
|---|---|
| LLM propôs + ESBMC confirmou + categoria bateu | `llm_confirmed_by_esbmc` |
| LLM propôs + ESBMC rodou e não encontrou violação | `not_confirmed_within_bound` |
| LLM propôs + ESBMC deu timeout/erro | `esbmc_inconclusive` |
| LLM propôs expressão que não existe no código | `llm_false_positive` |
| Flow A encontrou sem LLM | `esbmc_native_bug` |
| Flow A achou, LLM não viu | `llm_missed_esbmc_bug` |
| Smell detectado | `heuristic_smell_only` |
| Finding com categoria fora do escopo | `out_of_scope_finding` |

---

## Dataclasses (`research_pipeline/models.py`)

As estruturas que fluem pelo pipeline:

| Dataclass | Representa | Criada em |
|---|---|---|
| `CodeUnit` | Uma função Python extraída | `preprocess.py` |
| `Finding` | Hipótese de bug/smell da LLM | `findings.py` |
| `ESBMCResult` | Resultado do ESBMC (`property`, `status`, `output_snippet`) | `esbmc_runner.py` |
| `FinalResult` | Classificação final do arquivo | `report.py` |

---

## `scripts/compare_benchmarks.py`

Lê múltiplos JSONs de benchmark (um por modelo) e gera tabela comparativa de P/R/F1/MCC. Útil para colocar no paper.

```bash
python scripts/compare_benchmarks.py \
  reports/json/v1_benchmark/benchmark_gpt-4o.json \
  reports/json/v1_benchmark/benchmark_claude-sonnet-4-6.json \
  reports/json/v1_benchmark/benchmark_deepseek-r1-7b.json
```

---

## Mapa de dependências (simplificado)

```
src/main.py
  └── evaluator.py
        ├── pipeline.py
        │     ├── preprocess.py           → CodeUnit
        │     ├── llm/backends/factory.py → LLMAnalyzer
        │     │     └── prompts.py        → user_prompt
        │     │     └── findings.py       → normalize_findings
        │     └── esbmc_runner.py         → ESBMCResult
        ├── report.py                     → FinalResult + classificação
        └── models.py                     → dataclasses compartilhados
```
