# Apresentação 30/09/2026: versão final

Base: `slide.pdf` na raiz do repositório. Abaixo está o texto de **todos os 19 slides**: os slides 1
a 14 são os do PDF, já com os ajustes pequenos aplicados (marcados em "Ajuste"); os slides 15 a 19 são
novos e substituem os antigos 15 a 18. Os slides 15 a 18 usam **uma base só**, as 125 hipóteses da
rodada de 30/09, feita depois da revisão do harness.

"Fala" e "Ajuste" são só para você e não vão para o slide. Números conferidos em 30/09 contra
`artifacts/v2/exp-oracle-repair-cobertura/` (rodada de 30/09) e `artifacts/v2/exp-oracle-fixed-cobertura/`
(controle nas versões corrigidas).

---

## Slide 1

**Título:** Detecção de bugs em Python real com LLM e confirmação formal com ESBMC

**Subtítulo:** Evolução do pipeline de 09/09 a 30/09/2026

**Rodapé:** Fernanda · PPGINF · orientação: Lucas Cordeiro · 30/09/2026

**Ajuste:** "PPGI" virou "PPGINF"; entraram orientador e data.

---

## Slide 2

**Título:** A LLM fazia quase tudo: achava o bug, escolhia a categoria e escrevia o harness

- A LLM analisa uma função e aponta uma categoria de bug
- O programa confere se o trecho indicado existe no código
- A LLM gera um harness para testar a hipótese
- O ESBMC verifica o harness formalmente

**As 8 categorias**
- assertion_violation
- division_by_zero
- out_of_bounds
- none_misuse
- type_mismatch
- invalid_precondition
- variable_misuse
- integer_overflow

---

## Slide 3

**Título:** Problema 1: a LLM achava a função certa, mas errava a expressão e a categoria

104 bugs reais, gpt-4o-mini:

| A LLM acertou | |
|---|---|
| a função com bug | 97% |
| a categoria | 49% |
| a expressão exata do bug | 20% |

- Categoria: um mesmo bug cabe em mais de uma das 8 (um None que causa acesso fora dos limites é
  "uso de None" ou "fora dos limites"?).
- A LLM achava o lugar certo e era contada como erro.
- Expressão: com texto idêntico ao gabarito, só 20%. Espaço diferente ou um if em volta contavam
  como erro.

**Fala:** esta tabela é da rodada de 29/09; o slide 5 é da rodada de 27/09. Por isso a função aparece
com 97% aqui e 87% lá (ver R4).

---

## Slide 4

**Título:** Problema 2: o harness escrito pela LLM "confirmava" bugs que não existem

**Exemplo real (projeto black):**

```python
while self.previous_defs and self.previous_defs[-1] >= depth:
    self.previous_defs.pop()
```

**Harness**

```python
previous_defs: int = nondet_int()   # a lista virou um número qualquer
popped_value: int = previous_defs   # "simula" o pop(); o while sumiu
assert previous_defs >= 0           # propriedade inventada pela LLM
```

- LLM: "pop() pode falhar com a lista vazia". Falso: o while impede.
- Harness da LLM: trocou a lista por um número, apagou o while e inventou um assert.
- ESBMC: achou erro nesse assert, e o caso contou como "confirmado". Mas o erro só existia no harness.

---

## Slide 5

**Título:** Rodada de 27/09 (pipeline antigo): 47 bugs "confirmados", só 2 eram reais

- Rodada de 27/09 (gpt-4o-mini, 135 suspeitas de bug):
  - Função: acertou 118 de 135 (87%) ✓
  - Categoria: certa em só 34 das 118 (29%), e era ela que escolhia o harness
  - Expressão: igual à do bug real em só 20 das 118 (17%)
  - Harness: errado em 68 de 135 (50%): 33 não rodavam, 25 não testavam o código real, 10
    escondiam o bug

**Resultado: 47 "confirmados", só 2 eram o bug real.**

**Ajuste:** o título repetia o do slide 4; entrou a linha "Resultado".

---

## Slide 6

**Título:** De 09/09 a 30/09

| Data | O que foi feito |
|---|---|
| 09/09 | 106 bugs, harness escrito à mão; na busca automática, a LLM escrevia o harness |
| 10 a 22/09 | dataset auditado e ampliado para 116 bugs reais de 42 projetos |
| 27/09 | diagnóstico dos slides 3 a 5 (os problemas achados) |
| 29/09 | pipeline novo: a LLM não escreve mais código; confirmação exige execução real |
| 30/09 (finalizando) | experimentos repetidos 3 vezes, controle de falso positivo, harness revisado |

**Ajuste:** "slides 3 e 4" virou "slides 3 a 5"; saíram os espaços dentro dos parênteses.

---

## Slide 7

