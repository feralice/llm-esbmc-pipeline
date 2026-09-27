# Detecção V2: `single` e `two_stage`

## Estratégia padrão: `single`

`single` faz uma chamada por unidade. A resposta combina localização,
categoria e explicação no schema normal de findings. É a estratégia padrão e a
referência para comparabilidade entre rodadas.

## Estratégia experimental: `two_stage`

Ativação:

```bash
PYTHONPATH=src python3 src/main.py \
  --mode hybrid --v2-stage end-to-end \
  --detection-strategy two_stage \
  --input dataset/v2_real_world/detection \
  --ground-truth dataset/v2_real_world/ground_truths.json \
  --output-dir artifacts/v2-two-stage
```

1. `localize` encontra expressão, linha, operandos, guarda e contexto faltante.
2. `classify` recebe somente os candidatos localizados e escolhe uma das oito
   categorias formais.

Se a localização falhar, a classificação não é chamada. Se a classificação
falhar, a unidade permanece explicitamente como falha de detecção; não é
convertida em finding válido.

## O que medir

O relatório mantém os dados separados:

- `detection.trace`: contagens por função/unidade;
- `detection.trace_summary`: localizados, classificados, rejeitados e falhas;
- `telemetry.detection.localization_calls`;
- `telemetry.detection.classification_calls`;
- `telemetry.detection.tokens` e `failed_calls`, quando fornecidos pelo
  backend.

Não se adicionam few-shots específicos por categoria. A comparação correta
usa o mesmo corpus, backend, modelo, timeout, bound e configuração de síntese,
com múltiplas rodadas independentes. Os relatórios brutos de `single` e
`two_stage` não devem ser misturados no mesmo baseline.

## Limites de interpretação

Localizar uma expressão ou classificá-la corretamente não confirma o bug. A
confirmação depende da síntese do harness e do ESBMC. Ground truth é usado
somente depois da detecção, na avaliação.
