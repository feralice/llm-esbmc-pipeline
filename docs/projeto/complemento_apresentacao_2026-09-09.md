# Complemento da apresentação: 09/09/2026

Material resumido para complementar os slides de progresso da pesquisa.

## Mensagem central

> A V1 mostrou que a LLM pode orientar o ESBMC em funções sintéticas. A V2
> enfrenta o problema mais realista: localizar um bug em código real e criar
> automaticamente uma forma verificável de executá-lo no ESBMC-Python.

## Estado atual

- A arquitetura da V2 está implementada e testada.
- O dataset possui 117 casos reais, derivados de projetos reais, ESBMC e BugsInPy.
- A rodada end-to-end já terminou sem fornecer o gabarito à LLM.
- Foram analisadas 120 unidades AST e geradas 100 hipóteses.
- As 100 hipóteses passaram pela etapa de síntese/verificação.
- O relatório está em `artifacts/v2/end-to-end-117/v2_report.json`.

## Dados da rodada end-to-end executada em 08/09/2026

Esta foi a execução real do pipeline completo, sem fornecer o gabarito à etapa
de detecção da LLM.

| Medida | Resultado |
|---|---:|
| Casos do dataset | 117 |
| Unidades analisadas pela AST | 120 |
| Hipóteses geradas pela LLM | 100 |
| Hipóteses processadas na síntese | 100 |
| Função e categoria corretas | 28 |
| Confirmações formais no fluxo completo | 23 |
| Recall ponta a ponta | 22,1% sobre os 104 casos comparáveis |

### Classificação das 100 hipóteses processadas

| Classificação | Casos |
|---|---:|
| `confirmed_driver` | 71 |
| `confirmed_on_abstraction` | 14 |
| `safe_driver` | 5 |
| `esbmc_inconclusive` | 4 |
| `confirmed_unverified` | 3 |
| `over_restricted` | 2 |
| `safe_on_abstraction` | 1 |

### Leitura do resultado

O número de 22,1% é calculado como `23 / 104`: 23 casos confirmados entre os 104
arquivos de detecção únicos comparáveis na avaliação. O gabarito possui 106
registros porque dois pares de registros compartilham o mesmo arquivo de
detecção; além disso, 11 registros possuem duas categorias, totalizando 117
labels. O relatório apresenta 19,7% quando calcula `23 / 117` no nível de label.
Para a apresentação, use 22,1% e explique que o denominador é 104 arquivos
reais únicos.

O resultado mostra duas coisas diferentes. Quando a hipótese da LLM está correta,
o mecanismo de harness e o ESBMC conseguem confirmar muitos casos. Porém, na
detecção sem gabarito, a LLM ainda perde muitos casos ou escolhe a categoria
errada antes da síntese. Portanto, o gargalo atual está principalmente na
detecção e na classificação, não na execução do harness.

O relatório completo e o checkpoint da execução estão em:

```text
artifacts/v2/end-to-end-117/v2_report.json
artifacts/v2/end-to-end-117/v2_checkpoint.json
```

## Como explicar a V2

```text
Código Python
    ↓
Pre-processamento + AST
    ↓
LLM localiza unidade, categoria e expressão
    ↓
Geração de harness
    ↓
Validação determinística do harness
    ↓
ESBMC verifica formalmente
    ↓
Grounding diferencial + ablação
    ↓
Classificação e métricas
```

## Slide sobre o harness: caminhos de verificação

**Hipótese analisada nos três caminhos:** possível divisão por zero em
`total / divisor`.

```python
def divide(total, divisor):
    return total / divisor
```

### 1. Nativo

Chama o ESBMC diretamente para analisar a função original, sem gerar harness.
O ESBMC trata `total` e `divisor` como entradas simbólicas e procura um caso
como `divisor = 0`.

```text
Função original → ESBMC
```

### 2. Verbatim driver

Preserva o corpo da função original. O driver fornece entradas simbólicas e
chama a função real.

```python
def divide(total, divisor):
    return total / divisor

total = nondet_int()
divisor = nondet_int()
__ESBMC_assume(divisor != 0)
result = divide(total, divisor)

assert divisor != 0
```

Se o harness for inválido ou a verificação falhar de forma recuperável, a LLM
recebe o erro e gera uma nova versão do **mesmo Verbatim driver**.

### 3. Síntese escalar

A LLM reduz a hipótese à propriedade essencial da expressão suspeita. Esse
caminho é usado como fallback quando o Verbatim driver não funciona ou não se
aplica.

```python
divisor = nondet_int()
__ESBMC_assume(divisor != 0)
assert divisor != 0
result = 10 / divisor
```

É mais simples, mas pode perder relações importantes do código original. Se o
harness escalar falhar de forma recuperável, a LLM recebe o erro e tenta gerar
uma nova versão.

### Ordem dos caminhos

```text
ESBMC nativo
      ↓ se não concluir
Verbatim driver
      ↓ se falhar após o retry
Síntese escalar
```

