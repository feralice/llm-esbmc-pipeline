# Tabela de roteamento de prompts (v1, rascunho para revisão)

Status: proposta, não implementada. Nenhuma rodada usa esta tabela ainda.

## Por que existe

Hoje todo caso recebe o mesmo conjunto de variantes, e as variantes estão espalhadas em código e em arquivos `.txt`.
Esta tabela escolhe **um conjunto** por função, com base em características do código lidas por AST, antes da
detecção. A escolha é determinística e fica registrada no relatório.

## Como a escolha funciona

1. Para cada função, o AST é lido e cada característica abaixo é verificada.
2. A função recebe o conjunto da **primeira** linha da tabela que bate, na ordem da tabela (prioridade fixa).
3. Se nenhuma linha bate, vale o **padrão**: o conjunto atual das rodadas congeladas (`A1`, `A2`).
4. O nome da tabela (`routing_v1`) e o conjunto escolhido vão para o relatório e para a chave do cache.

Cuidados:
- A escolha **não** usa o resultado de nenhum conjunto de teste. A tabela é fixa antes de qualquer rodada.
- Não há escolha pelo LLM.
- Smells têm trilha própria e não entram nesta tabela.

## Tabela

| Ordem | Característica no AST | Categorias típicas | Conjunto de variantes | O que a variante pede |
|---|---|---|---|---|
| 1 | Divisão ou módulo (`/`, `//`, `%`), potência ou deslocamento com operando vindo de parâmetro | `division_by_zero`, `integer_overflow` | `A2`, `A16` | Partição de entradas e checagem de consistência interna |
| 2 | Subscrito `x[i]`, `len(...)`, `next(...)`, ou atributo de parâmetro que pode ser `None` | `out_of_bounds`, `none_misuse` | `A2`, `A12` | Partição de entradas e chamadores no repositório |
| 3 | `assert`, `raise`, ou variável reatribuída antes de uso | `assertion_violation`, `invalid_precondition`, `variable_misuse` | `A2`, `A20` | Partição de entradas e fatias de chamadores |
| - | Nenhuma das anteriores (padrão) | qualquer | `A1`, `A2` | Igual às rodadas congeladas |

## Justificativa de cada conjunto (a revisar)

- **`A2` em todos:** é o checklist de partição de entradas, já usado nas rodadas. Mantém um ponto comum.
- **`A16` (consistência interna):** pede que o LLM confira se o trecho é coerente consigo mesmo. Faz sentido onde há conta.
- **`A12` (chamadores no repositório):** mostra como a função é chamada. Útil quando a entrada vem de fora e pode ser `None`.
- **`A20` (fatias de chamadores):** mostra só os valores que chegam à função. Útil quando a condição depende de um `assert` ou de um estado anterior.

## Pontos para você decidir

1. A ordem de prioridade (quem ganha quando uma função tem duas características).
2. Se é melhor **unir** os conjuntos em vez de escolher o primeiro. A união deixa o prompt maior e mais caro.
3. Se `A21` (exceções dos chamadores) entra em alguma linha, depois que estiver funcionando.
4. Se o padrão deve continuar sendo `A1`,`A2`, para manter as rodadas congeladas comparáveis.

## O que ainda não sabemos

- Se estes conjuntos melhoram a detecção ou só mudam o custo. **Nada foi medido.** A tabela é uma hipótese a testar.
- Como a tabela interage com o cache. Ela precisa entrar na chave, senão uma rodada reaproveita resposta de outro conjunto.

## Próximo passo, se aprovado

1. Implementar a tabela num módulo próprio, com teste para cada linha e para o padrão.
2. Registrar `routing_v1` e o conjunto escolhido no relatório e na chave do cache.
3. Rodar primeiro num conjunto de desenvolvimento, comparando com o padrão, antes de qualquer rodada oficial.