**Título:** No pipeline novo, a LLM só aponta o bug e informa tipos; o resto é automático

**No slide:** a figura do pipeline.

**Fala:** a LLM aparece em dois passos e nunca escreve código. O bug só vale se o ESBMC e a execução
real do Python concordarem.

---

## Slide 8

**Título:** Os dois passos que preparam o harness: recorte (automático) e tipos (LLM)

Um arquivo real tem centenas de linhas e importa bibliotecas que o ESBMC não conhece. O recorte:
- copia só a função e o que ela usa, sem mudar nenhuma linha;
- apaga o que ela não usa (num caso real, 22 métodos da classe);
- troca cada biblioteca desconhecida por um substituto (ex.: o código chama numpy.diff(x); o ESBMC
  não conhece o numpy, então o substituto é uma função que devolve "qualquer lista de números", e o
  ESBMC testa todas).

**Tipos em JSON, pela LLM.** O ESBMC precisa saber o tipo de cada entrada para testar todos os
valores. A LLM responde só isto:

```json
{"params": {"value": "bool"}}
```

Ela não escreve código. Se o código já tem tipagem, vale a do código; a LLM só completa o que falta.
Se o tipo não combina com o que o código faz com a entrada (ex.: dividir por um texto), o ESBMC
recusa, e a LLM corrige.

---

## Slide 9

**Título:** O harness é montado pelo programa: substitutos + código real + chamada

```python
# SUBSTITUTO (do recorte): tornado é uma biblioteca de servidor web que o ESBMC não conhece
class tornado_web_RequestHandler:
    pass

# CÓDIGO REAL (do recorte): sem nenhuma alteração, mesma numeração de linhas
class WebSocketHandler(tornado_web_RequestHandler):
    stream = None
    def set_nodelay(self, value: bool) -> None:
        assert self.stream is not None      # linha 127: o bug
        self.stream.set_nodelay(value)

# CHAMADA (do JSON da LLM): "value é bool"
def _esbmc_main() -> None:
    value: bool = nondet_bool()             # qualquer bool: o ESBMC testa todos
    WebSocketHandler().set_nodelay(value)
```

Resultado: o ESBMC acha stream = None; o Python real dá AssertionError na linha 127: confirmado, sem
alterar a função.

**Ajuste:** a frase do resultado estava quebrada em dois parágrafos.

---

## Slide 10

**Título:** O recorte segue regras gerais para o que o ESBMC não aceita, e não ajustes por caso

| O código real tem | O ESBMC-Python 8.5 | O recorte faz |
|---|---|---|
| import tornado, import numpy... | não conhece a biblioteca | substituto automático |
| url = property(...) | não aceita property | url vira uma entrada qualquer |
| \_\_repr\_\_ = \_\_str\_\_ | não aceita apelido de método | troca por um def equivalente |
| sys.exit() | não carrega o módulo sys | modelo fixo: o programa termina ali |

**Ajuste:** saiu a última linha ("linha solta no arquivo..."), porque a coluna do meio dela não era
do ESBMC.

---

## Slide 11

**Título:** Por que executar no Python real

- Alguns erros pegos no ESBMC-Python 8.5:
  - Falso positivo: acusa IndexError (acesso em lista vazia) no laço while defs and defs[-1] >= d,
    que nunca falha
  - Falso negativo: não detecta o TypeError de None + 1, que falha no Python
- Critério: o ESBMC sugere os candidatos e o Python real confirma. Um bug só vale quando os dois
  apontam o mesmo erro na mesma linha.

**Ajuste:** saiu o 3º bullet, que repetia o 2º.

---

## Slide 12

**Título:** A categoria deixou de decidir o harness e a confirmação

Por quê: o mesmo bug cabe em mais de uma categoria.

```python
def primeiro_nome(usuario):
    return usuario.nome.split()[0]
```

- Se usuario for None, o erro é "uso indevido de None".
- Se o nome for vazio, o erro é "fora dos limites" (IndexError).
- A LLM que escolhia a "outra" categoria era contada como erro, mesmo apontando o lugar certo.

| | Antes (até 27/09) | Agora |
|---|---|---|
| O que a categoria fazia | escolhia como o harness era escrito | nada: é só uma informação extra |
| Como o bug é confirmado | a categoria tinha que "combinar" | pela falha real (ex.: IndexError) na linha apontada |
| Como se mede o acerto da LLM | categoria certa: 29% | função certa: 97% · expressão: 40% |

**Ajuste:** saiu o texto solto "Dificuldade para categorizar os bugs".

---

## Slide 13

**Título:** Dataset

- 104 avaliados: os outros 12 exigem conhecer a aplicação
- Versão corrigida: sem bug, então 0 confirmações
- 199 bugs novos, guardados pra ampliar o dataset
- Fonte: https://github.com/soarsmu/bugsinpy

