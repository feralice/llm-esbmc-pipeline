# Guia para construir o dataset do pipeline Modelos de Linguagem + AST + ESBMC

## Como usar este guia

Este documento é um **caderno de pesquisa e preparação para reuniões de orientação**. Ele reúne
problemas encontrados, alternativas metodológicas, limitações, possibilidades de evolução e dúvidas
em aberto. A presença de um item aqui não significa que ele precise ser implementado no mestrado.

Cada ponto deve receber uma das seguintes decisões após estudo ou conversa com o orientador:

- **fazer agora:** necessário para tornar o experimento atual válido;
- **experimento exploratório:** implementar em uma amostra pequena para avaliar viabilidade;
- **dissertação:** importante para o estudo completo, mas não necessariamente para o artigo curto;
- **trabalho futuro:** relevante, porém fora do tempo ou escopo atual;
- **não fazer:** alternativa rejeitada, mantendo registrada a justificativa.

Prioridade inicial sugerida:

1. corrigir a separação entre entrada da LLM e oráculo do ESBMC;
2. decidir com o orientador o que o V2 realmente medirá;
3. corrigir ou separar os 64 rótulos sem casamento AST;
4. executar um estudo pequeno de síntese automática de harness;
5. reduzir falsos positivos de smells com crítica, repetição ou votação;
6. ampliar e repetir o experimento somente depois de estabilizar o protocolo.

As referências encontradas na literatura estão organizadas separadamente em
[`LEITURAS_RECOMENDADAS.md`](LEITURAS_RECOMENDADAS.md).

### Convenção: modelos de linguagem, LLMs e SLMs

Esta pesquisa não utiliza somente LLMs. Ela compara **LLMs** (*Large Language Models*) e **SLMs**
(*Small Language Models*). Por isso, o termo preferido no texto metodológico deve ser **modelos de
linguagem**, abrangendo os dois grupos.

Neste guia, algumas passagens ainda usam “LLM” como abreviação histórica do nome do pipeline ou para
descrever um trabalho que trata especificamente de LLMs. Isso não significa que todos os modelos
avaliados sejam grandes.

Regras para a dissertação e os próximos relatórios:

- usar **modelo de linguagem** quando a afirmação valer para LLMs e SLMs;
- usar **LLM** somente para modelos classificados como grandes ou quando esse for o termo da fonte;
- usar **SLM** para os modelos pequenos/locais definidos pelo protocolo;
- declarar o critério usado para separar os grupos, pois não existe um limite universal;
- não assumir que modelo local é necessariamente SLM ou que modelo pago é necessariamente LLM;
- apresentar resultados individuais e também agregados por grupo;
- evitar concluir que porte causou a diferença quando arquitetura, treinamento, quantização e prompt
  também variam.

O nome interno “pipeline LLM + AST + ESBMC” pode ser preservado por compatibilidade, mas uma forma
mais precisa no texto novo seria **pipeline híbrido com modelos de linguagem, AST e ESBMC**.

### Registro de decisões da orientação

Após cada reunião, as decisões podem ser registradas nesta tabela. Não apagar perguntas rejeitadas;
registrar o motivo ajuda a justificar o recorte metodológico posteriormente.

| Data | Item/pergunta | Decisão | Motivo | Ação | Prazo |
|---|---|---|---|---|---|
| 2026-08-23 | Objetivo do V2 | Medir detecção e confirmação formal de forma encadeada | O modelo de linguagem propõe o candidato; AST e ESBMC o confirmam, rejeitam ou classificam como inconclusivo | Separar métricas por etapa e também avaliar o resultado fim a fim | A definir |
| 2026-08-23 | Relação entre V1 e V2 | Ainda não decidida | O V1 é o benchmark controlado do artigo já concluído; o V2 é uma evolução em construção e ainda não foi definido formalmente como estudo de transferência | Discutir protocolo e alegações do V2 com o orientador | Próxima orientação |

### Resultado esperado da próxima reunião

Não é necessário resolver todas as perguntas do guia. O objetivo mínimo é sair com estas decisões:

1. contribuição principal do mestrado;
2. objetivo do V2: detecção, confirmação ou ambos;
3. tratamento dos harnesses e dos oráculos ocultos;
4. categorias que permanecerão no experimento principal;
5. escopo de code smells;
6. próxima evolução que será implementada e comparada quantitativamente.

## 1. O problema em uma frase

O código apresentado à LLM deve permitir que ela **suspeite do defeito**, enquanto um arquivo
separado pode conter o `assert`, as entradas não determinísticas e outras adaptações necessárias
para o ESBMC **confirmar a suspeita**.

Essas duas tarefas são diferentes:

- **detecção:** a LLM lê o código e propõe um possível defeito;
- **confirmação:** o ESBMC procura uma entrada que demonstre formalmente a falha.

Um `assert` criado para o experimento é um **oráculo de verificação**. Ele ajuda o ESBMC a saber
qual propriedade deve ser satisfeita. Esse `assert` não deve ser tratado como se fosse o defeito
original encontrado pela LLM.

## 2. Exemplo do problema atual

Considere uma versão simplificada de um bug real do Ansible (`BugsInPy ansible/2`). O método
`__gt__` foi implementado a partir de “não é menor que”:

```python
def greater_than_buggy(a: int, b: int) -> bool:
    return not (a < b)

def greater_than_correct(a: int, b: int) -> bool:
    return b < a

def main() -> None:
    a: int = nondet_int()
    b: int = nondet_int()
    assert greater_than_buggy(a, b) == greater_than_correct(a, b)
```

O bug não é o `assert`. O bug está em `not (a < b)`: quando `a == b`, essa expressão resulta em
`True`, embora `a > b` devesse resultar em `False`. A correção real fornece a expressão `b < a`.
O `assert` foi criado no harness apenas para pedir ao ESBMC que encontre uma entrada em que as
versões divergirem. O contraexemplo pode usar `a == b`.

Porém, se o pipeline enviar o harness completo, nomes e versão corrigida entregam a resposta. Para
detecção, o modelo deveria receber uma forma neutra da função defeituosa:

```python
def greater_than(a: int, b: int) -> bool:
    return not (a < b)
```

Aqui há uma evidência analisável: o modelo pode raciocinar sobre igualdade e perceber que “não
menor” significa “maior ou igual”, não “maior”. Ainda assim, a versão corrigida e o oráculo ficam
ocultos para que o acerto não venha do gabarito.

Portanto, o arquivo completo pode ser um bom **harness para o ESBMC**, mas ainda ser uma entrada
inadequada para medir a capacidade de detecção da LLM.

## 3. Estrutura recomendada

Cada caso deve ter três componentes.

```text
dataset/v3/
├── detection/
│   └── caso_001.py
├── harnesses/
│   └── caso_001_harness.py
└── manifest.json
```

### 3.1 Arquivo de detecção

É o código mostrado à LLM e usado no casamento AST. Deve conter o núcleo real do defeito, mas não
deve entregar a resposta.

```python
def greater_than(a: int, b: int) -> bool:
    return not (a < b)
```

Regras:

- usar nome neutro: `calculate`, não `calculate_buggy`;
- remover comentários como “bug real”, “antes da correção” e “esta linha falha”;
- não incluir a implementação corrigida;
- não incluir o `assert` criado como oráculo do experimento;
- preservar, tanto quanto possível, a lógica da versão anterior ao commit de correção;
- manter anotações de tipo quando exigidas pelo ESBMC-Python.

### 3.2 Harness de verificação

É o arquivo usado pelo ESBMC. Pode importar, copiar ou chamar a função de detecção e acrescentar o
que for necessário para tornar a propriedade verificável.

```python
def greater_than(a: int, b: int) -> bool:
    return not (a < b)

def greater_than_expected(a: int, b: int) -> bool:
    return b < a

def main() -> None:
    a: int = nondet_int()
    b: int = nondet_int()
    assert greater_than(a, b) == greater_than_expected(a, b)
```

O harness pode conter:

- `nondet_int()`, `nondet_float()` e outras entradas simbólicas;
- `__ESBMC_assume(...)` para reproduzir precondições reais;
- um `assert` que expresse o comportamento esperado;
- uma implementação de referência, quando ela vier diretamente da correção real;
- uma abstração pequena para substituir uma biblioteca não suportada.

Esses elementos devem ser documentados. Eles não podem ser apresentados como se fizessem parte do
código original quando foram criados apenas para a verificação.

### 3.3 Manifesto

O manifesto conecta o código real ao harness e registra todas as decisões.

