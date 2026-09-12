# Dúvidas e dificuldades para discussão com o orientador

Data: 11 de setembro de 2026
Tema: limites da taxonomia de categorias e da natureza do oráculo formal no dataset de bugs reais

## Contexto

O método combina três etapas: uma LLM propõe, a partir do código real e bugado,
qual é a categoria do defeito; um verificador formal confirma se essa categoria
corresponde a uma propriedade de fato violável; e o resultado é comparado contra
um gabarito derivado do commit de correção real do projeto. A primeira etapa só
tem valor se a categoria puder ser inferida olhando exclusivamente o código
bugado, sem acesso ao commit de correção. Ao revisar o dataset em profundidade,
identifiquei dois pontos que não têm uma solução óbvia dentro da taxonomia
atual e que valem uma conversa.

## Primeira dificuldade: nem todo defeito real cabe nas categorias existentes

A taxonomia atual cobre oito tipos de defeito, todos ligados a uma propriedade
que o verificador formal consegue checar diretamente: divisão por zero, acesso
fora dos limites, violação de asserção, uso indevido de valor nulo,
incompatibilidade de tipo, precondição inválida, uso da variável errada e
estouro de inteiro.

Durante a auditoria, encontrei casos reais de bug cujo defeito não é nenhuma
dessas oito coisas: é um valor numérico constante gravado errado no código
(por exemplo, uma aproximação de uma constante matemática com dígitos
incorretos), ou uma inconsistência interna entre a documentação da própria
função e a condição que ela implementa. Nesses casos, o defeito é
perfeitamente identificável só de olhar o código, sem qualquer necessidade do
commit de correção. Só que a violação formal que o verificador acaba
confirmando é sempre um "assert falhou", porque tecnicamente é assim que o
oráculo é construído (comparando o valor produzido contra o valor esperado).
Rotular esse caso como "violação de asserção" seria enganoso: o código real
não tem nenhuma asserção, e uma LLM competente que respondesse "constante
numérica incorreta" estaria certa, mas seria marcada como errada pelo
critério de avaliação atual.

A solução provisória adotada foi excluir esses poucos casos do conjunto usado
para avaliar a precisão da primeira etapa (a LLM), mantendo-os no restante do
pipeline (mineração, construção do harness, confirmação formal). Isso evita
distorcer a métrica, mas não resolve o problema de fundo: a taxonomia de oito
categorias não é exaustiva para todo bug real que o verificador consegue
formalizar. Vale decidir com o orientador se isso é aceitável como limitação
declarada do método, ou se é o caso de propor uma nona categoria (algo como
"erro de constante" ou "erro de lógica sem exceção associada"), o que por sua
vez exigiria minerar mais exemplos reais desse tipo para a categoria não ficar
com um ou dois casos apenas.

## Segunda dificuldade: o oráculo do harness nem sempre reproduz o mesmo tipo de falha do código real

Uma parte considerável dos casos do dataset não pode ser reduzida a uma
exceção nativa (divisão por zero, índice inválido, etc.) porque o defeito real
é uma diferença silenciosa de resultado: a versão bugada calcula um valor, a
versão corrigida calcula outro, e nenhuma das duas levanta exceção. Para esses
casos, o harness formal precisa reconstruir as duas versões (a bugada e a
corrigida) e comparar os resultados através de uma asserção escrita
propositalmente para o experimento, não uma asserção que exista no código
original do projeto.

Isso é metodologicamente correto, mas levanta uma questão que ainda não tenho
resposta fechada: quando o verificador formal confirma a violação dessa
asserção sintética, o que exatamente está sendo confirmado? A resposta mais
honesta é que se confirma que as duas versões produzem valores diferentes sob
as mesmas entradas, e que essa diferença reproduz o mecanismo causal do bug
real (verificado manualmente contra o commit de correção, caso a caso). Não se
confirma que o código original "quebra" da mesma forma que o harness "quebra".
Isso é uma diferença sutil entre provar uma discrepância de resultado e provar
uma falha de execução, e afeta como a categoria desses casos deveria ser
comunicada tanto para a LLM quanto no relatório final da dissertação. Vale
alinhar com o orientador qual é o vocabulário certo para essa distinção antes
da qualificação, para não dar a entender que todo item do dataset representa
um crash real quando parte deles representa uma divergência de valor
comprovada por comparação direta.

## Encaminhamento sugerido

Ambos os pontos não bloqueiam o andamento do pipeline: o dataset está íntegro,
os casos problemáticos estão isolados e documentados, e a métrica de avaliação
já reflete essa separação. O que falta é uma decisão de enquadramento teórico,
que impacta diretamente como o capítulo de metodologia da dissertação descreve
a taxonomia e o papel do oráculo formal.