O retry não significa três tentativas fixas. O padrão é uma tentativa inicial
mais uma tentativa extra para cada estratégia de harness. O caminho nativo não
usa retry porque não gera harness pela LLM.

### Relação com a ablação

O `__ESBMC_assume` representa uma hipótese sobre as entradas permitidas. No
exemplo, `divisor != 0` impede que o ESBMC explore justamente o caso de divisão
por zero. Se o harness for considerado seguro, a ablação remove esse `assume` e
executa o ESBMC novamente:

```text
Harness original:
__ESBMC_assume(divisor != 0)
Resultado: seguro

Harness ablado:
# assume removido
Resultado: divisão por zero encontrada
```

Nesse caso, o harness original foi classificado como `over_restricted`: a
hipótese de entrada escondeu o bug. Em um caso real, o `assume` deve representar
uma pré-condição garantida pelo chamador; a ablação verifica se essa restrição
foi forte demais.

## O que é Harness Validation

O harness é um pequeno programa de teste criado para executar a função suspeita
com entradas simbólicas. Antes de entregá-lo ao ESBMC, o pipeline faz uma
checagem automática para evitar que a LLM tenha produzido um arquivo quebrado ou
que não tenha relação com o bug analisado.

Em linguagem simples, o validador pergunta:

> Este programa consegue rodar no ESBMC e ainda está testando o problema correto?

Para responder, ele verifica se:

- o código pode ser lido pelo Python;
- não há bibliotecas externas que o ESBMC-Python não entende;
- os nomes usados no harness existem;
- as entradas simbólicas usam chamadas válidas, como `nondet_int()`;
- o programa realmente chama a função e testa algum resultado;
- o verbatim driver ainda contém a expressão real apontada pela LLM;
- o harness não usa loops ou recursos incompatíveis com o ESBMC-Python.

Se alguma checagem falhar, o ESBMC nem é executado naquele harness. O erro é
registrado e, quando for possível corrigir, enviado à LLM para uma nova tentativa.
Essa etapa não prova que o bug existe; ela apenas garante que o teste está bem
formado. A decisão formal continua sendo do ESBMC.

## O que é grounding diferencial

Para `incorrect_result` e `assertion_violation`, uma violação de `assert` só é
considerada forte quando o harness compara o resultado da função com uma segunda
computação esperada:

```python
buggy_result = target(input_value)
expected_result = independent_computation(input_value)
assert buggy_result == expected_result
```

O validador rejeita propriedades vagas, constantes ou valores `nondet_*()` usados
como se fossem um oráculo. Sem essa segunda computação, o caso pode ser
classificado como `confirmed_unverified`: há uma violação, mas falta evidência
independente de que a propriedade representa o comportamento correto.

## O que é ablação

A ablação só é executada quando o harness original parece seguro. O pipeline
identifica todos os `__ESBMC_assume` do harness e cria uma versão para cada um,
removendo **somente aquele assume**. Cada versão é executada novamente pelo
ESBMC.

Assim, a quantidade de execuções extras é igual à quantidade de hipóteses de
entrada removíveis:

```text
0 assumes  → 0 execuções extras
1 assume   → 1 execução extra
2 assumes  → 2 execuções extras
3 assumes  → 3 execuções extras
```

Exemplo:

```text
Harness original: seguro
        ↓ remove assume_1
ESBMC novamente: seguro
        ↓ remove assume_2
ESBMC novamente: bug encontrado
        ↓
Resultado: over_restricted
```

Nesse exemplo, `assume_2` estava restringindo o espaço de entradas e escondendo
o bug. A ablação registra qual hipótese causou o mascaramento. Guardas de NaN,
como `x == x`, são reconhecidas e não são removidas, pois sua retirada admitiria
valores que não representam entradas reais do domínio modelado.

A ablação não é uma nova estratégia de detecção e não corrige o harness; é uma
checagem de confiabilidade aplicada depois de um resultado seguro.

## Resultados: duas avaliações diferentes

### Síntese isolada

Nesta avaliação, a hipótese de bug vem do gabarito. Ela mede somente a capacidade
de gerar e verificar o harness.

- 69,2% de confirmação formal;
- 75,2% incluindo casos rebaixados por falta de grounding independente;
- 95 de 117 casos tiveram veredito pelo verbatim driver.

Essa avaliação não mede se a LLM consegue encontrar o bug sozinha.

### End-to-end sem gabarito

Nesta avaliação, a LLM recebe apenas o código de detecção e precisa localizar a
unidade, a categoria e a expressão.

- 104 casos comparados com o gabarito;
- 28 casos com função e categoria corretas;
- recall de função + categoria: 26,9%;
- 23 casos confirmados formalmente pelo ESBMC;
- confirmação ponta a ponta: 22,1% dos 104 casos.

O resultado mostra que a classificação da categoria pela LLM é um gargalo
importante, mas não o único. Mesmo quando a categoria é identificada
corretamente, ainda existem perdas nas etapas de grounding, síntese do harness
e verificação formal pelo ESBMC.