```json
{
  "id": "caso_001",
  "detection_file": "detection/caso_001.py",
  "harness_file": "harnesses/caso_001_harness.py",
  "function": "calculate",
  "categories": ["invalid_precondition"],
  "expression": "x + 2",
  "provenance": {
    "project": "projeto-real",
    "commit": "abc123",
    "original_file": "src/module.py",
    "original_function": "calculate"
  },
  "oracle": {
    "kind": "fixed_version_equivalence",
    "expression": "calculate(x) == expected(x)",
    "source": "implementação posterior ao commit de correção"
  },
  "abstraction": {
    "used": false,
    "description": ""
  }
}
```

## 5. Como lidar com limitações do ESBMC-Python

Nem todo bug Python real pode ser verificado atualmente. Isso não torna o bug inválido; significa
apenas que ele está fora da capacidade atual da ferramenta.

Para cada candidato, use uma destas decisões.

### Decisão A — suportado diretamente

O ESBMC entende as operações originais. Preserve o código quase sem mudanças.

Exemplos normalmente mais simples:

- aritmética com `int` e `float`;
- condicionais e laços limitados;
- divisão inteira;
- acesso a listas e strings;
- `assert` e funções simples.

### Decisão B — abstração fiel

Uma dependência não é suportada, mas o mecanismo do defeito pode ser representado por tipos
simples. A abstração precisa preservar as entradas relevantes e a condição de falha.

Exemplo: representar o comportamento de um `int8` com aritmética explícita. Nesse caso, o resultado
vale para a abstração de `int8`, não para o `int` comum de Python, que não possui overflow de largura
fixa.

### Decisão C — somente erro de conversão

O frontend rejeita o programa antes de gerar propriedades. Isso não é uma confirmação formal por
contraexemplo. Registre como `unsupported_conversion`, não como `VERIFICATION FAILED` válido.

### Decisão D — timeout ou resultado inconclusivo

Se o tempo acabar, registre `inconclusive`. Não conte como defeito confirmado nem como programa
correto.

### Decisão E — impossível de representar com fidelidade

Se a adaptação exigiria inventar o comportamento que causou o bug, rejeite o candidato para o
benchmark formal. Mantenha-o em uma lista de excluídos, com o motivo. Essa transparência fortalece
a pesquisa.

## 6. O que o AST deve validar

O AST não prova que existe um bug. Ele apenas verifica se a LLM apontou algo que realmente aparece
no código analisado e que possui a forma correta para a categoria.

- `division_by_zero`: deve apontar uma operação `/`, `//` ou `%`;
- `out_of_bounds`: deve apontar um acesso indexado, `pop` ou `insert`;
- `assertion_violation`: deve apontar a condição de um `assert` real;
- categorias sem um tipo de nó exclusivo, como `invalid_precondition` e `variable_misuse`: a
  expressão deve existir no código, mas a confirmação depende da propriedade executada pelo ESBMC.

Se o JSON aponta para uma expressão que existe somente em `main()` e a LLM analisou outra função,
o rótulo está mal alinhado com a entrada de detecção.

## 7. Checklist para aceitar um caso

### Procedência

- [ ] O projeto, commit, arquivo e função originais foram registrados.
- [ ] A versão com bug veio de antes do commit de correção.
- [ ] O patch completo foi revisado manualmente.
- [ ] O mecanismo do defeito foi explicado em uma frase.

### Entrada da LLM

- [ ] O nome da função não contém `buggy`, `fixed`, `unsafe` ou equivalente.
- [ ] Comentários e docstrings não revelam a resposta.
- [ ] A implementação corrigida não é mostrada à LLM.
- [ ] O oráculo criado para o ESBMC não é mostrado como parte do defeito original.
- [ ] A expressão do ground truth aparece na função analisada.
- [ ] A linha e a categoria correspondem à AST dessa função.

### Harness do ESBMC

- [ ] O harness possui uma propriedade explícita e justificável.
- [ ] As entradas simbólicas têm tipos compatíveis.
- [ ] Cada `__ESBMC_assume` corresponde a uma precondição real, não a uma restrição criada para
      forçar a falha.
- [ ] O ESBMC gera pelo menos uma VCC.
- [ ] O resultado é `VERIFICATION FAILED` por causa da propriedade esperada.
- [ ] Timeout, erro de conversão e zero VCC não são contados como confirmação.
- [ ] A categoria do contraexemplo é compatível com o rótulo declarado.

### Abstração

- [ ] Foi registrado se houve abstração.
- [ ] Está claro o que foi removido ou substituído.
- [ ] A abstração preserva o mecanismo causal do bug.
- [ ] A conclusão é limitada ao que a abstração realmente representa.

## 8. Como interpretar o estado atual do V2

A auditoria atual encontrou 116 rótulos verificáveis:

- 52 estão ligados a uma expressão encontrada na função-alvo;
- 64 não estão ligados corretamente à AST da função-alvo;
- muitos harnesses possuem nomes, comentários ou oráculos que não devem ser mostrados diretamente
  à LLM.

Isso não significa que os 64 bugs sejam falsos. Significa que o arquivo atual prova uma propriedade
para o ESBMC, mas o ground truth de detecção ainda não está alinhado com o código apresentado à
LLM.

O pipeline já sanitiza a cópia enviada ao modelo, removendo comentários, docstrings e nomes como
`buggy`. Essa proteção reduz vazamentos, mas não substitui a correção do dataset: cada expressão
esperada ainda precisa existir na função de detecção.

## 9. Ordem prática para corrigir o dataset

1. Não apagar os harnesses atuais: eles continuam úteis para o ESBMC.
2. Criar `detection/` e extrair uma função neutra por caso.
3. Manter ou mover os arquivos atuais para `harnesses/`.
4. Criar o manifesto ligando detecção, harness, procedência, oráculo e abstração.
5. Corrigir primeiro os 64 casos sem casamento AST.
6. Rodar a auditoria do dataset.
7. Rodar o ESBMC e confirmar VCC, propriedade e categoria esperadas.
8. Somente depois executar os modelos e comparar LLM isolada, LLM + AST e LLM + AST + ESBMC.

## 10. Regra final

Um caso só entra no experimento principal quando as duas afirmações abaixo forem verdadeiras:

> A LLM recebeu uma função neutra que contém evidência observável do possível defeito.

> O ESBMC recebeu um harness documentado que expressa e viola uma propriedade derivada do bug real.

Quando apenas a segunda afirmação é verdadeira, o caso pode permanecer como artefato de verificação,
mas ainda não deve medir a capacidade de detecção da LLM.

## 11. Dúvidas para discutir com o orientador

As perguntas abaixo representam decisões metodológicas. Elas não devem ser resolvidas apenas com
uma alteração de código, pois mudam o que o experimento mede e quais conclusões poderão ser
defendidas.

### 11.1 Objetivo do dataset

1. **Decisão tomada:** o V2 deve medir as duas capacidades de forma encadeada:
   - **detecção:** o modelo de linguagem propõe função, categoria e expressão suspeita sem receber o
     oráculo oculto;
   - **validação estrutural:** o AST verifica se a evidência indicada existe no código e é compatível
     com a categoria;
   - **confirmação formal:** o ESBMC procura um contraexemplo para uma propriedade independente;
   - **decisão:** o pipeline confirma, rejeita ou declara o candidato inconclusivo.

   O ESBMC confirma a violação de uma propriedade formal. Para afirmar que confirmou o bug descrito
   pela LLM, também é necessário demonstrar que a propriedade verificada corresponde à categoria e
   ao comportamento esperado do caso real.
2. Um caso em que o defeito só fica evidente ao comparar a versão defeituosa com a corrigida pode
   entrar na avaliação de detecção da LLM?
3. Esses casos devem formar dois conjuntos diferentes?
   - conjunto de detecção, com informação suficiente na função isolada;
   - conjunto de confirmação, com harness e oráculo formal.
4. **Decisão pendente:** o V1 é o benchmark controlado utilizado no artigo já concluído. O V2 é uma
   evolução da pesquisa cujo protocolo ainda não foi definido. Discutir com o orientador se o V2
   será:
   - um estudo de transferência do pipeline do V1 para código de produção;
   - um novo benchmark com protocolo próprio;
   - uma avaliação da síntese automática de harnesses;
   - ou uma combinação dessas frentes em experimentos separados.

   V1 e V2 não precisam obrigatoriamente ter protocolos idênticos se responderem perguntas de
   pesquisa diferentes. Entretanto, uma comparação quantitativa direta entre eles só é válida nas
   etapas, categorias, métricas e condições que forem equivalentes. As diferenças de protocolo
   precisam ser declaradas, não tratadas como melhoria causada apenas pela nova versão.

