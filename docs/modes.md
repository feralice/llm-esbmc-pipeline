# Modos de Execução

## Visão geral

```
python src/main.py --mode <modo> [opções]
```

| Modo | Flow A (ESBMC-only) | Flow B (LLM + ESBMC) | Flow C (LLM-only) | Relatório |
|---|:---:|:---:|:---:|---|
| `esbmc-direct` | ✅ | ❌ | ❌ | `esbmc_direct_results.json` |
| `llm-first` | ❌ | ✅ | ❌ | `report.json` |
| `full` | ✅ | ✅ | ❌ | `full_report.json` |
| `benchmark` | ✅ | ✅ | ✅ | métricas no terminal |
| `esbmc-harness` | experimental | ❌ | ❌ | `esbmc_harness_results.json` |

**Flow A:** ESBMC-only. O pipeline detecta funções via AST e roda ESBMC com `--function <funcao>` em cada função, sem LLM.

**Flow B:** LLM + ESBMC. A LLM propõe achados, o AST normaliza/valida, e o ESBMC confirma os bugs verificáveis com `--function <funcao>`.

**Flow C:** LLM-only. A LLM propõe achados e o pipeline avalia contra o ground truth sem chamada ao ESBMC.

---

## `esbmc-direct`

Roda o ESBMC sem LLM, mas com ponto de entrada simbólico por função usando `--function`.

```bash
python src/main.py --mode esbmc-direct \
  --input dataset/labeled/ok/bugs \
  --bound 5 \
  --timeout 30
```

**Quando usar:** baseline justo para comparação. Mostra o que o ESBMC consegue verificar sem orientação da LLM, recebendo apenas as funções detectadas pelo AST.

---

## `llm-first`

Roda apenas o Flow B: LLM → AST → ESBMC `--function`.

```bash
python src/main.py --mode llm-first \
  --input dataset/labeled/ok/bugs \
  --model gpt-5.5-2026-04-23 \
  --bound 5 \
  --timeout 30
```

**Quando usar:** testar a análise da LLM com confirmação formal, sem rodar o baseline Flow A.

---

## `full` (recomendado)

Roda Flow A + Flow B para cada arquivo. O resultado inclui tanto o baseline ESBMC-only quanto a análise da LLM confirmada pelo ESBMC com `--function`.

```bash
python src/main.py --mode full \
  --input dataset/labeled/ok/bugs \
  --model gpt-5.5-2026-04-23 \
  --bound 5 \
  --timeout 30 \
  --report reports/json/full_report.json
```

**Parâmetros:**

| Parâmetro | Descrição | Padrão |
|---|---|---|
| `--input` | Arquivo(s) Python ou diretório (recursivo) | obrigatório |
| `--model` | Modelo LLM (`gpt-5.5-2026-04-23`, `claude`, `qwen2.5-coder:7b`) | `gpt-5.5-2026-04-23` |
| `--backend` | Backend LLM (`openai`, `anthropic`, `ollama`) | inferido do model |
| `--bound` | Bound de unwinding do ESBMC | 5 |
| `--timeout` | Timeout por chamada ESBMC (segundos) | 30 |
| `--report` | Caminho do JSON de saída | `artifacts/full-pipeline/full_report.json` |
| `--ground-truth` | Diretório de ground truth para comparação | sem padrão |

---

## `benchmark`

Avalia um modelo contra um conjunto de ground truths anotados.

```bash
python src/main.py --mode benchmark \
  --input dataset/labeled/ground_truths/bugs \
  --model gpt-5.5-2026-04-23 \
  --bound 5 \
  --timeout 30
```

**Entrada:** diretório com JSONs de ground truth no formato:

```json
{
  "category": "division_by_zero",
  "items": [
    {
      "file": "pandas_73_division_by_zero.py",
      "function": "pandas_division_behavior",
      "expected_category": "division_by_zero",
      "verifiable": true
    }
  ]
}
```

Os arquivos Python ficam em `dataset/labeled/ok/bugs/<categoria>/`.

**Saída:** métricas no terminal — Precision, Recall, F1 por categoria.

---

## `esbmc-harness` (experimental)

Gera harnesses automáticos para funções e roda o ESBMC neles. Modo experimental — não é a contribuição principal.

```bash
python src/main.py --mode esbmc-harness \
  --input dataset/labeled/ok/bugs \
  --bound 5 \
  --timeout 30
```

---

## Aliases de modelo

| Alias | Modelo completo |
|---|---|
| `claude` | `claude-sonnet-4-6` |
| `gpt` | `gpt-5.5-2026-04-23` |

---

## Variáveis de ambiente

```bash
OPENAI_API_KEY=        # necessária para backend openai
ANTHROPIC_API_KEY=     # necessária para backend anthropic
OLLAMA_BASE_URL=       # opcional, padrão: http://localhost:11434/v1
```

Configure no arquivo `.env` na raiz do projeto (use `.env.example` como base).
