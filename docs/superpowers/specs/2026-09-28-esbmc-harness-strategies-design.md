
# Estratégias de Harness Orientadas ao ESBMC

## Objetivo

Usar uma classificação de quatro valores, orientada ao ESBMC, como saída de pesquisa da LLM, mantendo a mecânica do harness e as evidências da verificação formal separadas das métricas de detecção.

## Desenho

A LLM classifica cada hipótese localizada em exatamente uma das quatro categorias abaixo. Elas descrevem como a hipótese pode ser verificada pelo ESBMC:

- `native_runtime`: usar as propriedades de runtime nativas do ESBMC por meio da função real ou de um driver fiel, como divisão, limites, overflow e exceções.
- `explicit_assertion`: sintetizar uma asserção direta quando o ESBMC não emitir automaticamente a propriedade necessária.
- `differential_assertion`: comparar a expressão com bug e a expressão pretendida usando as mesmas entradas simbólicas.
- `unsupported`: não fabricar um harness para um caso que não possa ser modelado com segurança.

O modo `single` continua sendo a condição de detecção com uma chamada à LLM. O modo `two_stage` continua sendo a condição com duas chamadas: localização e classificação. Ambos produzem o mesmo campo de quatro categorias e usam o mesmo pipeline de harness e verificação pelo ESBMC. O modo `end-to-end` continua executando detecção, síntese e ESBMC; o modo `synthesis` continua pulando a detecção e usando candidatos conhecidos.

As métricas de detecção são baseadas na localização do arquivo, função e expressão. A propriedade violada pelo ESBMC é a evidência formal; qualquer mapeamento para CWE acontece depois da verificação. A classificação da LLM é um dado de pesquisa, não a verdade da detecção.

## Compatibilidade

Os labels dos datasets existentes e os relatórios antigos com oito categorias semânticas continuam legíveis como dados legados. Os novos candidatos V2 usam as quatro categorias acima como classificação operacional do harness. Categorias antigas podem ser mantidas como campo de compatibilidade ao carregar dados antigos, mas não serão emitidas pelo novo detector.

A categoria nunca será usada como verdade da detecção: localização e verificação pelo ESBMC continuam sendo sinais separados.

## Critérios de sucesso

1. Os dois modos de detecção preservam os mesmos campos da descoberta e emitem o mesmo campo de quatro categorias.
2. O roteamento do harness é determinístico a partir dessa categoria.
3. Uma categoria ausente ou `unsupported` não pode ser transformada silenciosamente em um harness válido.
4. Relatórios e checkpoints antigos continuam sendo desserializados sem o novo campo.
5. Os testes padrão não fazem chamadas a provedores reais de LLM.