### 11.2 Separação entre função e harness

5. Devemos adotar oficialmente dois arquivos por caso: uma entrada neutra para a LLM e um harness
   separado para o ESBMC?
6. Se o `assert` estiver apenas no harness, qual expressão deve constar no ground truth da etapa de
   detecção: a operação suspeita da função, a precondição ausente ou a propriedade do harness?
7. Para categorias sem um nó AST característico, basta exigir que a expressão apontada exista na
   função, ou precisamos de uma regra estrutural mais forte?
8. O ESBMC deve verificar a função isolada com `--function` ou o harness completo por meio de
   `main()`? Como documentar as categorias em que uma dessas formas não funciona?

### 11.3 Uso de implementações corrigidas como oráculo

9. É metodologicamente aceitável comparar `buggy(x)` e `correct(x)` dentro do harness quando a
   implementação correta foi extraída do commit de correção?
10. Nesse caso, devemos chamar a propriedade de “equivalência com a versão corrigida”, evitando
    dizer que o ESBMC descobriu sozinho a especificação?
11. A implementação corrigida pode ser mostrada à LLM ou isso tornaria a tarefa artificialmente
    fácil? A recomendação atual é não mostrá-la.
12. Casos que dependem exclusivamente dessa comparação devem ser analisados separadamente nos
    resultados?

### 11.4 Abstrações de código real

13. Qual grau de alteração ainda permite chamar um caso de “bug real”?
14. Devemos usar rótulos explícitos como `direct_reproduction`, `extracted` e `abstracted`?
15. Quantos casos abstratos podem compor o dataset sem enfraquecer a alegação de validade externa?
16. Uma abstração manual deve ser revisada por outra pessoa para confirmar que preserva o mecanismo
    causal do bug?
17. Devemos manter no dataset principal casos em que bibliotecas como NumPy e pandas foram
    substituídas por tipos escalares simples, ou colocá-los em um subconjunto separado?
18. No caso de `integer_overflow`, a abstração explícita de `int8` é suficiente para manter a
    categoria, mesmo que o ESBMC-Python não execute o tipo NumPy original?

### 11.5 Limitações do ESBMC-Python

19. Um erro detectado durante conversão, como `NameError` ou atributo não suportado, deve ser contado
    como achado formal ou somente como programa não suportado? A recomendação atual é classificá-lo
    como não suportado.
20. Qual será o tratamento oficial para timeout, zero VCC e resultado inconclusivo?
21. Devemos excluir antecipadamente bugs que dependam de recursos não suportados ou registrar todas
    as exclusões para medir a cobertura do ESBMC-Python?
22. A seleção apenas de defeitos que o ESBMC consegue representar cria circularidade ou viés de
    seleção? Como essa ameaça deve ser declarada?
23. É necessário criar também um conjunto de bugs reais rejeitados, com os respectivos motivos, para
    tornar visível o limite de cobertura da ferramenta?
24. Quando o ESBMC comprova apenas um `assert` criado no harness, podemos afirmar que ele confirmou a
    categoria original ou somente que encontrou uma violação da propriedade modelada?

### 11.6 Taxonomia

25. As oito categorias formais atuais devem ser mantidas?
   - `assertion_violation`;
   - `division_by_zero`;
   - `out_of_bounds`;
   - `none_misuse`;
   - `type_mismatch`;
   - `invalid_precondition`;
   - `variable_misuse`;
   - `integer_overflow`.
26. `variable_misuse`, atualmente com poucos exemplos, deve continuar como categoria própria ou ser
    incorporada a outra categoria?
27. `invalid_precondition` está amplo demais? Precisamos definir critérios objetivos para separar
    precondição inválida, `none_misuse` e `out_of_bounds`?
28. Um mesmo caso pode receber várias categorias? Se sim, a avaliação será por caso, por categoria ou
    pelas duas formas?
29. `assertion_violation` descreve a causa do bug ou apenas a forma da propriedade usada para
    observá-lo? Devemos renomear ou restringir essa categoria?
30. As categorias devem ser informadas no prompt ou o modelo deve descobri-las livremente? Informar
    a taxonomia facilita a tarefa e precisa ser reconhecido como ameaça de construto.

### 11.7 Ground truth e revisão

31. Uma única anotadora é suficiente para esta fase exploratória?
32. Para a próxima avaliação, precisamos de um segundo revisor independente para uma amostra ou para
    todos os casos?
33. Como resolver divergências sobre categoria, expressão culpada e fidelidade da abstração?
34. O ground truth deve apontar obrigatoriamente para uma expressão presente na função enviada à
    LLM?
35. Além da expressão, devemos registrar a linha, o tipo do nó AST, a propriedade formal e a origem
    do oráculo?
36. Os 64 rótulos atualmente sem casamento AST devem ser corrigidos, separados como casos de
    confirmação ou excluídos da avaliação de detecção?

### 11.8 Protocolo experimental e alegações

37. Qual é o número mínimo de casos externos independentes necessário para sustentar uma avaliação
    preliminar de validade externa?
38. Bugs extraídos do próprio repositório do ESBMC devem aparecer separados de BugsInPy e de outros
    projetos externos?
39. Os resultados devem ser apresentados separadamente por nível de fidelidade da reprodução?
40. Devemos comparar:
    - LLM isolada;
    - LLM + AST;
    - LLM + AST + ESBMC;
    - votação entre modelos + AST + ESBMC?
41. A votação deve priorizar aumento de recall, e qual limite inicial é justificável: 2 de 5, 3 de 5
    ou uma análise de sensibilidade de todos os limites?
42. É necessário repetir cada modelo três vezes antes de afirmar melhoria, considerando o não
    determinismo das APIs?
43. Como contabilizar um caso em que a LLM encontra a causa correta, mas descreve uma expressão ou
    linha diferente da escolhida no ground truth?
44. Qual formulação é defensável no texto: “bugs reais verificados pelo ESBMC” ou “abstrações de bugs
    reais com propriedades verificadas pelo ESBMC”?

### 11.9 Decisões prioritárias para a próxima reunião

Se não houver tempo para discutir todas as perguntas, estas são as cinco decisões que mais afetam o
próximo experimento:

1. O V2 mede detecção, confirmação formal ou ambas em conjuntos separados?
2. Será adotada a separação oficial entre função neutra e harness do ESBMC?
3. Os 64 rótulos sem casamento AST serão corrigidos, separados ou excluídos?
4. Qual grau de abstração permite manter a alegação de código real?
5. O que exatamente pode ser chamado de “confirmação do bug” quando o ESBMC verifica um `assert`
   criado no harness?

## 12. Dataset com dois arquivos não significa exigir dois arquivos do usuário

Existe uma diferença importante entre **avaliar cientificamente o pipeline** e **oferecer o
pipeline para uso real**.

No experimento, dois arquivos podem ser mantidos internamente:

```text
função neutra ───────────────→ entrada da LLM
harness revisado e oculto ──→ gabarito/propriedade do ESBMC
```

Isso impede que a LLM veja antecipadamente o `assert`, a versão corrigida ou outra informação que
entregue a resposta. Os dois arquivos funcionam como pergunta e gabarito de uma prova.

No uso real, a interface pode continuar simples:

```text
arquivo ou repositório do usuário
              ↓
           pipeline
              ↓
relatório de candidatos e confirmações
```

O usuário não precisa conhecer `nondet_int()`, escrever `__ESBMC_assume(...)` nem preparar um
harness manualmente. Se um harness for necessário, ele deve ser produzido internamente pelo
pipeline.

Portanto:

- **dois arquivos no dataset:** mecanismo de avaliação e reprodução científica;
- **um arquivo no produto:** experiência esperada para o usuário final.

## 13. Duas alternativas para o pipeline

### 13.1 Alternativa A — harness previamente preparado no dataset

Para cada caso avaliado, a pesquisadora mantém:

```text
detection/caso_001.py
harnesses/caso_001_harness.py
```

Fluxo:

```text
função neutra → LLM → AST → candidato
                              ↓
                    harness oculto revisado
                              ↓
                            ESBMC
```

Vantagens:

- a LLM não recebe o gabarito;
- a propriedade foi derivada do commit, teste ou especificação real;
- o resultado é reproduzível;
- erros na geração do harness não são confundidos com erros de detecção da LLM;
- permite comparar justamente os modelos.

Limitações:

- exige preparar e revisar um harness por caso do benchmark;
- não representa sozinho toda a automação desejada no uso real;
- mede detecção e confirmação usando um oráculo previamente disponível.

