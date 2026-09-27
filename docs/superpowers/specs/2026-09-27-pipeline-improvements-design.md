# Melhorias incrementais no pipeline de detecção e verificação

## Objetivo

Melhorar a auditabilidade, a retomada e a qualidade operacional do pipeline
V2 sem alterar o comportamento padrão da estratégia `single` nem misturar
resultados experimentais `two_stage` com os benchmarks históricos.

## Estratégias de detecção

`single` continua sendo a estratégia padrão. Uma chamada da LLM localiza a
hipótese, escolhe a categoria e retorna o finding usado pelo pipeline atual.

`two_stage` continua opt-in. A primeira chamada localiza candidatos sem
categoria; a segunda classifica somente os candidatos localizados. A estratégia
experimental não receberá ground truth, nome de dataset ou caminho de arquivo.

Não serão adicionados few-shots específicos por categoria nesta etapa. A
melhoria será medida por contratos, grounding, feedback do harness e
telemetria, sem introduzir exemplos que possam alterar a comparabilidade dos
benchmarks.

## Melhorias de detecção

- Preservar separadamente localização, classificação e grounding no relatório.
- Registrar rejeições com motivo explícito, sem convertê-las em Findings
  verificáveis.
- Manter a taxonomia formal atual e rejeitar categorias desconhecidas.
- Garantir que a estratégia `single` permaneça compatível e sem chamadas extras.

## Melhorias de síntese e retry

Cada tentativa continuará produzindo um artefato próprio. O retry poderá
reutilizar o conteúdo válido da tentativa anterior e corrigir somente a falha
identificada, sem reutilizar uma propriedade, assume ou resultado ESBMC que
não tenha sido revalidado. O relatório registrará tentativa, motivo da falha,
camada de síntese e veredito.

## Telemetria e checkpoint

O relatório registrará chamadas, tokens, duração e falhas por etapa de detecção
(`single`, `localize`, `classify`) e de síntese. Checkpoints continuarão sendo
gravados por unidade e por resultado, com fingerprint que inclui estratégia,
prompts e fontes. Retomadas não poderão duplicar candidatos, eventos ou
resultados.

## Avaliação

As métricas continuarão separando confirmação do corpo real de confirmação
apenas da abstração escalar. O relatório poderá mostrar métricas por categoria
e perdas por estágio. Comparações entre `single` e `two_stage` exigirão rodadas
controladas, múltiplas repetições, corpus positivo e negativo, e armazenamento
dos relatórios brutos. Nenhuma conclusão de melhoria será incorporada aos
benchmarks históricos automaticamente.

## Fora de escopo

- Few-shots específicos por categoria.
- Mudança da taxonomia formal.
- Chamadas LLM reais na suíte padrão.
- Integração do corpus CPS/embarcado nesta etapa.
- Alteração das flags ou do comportamento interno do ESBMC-Python.
