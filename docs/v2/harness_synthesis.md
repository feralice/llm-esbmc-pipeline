# V2: síntese e verificação de harness

Este documento descreve a implementação atual, não uma proposta futura. O
pipeline usa a LLM para construir um artefato pequeno e verificável a partir de
uma hipótese formal já localizada e grounded no código.

## Ordem dos tiers

Para cada `ScanCandidate`, o pipeline tenta, conforme a configuração:

1. `native`: execução direta da função original quando o caso é compatível;
2. `real_body`: preservação do corpo original em um harness de corpo real;
3. `driver`: Verbatim Driver, preservando o corpo e sintetizando entradas e
   asserções;
4. `scalar`: abstração da expressão suspeita, usada como fallback;
5. `loop`: variante de reparo para casos com laços bounded quando habilitada.

Cada resultado informa `verification_target`, `abstraction_level` e
`harness_tier`. A classificação `confirmed_on_abstraction` confirma apenas o
modelo escalar; os tiers `native`, `real_body` e `driver` são os que podem
sustentar a confirmação do código real.

## Validação antes do ESBMC

O validador estrutural verifica sintaxe, presença de driver/função, intrínsecos
permitidos, propriedade esperada e compatibilidade com a categoria. O
`driver_check` também verifica se o corpo real foi preservado. Compatibilidade
não é prova semântica: apenas impede que um harness obviamente inválido seja
contado como resultado formal.

## Feedback e retries

Uma falha recuperável gera novo attempt com feedback determinístico do
validador ou do ESBMC. `results[].attempt_history` registra cada tentativa,
incluindo:

- número da tentativa e estilo do harness;
- camada da falha e razões de compatibilidade;
- status/resumo do ESBMC e Pytest quando solicitado;
- tokens, duração e feedback usado.

O texto do harness anterior pode ser fornecido para reparo, mas o novo attempt
sempre executa novamente a validação e o ESBMC. Nenhum veredito ou assumption
da tentativa anterior é reutilizado como evidência.

## Ablação

Quando o resultado parece seguro, cada `__ESBMC_assume` pode ser removido
isoladamente. Se a violação aparece sem um assume, o resultado é marcado como
`over_restricted`. A ablação é uma análise de confiança do harness; não é uma
nova etapa de detecção.

## Pytest

`--generate-pytest-testcase` é opcional e roda depois do ESBMC para materializar
valores concretos do contraexemplo. O teste gerado é validado com `ast.parse` e
fica registrado no resultado. Uma falha na geração do Pytest não altera o
veredito formal original.

## Limitação metodológica

Um harness escalar pode confirmar uma propriedade da abstração e ainda assim
omitir o caminho real que contém o bug. Por isso os relatórios e as métricas
separam confirmação do código real de confirmação apenas da abstração.