---

## Slide 14

**Título:** A LLM acha a função com bug em 97% dos casos; a expressão, em 40%

| A LLM acertou (104 bugs, gpt-4o-mini) | |
|---|---|
| o arquivo | 98% |
| a função | 97% |
| a expressão (forma equivalente) | 40% |
| a expressão (texto idêntico) | 20% |

- Contar formas equivalentes (mesmo código com outro espaçamento, ou dentro de um if) dobra o
  acerto; o ponto fraco que resta é a linha exata dentro da função certa.

**Ajuste:** o bullet estava quebrado em dois.

---

## Slide 15 · novo

**Título:** Depois da revisão do harness, só 12 de 125 casos recebem resposta do ESBMC

Rodada de 30/09: a localização do bug é dada, para medir só a verificação. A LLM só informa os tipos.

```
125 casos
 ├─ 65 param antes de chegar ao ESBMC
 │    ├─ 56 o harness não consegue montar o programa      → slide 16
 │    ├─  7 a LLM não dá tipos válidos
 │    └─  2 falha de rede
 └─ 60 chegam ao ESBMC
      ├─ 39 o ESBMC recusa o programa                     → slide 17
      ├─  9 o ESBMC não termina (tempo ou inconclusivo)   → slide 18
      └─ 12 o ESBMC dá uma resposta                       → slide 18
           ├─ 3 confirmados (youtube-dl, thefuck, tornado)
           └─ 9 não confirmados
```

Mesmo com o bug já localizado, só 12 de 125 chegam a uma resposta.

**Fala:** nas versões já corrigidas, onde não há bug, o pipeline confirmou 0. O que trava não é a
LLM: é fazer o código Python real ser aceito pelo verificador.

---

## Slide 16 · novo

**Título:** Dificuldade 1: em 56 dos 125 casos, o harness não consegue montar o programa

| O que falha | Exemplo | Casos |
|---|---|---|
| O recorte esquece um nome que a função usa | `gamma` usa `exp` e `sqrt`, que não vieram junto | 25 |
| A biblioteca não tem substituto, ou ele sai errado | chamada com `*args`; `traceback.format_exception` | 15 |
| A entrada tem um tipo que o harness não sabe gerar | listas de tuplas, objetos de biblioteca | 9 |
| Outras situações | funções `async`, atributos herdados | 7 |
| **Total** | | **56** |

Código real de projetos grandes (scrapy, tornado, pandas) usa muitas bibliotecas e recursos
dinâmicos, e cada um exige uma regra nova no harness.

---

## Slide 17 · novo (substitui o antigo 17)

**Título:** Dificuldade 2: em 39 dos 125 casos, o ESBMC recebe o programa e recusa

O ESBMC precisa saber o tipo exato de cada valor antes de rodar; o Python real decide muita coisa só
na execução.

| O ESBMC-Python 8.5 recusa | Exemplo real | Casos |
|---|---|---|
| Texto montado com variável | `'%s %s' % (status, msg)` (scrapy) | 5 |
| Atributo resolvido na execução | `type(x).__name__`, `x.__dict__` | 5 |
| Tipo que ele não deduz | atributo de classe sem anotação | 7 |
| Desempacotar resultado | `a, b = f()` (black) | 4 |
| Argumentos variáveis | `zip(*tokens)`, `f(*args, **kwargs)` | 3 |
| Biblioteca padrão sem modelo | `threading.RLock()`, `OrderedDict` | 4 |
| Outros | `NotImplemented`, erro interno do ESBMC | 11 |
| **Total** | | **39** |

O harness não pode reescrever essas linhas: se reescrever, deixa de verificar o código real.

**Fala:** a classificação foi feita pela mensagem de erro e pela linha de cada caso. O do `%` foi
reproduzido isolado; os outros ainda precisam de um exemplo mínimo antes de virar issue.

---

## Slide 18 · novo

**Título:** Dificuldade 3: dos 21 casos que o ESBMC processa até o fim, ele não termina em 9 e pode errar nos outros

| Dos 21 casos | Casos |
|---|---|
| Não termina: passa de 180 s ou dá resultado inconclusivo | 9 |
| O ESBMC aponta erro e o Python real **não** reproduz | 2 |
| Falha em outra linha | 1 |
| Nenhum dos dois acha falha | 6 |
| **Confirmados: ESBMC e Python real falham na mesma linha** | **3** |

O ESBMC-Python também erra em exemplos simples:
- **Falso positivo:** `while defs and defs[-1] >= d: defs.pop()` nunca falha, e ele acusa
  `IndexError`.
- **Falso negativo:** `v = None; v + 1` falha com `TypeError`, e ele não detecta.

