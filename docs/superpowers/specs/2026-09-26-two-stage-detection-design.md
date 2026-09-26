# Detecção em duas etapas para o pipeline V2

## Objetivo

Separar a decisão de “há uma falha alcançável e onde ela está?” da decisão de
“qual categoria descreve essa falha?”. A estratégia será opt-in, preservando a
estratégia atual para comparações e para não alterar benchmarks históricos sem
uma rodada explícita.

## Decisão

Adicionar a estratégia de detecção two_stage:

1. localização: a LLM retorna zero ou mais candidatos com expressão executável,
   linha, operandos, guarda e contexto necessário, sem escolher categoria;
2. classificação: somente os candidatos localizados são enviados a uma segunda
   chamada, que escolhe uma das oito categorias formais ou rejeita o candidato.

Smells continuam na estratégia single nesta etapa. A estratégia two_stage
processa apenas bugs formais e devolve Finding normalizado para o pipeline
existente.

## Contrato de dados

A etapa de localização usará um schema próprio, sem campo category. Cada item
terá id ordinal, expression, line, operands, guard_evidence, missing_guard,
context_needed e explanation.

A etapa de classificação usará um schema próprio com candidate_id, category,
verifiable, explanation e metadata. A categoria deve ser uma das oito
categorias formais. O resultado final será convertido para Finding, preservando
a evidência da localização e adicionando a categoria da segunda etapa.

Nenhum prompt enviará ground truth, nome de dataset ou caminho do arquivo. O
código e os metadados continuarão delimitados como dados não confiáveis.

## Integração

- Cada backend manterá analyze(unit) inalterado para compatibilidade.
- Backends ganharão analyze_stage(unit, stage, candidates) ou uma interface
  equivalente usada pelo wrapper TwoStageAnalyzer.
- O wrapper fará as duas chamadas, agregará os tokens/tempo por etapa e
  retornará Findings normais.
- A CLI ganhará --detection-strategy {single,two_stage}, com single como padrão.
- Checkpoints e relatórios registrarão a estratégia e a telemetria agregada.

## Falhas e limites

- Se a localização retornar zero candidatos, a estratégia termina sem chamar a
  classificação.
- Se a classificação falhar, a unidade será registrada como erro da detecção,
  sem fabricar categoria.
- O mesmo MAX_PROMPT_SOURCE_CHARS será usado nas duas etapas.
- Chamadas reais continuarão fora da suíte padrão; testes usarão backends falsos
  ou respostas injetadas.
- O aumento de custo será explícito na telemetria: chamadas de localização e de
  classificação separadas.

## Métricas

A avaliação existente continuará comparando Findings finais por função e
categoria. A estratégia também registrará, no relatório experimental, número de
candidatos localizados, candidatos classificados, rejeições na classificação e
chamadas por etapa. Não serão comparadas taxas de classificação usando uma
execução única como conclusão; a comparação experimental exigirá múltiplas
rodadas e fixtures positivos e negativos.

## Fora de escopo

- Alterar a taxonomia das oito categorias formais.
- Misturar smells na etapa de classificação.
- Enviar ground truth para qualquer etapa.
- Alterar a síntese de harness ou o ESBMC.

