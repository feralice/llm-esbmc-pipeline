# Referência Técnica do Pipeline — llm-esbmc (V1)

> Fonte de verdade para arquitetura, fluxos de execução, métricas e decisões metodológicas.
> Atualizada em 2026-06-07 para refletir: `prompt_mode=raw` como padrão, remoção do path do prompt, bootstrap 95% CIs, correção de exemplos quasi-isomórficos no system prompt.

---

## 1. Objetivo do Pipeline

Investigar se LLMs podem **orientar** o ESBMC (Bounded Model Checker) a verificar propriedades de segurança em funções Python que o verificador formal sozinho teria dificuldade de priorizar. O pipeline compara três estratégias:

| Estratégia | Nome | Descrição |
|---|---|---|
| **Flow A** | ESBMC puro | Verificação formal sem LLM — baseline clássico |
| **Flow B** | Híbrido LLM + ESBMC | LLM propõe hipóteses → ESBMC prova ou refuta |
| **Flow C** | LLM puro | LLM sem verificação formal — baseline de qualidade da IA |

---

## 2. Dataset

```
dataset/labeled/
  ok/
    bugs/
      assertion_violation/   av_01.py … av_15.py   (15 arquivos)
      division_by_zero/      dz_01.py … dz_15.py   (15 arquivos)
      out_of_bounds/         oob_01.py … oob_15.py  (15 arquivos)
    clean/                   clean_01.py … clean_10.py (10 arquivos)
    smells/
      complex_conditional/   cc_01.py … cc_05.py   (5 arquivos)
      long_method/           lm_01.py … lm_05.py   (5 arquivos)
      many_parameters/       mp_01.py … mp_05.py   (5 arquivos)
  ground_truths/             *.json (1 por categoria)
```

**Total: 70 arquivos, 70 funções.** Cada arquivo contém exatamente 1 função e 0 ou 1 bug.

**Características:**
- 100% sintético, criado para o benchmark
- Média de 2-5 LOC por função de bug, 5-18 LOC para smells
- Sem `len()` (limitação do frontend Python do ESBMC)

---

## 3. Ground Truth

Cada entry de GT define:

```json
{
  "id": "dz_01",
  "file": "dz_01.py",
  "function": "compute_ratio",
  "expected_category": "division_by_zero",
  "verifiable": true,
  "expression": "total // count",
  "line": 2,
  "expected_type": "ZeroDivisionError",
  "should_go_to_esbmc": true
}
```

**Matching é estrito:** um Finding só é TP se `category == expected_category` **E** `function == function` do GT. Acertar a categoria mas errar a função = FN + FP.

---

## 4. Arquitetura do Pipeline — Passo a Passo

```
arquivo.py
    │
    ▼
[Passo 1] preprocess.py ─── AST extrai CodeUnit
    │                         (source, name, parameters, type_hints,
    │                          operations, guards, metrics)
    ▼
[Passo 2] prompts.py ─────── Constrói user prompt
    │                         raw mode: apenas source + metadados básicos
    │                         ast_hints mode: + operações pré-extraídas (ablação)
    ▼
[Passo 3] LLM backend ────── Envia system_prompt + user_prompt
    │                         temperature=0, retry com backoff exponencial
    │                         Retorna JSON: {"findings": [...]}
    ▼
[Passo 4] findings.py ───────Normalização + Validação AST
    │                         • strip_markdown_json: remove fences + texto extra
    │                         • finding_from_dict: parse do JSON
    │                         • normalize_findings: valida cada finding
    │                           → expression_exists_in_executable_ast?
    │                             NÃO → finding_type = "llm_false_positive" (alucinação)
    │                             SIM → finding permanece como suspected_bug
    │                           → categoria suportada?
    │                             NÃO → out_of_scope_finding
    ▼
[Passo 5] esbmc_runner.py ── Para cada finding verifiable=True:
    │                         run_esbmc_on_function(
    │                           --function <nome>, flags por categoria,
    │                           --unwind <bound>, parâmetros simbólicos
    │                         )
    │                         Flow A (baseline): roda em todas as funções sem LLM
    ▼
[Passo 6] evaluator.py ──── Matching com GT + acúmulo de EvalCounts
    │                         → compute_bootstrap_cis (B=2000)
    ▼
    JSON de relatório + saída no terminal
```

