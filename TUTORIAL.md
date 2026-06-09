# Tutorial — Benchmark V1

> **Nota:** Para a especificação completa da metodologia, métricas e categorias, consulte a [**Referência Oficial do Benchmark V1**](docs/benchmark_v1_reference.md).

## Pré-requisitos

```bash
source .env          # Linux/macOS  |  no Windows: carregue as variáveis manualmente
where esbmc          # verificar se ESBMC está no PATH
esbmc --version
python -m pytest
```

---

## Os três fluxos

| Fluxo | O que faz | Métricas geradas |
|-------|-----------|-----------------|
| **Flow A** | ESBMC puro, sem LLM | `esbmc_direct_tp/fp/fn` |
| **Flow B** | LLM aponta → ESBMC confirma | `hybrid_bug_tp/fp/fn` |
| **Flow C** | LLM puro, sem ESBMC | `bug_tp/fp/fn` |

> `--mode benchmark` roda os **três fluxos de uma vez** e imprime as métricas de todos.
> Não é necessário rodar separadamente para obter P/R/F1 de cada fluxo.

---

## 1. Benchmark completo (Flow A + B + C em um comando)

```bash
python src/main.py \
  --mode benchmark \
  --input dataset/labeled/ground_truths \
  --model gpt-4o \
  --prompt-mode raw \
  --bound 5 --timeout 30 \
  --report reports/json/v1_benchmark/benchmark_gpt-4o.json
```

Saída no terminal mostra P/R/F1 para Flow C (LLM), Flow B (híbrido) e Flow A (ESBMC) separadamente.

> **`--prompt-mode raw` é obrigatório** em avaliações científicas. Sem ele o prompt vaza operações pré-extraídas que dão dica do tipo de bug.

---

## 2. Comparar vários LLMs

### Modelos V1 (um por vez)

```bash
# GPT-4o
python src/main.py \
  --mode benchmark \
  --input dataset/labeled/ground_truths \
  --model gpt-4o \
  --prompt-mode raw \
  --bound 5 --timeout 30 \
  --report reports/json/v1_benchmark/benchmark_gpt-4o.json

# Claude Sonnet 4.6
python src/main.py \
  --mode benchmark \
  --input dataset/labeled/ground_truths \
  --model claude-sonnet-4-6 \
  --prompt-mode raw \
  --bound 5 --timeout 30 \
  --report reports/json/v1_benchmark/benchmark_claude-sonnet-4-6.json

# DeepSeek-R1 7b (Ollama local — llm-timeout maior)
python src/main.py \
  --mode benchmark \
  --input dataset/labeled/ground_truths \
  --model deepseek-r1:7b \
  --prompt-mode raw \
  --bound 5 --timeout 30 --llm-timeout 600 \
  --report reports/json/v1_benchmark/benchmark_deepseek-r1-7b.json

# Qwen2.5-Coder 7b (Ollama local)
python src/main.py \
  --mode benchmark \
  --input dataset/labeled/ground_truths \
  --model qwen2.5-coder:7b \
  --prompt-mode raw \
  --bound 5 --timeout 30 --llm-timeout 600 \
  --report reports/json/v1_benchmark/benchmark_qwen2.5-coder-7b.json
```

Gera `reports/json/v1_benchmark/benchmark_<modelo>.json` para cada modelo.

> **`--llm-timeout 600`** é necessário para modelos locais Ollama. Reasoning models como DeepSeek-R1 podem levar vários minutos por função — o padrão (300 s) costuma causar timeout em funções mais complexas.

---

## 3. Comparar resultados

```bash
python scripts/compare_benchmarks.py --dir reports/json/v1_benchmark
```

---

## 4. Visualizar no frontend

```bash
explorer.exe frontend/index.html
```

Arrastar todos os arquivos `reports/json/v1_benchmark/benchmark_*.json` → aba **Benchmark / Modelos**.

---

## Modos individuais (exploração, não benchmark)

### Flow A — só ESBMC (sem LLM, sem métricas de ground truth)

```bash
python src/main.py \
  --mode esbmc-only \
  --input dataset/labeled/ok/bugs \
  --output-dir artifacts/results/flow_a \
  --bound 5 --timeout 30
```

### Flow B — LLM + ESBMC em arquivo(s) individual(is)

```bash
python src/main.py \
  --mode hybrid \
  --input dataset/labeled/ok/bugs/assertion_violation/av_01.py \
  --model gpt-4o \
  --bound 5 --timeout 30
```

### Flow C — só LLM (sem ESBMC)

```bash
python src/main.py \
  --mode llm-only \
  --input dataset/labeled/ok/bugs/assertion_violation/av_01.py \
  --model gpt-4o
```

---

## Validar dataset sem LLM

```bash
python scripts/verify_dataset.py
python scripts/verify_benchmark_dataset.py dataset/labeled/ground_truths
python scripts/run_esbmc_dataset.py
```

---

## Testes

```bash
python -m pytest
```
