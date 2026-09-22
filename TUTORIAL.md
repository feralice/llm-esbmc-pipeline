# Tutorial: Execução do Pipeline

> **Nota:** A V2 é o fluxo principal atual. A V1 permanece como baseline reproduzível para comparação.

## Pré-requisitos

```bash
source .env          # Linux/macOS  |  no Windows: carregue as variáveis manualmente
where esbmc          # verificar se ESBMC está no PATH
esbmc --version
python -m pytest
```

O pytest padrão não chama APIs reais. Para executar explicitamente essas
integrações, use `python -m pytest -m live_llm`.

---

## 1. V2 end-to-end

Esta execução mede o método completo. A LLM recebe os arquivos de detecção e
precisa encontrar a unidade, a categoria e a expressão por conta própria.

```bash
PYTHONPATH=src .venv/bin/python src/main.py \
  --mode hybrid --v2-stage end-to-end \
  --input dataset/v2_real_world/detection \
  --ground-truth dataset/v2_real_world/ground_truths.json \
  --synth-backend codex \
  --output-dir artifacts/v2/end-to-end-117
```

O pipeline executa: preprocessamento AST, detecção LLM, grounding da expressão,
`verbatim-driver`, síntese escalar quando necessário, validação do harness,
ESBMC, grounding diferencial e ablação de `__ESBMC_assume`.

Saídas principais: `v2_report.json`, `v2_checkpoint.json`, `harnesses/` e
`llm_telemetry.json`. Para retomar uma execução interrompida, repita o comando
com `--resume`; a configuração, as fontes e os prompts precisam ser os mesmos.

### Síntese isolada

Para avaliar apenas a geração e a verificação dos harnesses, usando hipóteses
conhecidas no gabarito:

```bash
PYTHONPATH=src .venv/bin/python src/main.py \
  --mode hybrid --v2-stage synthesis \
  --input dataset/v2_real_world/detection \
  --ground-truth dataset/v2_real_world/ground_truths.json \
  --synth-backend codex \
  --output-dir artifacts/v2/synthesis
```

Esse modo não mede a detecção autônoma da LLM.

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

## 2. Benchmark V1 completo (Flow A + B + C em um comando)

```bash
python src/main.py \
  --mode benchmark \
  --input dataset/labeled/ground_truths \
  --model gpt-4o \
  --bound 5 --timeout 30 \
  --report reports/json/v1_benchmark/benchmark_gpt-4o.json
```

Saída no terminal mostra P/R/F1 para Flow C (LLM), Flow B (híbrido) e Flow A (ESBMC) separadamente.

O pipeline usa um único prompt, sem expor à LLM as operações pré-extraídas pelo AST.

---

## 3. Comparar vários LLMs na V1

### Modelos V1 (um por vez)

```bash
# GPT-4o
python src/main.py \
  --mode benchmark \
  --input dataset/labeled/ground_truths \
  --model gpt-4o \
  --bound 5 --timeout 30 \
  --report reports/json/v1_benchmark/benchmark_gpt-4o.json

# Claude Sonnet 4.6
python src/main.py \
  --mode benchmark \
  --input dataset/labeled/ground_truths \
  --model claude-sonnet-4-6 \
  --bound 5 --timeout 30 \
  --report reports/json/v1_benchmark/benchmark_claude-sonnet-4-6.json

# DeepSeek-R1 7b (Ollama local: llm-timeout maior)
python src/main.py \
  --mode benchmark \
  --input dataset/labeled/ground_truths \
  --model deepseek-r1:7b \
  --bound 5 --timeout 30 --llm-timeout 600 \
  --report reports/json/v1_benchmark/benchmark_deepseek-r1-7b.json

# Qwen2.5-Coder 7b (Ollama local)
python src/main.py \
  --mode benchmark \
  --input dataset/labeled/ground_truths \
  --model qwen2.5-coder:7b \
  --bound 5 --timeout 30 --llm-timeout 600 \
  --report reports/json/v1_benchmark/benchmark_qwen2.5-coder-7b.json
```

Gera `reports/json/v1_benchmark/benchmark_<modelo>.json` para cada modelo.

Para retomar um benchmark interrompido, repita exatamente a mesma configuração
e acrescente `--resume`. No modo benchmark, `--report` é obrigatório para
localizar o checkpoint. Casos ausentes ficam em `coverage.failed_cases` e uma
execução parcial retorna código de saída `2`.

> **`--llm-timeout 600`** é necessário para modelos locais Ollama. Reasoning models como DeepSeek-R1 podem levar vários minutos por função: o padrão (300 s) costuma causar timeout em funções mais complexas.

### Atalho: todos de uma vez

```bash
bash scripts/run_all_benchmarks.sh
```