---

## 5. Prompt Mode

### `raw` (padrão — usado em todas as avaliações científicas)

O modelo recebe apenas o código-fonte da função e metadados mínimos:

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

**Importante:** O campo `path` foi removido intencionalmente — ele exporia o nome da categoria via estrutura de diretórios (ex: `bugs/division_by_zero/dz_01.py` vaza o rótulo).

### `ast_hints` (ablação apenas)

Modo legado que injeta operações pré-extraídas pelo AST antes de enviar ao LLM:
- Divisões detectadas com linha e expressão
- Subscripts detectados
- Guardas/asserts existentes
- Métricas derivadas: `operation_count`, `branch_count`, `loop_count`

**Não usar em avaliações principais.** Comparar `raw` vs `ast_hints` é uma contribuição científica: mede o quanto o pre-processamento AST inflava artificialmente as métricas.

---

## 6. Flags ESBMC por Categoria (Flow B)

```python
_FLOW_B_CATEGORY_FLAGS = {
    "division_by_zero":    ["--no-bounds-check"],
    "out_of_bounds":       ["--no-div-by-zero-check", "--assign-param-nondet"],
    "assertion_violation": [],
}
```

- `--function <nome>`: ESBMC usa a função como ponto de entrada; todos os parâmetros tornam-se simbólicos (não-determinísticos), o que equivale a "testar todos os valores possíveis".
- `--assign-param-nondet`: necessário para OOB — inicializa parâmetros de lista com valores simbólicos, permitindo que o ESBMC explore índices fora do bounds.
- `--no-bounds-check` / `--no-div-by-zero-check`: desativa verificações de outras categorias para reduzir ruído nas propriedades reportadas.

**Por que `--function` é central:** Sem ele, o ESBMC analisa o módulo inteiro como main() e não consegue testar funções isoladas com parâmetros livres. Com `--function`, cada parâmetro recebe um valor simbólico ∈ domínio do tipo, e o BMC prova se existe algum valor que causa a violação.

---

## 7. Validação AST (Passo 4)

### O que é uma alucinação?

Quando a LLM reporta `expression = "a // b"` mas essa expressão não existe no código executável da função, o finding é marcado como `llm_false_positive` (alucinação).

A validação usa `expression_exists_in_executable_ast()`:
1. Parseia o source da função com `ast.parse()`
2. Caminha por todos os nós executáveis (ignora strings, comentários)
3. Usa `ast.unparse()` para comparar expressões normalizadas
4. Retorna `True` se a expressão existe em algum nó executável

### Ghost Bug

Um finding marcado como `suspected_bug` (finding_type) mas com `verifiable=False` é chamado de **Ghost Bug**. Isso ocorre quando a LLM usa o tipo correto mas não marca o finding como verificável. São tratados como FP mas **não entram no denominador da hallucination_rate** porque o AST não os rejeitou explicitamente.

---

## 8. EvalCounts — O que cada campo significa

