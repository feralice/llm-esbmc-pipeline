# Tutorial — Benchmark V1

> **Nota:** Para a especificação completa da metodologia, métricas e categorias, consulte a [**Referência Oficial do Benchmark V1**](docs/benchmark_v1_reference.md).

## Pré-requisitos

```bash
cd /mnt/c/Users/ferna/Documents/mestrado/llm_esbmc
source .env 
which esbmc
esbmc --version
python3 -m pytest
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
python3 src/main.py \
  --mode benchmark \
  --input dataset/labeled/ground_truths \
  --model gpt-4o \
  --bound 5 --timeout 30 \
  --report reports/json/v1_benchmark/benchmark_gpt_4o.json
```

Saída no terminal mostra P/R/F1 para Flow C (LLM), Flow B (híbrido) e Flow A (ESBMC) separadamente.

---

## 2. Comparar vários LLMs

### Opção A — um por vez (controle total)

```bash
python3 src/main.py \
  --mode benchmark \
  --input dataset/labeled/ground_truths \
  --model gpt-4o \
  --bound 5 --timeout 30 \
  --report reports/json/v1_benchmark/benchmark_gpt_4o.json

python3 src/main.py \
  --mode benchmark \
  --input dataset/labeled/ground_truths \
  --model claude \
  --bound 5 --timeout 30 \
  --report reports/json/v1_benchmark/benchmark_claude_sonnet_4_6.json

python3 src/main.py \
  --mode benchmark \
  --input dataset/labeled/ground_truths \
  --model deepseek-r1:7b \
  --bound 5 --timeout 30 \
  --report reports/json/v1_benchmark/benchmark_deepseek_r1_7b.json
```

### Opção B — matriz automática (todos de uma vez)

```bash
python3 scripts/run_benchmark_matrix.py \
  --models gpt-4o claude deepseek \
  --ground-truth dataset/labeled/ground_truths \
  --output-dir reports/json/v1_benchmark \
  --bound 5 --timeout 30
```

Gera `reports/json/v1_benchmark/benchmark_<modelo>.json` para cada modelo.

---

## 3. Comparar resultados

```bash
python3 scripts/compare_benchmarks.py --dir reports/json/v1_benchmark
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
python3 src/main.py \
  --mode esbmc-only \
  --input dataset/labeled/ok/bugs \
  --output-dir artifacts/results/flow_a \
  --bound 5 --timeout 30
```

### Flow B — LLM + ESBMC em arquivo(s) individual(is)

```bash
python3 src/main.py \
  --mode hybrid \
  --input dataset/labeled/ok/bugs/assertion_violation/av_01.py \
  --model gpt-4o \
  --bound 5 --timeout 30
```

### Flow C — só LLM (sem ESBMC)

```bash
python3 src/main.py \
  --mode llm-only \
  --input dataset/labeled/ok/bugs/assertion_violation/av_01.py \
  --model gpt-4o
```

---

## Validar dataset sem LLM

```bash
python3 scripts/verify_dataset.py
python3 scripts/verify_benchmark_dataset.py dataset/labeled/ground_truths
python3 scripts/run_esbmc_dataset.py
```

---

## Testes

```bash
python3 -m pytest
```
