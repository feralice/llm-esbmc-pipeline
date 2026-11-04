# Próximas melhorias do pipeline — PGENE601

**Data:** 03/11/2026  
**Objetivo:** medir três melhorias sem alterar a versão congelada usada como referência.

## Estado de referência

- O Codex apontou a linha do gabarito em **39/47 bugs**; isso é localização, não confirmação.
- A rodada formal está incompleta: há resultado salvo para **36/232 hipóteses distintas**.
- Entre essas 36: **24** tiveram tentativa formal em **8 bugs diferentes**; **7** foram recusadas na tradução do harness pelo ESBMC; **5** tiveram erro antes do ESBMC.
- O ESBMC confirmou **1 bug oficial** (divisão por zero no gpiozero). Houve também uma confirmação fora da linha oficial.
- No caso MAVProxy com formatação `%` de string, o self-healing tentou **3 rodadas** e não produziu reparo utilizável. O erro permaneceu sem veredito.
- Três hipóteses no GPS excederam o limite original de **180 s**. Ainda não há registro de que aumentar esse timeout resolveu esses casos.

## Modelo de trabalho

Usar **GPT-6.1 Sol, raciocínio High**, para as tarefas de código e reparo: é um equilíbrio adequado para trabalho técnico complexo e custo. Reservar GPT-6 Astra para uma revisão final mais exigente, se necessário. No experimento de self-healing, registrar o modelo realmente chamado e não confundir o modelo do assistente Codex com o modelo configurado no pipeline.

## Regras para os experimentos

- Preservar o checkpoint atual como baseline e salvar cada variante em uma pasta nova.
- Não alterar a versão congelada nem misturar resultados de variantes.
- Reutilizar hipóteses e harnesses existentes sempre que possível; registrar chamadas ao LLM, tempo e veredito.
- Não chamar um caso de confirmado sem veredito do ESBMC e reprodução da falha no código original.
- Separar `CONFIRMED`, `UNVALIDATED`, `TIMEOUT`, recusa de tradução, erro antes do ESBMC e caso ainda não processado.
- Não fazer commit sem pedido explícito.

## Experimento 2 — self-healing em obstáculos do ESBMC

**Pergunta:** uma variante do self-healing consegue reparar obstáculos reais de tradução que a rodada anterior não resolveu?

1. Reexecutar, em pasta isolada, as duas hipóteses MAVProxy que pararam na formatação `%` não suportada.
2. Usar os mesmos harnesses e hipóteses; configurar o self-healing com GPT-6.1 Sol e até três rodadas por obstáculo.
3. Registrar por rodada se o modelo propôs reparo, se a validação aceitou o patch, se o ESBMC avançou e se a hipótese foi reproduzida no código original.
4. Comparar com o baseline: reparos utilizáveis, novos vereditos, chamadas ao modelo e tempo.

**Sucesso:** ao menos um caso avança sem alterar o comportamento do código original; um patch sem verificação/reprodução conta somente como tentativa, não como sucesso.

## Experimento 3 — priorização e deduplicação de hipóteses

**Pergunta:** dá para reduzir as 232 hipóteses sem perder bugs que o Codex localizou?

1. Fazer primeiro uma análise offline, sem chamada ao LLM: agrupar expressões iguais após normalização sintática segura e medir a redução.
2. Medir também a ordem original das hipóteses por função (top 1, top 2 e top 3) contra o gabarito, apenas para avaliação retrospectiva.
3. Não usar linhas do gabarito para escolher hipóteses na execução real; elas servem somente para calcular cobertura após a análise.
4. Comparar total de hipóteses, bugs oficiais ainda cobertos, precisão, chamadas ao LLM e tempo de ESBMC.

**Sucesso:** menos hipóteses com a mesma cobertura dos 39 casos que o Codex apontou na linha oficial, ou uma redução com perda de cobertura explicitamente medida.

## Experimento 4 — timeout maior para os casos que excederam 180 s

**Pergunta:** mais tempo dá um veredito nos três casos de timeout do GPS?

1. Reexecutar os mesmos três harnesses e specs, sem nova síntese por LLM, com timeout de **300 s**.
2. Manter bound, solver, máquina e demais opções iguais ao baseline; registrar tempo real e uso de recursos.
3. Se algum caso continuar inconclusivo e o custo permitir, fazer uma segunda etapa a **600 s** somente nesses casos.
4. Comparar vereditos e custo com os resultados originais de 180 s.

**Sucesso:** um timeout vira veredito validado. Se continuar em timeout, o resultado ainda informa o custo necessário para decidir se vale ampliar o limite.

## Ordem de execução

1. Confirmar que o checkpoint baseline não está sendo atualizado por outro processo e copiar os artefatos necessários para pastas de variante.
2. Executar o experimento 4 primeiro: reutiliza harnesses e não requer chamada ao LLM.
3. Fazer a análise offline do experimento 3 e escolher uma regra candidata com a cobertura conhecida.
4. Executar o experimento 2 com GPT-6.1 Sol, registrando o consumo e as três rodadas por obstáculo.
5. Atualizar o registro de experimentos com comandos, artefatos, resultados e limitações; só então decidir qual variante merece uma rodada maior.

## Registro dos resultados

Para cada variante, guardar: configuração, versão/commit do pipeline, IDs das hipóteses, resultado individual, tempo, chamadas ao LLM, motivo de parada e comparação com o baseline. A versão congelada continua sendo a referência; qualquer melhoria só passa a integrar o pipeline depois de medida e aprovada pela autora.