```python
@dataclass
class EvalCounts:
    # ── Flow C: LLM puro vs GT ──────────────────────────────────────────
    bug_tp:   int   # LLM acertou bug (cat + função corretos)
    bug_fp:   int   # LLM reportou bug que não existe no GT
                    # inclui: hallucinations + ghost_bugs + clean FPs
    bug_fn:   int   # GT tinha bug mas LLM não reportou

    smell_tp: int   # LLM acertou smell
    smell_fp: int   # LLM reportou smell que não existe no GT
    smell_fn: int   # GT tinha smell mas LLM não reportou

    # ── Flow B: Híbrido LLM + ESBMC vs GT ──────────────────────────────
    hybrid_bug_tp: int  # LLM propôs + ESBMC confirmou + no GT
    hybrid_bug_fp: int  # ESBMC confirmou mas não está no GT
                        # ou ESBMC inconclusivo em função limpa
    hybrid_bug_fn: int  # GT tinha bug mas ESBMC não confirmou
                        # (inclui: ESBMC timeout, LLM não propôs)

    # ── Flow A: ESBMC puro vs GT ────────────────────────────────────────
    esbmc_direct_tp: int   # ESBMC encontrou bug diretamente no GT
    esbmc_direct_fp: int   # ESBMC reportou bug que não está no GT
    esbmc_direct_fn: int   # GT tinha bug mas ESBMC não encontrou

    # ── Nível de função (binário: bug / clean) ──────────────────────────
    # Usado para MCC. Somente arquivos de bug (45) e clean (10) participam.
    # Smells (15) ficam fora deste denominador.
    bug_func_tp: int   # Função tem bug, LLM acertou
    bug_func_fp: int   # Função está limpa, LLM falhou (falso alarme)
    bug_func_fn: int   # Função tem bug, LLM não encontrou
    bug_func_tn: int   # Função está limpa, LLM corretamente silenciou

    hybrid_bug_func_tp/fp/fn/tn: int   # Mesmo, para Flow B
    esbmc_direct_func_tp/fp/fn/tn: int # Mesmo, para Flow A

    # ── Contadores de eventos específicos ──────────────────────────────
    hallucination_count: int  # Findings rejeitados pelo AST validator
    ghost_bug_count:     int  # suspected_bug + verifiable=False
    llm_confirmed_by_esbmc:    int  # ESBMC confirmou hipótese da LLM
    not_confirmed_within_bound: int  # ESBMC rodou, não encontrou violação
    esbmc_inconclusive:         int  # Timeout, erro, ou categoria errada
    skipped_not_verifiable:     int  # Finding não marcado como verifiable
    esbmc_native_bug:           int  # Bugs encontrados pelo Flow A
    llm_missed_esbmc_bug:       int  # Bugs do Flow A que a LLM não viu

    # ── Dicts por categoria ─────────────────────────────────────────────
    per_category:        dict  # Flow C: {cat: {tp, fp, fn}}
    per_category_hybrid: dict  # Flow B: {cat: {tp, fp, fn}}
```

---

## 9. Métricas de Avaliação — Definições Completas

### 9.1 Precision / Recall / F1

```
Precision  =  TP / (TP + FP)     [de tudo que o sistema apontou, quanto era real?]
Recall     =  TP / (TP + FN)     [de tudo que era real, quanto o sistema encontrou?]
F1         =  2·P·R / (P + R)    [média harmônica — equilíbrio entre P e R]
```

Calculadas em **nível de finding** para bugs e smells separadamente.

**Exemplo numérico (GPT-4o, Flow B):**
```
hybrid_bug_tp = 45, hybrid_bug_fp = 4, hybrid_bug_fn = 0

Precision = 45 / (45 + 4)  = 0.918
Recall    = 45 / (45 + 0)  = 1.000
F1        = 2 · 0.918 · 1.0 / (0.918 + 1.0) = 0.957
```

### 9.2 MCC (Matthews Correlation Coefficient)

Calculado em **nível de função** (binário: função tem bug / não tem bug).

```
MCC = (TP·TN − FP·FN) / √[(TP+FP)·(TP+FN)·(TN+FP)·(TN+FN)]
```

- Varia de −1 (predição inversa perfeita) a +1 (predição perfeita)
- 0 = não melhor que aleatório
- **Vantagem sobre F1:** robusto a datasets desbalanceados — considera todos os quadrantes da matriz de confusão

**Denominador do MCC de bugs:** apenas 45 casos de bug + 10 casos clean = 55 funções. Os 15 smells ficam fora porque não são bugs.

### 9.3 Hallucination Rate

```
hallucination_rate = hallucination_count / total_verifiable_claims

total_verifiable_claims = bug_tp + bug_fp - ghost_bug_count
```

**Por que subtrair ghost_bug_count?**
Ghost bugs são findings `suspected_bug + verifiable=False`. Eles inflam `bug_fp` mas o AST não os rejeitou explicitamente — são um erro de classificação da LLM, não uma alucinação de localização. Removê-los dá uma taxa de alucinação mais honesta.