Por isso todo bug precisa também falhar no Python real, na mesma linha.

**Fala:** trocar o solver Bitwuzla por Boolector resolveu 2 de 7 casos de tempo.

---

## Slide 19 · novo (substitui o antigo 18)

**Título:** Dúvidas e próximos passos

**DÚVIDAS**
1. Fazer código Python real rodar no ESBMC está sendo o principal obstáculo. Por onde seguir?
   a. Mudar a pergunta: medir até onde a verificação formal de Python alcança bugs reais, e onde para
   b. Reescritas que não mudam o comportamento, só na cópia do ESBMC (ex.: `%` vira concatenação)
   c. Contribuir com o frontend Python do ESBMC nessas construções
2. Posso abrir issues no ESBMC-Python com os reprodutores (falso positivo, falso negativo, `sys`,
   `SystemExit`, teste pytest gerado inválido)?
3. A métrica principal da detecção: expressão equivalente (40%) ou idêntica (20%)?
4. Os 199 candidatos entram no dataset? Há tamanho mínimo para a qualificação?
5. Code smells: montei um dataset separado (379 trechos rotulados por humanos). Ainda devo focar
   neles?

**PRÓXIMOS PASSOS**
- Corrigir no harness os nomes que o recorte esquece (25 casos)
- Transformar cada bug confirmado num teste pytest com o gerador do ESBMC
  (`--generate-pytest-testcase`)
- Rodar a busca completa (a LLM procurando sozinha) com o harness revisado
- Testar o pipeline num repositório Python completo, fora do dataset
- Disciplina PGENE601: aplicar o pipeline a Python de sistemas ciber-físicos

---

## Conferência dos números (slides 15 a 18)

- 56 + 7 + 2 + 39 + 9 + 12 = **125**
- Slide 16: 25 + 15 + 9 + 7 = 56
- Slide 17: 5 + 5 + 7 + 4 + 3 + 4 + 11 = 39
- Slide 18: 21 = 9 + 12; e 12 = 3 + 6 + 2 + 1

---

# Reserva (só se perguntarem)

**R1: Agente com o plugin ESBMC** (rodada de 29/09, antes da revisão do harness)

Nos 49 casos em que o pipeline parava, um agente (Claude Code + plugin ESBMC) tentou montar a
verificação de forma interativa: 4 confirmados sem alterar a função (black, tornado, scrapy); 17
recusados pelo ESBMC, pelos mesmos motivos do slide 17; em 9 o ESBMC aponta erro e o Python real
não reproduz; em 6 o agente não terminou.

**R2: Pipeline antigo × pipeline novo** (mesmo cenário: gpt-4o-mini procurando sozinha)

| | 27/09: a LLM escreve o harness | 29/09: o programa monta o harness |
|---|---|---|
| Suspeitas levantadas | 135 | 138 |
| "Confirmados" | 47 | 1 |
| Que eram o bug real | 2 | 1 (tornado) |
| Confirmações falsas | 45 | 0 |

Das 138 suspeitas de 29/09, só 6 foram julgadas pelo ESBMC; as outras 132 pararam antes. Ainda não há
essa rodada com o harness revisado.

**R3: Medição sem LLM, antes e depois da revisão do harness** (outra base: 99 bugs e 176 candidatos)

| | Antes | Depois |
|---|---|---|
| Dataset (99 bugs): o ESBMC recebe o programa | 77 | 84 |
| … e dá veredito | 15 | 15 |
| BugsInPy, não usados para criar as regras (176): o ESBMC recebe | 111 | 122 |
| … e dá veredito | 18 | 20 |

O harness passou mais código ao ESBMC, mas quase tudo foi recusado em seguida.

**R4: Por que a função aparece com 87% (slide 5) e 97% (slides 3 e 14)?**

O slide 5 conta por suspeita (118 de 135, rodada de 27/09); o 97% conta por bug (101 de 104, rodada
de 29/09).

**R5: Dataset de code smells** (separado do dataset de bugs; nada dele vai para o ESBMC)

| Fonte | Smells | Quem rotulou | Trechos confirmados |
|---|---|---|---|
| PySmell (9 projetos Python reais) | 10 smells gerais de Python | inspeção manual dos autores | 60 |
| SpecDetect4AI: mlflow | 22 smells específicos de ML | 3 anotadores, consenso nas divergências | 178 |
| SpecDetect4AI: CodeSmile | 22 smells específicos de ML | mesmos anotadores, com revisão final | 141 |
| Smelly Code Dataset | 21 smells no estilo de Fowler | o autor, em código feito para ter smells | 7 arquivos |

379 arquivos, 24 smells, cada um com o trecho, o smell, quem validou e o link para a linha original.
