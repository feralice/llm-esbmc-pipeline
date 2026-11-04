# Contraexemplo parcial quando o ESBMC excede o tempo

## Objetivo

Em uma execução do ESBMC que termina por timeout, aproveitar uma propriedade de exceção que o solver já imprimiu, sem tratar o timeout como prova. O fluxo deve tentar reproduzir a mesma exceção no CPython; sem reprodução, o resultado continua inconclusivo.

## Abordagens consideradas

- Aumentar globalmente o timeout: simples, mas pode multiplicar o custo sem garantir progresso.
- Parar toda a verificação em cada primeira propriedade: pode mudar o comportamento e a cobertura da configuração congelada.
- Preservar evidência parcial e tentar replay: mantém as configurações originais, pode recuperar um caso útil e só confirma após reprodução. **Escolhida**, conforme a direção aceita pela Fernanda.

## Limites

- O status bruto da execução continua sendo `timeout`.
- Só entram na tentativa propriedades `uncaught exception` apontando para o programa gerado.
- `CONFIRMED` exige replay da mesma exceção no código Python.
- A extração adicional de witness de strings tem teto de 30 segundos; resultados sem reprodução continuam `ESBMC_TIMEOUT`.
- Não muda bounds, timeout padrão, backend/solver, dados anteriores ou regras da medição congelada.

## Partes afetadas

O runner preserva propriedades encontradas na saída parcial; `check` identifica evidência de exceção no alvo; o loop tenta o replay e registra se houve recuperação. Nenhum teste ou nova rodada é executado como parte desta alteração.