**Exemplo:**
```
hallucination_count = 1   (LLM disse "total // count" existe mas não existe)
bug_tp = 45, bug_fp = 12, ghost_bug_count = 0

total_verifiable_claims = 45 + 12 - 0 = 57
hallucination_rate = 1 / 57 = 1.75%
```

### 9.4 Formal Confirmation Rate (FCR)

Responde: "das hipóteses de bug que a LLM propôs E o AST validou, quantas o ESBMC conseguiu provar?"

```
FCR = llm_confirmed_by_esbmc /
      (llm_confirmed_by_esbmc + not_confirmed_within_bound + esbmc_inconclusive)
```

- **Numerador:** ESBMC encontrou violação E categoria bateu com a hipótese da LLM
- **`not_confirmed_within_bound`:** ESBMC rodou completamente no bound e não encontrou violação (pode ser FP da LLM ou bug acima do bound)
- **`esbmc_inconclusive`:** Timeout, erro interno do ESBMC, ou violação de categoria diferente da prevista

**Interpretação:** FCR alto = a LLM está gerando hipóteses de boa qualidade que o ESBMC consegue confirmar. FCR baixo = LLM está gerando FPs que desperdiçam chamadas ao verificador.

### 9.5 Noise Reduction Rate (NRR)

Responde: "o Flow B reduziu quantos FPs em comparação ao Flow C (LLM puro)?"

```
NRR = (bug_fp_flowC − bug_fp_flowB) / bug_fp_flowC
```

- **Positivo:** Flow B eliminou FPs (ESBMC filtrou hipóteses erradas da LLM)
- **Zero:** Flow B não reduziu FPs (ESBMC confirmou tudo que a LLM disse)
- **Negativo:** Flow B gerou mais FPs que Flow C (ESBMC inconclusivo em funções limpas inflou o FP)
- **Se `bug_fp_flowC = 0`:** matematicamente indefinido → reportado como `0.0` por convenção

### 9.6 Bootstrap 95% Confidence Intervals

**Problema:** n=70 casos. Uma diferença de 5pp entre F1 de dois modelos pode ser ruído estatístico.

**Solução:** Percentile bootstrap, B=2000 reamostras, seed=42.

**Como funciona:**
1. Cada arquivo = um caso com seu `EvalCounts` individual
2. Amostrar com reposição 70 casos (mesma dimensão do dataset original)
3. Somar os EvalCounts reamostrados → calcular a métrica
4. Repetir 2000 vezes → distribuição empírica da métrica
5. Percentis 2.5% e 97.5% = intervalo de 95%

```python
# Exemplo: CI para F1 do Flow B
bootstrap_ci(case_counts, lambda c: prf(c.hybrid_bug_tp, c.hybrid_bug_fp, c.hybrid_bug_fn)[2])
```

**Métricas com CI calculado:**
- Flow C (LLM puro): precision, recall, F1, MCC
- Flow B (híbrido): precision, recall, F1, MCC
- Flow A (ESBMC puro): precision, recall, F1, MCC
- Smells: precision, recall, F1

**Interpretação:** Se os CIs de dois modelos se sobrepõem, a diferença pode não ser estatisticamente significativa com n=70.

---

## 10. Lógica de Matching

```python
def _find_match(generated, expected, already_matched):
    cat      = expected["category"]
    exp_func = expected["function"]
    for i, g in enumerate(generated):
        if i in already_matched:
            continue
        g_func = g.metadata.get("function", "")
        if g.category == cat and g_func == exp_func:
            return i  # match encontrado
    return None  # FN
```

**Regra:** matching requer `category` E `function` idênticos. Isso evita "acertos por sorte" onde a LLM acerta o tipo de bug mas aponta para a função errada.

**Caso de clean file (`is_clean_case`):**
- GT declara `expected_category = "clean"`
- Qualquer finding da LLM neste arquivo = FP (bug_fp += 1)
- Nenhum finding = TN (bug_func_tn = 1)
- Smells em clean files também são FPs (smell_fp)

---

## 11. Classificações de Finding