Esta é a alternativa recomendada para o **experimento principal**, porque oferece maior controle
metodológico.

### 13.2 Alternativa B — a LLM gera o harness automaticamente

Fluxo:

```text
código real
    ↓
LLM identifica candidato
    ↓
LLM cria entradas simbólicas, precondições e propriedade
    ↓
validação estrutural e de segurança
    ↓
ESBMC executa o harness gerado
```

Essa alternativa se aproxima mais do uso real: a pessoa entrega somente o arquivo ou repositório e
o pipeline realiza o restante.

Entretanto, o harness gerado pela LLM não pode ser aceito sem validação. A LLM pode:

- inventar uma propriedade que não representa a intenção do programa;
- alterar a função original;
- escolher valores constantes que forçam uma falha;
- criar uma precondição artificial;
- usar `__ESBMC_assume(...)` para eliminar entradas que contradizem sua hipótese;
- comparar a função com um comportamento esperado sem fonte independente;
- produzir código não suportado pelo ESBMC-Python.

Contraexemplo metodológico: neste exemplo fictício não existe informação independente dizendo que
somar 1 é o comportamento correto:

```python
def soma(x: int) -> int:
    return x + 2

def main() -> None:
    x: int = nondet_int()
    assert soma(x) == x + 1
```

O ESBMC encontrará uma violação. Porém, sem documentação, teste ou especificação externa, não se
sabe por que `x + 1` seria o resultado correto. Nesse caso, o ESBMC comprovou que a implementação
contradiz a propriedade proposta pela LLM; ele não comprovou independentemente que a implementação
viola a intenção real do usuário.

Essa alternativa é recomendada como **evolução ou experimento exploratório** do pipeline.

### 13.3 Uso conjunto das duas alternativas

As alternativas não são mutuamente exclusivas:

1. O benchmark guarda um harness revisado e oculto como referência.
2. A LLM recebe somente a função neutra e gera seu próprio harness.
3. O harness gerado é comparado com o harness de referência.
4. O ESBMC executa ambos separadamente.
5. A avaliação mede duas capacidades:
   - a LLM encontrou o candidato correto?
   - a LLM sintetizou uma propriedade equivalente ou compatível com o oráculo independente?

Esse desenho permite pesquisar geração automática sem abandonar um gabarito confiável.

## 14. Fluxo recomendado para o usuário final

No uso real, o pipeline pode aceitar um arquivo completo ou um repositório.

```text
Arquivo/repositório
        ↓
Extração das funções
        ↓
LLM propõe categoria e expressão suspeita
        ↓
AST verifica se a expressão existe e tem a forma esperada
        ↓
┌─────────────────────────────────────────┐
│ Existe propriedade verificável nativa? │
└─────────────────────────────────────────┘
        ↓ sim                       ↓ não
 ESBMC direto             síntese interna de harness
                                  ↓
                         validações do harness
                                  ↓
                                ESBMC
```

Exemplo de categoria verificável de maneira mais direta:

```python
def get_item(values: list[int], index: int) -> int:
    return values[index]
```

A LLM aponta `values[index]`, o AST confirma que existe um `Subscript` e o ESBMC pode procurar um
índice inválido. O usuário não precisa fornecer um segundo arquivo.

Para defeitos relacionados a regra de negócio, a situação é diferente:

```python
def calcular_desconto(preco: float) -> float:
    return preco * 0.8
```

Somente o código não informa se o desconto deveria ser 20%, 10% ou nenhum. Para confirmar um bug,
o pipeline precisaria de pelo menos uma fonte de especificação:

- um `assert` já existente;
- testes do projeto;
- contrato ou precondição;
- documentação;
- versão corrigida de um commit;
- confirmação humana;
- propriedade sintetizada pela LLM, claramente marcada como hipótese.

## 15. Níveis de força da confirmação

O relatório não deve apresentar todas as falhas do ESBMC como evidência de igual força. Uma
classificação possível é:

### Nível 1 — propriedade nativa

O ESBMC detecta diretamente uma propriedade como divisão por zero, acesso fora dos limites ou
overflow compatível com seu modelo. É a confirmação automática mais forte dentro do escopo da
ferramenta.

### Nível 2 — propriedade existente no projeto

O programa ou seus testes já possuem um `assert`, contrato ou comportamento esperado. O ESBMC
encontra uma entrada que viola essa propriedade.

### Nível 3 — propriedade derivada de correção real

O harness usa a versão corrigida ou um teste acrescentado pelo commit como oráculo. A origem é
independente da LLM, mas o caso pode conter uma abstração manual.

### Nível 4 — propriedade sintetizada pela LLM

O ESBMC encontra uma violação da hipótese criada pela própria LLM. O resultado é útil, mas deve ser
apresentado como “contraexemplo para uma propriedade proposta”, não automaticamente como bug
confirmado.

### Nível 5 — inconclusivo ou não suportado

Timeout, zero VCC, erro de conversão ou recurso não modelado. O resultado não confirma nem refuta o
bug.

## 16. Validações mínimas para um harness gerado pela LLM

Antes de executar o ESBMC, o pipeline deve verificar automaticamente:

- a função original não foi alterada;
- o código do usuário aparece integralmente ou possui hash equivalente;
- o harness chama a função correta;
- as entradas são simbólicas quando necessário;
- cada `__ESBMC_assume(...)` está registrado para auditoria;
- nenhum `assume` afirma diretamente a condição que produz o resultado desejado;
- o `assert` é separado da função original;
- a expressão do candidato existe na AST original;
- a categoria é compatível com a operação apontada;
- o harness é sintaticamente válido;
- o frontend do ESBMC consegue convertê-lo;
- existe pelo menos uma VCC;
- o contraexemplo alcança a função original;
- a propriedade violada é a propriedade esperada, e não uma falha interna criada pelo harness.

Mesmo após essas verificações, uma regra de negócio proposta pela LLM pode precisar de confirmação
humana.

## 17. Novas dúvidas para discutir com o orientador

### 17.1 Experimento versus produto

45. Está correto manter dois arquivos internamente no benchmark, mas oferecer uma interface de
    arquivo ou repositório único ao usuário?
46. O trabalho atual precisa implementar a experiência completa de uso real ou pode primeiro
    validar cientificamente os componentes com harnesses previamente preparados?
47. A separação entre entrada e gabarito deve ser descrita como parte do protocolo experimental?
48. O harness oculto pode ser chamado de “ground truth formal” ou é melhor chamá-lo de “oráculo de
    verificação”?

### 17.2 Geração automática do harness

49. A síntese de harness pela LLM deve fazer parte do pipeline principal agora ou ser uma segunda
    contribuição/experimento futuro?
50. O mesmo modelo deve detectar o bug e gerar o harness, ou modelos/chamadas independentes reduzem
    o risco de confirmar a própria hipótese?
51. Devemos pedir que a LLM gere somente entradas simbólicas ou também permitir que ela crie a
    propriedade (`assert`)?
52. Quando não houver especificação independente, a propriedade gerada pela LLM precisa de aprovação
    humana antes de o resultado ser chamado de bug?
53. É necessário comparar automaticamente o harness sintetizado com um harness de referência no
    benchmark?
54. Quais usos de `__ESBMC_assume(...)` serão permitidos em harnesses gerados?
55. Como detectar uma propriedade artificial que apenas força o ESBMC a reprovar o programa?

### 17.3 Classificação da evidência

56. Os níveis de confirmação propostos neste guia são adequados?
57. Resultados baseados em propriedades nativas, testes existentes, commits corrigidos e hipóteses
    da LLM devem aparecer em grupos separados nas métricas?
58. A expressão “confirmado pelo ESBMC” deve ser reservada aos níveis 1 a 3?
59. Para o nível 4, devemos usar “violação encontrada para propriedade sintetizada pela LLM”?
60. Qual nível mínimo será aceito no conjunto principal de bugs formalmente confirmados?

### 17.4 Escopo viável da pesquisa

61. Para a próxima versão, é mais importante aumentar o número de bugs reais ou implementar a
    síntese automática de harness?
62. Podemos apresentar os harnesses revisados como infraestrutura experimental e deixar sua geração
    automática como evolução do pipeline?
63. Um pequeno experimento exploratório de síntese, separado do resultado principal, seria suficiente
    para demonstrar a viabilidade da interface de arquivo único?
64. A contribuição principal deve ser descrita como confirmação de achados da LLM, geração de
    propriedades formais ou combinação das duas?

### 17.5 Cinco novas decisões prioritárias

