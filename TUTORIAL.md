# Tutorial: Execução do Pipeline

> **Nota:** A V2 é o fluxo principal atual. O código da V1 foi removido; ficam os resultados e o dataset (seção 2).

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

## 1. V2 ponta a ponta

Mede o método completo: a LLM recebe o recorte de cada função, aponta a expressão suspeita, e o
motor de verificação confirma no arquivo completo.

```bash
PYTHONPATH=src .venv/bin/python src/main.py \
  --mode hybrid --v2-stage end-to-end \
  --input dataset/bugs_reais/funcao_com_bug \
  --ground-truth dataset/bugs_reais/ground_truths.json \
  --verification-sources dataset/bugs_reais/arquivo_com_bug \
  --model gpt-4o-mini --synth-backend openai --synth-model gpt-4o-mini \
  --bound 5 --timeout 180 \
  --output-dir artifacts/v2/e2e
```

O pipeline executa: detecção pela LLM, aterramento da expressão no AST, recorte verbatim com
stubs de bibliotecas, especificação das entradas pela LLM (JSON), montagem do harness, ESBMC com
até 2 reparos, e reexecução no CPython para validar o veredito.

Saídas: `v2_verify_report.json`, `v2_checkpoint.json`, `programs/` (cada programa verificado) e
`llm_telemetry.json`. Para retomar, repita o comando com `--resume`.

### Só verificação (hipóteses do gabarito)

Troque `--v2-stage end-to-end` por `--v2-stage synthesis`. Mede a verificação isolada da detecção.

### Experimentos

- `--spec-strategy resample`: amostras independentes com o mesmo orçamento (linha de base do reparo).
- `--verification-sources dataset/bugs_reais/arquivo_corrigido --verification-sources-strict`: roda
  nas versões corrigidas; todo `CONFIRMED` ali é confirmação falsa.
- `python scripts/v2_agent_arm.py --report <relatório> --out <pasta>`: braço com agente nos casos
  que o motor não roda.
- `python scripts/v2_reverdict.py <relatório>`: recalcula vereditos sem LLM nem ESBMC.

---

## 2. V1 (histórico)

A V1 (fluxos A/B/C, benchmark V1, ensemble, comparação de modelos e frontend) não roda mais: o código
foi removido. Os resultados continuam em `reports/json/v1_benchmark/` e `logs/`, o dataset em
`dataset/v1_sintetico/` e a descrição dos fluxos e métricas em `docs/historico/v1/`.

---

## 3. Referência: modos e backends

### Modos (`--mode`)

| Modo | Função interna | O que faz |
|---|---|---|
| `hybrid` | `mode_v2` | V2: detecção pela LLM e motor de verificação. Seção 1. |
| `benchmark` | `mode_v2` (força `--v2-stage end-to-end`) | Mesmo pipeline de `hybrid`, mas exige `--ground-truth`; é o nome usado pro benchmark V2 "oficial" reportado. |
| `scan` | `mode_scan` | Varre um repositório: grafo de chamadas, detecção por função e motor verify. Sem `--yes`, só monta o grafo e a seleção. |

`hybrid` e `benchmark` caem na mesma função (`mode_v2`) porque `--mode benchmark`
é um atalho que fixa `--v2-stage end-to-end` e obriga `--ground-truth`
(função `mode_benchmark` em `src/main.py`).

### Backends (`--backend` / `--synth-backend`)

| Backend | Onde roda | Precisa de |
|---|---|---|
| `openai` | API OpenAI | `OPENAI_API_KEY` |
| `anthropic` | API Anthropic (só `--backend`; não existe em `--synth-backend`) | `ANTHROPIC_API_KEY` |
| `google` | API Gemini | `GEMINI_API_KEY` |
| `ollama` | Ollama local | `--ollama-base-url` (padrão `http://localhost:11434/v1`) |
| `codex` | `codex exec` local | assinatura Codex já paga, sem token de API |
| `claude_cli` | `claude -p` local | assinatura Claude já paga; `ANTHROPIC_API_KEY` é filtrado do ambiente do subprocesso, não é lido |

`--backend` escolhe quem detecta; `--synth-backend` escolhe quem escreve a
especificação de entrada na V2 (padrão: mesmo valor de `--backend`). Combinações mistas são
válidas, ex: `--backend openai --synth-backend claude_cli`.

---

## 4. Testes

```bash
python -m pytest
```
