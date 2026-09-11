# V2: LLM + ESBMC-Python

Documento central da pesquisa. Ele registra o estado atual, o fluxo do método,
os arquivos de referência, as decisões metodológicas e as pendências.

Atualizado em: 09/09/2026

## Objetivo

Detectar bugs de runtime em código Python real com uma combinação de LLM,
grounding por AST, síntese de harness e verificação formal pelo ESBMC-Python.

## Fluxo atual

```text
Código real
  -> pré-processamento e AST
  -> LLM sugere função, categoria e expressão
  -> grounding confirma que a expressão existe no código
  -> síntese do harness
       1. caminho nativo do ESBMC
       2. Verbatim Driver
       3. Síntese Escalar
  -> validação estrutural do harness
  -> ESBMC verifica a propriedade
  -> retry se houver falha recuperável
  -> ablação se o resultado parecer seguro
  -> classificação e métricas
```

## Dataset V2

Arquivo principal: [`dataset/v2_real_world`](../../dataset/v2_real_world/README.md)

| Medida | Valor |
|---|---:|
| Itens do dataset | 106 |
| Rótulos de categoria | 117 |
| Projetos | 39 |
| Arquivos de detecção | 106 |
| Harnesses | 106 |
| Categorias formais | 9 no ground truth atual |

As 117 categorias não são 117 arquivos: alguns itens possuem mais de uma
categoria.

### Proveniência

O `ground_truths.json` agora recebe a proveniência disponível no manifest:

- URL do repositório;
- ID do bug no BugsInPy;
- `buggy_commit` e `fixed_commit`, quando conhecidos;
- links diretos para os commits quando o hash é válido;
- arquivo e função originais;
- referências de issue ou pull request quando existentes.

Não foram inventados hashes ausentes. Atualmente, 47/106 itens têm
proveniência completa com repositório, commit bugado e commit corrigido.

## O que o BugsInPy fornece

O BugsInPy fornece o projeto, o bug, os commits, o patch e os testes. Ele não
fornece a taxonomia usada pelo projeto, como `none_misuse`,
`invalid_precondition` ou `type_mismatch`. Essas categorias são rótulos de
pesquisa e precisam ser justificadas pela mudança do patch.

O ESBMC também não escolhe essas categorias. Ele informa uma propriedade
violada e, quando possível, um contraexemplo. A categoria semântica continua
sendo responsabilidade do ground truth e da análise do patch.

## Harness

### Caminhos

1. **Nativo:** chama o ESBMC diretamente sobre a função original.
2. **Verbatim Driver:** preserva o corpo da função e cria entradas simbólicas.
3. **Síntese Escalar:** reduz a hipótese à expressão essencial; é fallback e
   pode perder relações do código original.

### Validação

A validação verifica se o arquivo é sintaticamente válido, se o driver existe,
se a propriedade é executável, se os intrínsecos simbólicos são válidos e se a
expressão relevante aparece no harness. Ela responde se o harness pode ser
executado; não prova sozinha que a especificação criada pela LLM está correta.

### Retry

O padrão é uma tentativa inicial mais um retry quando a falha é recuperável.
Não são três tentativas fixas. O retry repete o mesmo caminho de síntese que
falhou, podendo gerar uma nova versão do Verbatim Driver ou da Síntese Escalar.

### Ablação

Quando o harness parece seguro, cada `__ESBMC_assume` é removido isoladamente e
o ESBMC é executado novamente. Se o bug aparece sem aquele assume, o harness
original estava restritivo demais e recebe a marca `over_restricted`. A ablação
é uma checagem de confiança, não uma nova detecção.

## Resultados atuais

### Auditoria do dataset

Relatório detalhado: [`auditoria_dataset_v2_2026-09-09.md`](auditoria_dataset_v2_2026-09-09.md)

- 117/117 expressões de detecção estão grounded no código-alvo.
- 105/106 harnesses produziram contraexemplo no ESBMC.
- `oob_real_10` ficou inconclusivo por timeout.
- Alguns rótulos semânticos precisam ser revisados contra os patches originais.

### End-to-end

O experimento end-to-end usa somente o código, sem fornecer a resposta do
ground truth à LLM. O resultado registrado é:

- 104 unidades únicas avaliadas;
- 28 com função e categoria corretas;
- 23 confirmadas formalmente;
- 22,1% de confirmação quando o denominador é o conjunto de 104 unidades;
- no relatório por rótulo, 23 verdadeiros positivos em 117 labels, com recall de
  19,7%.

Os denominadores são diferentes: 104 é o número de arquivos/unidades únicas;
117 é o número de labels, porque há itens multilabel.

## Arquivos importantes