1. Dois arquivos serão apenas internos ao benchmark, mantendo entrada única para o usuário final?
2. A geração automática de harness entra no experimento principal ou em um estudo exploratório?
3. A LLM poderá criar o `assert` ou somente preparar entradas para propriedades já existentes?
4. Como o relatório distinguirá propriedade independente de propriedade inventada pela LLM?
5. Qual nível de evidência autoriza o uso da expressão “bug confirmado pelo ESBMC”?

## 18. Vazamento de gabarito para a LLM

Se a LLM receber o harness completo, ela pode acertar porque o próprio arquivo revela a resposta.
Isso é chamado aqui de **vazamento de gabarito**.

Exemplo baseado no caso real simplificado do Ansible:

```python
def greater_than_buggy(a: int, b: int) -> bool:
    return not (a < b)

def greater_than_correct(a: int, b: int) -> bool:
    return b < a

def main() -> None:
    a: int = nondet_int()
    b: int = nondet_int()
    assert greater_than_buggy(a, b) == greater_than_correct(a, b)
```

O mecanismo do bug e da correção vem de um caso real; o código acima é uma redução escalar criada
para o ESBMC. Ele mostra quatro pistas que facilitam artificialmente a tarefa:

1. `greater_than_buggy` informa pelo nome qual função possui o defeito;
2. `greater_than_correct` entrega a implementação esperada;
3. o `assert` revela qual comparação deve valer;
4. `main()` mostra exatamente como alcançar e observar a divergência.

Um acerto nesse cenário não demonstra necessariamente que a LLM descobriu o bug. Ela pode apenas
repetir a informação que já estava explícita no harness.

### 18.1 O que a LLM deve receber

Para medir detecção, a LLM deve receber uma versão neutra:

```python
def greater_than(a: int, b: int) -> bool:
    return not (a < b)
```

No caso real, essa função deve preservar a lógica da versão anterior ao commit de correção. O
pipeline já sanitiza a cópia enviada ao modelo, removendo comentários, docstrings e nomes como
`buggy`, mas o dataset também deve ser organizado de forma neutra e auditável.

O avaliador mantém o oráculo separadamente:

```python
def greater_than(a: int, b: int) -> bool:
    return not (a < b)

def greater_than_expected(a: int, b: int) -> bool:
    return b < a

def main() -> None:
    a: int = nondet_int()
    b: int = nondet_int()
    assert greater_than(a, b) == greater_than_expected(a, b)
```

O segundo arquivo não é fornecido à LLM. Ele serve para avaliar e confirmar a hipótese em condições
controladas.

### 18.2 `assert` original versus `assert` criado para o experimento

Nem todo `assert` deve ser removido do código apresentado à LLM.

Um `assert` pode fazer parte do programa original:

```python
def withdraw(balance: int, amount: int) -> int:
    result: int = balance - amount
    assert result >= 0
    return result
```

Nesse caso, `assert result >= 0` é um contrato escrito pelo próprio desenvolvedor. Removê-lo
alteraria o programa original. Ele pode permanecer na entrada da LLM e pode ser utilizado pelo
ESBMC.

Outra situação é um `assert` acrescentado pela pesquisadora apenas para tornar o bug verificável:

```python
assert funcao_com_bug(x) == funcao_corrigida(x)
```

Esse `assert` não fazia parte do programa analisado. Ele é um oráculo experimental e deve ficar no
harness oculto.

Regra prática:

- **`assert` original do projeto:** permanece na entrada;
- **teste original do projeto:** pode servir de especificação independente, mas deve ser registrado;
- **`assert` criado para o experimento:** fica somente no harness;
- **versão corrigida do commit:** fica somente no harness/gabarito;
- **nomes `buggy`, `correct` ou `fixed`:** devem ser neutralizados antes da LLM;
- **comentários que descrevem o bug:** devem ser removidos da entrada da LLM;
- **procedência e resposta esperada:** ficam no manifesto, não no prompt.

### 18.3 Fluxo sem vazamento

```text
Função real defeituosa, com nome neutro
                  ↓
                 LLM
                  ↓
       categoria + expressão suspeita
                  ↓
 AST confirma que a expressão existe no código
                  ↓
      pipeline sintetiza um harness
                  ↓
                ESBMC
                  ↓
comparação com harness/oráculo oculto e revisado
```

Esse fluxo separa três perguntas:

1. A LLM detectou o defeito sem conhecer a resposta?
2. O AST confirmou que a evidência indicada existe no código?
3. O harness e o ESBMC demonstraram uma violação da propriedade correta?

### 18.4 Como auditar vazamento no dataset

Antes de executar um modelo, verificar automaticamente se a entrada contém:

- nomes com `buggy`, `broken`, `unsafe`, `correct`, `fixed` ou equivalentes;
- comentários com “bug real”, “antes da correção”, “esta linha falha” ou equivalentes;
- a função corrigida no mesmo arquivo enviado à LLM;
- um `assert` criado apenas para comparar a versão com bug e a corrigida;
- o identificador da categoria no caminho ou nome do arquivo;
- metadados de procedência que descrevam diretamente a correção;
- testes cujo nome ou mensagem informe o defeito esperado.

O arquivo original e o harness podem manter essas informações para reprodução. A restrição se
aplica à cópia que efetivamente entra no prompt da LLM.

## 19. Dúvidas sobre vazamento para discutir com o orientador

65. A distinção entre `assert` original e `assert` experimental é suficiente para definir o que a
    LLM pode receber?
66. Testes originais do projeto podem ser mostrados à LLM ou devem permanecer como especificação
    oculta?
67. Quando a LLM analisa um repositório real completo, esconder os testes torna o cenário menos
    realista ou evita vazamento na avaliação de detecção?
68. Devemos realizar dois experimentos: código sem testes e código com testes?
69. Um nome revelador que já existia no projeto original deve ser preservado por fidelidade ou
    neutralizado para controlar o experimento?
70. A sanitização automática do prompt deve ser descrita como mitigação de vazamento no artigo?
71. Precisamos medir separadamente o desempenho antes e depois da sanitização para demonstrar o
    impacto do vazamento?
72. A versão corrigida pode ser usada somente como oráculo oculto ou também como entrada em um
    experimento separado de localização de mudanças?
73. O manifesto completo deve ficar inacessível ao processo que chama a LLM, garantindo por código
    que o modelo não receba o ground truth?
74. Quais campos mínimos devem ser salvos para provar posteriormente exatamente qual código foi
    enviado a cada modelo?

### 19.1 Decisões prioritárias sobre vazamento

1. Quais artefatos a LLM poderá ler: somente a função, o arquivo completo ou também os testes?
2. Como distinguir automaticamente `assert` original de `assert` experimental?
3. Nomes reveladores originais serão preservados ou neutralizados no benchmark?
4. Será feita uma ablação para medir o efeito da sanitização?
5. O prompt final enviado a cada modelo será arquivado para auditoria e reprodução?

## 20. Limitações atuais do pipeline

Esta seção deve ser atualizada conforme os experimentos evoluírem. Reconhecer as limitações não
invalida a pesquisa; define corretamente o alcance das conclusões.

### 20.1 Limitações do dataset

- O V1 é sintético e pequeno, portanto pode não representar a variedade de projetos reais.
- Parte do V2 é uma abstração manual de bugs reais, não uma execução literal do projeto original.
- O V2 foi selecionado considerando o que o ESBMC-Python consegue representar, criando viés de
  seleção.
- Alguns casos contêm função defeituosa, função corrigida e oráculo no mesmo arquivo.
- A auditoria atual encontrou 64 de 116 rótulos sem casamento correto com a AST da função-alvo.
- Há categorias com poucos exemplos, especialmente `integer_overflow` e `variable_misuse`.
- A distribuição entre categorias é desbalanceada.
- Uma única autora participou da maior parte da anotação.
- O commit corretivo pode conter várias mudanças; nem toda linha alterada representa a causa do bug.
- Uma função isolada pode perder contexto de classe, módulo, chamadas e regras de negócio.
- Bugs selecionados do próprio ESBMC têm menor independência externa que bugs de outros projetos.

### 20.2 Limitações da LLM

- Modelos podem inventar expressões, linhas, categorias e explicações.
- Modelos podem produzir respostas diferentes em execuções repetidas.
- Temperatura e parâmetros nem sempre são iguais ou documentados por todos os provedores.
- Modelos hospedados podem mudar silenciosamente mantendo o mesmo nome público.
- O resultado depende do prompt e da taxonomia fornecida.
- Informar as categorias facilita a tarefa e limita a descoberta de defeitos fora da taxonomia.
- Modelos menores podem superdisparar code smells e gerar muitos falsos positivos.
- Uma explicação convincente não garante que a evidência exista no código.
- A LLM pode inferir o rótulo por nomes de arquivos, funções, comentários ou testes.
- Quando a mesma LLM detecta o bug e cria o oráculo, existe risco de confirmação da própria hipótese.

