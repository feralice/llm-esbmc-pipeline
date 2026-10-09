# Harness para bugs de resultado errado (propriedade escrita pela LLM)

Data: 2026-10-09. Item 8 do `docs/ESTADO.md`, priorizado por ela depois da rodada final.

## Problema

O ESBMC só procura quebras (exceção, `assert` falso). A maioria dos bugs do dataset não quebra: a
função devolve um valor errado (`failure_kind = resultado_errado`, 178 de 289). Hoje a LLM marca esses
achados com `verifiable: false`, eles ficam fora do ESBMC e só contam na detecção.

A LLM já descreve a propriedade violada em palavras. Exemplos reais da rodada `full-2026-10-04-sonnet`
(84 achados guardados):

- av_real_17: "devolve a string 'None' em vez de None quando nenhum formato casa";
- av_real_07: "a correspondência por substring faz a regra casar comandos que não são `ls`";
- bip_keras_14: "K.max devolve o valor máximo em vez do índice da classe (argmax)".

## Proposta

1. **Pós-condição executável.** Para um achado de resultado errado na linha suspeita, a LLM escreve
   uma expressão Python sobre as entradas e o resultado, por exemplo `result is None or result != 'None'`.
   Ela vem na mesma chamada que já pede os tipos (especificação JSON do nível 1), num campo novo
   `postcondition`, sem ver o gabarito, o patch nem a versão corrigida.
2. **Harness.** O nível 1 monta o programa como hoje e acrescenta, depois da chamada:
   `result = f(...)` e `__ESBMC_assert(<pós-condição>, "postcondition")`. O ESBMC procura entradas que
   violam a pós-condição; o CPython reexecuta o código original com a entrada do contraexemplo e
   confirma se a pós-condição falha de fato.
3. **O pipeline decide sozinho (decisão dela em 09/10).** A versão corrigida nunca entra na decisão,
   porque o objetivo é ver se o método acha o bug sozinho, como faria num bug novo. A confirmação de
   resultado errado exige:
   - violação da pós-condição achada pelo ESBMC;
   - a reexecução no CPython do código original com a entrada do contraexemplo violando a mesma
     pós-condição;
   - **sanidade da propriedade**: a pós-condição precisa valer para pelo menos uma parte das entradas
     que a busca no CPython gera (uma regra que falha para quase tudo, como `result == 42`, é uma regra
     errada, e o caso vira `PROPERTY_SUSPECT`).
   Passando nos três: `CONFIRMED_PROPERTY`.
   **A versão corrigida serve só para avaliar**, como o gabarito: depois da rodada, a mesma
   pós-condição é rodada na versão corrigida para medir quantas confirmações eram bugs reais (a regra
   passa na corrigida) e quantas eram regras erradas (falha nas duas). Esse número vai para a
   dissertação e nunca volta para a decisão.
4. **Contagem separada.** Confirmações por pós-condição (`CONFIRMED_PROPERTY`) são contadas à parte
   das confirmações por exceção, e as duas somadas só com a ressalva explícita.
5. **Regras gerais.** O prompt pede uma propriedade sobre o comportamento esperado pelo nome, pela
   docstring e pelo uso; nunca valores do dataset. Pós-condição que chama código externo ou tem efeito
   colateral é recusada (só operadores, `len`, `isinstance`, comparações e acesso a atributos do resultado).

## Como medir

- Primeiro nos bugs de resultado errado da amostra de 50 (30 bugs) cuja linha a LLM acerta.
- Métricas: quantas pós-condições o ESBMC aceita; quantas viram `CONFIRMED_PROPERTY` (decisão do
  pipeline); quantas `PROPERTY_SUSPECT`; e, só na avaliação, quantas `CONFIRMED_PROPERTY` passam na
  versão corrigida (bug real) e quantas falham nas duas (regra errada).
- Depois, nos 178 da rodada completa.

## Fora do escopo

- Propriedades sobre estado externo (arquivos, rede).
- Inferir a propriedade a partir de testes do projeto (seria outra fonte; fica como ideia).