| Classificação | Quando ocorre |
|---|---|
| `llm_confirmed_by_esbmc` | LLM propôs + ESBMC confirmou + categoria bateu |
| `llm_false_positive` | Expressão não existe no código (alucinação AST) |
| `heuristic_smell_only` | Smell — sem verificação ESBMC |
| `not_confirmed_within_bound` | ESBMC rodou, não encontrou violação no bound |
| `esbmc_inconclusive` | Timeout / erro / categoria errada no ESBMC |
| `llm_only_suspected` | Flow C — LLM suspeitou, sem confirmação |
| `esbmc_native_bug` | Flow A encontrou sem LLM |
| `llm_missed_esbmc_bug` | Flow A achou, LLM não apontou |
| `out_of_scope_finding` | Categoria fora das 6 suportadas |
| `skipped_not_verifiable` | Finding não marcado como verifiable |

---

## 12. Backends LLM

| Backend | Modelo padrão | Inferência do modelo |
|---|---|---|
| `openai` | `gpt-4o` | nomes com `gpt`, `o1`, `o3`, `o4` |
| `anthropic` | `claude-sonnet-4-6` | nomes com `claude` |
| `ollama` | `deepseek-r1:7b` | qualquer outro nome |

**Todos os modelos usam `temperature=0`** para máxima reprodutibilidade.

**Retry com backoff exponencial** em erros 429/500/502/503/504.

**`strip_markdown_json`:** remove fences de markdown E texto extra após o JSON via `raw_decode` — necessário porque modelos de raciocínio (Claude 4, DeepSeek-R1) frequentemente adicionam explicações após o objeto JSON.

---

## 13. Configuração Experimental Padrão (V1)

| Parâmetro | Valor | Justificativa |
|---|---|---|
| `bound` | 5 | Suficiente para funções de 2-5 LOC sem loops |
| `timeout` (ESBMC) | 30s | Evita travamentos em funções com análise cara |
| `llm_timeout` | 300s | Suficiente para modelos locais lentos (DeepSeek) |
| `temperature` | 0 | Reprodutibilidade máxima |
| `prompt_mode` | `raw` | Sem leakage de operações pré-extraídas |
| Bootstrap B | 2000 | Estabilidade do percentil com n=70 |
| Bootstrap seed | 42 | Reprodutibilidade dos CIs |

---

## 14. Estrutura do JSON de Relatório

```json
{
  "model": "openai/gpt-4o",
  "backend": "openai",
  "prompt_mode": "raw",
  "ground_truth": "/path/to/ground_truths",
  "bound": 5,
  "timeout": 30,
  "metrics": {
    "bugs_llm_only": {
      "precision": 0.7895,
      "recall": 1.0,
      "f1": 0.8824,
      "tp": 45, "fp": 12, "fn": 0,
      "function_accuracy": 0.8727,
      "function_mcc": 0.5145,
      "function_tp": 45, "function_fp": 7, "function_fn": 0, "function_tn": 3
    },
    "bugs_hybrid_pipeline": {
      "precision": 0.9184,
      "recall": 1.0,
      "f1": 0.9574,
      "tp": 45, "fp": 4, "fn": 0,
      "function_accuracy": 1.0,
      "function_mcc": 1.0,
      "function_tp": 45, "function_fp": 0, "function_fn": 0, "function_tn": 10,
      "llm_confirmed_by_esbmc": 48,
      "not_confirmed_within_bound": 5,
      "esbmc_inconclusive": 1,
      "formal_confirmation_rate": 0.8889,
      "noise_reduction_rate": 0.6667
    },
    "smells": {
      "precision": 0.8462, "recall": 0.7333, "f1": 0.7857,
      "tp": 11, "fp": 2, "fn": 4
    },
    "esbmc_direct_baseline": {
      "precision": 1.0, "recall": 1.0, "f1": 1.0,
      "tp": 45, "fp": 0, "fn": 0,
      "function_accuracy": 1.0, "function_mcc": 1.0
    }
  },
  "hallucinations": {
    "count": 1,
    "rate": 0.0175
  },
  "per_category_llm": {
    "assertion_violation": {"precision": 0.88, "recall": 1.0, "f1": 0.94, "tp": 15, "fp": 2, "fn": 0},
    "division_by_zero":    {"precision": 0.68, "recall": 1.0, "f1": 0.81, "tp": 15, "fp": 7, "fn": 0},
    "out_of_bounds":       {"precision": 0.83, "recall": 1.0, "f1": 0.91, "tp": 15, "fp": 3, "fn": 0}
  },
  "per_category_hybrid": {
    "assertion_violation": {"precision": 1.0,  "recall": 1.0, "f1": 1.0,  "tp": 15, "fp": 0, "fn": 0},
    "division_by_zero":    {"precision": 0.94, "recall": 1.0, "f1": 0.97, "tp": 15, "fp": 1, "fn": 0},
    "out_of_bounds":       {"precision": 0.83, "recall": 1.0, "f1": 0.91, "tp": 15, "fp": 3, "fn": 0}
  },
  "confidence_intervals_95": {
    "llm_bug_precision":    [0.70, 0.88],
    "llm_bug_recall":       [1.0,  1.0],
    "llm_bug_f1":           [0.81, 0.94],
    "llm_bug_mcc":          [0.00, 0.77],
    "hybrid_bug_precision": [0.84, 0.98],
    "hybrid_bug_recall":    [1.0,  1.0],
    "hybrid_bug_f1":        [0.92, 0.99],
    "hybrid_bug_mcc":       [1.0,  1.0],
    "esbmc_bug_f1":         [1.0,  1.0],
    "smell_f1":             [0.55, 0.96]
  }
}
```