### 20.3 Limitações do casamento AST

- O AST confirma presença e forma sintática, não a existência semântica do bug.
- Um acesso indexado não é automaticamente `out_of_bounds`.
- Uma divisão não é automaticamente divisão por zero.
- Categorias como `invalid_precondition` e `variable_misuse` não possuem um único tipo de nó
  característico.
- Comparação textual por `ast.unparse()` pode rejeitar paráfrases semanticamente equivalentes.
- A linha fornecida pela LLM pode mudar após sanitização ou normalização do código.
- Expressões repetidas na mesma função podem dificultar a localização exata.
- O AST de uma única função não contém necessariamente o contexto interprocedural necessário.

### 20.4 Limitações do ESBMC-Python

- Nem todas as bibliotecas, tipos e operações Python são modelados.
- NumPy, pandas, reflexão, arquivos, rede e objetos complexos frequentemente exigem abstração.
- Alguns erros ocorrem durante a conversão, antes da geração de VCC.
- `VERIFICATION SUCCESSFUL` com zero VCC não demonstra ausência de bug.
- Timeout e erro da ferramenta são resultados inconclusivos.
- O resultado depende de unwind, timeout, solver e opções de execução.
- Uma propriedade criada no harness pode não representar a intenção real do programa.
- O ESBMC pode confirmar a violação do `assert`, mas não descobrir sozinho uma regra de negócio.
- Uma abstração incorreta pode criar ou remover comportamentos.
- Uma violação pode ocorrer em propriedade diferente daquela associada ao candidato da LLM.

### 20.5 Limitações da avaliação

- Uma execução por modelo não permite estimar variância.
- Sem teste estatístico, não se deve usar “melhoria significativa”.
- Precisão e recall agregados podem esconder categorias com comportamento ruim.
- Comparar modelos com configurações diferentes ameaça a validade de construto.
- O custo, os tokens e a latência precisam ser registrados nas próximas execuções.
- A votação pode aumentar recall e simultaneamente reduzir precisão.
- Um ground truth produzido por LLM e avaliado por LLM cria circularidade.
- Um benchmark conhecido ou presente nos dados de treinamento pode causar contaminação.
- Resultados em funções curtas não demonstram escalabilidade para repositórios completos.

### 20.6 Limitações específicas de code smells

- Code smell não é necessariamente bug nem falha executável.
- O ESBMC não serve como oráculo natural para `long_method`, `many_parameters` ou
  `complex_conditional`.
- Diferentes desenvolvedores podem discordar sobre o mesmo smell.
- Limiares numéricos são decisões operacionais, não leis universais.
- Uma função longa pode ser coesa e aceitável; uma função curta pode ter baixa qualidade.
- Modelos podem classificar estilo pessoal como smell.
- Sem filtro posterior, todo falso positivo da LLM chega diretamente ao relatório.
- Dar exemplos rotulados no prompt pode melhorar consistência, mas também aproximar a tarefa de
  simples imitação.

## 21. Evolução proposta do pipeline

Uma evolução de mestrado pode ser organizada em etapas incrementais. Não é necessário resolver todo
o Python nem todos os tipos de defeito em uma única versão.

### Etapa 1 — dataset auditável

- separar função de detecção e harness;
- neutralizar vazamentos;
- criar manifesto com procedência, oráculo e abstração;
- corrigir os rótulos sem casamento AST;
- registrar candidatos excluídos e os motivos;
- classificar fidelidade como reprodução direta, extração ou abstração.

### Etapa 2 — AST explicável

- manter regras específicas por categoria;
- registrar por que cada candidato foi aceito ou rejeitado;
- testar expressões equivalentes, linhas deslocadas e nós de formato incorreto;
- preservar mapeamento entre linhas do código sanitizado e do código original;
- futuramente considerar análise interprocedural onde for necessária.

### Etapa 3 — votação entre modelos

- executar os modelos separadamente;
- agregar por arquivo, função, categoria e expressão;
- testar limites de concordância de 1 a N modelos;
- medir o trade-off entre precisão e recall;
- preservar evidências individuais para auditoria.

### Etapa 4 — síntese automática de harness

- solicitar entradas simbólicas e propriedade separadamente da detecção;
- impedir alterações na função original;
- auditar todos os `assume` e `asserts` gerados;
- verificar sintaxe, conversão, VCC, alcance e propriedade violada;
- comparar o harness gerado com o oráculo oculto do benchmark;
- marcar a força da evidência no relatório.

### Etapa 5 — uso em arquivo ou repositório completo

- receber uma única entrada do usuário;
- extrair funções automaticamente;
- identificar dependências e funções chamadas;
- decidir quando uma função isolada é suficiente;
- produzir harnesses temporários internamente;
- apresentar resultado por função com confirmação, hipótese ou inconclusão.

### Etapa 6 — avaliação ampliada

- aumentar bugs externos independentes;
- repetir cada modelo ao menos três vezes;
- registrar snapshot, data, temperatura, tokens, custo e latência;
- apresentar resultados por categoria e por nível de fidelidade;
- aplicar análise estatística adequada;
- comparar com baselines e outras abordagens quando houver compatibilidade.

## 22. Como melhorar a pesquisa de code smells usando somente modelos de linguagem

É possível estudar code smells somente com LLMs e SLMs, sem ESBMC e sem um detector
tradicional no fluxo avaliado. Entretanto, o ground truth deve continuar independente dos modelos
avaliados.

### 22.1 Definir exatamente cada smell

O prompt precisa usar definições operacionais reproduzíveis. Para as categorias atuais:

- `long_method`: quantidade mínima definida de linhas executáveis;
- `many_parameters`: quantidade mínima de parâmetros, excluindo `self` e `cls`;
- `complex_conditional`: quantidade mínima de operadores `and`/`or` dentro de uma condição.

Os limiares atuais estão centralizados em `research_pipeline/config/smell_thresholds.json`. Eles
devem ser apresentados como escolhas do experimento e submetidos à validação do orientador.

Somente pedir “encontre code smells” deixa a tarefa subjetiva e favorece superdetecção.

### 22.2 Exigir evidência verificável na resposta

Para cada smell, a LLM deve retornar:

```json
{
  "category": "complex_conditional",
  "function": "target_function",
  "evidence": "a and b or c and d",
  "measured_value": 3,
  "threshold": 3,
  "explanation": "A condição contém três conectores booleanos.",
  "confidence": "high"
}
```

Mesmo quando a detecção é feita somente por modelos de linguagem, pedir valor medido, limiar e trecho de evidência
reduz respostas vagas e permite auditoria posterior.

### 22.3 Usar duas chamadas com papéis diferentes

Uma evolução simples é separar proponente e crítico:

```text
Modelo A: propõe smells
          ↓
Modelo B: tenta refutar cada smell usando definição e evidência
          ↓
resultado final com concordância ou divergência
```

O segundo modelo deve receber instrução explícita para rejeitar o achado quando:

- a contagem estiver errada;
- o limiar não for atingido;
- o trecho não existir;
- a categoria não corresponder à definição;
- a justificativa for apenas uma preferência estilística.

É melhor usar modelos ou chamadas independentes do que pedir ao mesmo contexto para confirmar a
própria resposta.

### 22.4 Votação entre modelos

Executar cinco modelos e aceitar somente smells com concordância mínima pode diminuir o ruído.

Devem ser avaliados todos os limites:

- 1 de 5: maior recall, provavelmente mais falsos positivos;
- 2 de 5: compromisso inicial;
- 3 de 5: maioria;
- 4 ou 5 de 5: maior confiança, provavelmente menor recall.

O limite não deve ser escolhido somente porque produz o melhor resultado final. Ele deve ser
definido previamente ou selecionado em um conjunto de validação separado.

### 22.5 Auto-consistência

Cada modelo pode ser executado três vezes. Um smell recebe uma estabilidade interna:

```text
0/3: nunca detectado
1/3: instável
2/3: provável
3/3: estável
```

Depois, essa estabilidade pode ser combinada com a concordância entre modelos. Isso permite estudar
se os falsos positivos são achados persistentes ou respostas ocasionais.

### 22.6 Permitir abstenção

O modelo deve poder responder que não há evidência suficiente. Forçar uma categoria aumenta o
número de falsos positivos.

Exemplo de saída:

```json
{
  "decision": "abstain",
  "reason": "A função está próxima do limiar e o contexto é insuficiente."
}
```

