# Proposta de projeto: verificação formal guiada por LLM em software Python de sistemas ciber-físicos e embarcados

## Pergunta de pesquisa

O método de detecção e verificação de bugs guiado por LLM, já validado em
software Python de propósito geral, mantém uma taxa de confirmação formal
comparável quando aplicado a software Python que controla ou interage com
sistemas ciber-físicos e embarcados?

## Motivação

Python é hoje usado nesse domínio por meio de interpretadores para
microcontrolador, como MicroPython e CircuitPython, e de bibliotecas cliente
de robótica, como os pacotes Python do ROS 2. O método de síntese de harness e
verificação formal já desenvolvido ainda não foi avaliado sobre esse tipo de
código, cujo comportamento costuma depender de hardware, temporização e
protocolos de comunicação, características ausentes do corpus já testado.

## Corpus proposto

Cinco a dez bugs reais, com commit de correção documentado, minerados de um
candidato de software Python para sistemas ciber-físicos ou embarcados. A
seleção final depende de o candidato possuir histórico de bugs suficientemente
documentado para permitir a mineração com a mesma exigência de proveniência já
usada no projeto. Além das oito categorias formais usadas no corpus geral,
condição de corrida e deadlock serão consideradas como categorias candidatas,
mas ficarão em um corpus separado quando exigirem flags de verificação que não
se aplicam ao corpus geral.

## Método

Será reaplicado o método existente: a LLM localizará a função, a categoria e a
expressão suspeitas a partir do código neutro; um harness com entradas
simbólicas será sintetizado; o ESBMC verificará formalmente a hipótese; e uma
etapa de ablação avaliará se alguma pré-condição assumida mascarou o bug.

## Entregável final

Será produzido um relato comparativo entre a taxa de confirmação formal no
corpus escolhido e a taxa obtida no corpus geral, incluindo uma discussão das
limitações do verificador para código de contexto ciber-físico e embarcado.
