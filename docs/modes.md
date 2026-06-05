# Modos de Execução

## Visão geral

```
python src/main.py --mode <modo> [opções]
```

| Modo | Flow A (ESBMC direto) | Flow B (LLM + ESBMC) | Relatório |
|---|:---:|:---:|---|
| `esbmc-direct` | ✅ | ❌ | `esbmc_direct_results.json` |
| `llm-first` | ❌ | ✅ | `report.json` |
| `full` | ✅ | ✅ | `full_report.json` |
| `benchmark` | ✅ | ✅ | métricas no terminal |
| `esbmc-harness` | ✅ (harness) | ❌ | `esbmc_harness_results.json` |

---

## `esbmc-direct`

Roda o ESBMC diretamente nos arquivos originais, sem LLM.

```bash
python src/main.py --mode esbmc-direct \
  --input dataset/labeled/ok/bugs \
  --bound 5 \
  --timeout 30
```

**Quando usar:** baseline para comparação. Mostra o que o ESBMC consegue verificar sem orientação da LLM.

**Limitação:** arquivos com apenas definições de função geram `no_vcc_generated` — o ESBMC precisa de um ponto de entrada (chamada top-level ou `main()`) para gerar VCCs.

---

## `llm-first`

Roda apenas o Flow B: LLM → AST → Formalizer → Instrumenter → ESBMC.

```bash
python src/main.py --mode llm-first \
  --input dataset/labeled/ok/bugs \
  --model gpt-4o \
  --bound 5 \
  --timeout 30
```

**Quando usar:** testar a análise da LLM isolada, sem o contexto do ESBMC direto.

---

## `full` (recomendado)

Roda Flow A + Flow B para cada arquivo. O resultado inclui tanto o ESBMC direto quanto a análise da LLM com ESBMC instrumentado.

```bash
python src/main.py --mode full \
  --input dataset/labeled/ok/bugs \
  --model gpt-4o \
  --bound 5 \
  --timeout 30 \
  --report reports/json/full_report.json
```

**Parâmetros:**

| Parâmetro | Descrição | Padrão |
|---|---|---|
| `--input` | Arquivo(s) Python ou diretório (recursivo) | obrigatório |
| `--model` | Modelo LLM (`gpt-4o`, `claude`, `qwen2.5-coder:7b`) | `gpt-4o` |
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
  --model gpt-4o \
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
| `gpt` | `gpt-4o` |

---

## Variáveis de ambiente

```bash
OPENAI_API_KEY=        # necessária para backend openai
ANTHROPIC_API_KEY=     # necessária para backend anthropic
OLLAMA_BASE_URL=       # opcional, padrão: http://localhost:11434/v1
```

Configure no arquivo `.env` na raiz do projeto (use `.env.example` como base).