A taxa de abstenção deve ser relatada junto com precisão e recall.

### 22.7 Separar smells objetivos e contextuais

Uma taxonomia útil é:

- **quantitativos:** `long_method`, `many_parameters`, `complex_conditional`;
- **contextuais:** baixa coesão, nome inadequado, responsabilidade múltipla, feature envy e outros.

Os três smells atuais são mais adequados para uma avaliação inicial porque permitem critérios
numéricos. Smells contextuais exigem mais contexto do repositório e maior concordância humana.

Não se deve misturar os dois grupos em uma única métrica sem explicar a diferença.

### 22.8 Construir ground truth independente

Se os mesmos modelos avaliados criarem os rótulos corretos, a avaliação será circular. Alternativas:

- dois revisores humanos aplicam o protocolo escrito;
- um revisor anota e outro revisa uma amostra;
- divergências são resolvidas por discussão ou terceiro avaliador;
- as contagens objetivas são registradas junto ao rótulo;
- casos limítrofes são marcados separadamente.

Uma ferramenta ou script pode ser usado apenas para conferir contagens durante a construção do
ground truth, mesmo que o fluxo experimental avaliado seja “somente modelos de linguagem”. Isso não transforma a
ferramenta em detector comparado; ela atua como controle da anotação.

### 22.9 Criar casos negativos difíceis

O dataset não deve conter apenas exemplos obviamente positivos. Deve incluir:

- função com uma linha abaixo do limiar;
- muitos parâmetros incluindo `self`/`cls`, que não devem entrar na contagem;
- condição longa visualmente, mas com poucos conectores;
- função longa e coesa que desafia a definição puramente numérica;
- função curta com responsabilidade múltipla;
- comentários e strings longas que não contam como linhas executáveis;
- expressões booleanas aninhadas;
- funções sem smell.

Esses casos mostram se o modelo aprendeu a regra ou apenas associa “código grande” a smell.

### 22.10 Avaliação recomendada para smells

Relatar por modelo e categoria:

- TP, FP e FN absolutos;
- precisão, recall e F1;
- quantidade total de previsões;
- taxa de abstenção;
- estabilidade em três execuções;
- concordância entre modelos;
- resultado para cada limite de votação;
- matriz de confusão por smell;
- exemplos representativos de falso positivo e falso negativo.

No caso já observado do Qwen, os 158 falsos positivos vieram de 172 previsões totais de smell:
14 verdadeiros positivos e 158 falsos positivos. A precisão foi `14 / 172 = 0,081`. Esse exemplo
mostra por que apenas recall alto não é suficiente.

### 22.11 Experimentos possíveis

Uma sequência de ablação pode comparar:

1. prompt genérico: “encontre code smells”;
2. prompt com definições e limiares;
3. prompt com saída estruturada e evidência;
4. proponente + crítico;
5. três execuções por modelo;
6. votação entre modelos;
7. votação com abstenção e confiança calibrada.

Assim, a pesquisa demonstra qual componente reduz os falsos positivos, em vez de apresentar apenas
uma infraestrutura nova.

## 23. Dúvidas sobre code smells para discutir com o orientador

75. O estudo deve continuar combinando bugs e smells ou separar os dois experimentos?
76. Os três smells quantitativos atuais são suficientes para esta etapa?
77. Os limiares adotados representam definições científicas defensáveis ou apenas regras locais do
    benchmark?
78. Devemos validar os limiares com literatura, especialistas ou ambos?
79. Uma função que ultrapassa o limiar deve ser sempre rotulada como smell ou apenas como candidata?
80. O ground truth precisa de dois revisores humanos?
81. Devemos incluir smells contextuais ou manter somente categorias mensuráveis?
82. O experimento “somente modelos de linguagem” pode usar scripts para conferir o ground truth sem usar esses scripts
    no fluxo de detecção avaliado?
83. Qual estratégia deve ser a contribuição principal: votação, proponente/crítico,
    auto-consistência ou combinação delas?
84. O limite de votação será definido antes do teste ou escolhido em conjunto de validação?
85. Devemos permitir abstenção e tratá-la separadamente de erro?
86. Três execuções por modelo são suficientes para medir estabilidade?
87. Precisão deve ser priorizada sobre recall para evitar relatórios inutilizáveis?
88. Como apresentar casos em que os revisores humanos discordam?
89. O caso Qwen com 158 falsos positivos deve motivar formalmente a etapa de crítica/votação?
90. A pesquisa deve avaliar modelos pagos versus locais também para smells?

### 23.1 Decisões prioritárias sobre smells

1. Bugs e smells serão estudos separados ou dois fluxos do mesmo estudo?
2. Quais definições e limiares serão considerados ground truth?
3. Quem realizará a anotação humana independente?
4. Qual mecanismo será implementado primeiro: crítico, repetição ou votação?
5. Qual redução de falsos positivos será considerada evidência de melhoria?

## 24. Ponto de retomada dos estudos

Esta seção registra o estado da pesquisa em 23 de agosto de 2026 para facilitar a continuação dos
estudos e a próxima conversa com o orientador.

### 24.1 O que já foi decidido

O objetivo geral do pipeline combina detecção e confirmação:

```text
código sem gabarito
        ↓
LLM ou SLM propõe função, categoria e expressão suspeita
        ↓
AST verifica se a evidência existe e é compatível com a categoria
        ↓
ESBMC tenta demonstrar a violação de uma propriedade correspondente
        ↓
confirmado, rejeitado, não confirmado ou inconclusivo
```

O V1 permanece como benchmark controlado do artigo já concluído. O V2 é uma evolução em construção;
ainda não foi definido formalmente como estudo de transferência, benchmark de síntese de harness ou
combinação de experimentos.

Os 106 arquivos atuais do V2 já funcionam como harnesses:

- todos foram executados pelo ESBMC;
- todos geraram pelo menos uma VCC;
- todos produziram `VERIFICATION FAILED`;
- existem 116 rótulos porque alguns arquivos possuem mais de uma categoria.

Isso confirma que há uma propriedade violada em cada harness. Ainda é necessário verificar se, em
cada caso, a propriedade violada corresponde exatamente à categoria e à hipótese que o modelo deve
detectar.

### 24.2 Cinco decisões necessárias para continuar

#### Decisão 1 — entrada do modelo

Definir se LLMs e SLMs receberão:

- somente uma função;
- um arquivo completo;
- um arquivo completo sem o harness experimental;
- ou um repositório completo.

Recomendação inicial: fornecer a função completa e o menor contexto necessário, preservando
`asserts` originais, mas ocultando versão corrigida, comentários reveladores e `asserts` criados
somente para o experimento.

#### Decisão 2 — origem do harness

Alternativas:

- executar somente o harness manual já existente;
- pedir ao modelo que gere um harness;
- pedir ao modelo que gere um harness e usar o manual como gabarito oculto.

Recomendação inicial: usar a terceira opção. Ela permite avaliar a automação desejada para o usuário
final sem perder um oráculo independente no benchmark.

#### Decisão 3 — significado dos resultados

Proposta de estados distintos:

- **confirmado:** o ESBMC encontrou um contraexemplo para a propriedade correta e correspondente ao
  candidato;
- **rejeitado pelo AST:** a expressão não existe ou possui forma incompatível com a categoria;
- **não confirmado dentro do limite:** o ESBMC executou, mas não encontrou a violação nas condições
  configuradas;
- **inconclusivo:** timeout, erro da ferramenta, zero VCC ou recurso não suportado;
- **propriedade hipotética violada:** o ESBMC encontrou contraexemplo para uma propriedade criada
  pelo modelo, mas sem fonte independente que demonstre que ela representa a intenção real.

Não tratar automaticamente “nenhuma violação encontrada dentro do limite” como prova de que o
candidato é falso.

#### Decisão 4 — categorias da primeira evolução

Recomendação: começar com categorias que possuem relação mais direta com a AST e com propriedades
formais:

1. `division_by_zero`;
2. `out_of_bounds`;
3. `assertion_violation`.

Deixar inicialmente para uma segunda etapa:

- `none_misuse`;
- `type_mismatch`;
- `invalid_precondition`;
- `variable_misuse`;
- `integer_overflow`.

Essa ordem é uma recomendação técnica, não uma decisão definitiva. Deve ser validada após verificar
quantos casos reais utilizáveis existem em cada categoria.

#### Decisão 5 — função do V2

Definir se o V2 será:

- um conjunto de harnesses verificáveis;
- um benchmark de detecção sem vazamento;
- um benchmark de síntese automática de harness;
- ou três conjuntos/experimentos relacionados.