---

## 15. Limitações Metodológicas

| Limitação | Impacto |
|---|---|
| Dataset 100% sintético, 2-5 LOC | Baixa validade externa para código de produção |
| Single-function, single-bug por arquivo | Infla artificialmente P/R (sem confounders) |
| Taxonomia fechada no system prompt | Avaliação de classificação, não detecção open-ended |
| Um anotador, sem IRR | Ground truth sem verificação inter-anotador |
| ESBMC Python experimental | Não suporta `len()`, bibliotecas externas, etc. |
| n=70 | CIs largos — diferenças < 8pp podem ser ruído |

---

## 16. Limitações ESBMC Python

- Não suporta `len()` em nenhum contexto → dataset validado sem `len()`
- Não suporta `list` como tipo nativo em alguns contextos → `--assign-param-nondet` compensa para OOB
- Frontend Python é experimental — crashes ocasionais em sintaxe complexa
- Loops sem bound fixo precisam de `--unwind` explícito

---

## 17. Glossário

| Termo | Significado |
|---|---|
| **BMC** | Bounded Model Checking — verifica propriedades dentro de um bound de desrolamento |
| **VCC** | Verification Condition — condição gerada pelo ESBMC para provar/refutar |
| **Finding** | Achado bruto da LLM antes de qualquer validação |
| **Ghost Bug** | Finding `suspected_bug + verifiable=False` — erro de classificação, não alucinação |
| **Alucinação** | Finding onde a expressão reportada não existe no código executável |
| **Qualname** | Nome qualificado da função (ex: `Classe.metodo`) |
| **Flow A** | ESBMC puro sem LLM — baseline formal |
| **Flow B** | LLM propõe, ESBMC confirma — pipeline híbrido |
| **Flow C** | LLM puro sem ESBMC — baseline de IA |
| **raw mode** | Prompt sem pré-extração de operações AST — padrão científico |
| **ast_hints mode** | Prompt com operações pré-extraídas — apenas ablação |
| **FCR** | Formal Confirmation Rate — fração das hipóteses LLM confirmadas pelo ESBMC |
| **NRR** | Noise Reduction Rate — redução de FPs do Flow C para Flow B |
| **MCC** | Matthews Correlation Coefficient — métrica robusta para datasets desbalanceados |
| **Bootstrap CI** | Intervalo de confiança por reamostragem com reposição (percentile method) |
| **is_clean_case** | Arquivo sem nenhum bug esperado no GT — qualquer finding = FP |
