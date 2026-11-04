# Plano: aproveitar contraexemplo parcial após timeout do ESBMC

1. No timeout, preservar os detalhes de propriedades e contraexemplos que já aparecem na saída parcial.
2. Na verificação, reconhecer somente contraexemplo completo de exceção pertencente ao programa gerado; manter timeout como estado de execução.
3. Tentar replay normal e, se necessário, extrair strings do witness com uma tentativa limitada a 30 segundos.
4. Marcar como confirmado somente quando o CPython reproduzir a mesma exceção dentro da função alvo. Se não reproduzir, manter `ESBMC_TIMEOUT` e registrar a evidência parcial.
5. Rever o diff sem executar testes, conforme a instrução vigente.

Fora de escopo: mudar timeout padrão, bounds, solver, baseline congelada ou classificação de outros erros.