Estrutura recomendada caso o V2 avalie detecção e síntese:

```text
dataset/v2/
├── detection/   # entrada neutra para LLMs e SLMs
├── harnesses/   # harness manual oculto e previamente validado
└── manifest.json
```

### 24.3 Primeiro experimento recomendado

Antes de reorganizar os 106 arquivos, executar uma prova de conceito:

1. selecionar de 10 a 15 casos;
2. começar pelas três categorias mais diretamente verificáveis;
3. criar uma entrada neutra para cada caso;
4. preservar os harnesses atuais como gabarito oculto;
5. pedir ao modelo que localize o bug;
6. validar a expressão pelo AST;
7. pedir ao modelo que gere o harness;
8. verificar que a função original não foi alterada;
9. executar o harness gerado no ESBMC;
10. comparar sua propriedade e seu resultado com o harness manual.

Pergunta experimental possível:

> Em que medida LLMs e SLMs conseguem gerar automaticamente harnesses válidos para confirmar, com
> o ESBMC-Python, candidatos a bugs em código Python proveniente de projetos de produção?

Métricas mínimas:

- candidato correto proposto;
- expressão aceita pelo AST;
- harness sintaticamente válido;
- harness aceito pelo frontend;
- pelo menos uma VCC gerada;
- contraexemplo encontrado;
- propriedade equivalente ou compatível com o oráculo manual;
- alteração indevida da função original;
- timeout e resultado inconclusivo;
- tempo e tokens por etapa.

### 24.4 O que não precisa ser decidido agora

Para manter o foco, podem aguardar:

- votação definitiva entre cinco modelos;
- expansão para todas as oito categorias;
- experimento completo de code smells;
- comparação com todos os baselines externos;
- execução em repositórios completos;
- reorganização imediata dos 106 casos;
- análise estatística final.

Primeiro deve ser decidido e testado o protocolo mínimo de entrada neutra, geração de harness e
confirmação formal.

## 25. Execução do protocolo mínimo (23 de agosto de 2026)

Esta seção registra o resultado real de executar a Alternativa A (§13.1) e o protocolo do §24.3
nos 100 casos do V2 (não só nos 10-15 recomendados — a reorganização completa acabou saindo
junto, ver §25.4). São achados empíricos, não recomendações teóricas; complementam, não substituem,
as seções anteriores.

### 25.1 Estrutura implementada

```text
dataset/v2_real_world/
├── detection/           # 100 arquivos, código real intocado (nome/comentário/classe do commit original)
├── bugs/                # 100 harnesses, já existiam, intocados
├── ground_truths.json   # metadados + categoria(s) + expressão, um arquivo só (não mais por categoria)
├── manifest_pilot.json  # liga detection_file ↔ harness_file ↔ provenance ↔ oracle ↔ abstraction
└── candidates_phase1.json  # histórico de mineração/triagem, não é dataset final
```

Diferença do §3 original: `detection/` guarda o código real **sem nenhuma edição** (nem
neutralização de nome), porque a neutralização (`buggy`→nome neutro, remoção de comentário
revelador) já é responsabilidade do `research_pipeline` no momento de montar o prompt, não do
dataset. Isso evita manter duas fontes de verdade (dataset editado + pipeline editando de novo).

### 25.2 Erros de proveniência encontrados construindo os 100 (achado principal)

Além dos "64 rótulos sem casamento AST" já diagnosticados no §8, apareceram **duas classes de erro
de coleta** que são anteriores ao problema de AST — se a proveniência está errada, nenhum
casamento de AST corrige isso:

**A) `buggy_commit` era o próprio commit do fix.** Aconteceu em pelo menos 8 dos 100 itens
(principalmente nos minerados fora do BugsInPy, direto do GitHub). A mensagem do commit já dizia
"Fix ..."/"Fixes #N" — sintoma fácil de checar automaticamente: `git log --oneline -1
<buggy_commit>` e comparar a mensagem contra um regex de padrão de fix antes de aceitar o commit
como "código com bug". Correção usada: commit pai do que estava gravado.

**B) `source_function` não existia com esse nome no commit real.** Aconteceu em pelo menos 6 itens
— nome de função foi inferido errado durante a mineração (às vezes por analogia com o nome do
patch, não pelo código de verdade). Dois casos chegaram a extrair a **função errada por completo**
(`tqdm.__init__` em vez de `tqdm.format_meter`; `_Projection.multi_get` em vez de
`_Projection.get_index`) — a função extraída nem continha a linha do bug. Isso só foi pego
comparando o comentário do harness (`# Real code (arquivo:linha): ...`) contra o texto do arquivo
extraído; casamento de nome de função sozinho não detecta.

**C) Duplicata do mesmo bug real sob dois IDs diferentes.** 9 casos no total (não só o par do
piloto original) — mesmo commit, mesmo arquivo, mesma função, minerados em passadas diferentes sem
checar sobreposição. Dataset foi de 105 para **100 itens únicos** depois de deduplicar.

**Recomendação para o checklist do §7 ("Procedência")**, com base no que realmente pegou os erros
acima:

- [ ] `git log --oneline -1 <buggy_commit>` não descreve uma correção (senão, usar o pai).
- [ ] A expressão citada no comentário do harness aparece literalmente no arquivo de `detection/`
      extraído (não só o nome da função bater).
- [ ] `(projeto, arquivo, função)` não repete outro ID já aceito no dataset.

### 25.3 Tamanho real dos arquivos-fonte

Function-level, não file-level, foi a única opção viável na prática: arquivos reais chegaram a
4751 linhas (`pandas/core/series.py`), 3824 (`youtube_dl/utils.py`), 3337 (`black.py`). A
recomendação do §14 ("Decisão 1: fornecer a função completa e o menor contexto necessário") se
confirma como a única escolha viável, não só preferível — arquivo inteiro nesses casos não caberia
em prompt nenhum de forma razoável.

### 25.4 Pipeline de detecção mínimo, sem tocar no `research_pipeline` existente

Implementado em `scripts/v2_pilot_detect.py`, reusando (sem modificar) `preprocess.py`,
`llm/backends`, `llm/prompts`, `ast_utils.expression_exists_in_executable_ast`. Diferença do Flow B
do V1: o ESBMC **não roda por LLM** — já rodou uma vez na construção do harness (fato fixo,
gravado no manifesto), então o script só compara a proposta do modelo contra o gabarito, não
verifica de novo a cada chamada. Mais simples que Flow B, porque não sintetiza nada.

Teste inicial rodando com 1 modelo local (qwen2.5-coder:7b, grátis): **0 de 72 detectados**
(protótipo isolado, `scripts/v2_pilot_detect.py`, já removido). 100% miss — mas é modelo pequeno
(7B) local, não prova nada sobre o dataset/método em si, só sobre a capacidade desse modelo
específico. Falta testar com modelo maior antes de tirar qualquer conclusão sobre a Alternativa A.

**Atualização**: o protótipo separado foi descartado por decisão da Fernanda ("evolua o flow em vez
de colocar um script"). A lógica foi incorporada direto no `hybrid` (Flow B) existente em
`research_pipeline/pipeline.py`: `run_pipeline_multi()` ganhou um parâmetro opcional `harness_for`
(mapa `{detection_file: harness_file}`). Quando presente, um finding verificável roda o ESBMC no
harness oculto (`run_esbmc_direct`, arquivo inteiro, sem `--function`) em vez de rodar `--function`
no mesmo arquivo que a LLM leu — preserva a separação detecção/oráculo sem duplicar máquina de
avaliação nova. Uso: `python src/main.py --mode hybrid --input dataset/v2_real_world/detection
--v2-manifest dataset/v2_real_world/manifest_pilot.json --model <modelo>`. Sem a flag, `hybrid` se
comporta exatamente como antes (V1, arquivo único) — mudança aditiva, não quebra nada existente.

Auditoria de 105 itens confirmou 102 genuinamente corretos (violação bate com a categoria
declarada), 9 só precisando de `--unwind`/`--timeout` maior (anotado, não é erro), e 3 com falsa
confirmação por bound insuficiente (`av_real_06`, `av_real_14`, `vm_real_01`) — **consertados**:
trocar `--unwind N --timeout Ns` por `--incremental-bmc` faz os três baterem na propriedade real
(k=20/21/2). `esbmc_runner.py` já usa `--incremental-bmc` por padrão em toda função de verificação
— o problema só existiu porque o teste manual durante a mineração usava `--unwind` direto via bash,
fora do pipeline. **Dataset fecha 105/105 genuinamente confirmados.**