## Principais dificuldades

- A LLM frequentemente localiza a função correta, mas confunde a categoria do bug.
- O prompt apresenta muitas categorias simultaneamente, aumentando a ambiguidade.
- Código real possui classes, dependências, exceções e bibliotecas fora do suporte
  completo do ESBMC-Python.
- Alguns casos ficam inconclusivos por limitação do verificador.
- Resultados de comportamento incorreto exigem uma segunda computação independente.
- A auditoria de proveniência ainda encontrou pelo menos um caso em que o arquivo
  apresentado à LLM continha a função errada, apesar da auditoria estrutural inicial.
- `missing_return` e `KeyError` apareceram como possíveis categorias adicionais,
  mas ainda não fazem parte da taxonomia oficial.

## Interpretação do resultado principal

O número de 22,1% não significa que o ESBMC confirmou apenas 22,1% das hipóteses
corretas. Ele mede o método completo, incluindo a etapa mais difícil: a LLM ter
que descobrir sozinha a função e a categoria antes da verificação.

Quando a hipótese correta é fornecida, 23 de 28 casos foram confirmados no
fluxo de síntese e verificação. Os cinco casos restantes foram seguros,
super-restritos, não verificáveis ou inconclusivos. Assim, a melhoria deve
considerar tanto a detecção da LLM quanto o grounding, a síntese do harness e a
verificação formal.

## Dúvidas para o orientador

### Sobre a LLM

1. **A LLM precisa decidir a categoria do bug?** Algumas categorias, como
   divisão por zero, acesso fora de limites e overflow, possuem sinais sintáticos
   que talvez possam ser identificados diretamente pelo AST.
2. **A LLM precisa informar a expressão exata do bug?** Isso ajuda a conectar a
   hipótese ao código, mas também aumenta a chance de erro na resposta.
3. **Vale exigir casamento exato entre a expressão e o código?** Um casamento
   estrito reduz alucinações, mas pode rejeitar expressões equivalentes escritas
   de outra forma.
4. **Few-shot por categoria reduziria os erros?** Exemplos específicos podem
   ajudar a LLM a diferenciar categorias parecidas.
5. **Devemos separar bugs formais e code smells?** Misturar as duas tarefas faz a
   LLM escolher entre muitas categorias na mesma análise.

### Sobre o harness

6. **O Verbatim Driver é melhor que a Síntese Escalar?** O driver preserva mais
   código real; a síntese escalar é mais simples, mas pode perder contexto.
7. **Como garantir que o harness preserva o bug original?** A LLM pode alterar a
   expressão, remover uma condição ou criar um comportamento que não existia.
8. **Como lidar com recursos não suportados?** Classes, bibliotecas externas e
   exceções podem impedir que um caso real seja convertido para o ESBMC-Python.
9. **Devemos adicionar `missing_return` e `KeyError` à taxonomia?** O ESBMC já
   consegue detectar esses casos, mas eles ainda não aparecem como categorias
   oficiais no prompt, no schema e nas métricas do projeto.

### Sobre o ESBMC

10. **Devemos usar flags diferentes por categoria?** Parâmetros específicos
    podem melhorar a verificação de certos tipos de bug.
11. **`--strict-types`, `--ir` e `--unsigned-overflow-check` ajudam no Python?**
    Essas opções existem, mas ainda é preciso medir o efeito real no frontend
    Python.
12. **Contratos, pré-condições e pós-condições estão maduros no Python?** Isso
    define se vale usar essas propriedades como uma nova camada do harness.
13. **Quando o ESBMC fica inconclusivo, qual é a causa?** Precisamos separar uma
    limitação do verificador de um harness mal construído.

### Sobre a metodologia

14. **O dataset está corretamente ligado à origem dos bugs?** A função, a
    expressão e o commit precisam corresponder ao caso real apresentado à LLM.
15. **Como separar as fontes de erro?** As métricas devem distinguir erro da LLM,
    erro do harness e limitação do ESBMC.

## Próximos passos

1. Auditar completamente os casos com provenance e hash de commit.
2. Testar few-shot específico por categoria.
3. Avaliar prompts separados para bugs formais e code smells.
4. Investigar classificação determinística por AST para categorias com assinatura
   sintática clara, como divisão, índice e overflow.
5. Comparar a versão base e a V2 com métricas equivalentes.
6. Consolidar custo computacional em tempo, tokens e custo monetário.
7. Comparar com EVA, PyVeritas e outros trabalhos relacionados.

## Fechamento sugerido

> A contribuição atual da V2 é transformar uma hipótese textual sobre código real
> em uma verificação formal auditável. O método já resolve a parte de síntese e
> verificação quando a hipótese está correta. O resultado end-to-end mostrou que
> o próximo desafio é reduzir o erro de classificação da LLM, especialmente entre
> categorias que compartilham a mesma função ou expressão suspeita.
