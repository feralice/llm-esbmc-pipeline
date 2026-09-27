# Pipeline V2 — LLM + AST + Harness + ESBMC-Python

Documento central da V2. Descreve o fluxo implementado, os artefatos de
execução, as estratégias de detecção e a forma correta de interpretar os
resultados.

Atualizado em: 27/09/2026

## Objetivo

Detectar hipóteses de bugs formais em código Python real usando LLM para
triagem, AST para grounding estrutural, síntese de harness e ESBMC-Python para
verificação. Code smells continuam separados: são calculados por política AST
e não entram na síntese de harness ou no ESBMC.

## Fluxo implementado

```text
código Python
  -> preprocess_file / AST -> CodeUnit
  -> detecção LLM (single, padrão)
       expressão + linha + categoria + evidência
  -> normalize_findings / grounding AST
       rejeita expressão ausente, categoria inválida ou finding fora do escopo
  -> ScanCandidate formal
  -> síntese do harness
       real-body -> Verbatim Driver -> síntese escalar -> loop fallback
  -> compatibilidade estrutural
  -> ESBMC e, opcionalmente, geração de teste Pytest
  -> retry recuperável, ablação e classificação final
  -> relatório, telemetria e checkpoint resumível
```

O AST não confirma sozinho que existe um bug: confirma que a evidência textual
da LLM corresponde a uma operação executável do código. A confirmação depende
do harness e do resultado do ESBMC.

## Detecção

### `single` — padrão

Uma chamada LLM produz localização, categoria e explicação em um JSON. É a
estratégia usada para manter comparabilidade com as rodadas anteriores.

### `two_stage` — experimental e opt-in

Com `--detection-strategy two_stage`, a LLM faz duas chamadas:

1. `localize`: encontra candidatos concretos, linha, expressão e guarda;
2. `classify`: atribui uma das oito categorias formais aos candidatos já
   localizados.

Não há few-shot específico por categoria. As estratégias devem ser avaliadas
em relatórios separados; nunca se deve misturar seus resultados no mesmo
baseline.

Detalhes: [`two_stage_detection.md`](two_stage_detection.md).

## Grounding AST e code smells

- `src/research_pipeline/ast_utils.py` valida expressões e linhas reportadas
  pela LLM.
- `src/research_pipeline/preprocess.py` extrai `CodeUnit`, operações, guardas,
  parâmetros e métricas.
- `src/research_pipeline/smell_policy.py` calcula `long_method`,
  `many_parameters` e `complex_conditional` por métricas AST determinísticas.

Smells não são enviados ao ESBMC. Em V2, apenas findings formais verificáveis
viram `ScanCandidate`.

## Síntese e verificação

Os tiers de evidência são diferentes e precisam permanecer separados:

| Tier | O que é executado | Interpretação |
|---|---|---|
| `native` | função original via suporte nativo do ESBMC | evidência nativa |
| `real_body` | corpo original preservado | evidência sobre o corpo real |
| `driver` | Verbatim Driver com corpo real e entradas simbólicas | evidência sobre um slice preservado |
| `scalar` | abstração escalar sintetizada | confirmação da abstração, não do programa completo |

`confirmed_on_abstraction` não deve ser narrado como prova do código original.
`attempt_history` registra cada tentativa de síntese/verificação. O texto de
um harness anterior pode ser usado como contexto de reparo, mas seu veredito
ESBMC, assumptions e resumo não são herdados pela tentativa seguinte.

## Relatório V2

Os artefatos ficam no diretório informado por `--output-dir`:

- `v2_report.json`: configuração, detecção, avaliação e resultados;
- `llm_telemetry.json`: eventos por chamada, tokens, duração e falhas;
- `v2_checkpoint.json`: progresso de detecção e síntese para `--resume`;
- harnesses e, se solicitado, testes Pytest gerados.

No bloco `detection`:

- `strategy` identifica `single` ou `two_stage`;
- `candidates` contém apenas hipóteses formais encaminhadas à síntese;
- `rejected_findings` registra findings descartados;
- `trace` detalha cada unidade analisada;
- `trace_summary` separa localizados, classificados, rejeitados e falhas por
  etapa.

No bloco `telemetry.detection`, `localization_calls` e
`classification_calls` aparecem quando aplicável. Ausência de token, cache ou
métrica significa dado não fornecido pelo backend, não zero medido.

## Execução básica

```bash
PYTHONPATH=src python3 src/main.py \
  --mode hybrid \
  --v2-stage end-to-end \
  --input dataset/v2_real_world/detection \
  --ground-truth dataset/v2_real_world/ground_truths.json \
  --output-dir artifacts/v2
```

Para experimentar a detecção em duas etapas:

```bash
PYTHONPATH=src python3 src/main.py \
  --mode hybrid --v2-stage end-to-end \
  --detection-strategy two_stage \
  --input dataset/v2_real_world/detection \
  --ground-truth dataset/v2_real_world/ground_truths.json \
  --output-dir artifacts/v2-two-stage
```

## Arquivos de referência

| Tema | Arquivo |
|---|---|
| Dataset e ground truth | [`dataset/v2_real_world/README.md`](../../dataset/v2_real_world/README.md) |
| Pipeline de scan | [`src/research_pipeline/scan/pipeline.py`](../../src/research_pipeline/scan/pipeline.py) |
| Detecção e backends | [`src/research_pipeline/llm/`](../../src/research_pipeline/llm/) |
| Grounding AST | [`src/research_pipeline/ast_utils.py`](../../src/research_pipeline/ast_utils.py) |
| Política de smells | [`src/research_pipeline/smell_policy.py`](../../src/research_pipeline/smell_policy.py) |
| Síntese de harness | [`harness_synthesis.md`](harness_synthesis.md) |
| Experimento `two_stage` | [`two_stage_detection.md`](two_stage_detection.md) |
| Avaliação V2 | [`src/research_pipeline/v2_evaluator.py`](../../src/research_pipeline/v2_evaluator.py) |

## Estado metodológico

A implementação e os testes do pipeline estão concluídos. A interpretação
experimental continua exigindo separar: erro de detecção da LLM, rejeição AST,
falha de síntese, limitação do ESBMC e confirmação apenas em abstração. A
revisão de proveniência e categoria do dataset real permanece uma atividade de
validade externa, não uma etapa automática do ESBMC.