Roda os 5 modelos (Gemini com fallback entre versões, Claude e GPT em paralelo; Qwen e
DeepSeek sequenciais via Ollama, já que dividem a mesma GPU). Logs individuais em
`logs/benchmark/<modelo>.log`, JSONs em `reports/json/v1_benchmark/`. Variáveis de ambiente
`GROUND_TRUTH`, `OUT_DIR`, `BOUND`, `TIMEOUT`, `LLM_TIMEOUT` sobrescrevem os padrões.

---

## 4. Comparar resultados

```bash
python scripts/compare_benchmarks.py --dir reports/json/v1_benchmark
```

---

## 5. Visualizar no frontend

```bash
explorer.exe frontend/index.html
```

Arrastar todos os arquivos `reports/json/v1_benchmark/benchmark_*.json` → aba **Benchmark / Modelos**.

---

## 6. Modos individuais (exploração, não benchmark)

### Flow A: só ESBMC (sem LLM, sem métricas de ground truth)

```bash
python src/main.py \
  --mode esbmc-only \
  --input dataset/labeled/ok/bugs \
  --output-dir artifacts/results/flow_a \
  --bound 5 --timeout 30
```

### Flow B: LLM + ESBMC em arquivo(s) individual(is)

```bash
python src/main.py \
  --mode hybrid-direct \
  --input dataset/labeled/ok/bugs/assertion_violation/av_01.py \
  --model gpt-4o \
  --bound 5 --timeout 30
```

> `--mode hybrid` (sem `-direct`) não é o Flow B legado: ele cai no pipeline
> V2 (`mode_v2`), que faz detecção + síntese de harness + ESBMC. Use
> `hybrid-direct` para o Flow A/B/C clássico da V1.

### Flow C: só LLM (sem ESBMC)

```bash
python src/main.py \
  --mode llm-only \
  --input dataset/labeled/ok/bugs/assertion_violation/av_01.py \
  --model gpt-4o
```

---

## 7. Validar dataset sem LLM

```bash
python scripts/verify_dataset.py
python scripts/verify_benchmark_dataset.py dataset/labeled/ground_truths
```

---

## 8. Referência: modos e backends

### Modos (`--mode`)

| Modo | Função interna | O que faz |
|---|---|---|
| `hybrid` | `mode_v2` | V2 end-to-end: detecção LLM, grounding, síntese de harness, ESBMC. Seção 1. |
| `benchmark` | `mode_v2` (força `--v2-stage end-to-end`) | Mesmo pipeline de `hybrid`, mas exige `--ground-truth`; é o nome usado pro benchmark V2/V1 "oficial" reportado. Seção 2. |
| `hybrid-direct` | `mode_hybrid` | Flow B legado da V1: `run_pipeline_multi`, LLM aponta e ESBMC confirma num só passo, sem síntese de harness. Seção 6. |
| `benchmark-v1` | `mode_benchmark_v1` | Benchmark V1 completo: roda Flow A + B + C juntos, imprime P/R/F1 dos três. |
| `esbmc-only` | `mode_esbmc_only` | Só ESBMC, sem LLM (Flow A). Seção 6. |
| `llm-only` | `mode_llm_only` | Só LLM, sem ESBMC (Flow C). Seção 6. |
| `ensemble` | `mode_ensemble` | Agrega votos de vários `per_file/` já gerados por modelos diferentes; não chama LLM nem ESBMC. |

`hybrid` e `benchmark` caem na mesma função (`mode_v2`) porque `--mode benchmark`
é um atalho que fixa `--v2-stage end-to-end` e obriga `--ground-truth`
(`main.py:971-980`).

### Backends (`--backend` / `--synth-backend`)

| Backend | Onde roda | Precisa de |
|---|---|---|
| `openai` | API OpenAI | `OPENAI_API_KEY` |
| `anthropic` | API Anthropic (só `--backend`; não existe em `--synth-backend`) | `ANTHROPIC_API_KEY` |
| `google` | API Gemini | `GEMINI_API_KEY` |
| `ollama` | Ollama local | `--ollama-base-url` (padrão `http://localhost:11434/v1`) |
| `codex` | `codex exec` local | assinatura Codex já paga, sem token de API |
| `claude_cli` | `claude -p` local | assinatura Claude já paga; `ANTHROPIC_API_KEY` é filtrado do ambiente do subprocesso, não é lido |
| `gemini_cli` | Gemini CLI local | conta autenticada (pessoal ou empresarial); precisa do CLI headless disponível no diretório de execução |

`--backend` escolhe quem detecta; `--synth-backend` escolhe quem sintetiza o
harness na V2 (padrão: mesmo valor de `--backend`). Combinações mistas são
válidas, ex: `--backend openai --synth-backend claude_cli`.

---

## 9. Testes

```bash
python -m pytest
```
