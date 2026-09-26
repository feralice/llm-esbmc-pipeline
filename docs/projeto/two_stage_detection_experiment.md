# Experimento de detecção em duas etapas

A estratégia `two_stage` separa a detecção em duas chamadas:

1. localização de uma falha formal alcançável, com expressão, linha e guarda;
2. classificação da hipótese localizada em uma das oito categorias formais.

Ela é opt-in e pode ser executada com `--detection-strategy two_stage`. A
estratégia padrão continua sendo `single`, para preservar comparabilidade com
as rodadas anteriores.

## Interpretação

A primeira etapa mede se a LLM encontra uma causa raiz concreta. A segunda mede
se ela escolhe a categoria correta depois que a evidência já está registrada.
Uma chamada que localiza um trecho não é, por si só, confirmação formal do bug;
o ESBMC continua sendo responsável pela verificação do harness.

## Protocolo recomendado

Comparar `single` e `two_stage` usando o mesmo corpus, backend, modelo, bound,
timeout e configuração de síntese. Fazer múltiplas rodadas por configuração,
guardar os relatórios brutos e incluir casos positivos e negativos de todas as
categorias avaliadas. Não concluir melhoria a partir de uma única execução
estocástica.

O relatório deve preservar a estratégia, os candidatos localizados, as
classificações produzidas e a telemetria de cada etapa. Ground truth só pode
ser usado depois da execução, na avaliação.