| Assunto | Arquivo |
|---|---|
| Dataset e definição dos casos | [`dataset/v2_real_world/README.md`](../../dataset/v2_real_world/README.md) |
| Proveniência e ground truth | [`ground_truths.json`](../../dataset/v2_real_world/ground_truths.json) |
| Casamento com código de detecção | [`manifest.json`](../../dataset/v2_real_world/manifest.json) |
| Auditoria estrutural | [`src/research_pipeline/dataset_audit.py`](../../src/research_pipeline/dataset_audit.py) |
| Categorias suportadas | [`src/research_pipeline/llm/categories.py`](../../src/research_pipeline/llm/categories.py) |
| Compatibilidade do harness | [`src/research_pipeline/scan/compat.py`](../../src/research_pipeline/scan/compat.py) |
| Síntese e execução do scan | [`src/research_pipeline/scan/pipeline.py`](../../src/research_pipeline/scan/pipeline.py) |
| Relatório de auditoria | [`auditoria_dataset_v2_2026-09-09.md`](auditoria_dataset_v2_2026-09-09.md) |
| Status e handoff | [`handoff_2026-09-08.md`](handoff_2026-09-08.md) |
| Cronograma | [`cronograma_pesquisa.csv`](cronograma_pesquisa.csv) |

## Pendências

1. Revisar categorias suspeitas contra os patches do BugsInPy.
2. Recuperar commits e patches ausentes.
3. Registrar a saída completa do ESBMC por harness.
4. Reexecutar `oob_real_10` com parâmetros de busca alternativos.
5. Separar no relatório final erro da LLM, erro do harness e limitação do ESBMC.
6. Consolidar custo de tokens, tempo e custo monetário.
7. Comparar baseline e pipeline evoluído.

## Histórico de construção da V2

A V2 foi criada para substituir as funções sintéticas da V1 por bugs em código
Python real. A mudança trouxe classes, dependências, bibliotecas, chamadores e
construções que o ESBMC-Python não modela completamente.

O trabalho foi executado em etapas:

1. **Mineração:** seleção de bugs em projetos conhecidos, principalmente no
   BugsInPy, além de casos do próprio ESBMC e casos externos.
2. **Proveniência:** registro do projeto, ID do bug, arquivo, função, commits,
   patch e issue ou pull request quando disponíveis.
3. **Isolamento:** extração da função e da expressão relevante, removendo ou
   substituindo dependências incompatíveis com o ESBMC-Python.
4. **Ground truth inicial:** registro da função, categoria, expressão e
   propriedade esperada.
5. **Auditoria e correção:** comparação entre patch, arquivo mostrado à LLM e
   harness. Foram corrigidas divergências de função, expressão, commit e
   abstração.
6. **Síntese:** construção do caminho nativo, Verbatim Driver e Síntese Escalar.
7. **Verificação:** execução do ESBMC, análise do contraexemplo e classificação
   do resultado.
8. **End-to-end:** execução sem fornecer à LLM a resposta do ground truth.

O ground truth foi revisado durante o desenvolvimento. Uma expressão presente
no harness não era suficiente: ela precisava corresponder ao código bugado, ao
patch e à propriedade que o ESBMC realmente verificava.

## Critérios de validade do caso

Cada caso da V2 precisa ser analisado em três níveis:

1. **Grounding estrutural:** a expressão apontada existe no código mostrado à
   LLM.
2. **Proveniência:** o código corresponde ao `buggy_commit` do projeto real e
   a correção corresponde ao `fixed_commit`.
3. **Validade semântica:** o harness verifica a mesma falha descrita pelo patch.

O auditor atual comprovou o primeiro nível para 117/117 labels. A auditoria de
proveniência ainda depende dos commits e patches disponíveis para cada caso.

## Como registrar cada experimento

Para permitir a publicação posterior, cada rodada deve guardar:

- versão do código e do dataset;
- modelo, backend, prompt e configuração da LLM;
- entrada enviada à LLM;
- resposta estruturada recebida;
- função, categoria e expressão previstas;
- resultado do grounding;
- caminho do harness utilizado;
- conteúdo ou hash do harness gerado;
- `__ESBMC_assume` usados;
- parâmetros do ESBMC, limite de busca e timeout;
- saída completa do ESBMC e contraexemplo;
- resultado da ablação, quando aplicável;
- tempo, tokens e custo da chamada;
- classificação final e motivo de falha.

## Limitações conhecidas

O ESBMC não escolhe a categoria semântica do bug. Ele verifica a propriedade
fornecida e retorna uma violação, uma prova de segurança ou um resultado
inconclusivo. A categoria precisa ser justificada pelo patch e pelo
comportamento do programa.

Código com classes, bibliotecas numéricas, strings, exceções e dependências
externas pode exigir abstração. Essa abstração pode confirmar a propriedade
essencial, mas também pode perder uma relação importante do código original.

## Formulação recomendada

> A V2 está estruturalmente implementada e testada. O grounding das expressões
> e a execução dos harnesses foram validados. A auditoria de proveniência e a
> revisão semântica das categorias continuam em andamento, principalmente nos
> casos sem commit ou patch local disponível.
