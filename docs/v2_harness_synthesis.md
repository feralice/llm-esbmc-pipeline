# Proposta V2 - LLM-Guided Harness Synthesis

> Nota de desenho para uma evolucao futura do projeto. Este documento nao
> descreve o pipeline V1 atual.

## 1. Motivacao

O pipeline V1 avalia uma configuracao controlada:

```text
funcao Python simples e compativel
  -> LLM propoe hipotese local de bug
  -> filtro AST valida se a expressao existe
  -> ESBMC roda no arquivo original com --function e parametros nondet
  -> benchmark compara com ground truth
```

Essa abordagem e adequada para o benchmark atual, mas nao resolve o problema
de codigo Python complexo do mundo real. Projetos reais frequentemente usam
I/O, bibliotecas externas, objetos dinamicos, frameworks, banco de dados,
rede, decorators, async/await e outros recursos que o frontend Python do ESBMC
nao suporta de forma ampla.

A V2 investigaria a LLM como ponte entre codigo Python complexo e um modelo
verificavel pelo ESBMC.

## 2. Ideia central

Na V2, a LLM nao apenas apontaria uma hipotese de bug. Ela tambem tentaria
produzir uma abstracao verificavel:

```text
codigo Python complexo
  -> LLM identifica trecho suspeito
  -> LLM extrai uma fatia verificavel
  -> LLM substitui dependencias por stubs/nondet/assume
  -> LLM gera harness compativel com ESBMC
  -> ESBMC confirma ou rejeita a hipotese
```

Em outras palavras, a contribuicao potencial seria transformar uma hipotese
informal sobre codigo real em um programa pequeno, autocontido e verificavel.

## 3. Diferenca para a V1

| Aspecto | V1 atual | V2 proposta |
|---|---|---|
| Entrada | Funcao simples e compativel | Codigo Python mais complexo |
| Papel da LLM | Propor hipotese local | Propor hipotese + abstracao/harness |
| Codigo verificado | Arquivo original | Modelo/harness sintetizado |
| Dependencias externas | Fora do escopo | Substituidas por stubs ou nondet |
| ESBMC | `--function` no original | Verificacao do harness gerado |
| Risco principal | Hipotese falsa da LLM | Abstracao incorreta ou incompleta |

A V1 nao faz harness synthesis, model extraction ou stubbing. A V2 teria esses
elementos como objeto de pesquisa.

## 4. Exemplo conceitual

Codigo original:

```python
def process_payment(user, cart, coupon, gateway):
    total = cart.total()

    if coupon:
        total = total - coupon.discount

    if total <= 0:
        return False

    response = gateway.charge(user.card, total)
    return response.ok
```

Esse codigo e ruim para verificar diretamente porque depende de objetos e
servicos externos. Uma abstracao verificavel poderia ser:

```python
from nondet import nondet_bool, nondet_int
from esbmc import assume

def process_payment_model(cart_total: int, has_coupon: bool, discount: int) -> bool:
    total: int = cart_total

    if has_coupon:
        total = total - discount

    if total <= 0:
        return False

    return True

cart_total: int = nondet_int()
discount: int = nondet_int()
has_coupon: bool = nondet_bool()

assume(cart_total >= 0)
assume(discount >= 0)
assume(discount <= cart_total)

result: bool = process_payment_model(cart_total, has_coupon, discount)

if has_coupon:
    assert result == (cart_total - discount > 0)
else:
    assert result == (cart_total > 0)
```

O ESBMC verificaria o modelo, nao o sistema original completo.

## 5. Limite pratico do ESBMC-Python

A V2 precisa partir de uma premissa metodologica explicita: o ESBMC-Python nao
e um interpretador/verificador completo para qualquer programa Python. Ele e
mais adequado para programas pequenos, autocontidos e com comportamento
simbolicamente modelavel.

Portanto, a V2 nao deve prometer:

```text
verificar projetos Python complexos de ponta a ponta
```

O objetivo realista seria:

```text
extrair de codigo complexo um modelo pequeno o suficiente para o ESBMC verificar
```

### 5.1 O que tende a funcionar

Casos com maior chance de serem verificaveis:

- Funcoes puras ou quase puras.
- Codigo com tipos primitivos: `int`, `float`, `bool`, `str`.
- Propriedades locais expressas com `assert`.
- Operacoes aritmeticas, comparacoes e condicionais.
- Loops com bound pequeno via `--unwind`.
- Listas, tuplas, dicionarios e strings quando usam operacoes modeladas.
- Classes simples com atributos e metodos sem dinamismo pesado.
- Funcoes em que parametros podem ser substituidos por valores nondet.
- Bugs como divisao por zero, out-of-bounds, assertion violation, overflow e
  type mismatch simples.

Exemplo de alvo bom:

```python
def normalize_score(score: int, maximum: int) -> int:
    return (score * 100) // maximum
```

Hipotese verificavel:

```text
maximum pode ser zero.
```

Harness possivel:

```python
from nondet import nondet_int

def normalize_score(score: int, maximum: int) -> int:
    return (score * 100) // maximum

score: int = nondet_int()
maximum: int = nondet_int()

normalize_score(score, maximum)
```

### 5.2 O que deve ser abstraido

Em codigo real, muitos elementos devem virar stubs, nondet ou assumptions:

| Elemento no codigo real | Abstracao possivel |
|---|---|
| Entrada de usuario | `nondet_int`, `nondet_bool`, `nondet_*` |
| Arquivo / JSON / CSV | Valores simbolicos com `assume` |
| Banco de dados | Stub que retorna valor nondet dentro de um intervalo |
| API HTTP | Stub com status/value nondet |
| Objeto complexo | Campos primitivos relevantes |
| Biblioteca externa | Modelo pequeno da funcao usada |
| Configuracao global | Constantes ou parametros simbolicos |

Exemplo:

```python
def get_balance_from_db(user_id: int) -> int:
    balance: int = nondet_int()
    assume(balance >= 0)
    return balance
```

Esse stub nao prova nada sobre o banco real. Ele apenas permite verificar a
logica que consome o saldo.

### 5.3 O que deve ficar fora do escopo inicial

Para uma V2 viavel, estes casos devem ser tratados como fora de escopo ou como
`unsupported_harness`:

- Frameworks web completos: Django, Flask, FastAPI em execucao real.
- I/O real: arquivos, rede, sockets, subprocessos.
- Banco de dados real.
- Pandas, TensorFlow, PyTorch, scikit-learn e bibliotecas grandes nao
  modeladas.
- `async`/`await`.
- `eval`, `exec`, reflexao e monkey patching.
- Decorators/metaclasses/descriptors complexos.
- Dependencias dinamicas carregadas em runtime.
- Concorrencia Python real, exceto modelos muito controlados.
- Programas que dependem fortemente de efeitos colaterais globais.

Esses casos ainda podem ser analisados pela LLM, mas a V2 deveria exigir uma
abstracao antes de chamar o ESBMC.

### 5.4 Escopo recomendado para uma V2 inicial

Uma primeira V2 defensavel poderia limitar o problema a:

```text
funcoes Python reais ou semi-reais
  com dependencias externas simples
  convertidas em harnesses autocontidos
  para confirmar bugs locais verificaveis
```

Categorias iniciais recomendadas:

- `division_by_zero`
- `out_of_bounds`
- `assertion_violation`
- `integer_overflow`
- `none_misuse`
- `type_mismatch`
- `invalid_precondition`

Essa restricao torna o estudo mais honesto: a avaliacao mede a capacidade da
LLM de produzir uma abstracao util, nao a capacidade do ESBMC de entender todo
o ecossistema Python.

### 5.5 Como reportar resultados

Os resultados da V2 deveriam separar claramente:

```text
bug confirmado no codigo original        -> quando ESBMC roda no original
bug confirmado na abstracao              -> quando ESBMC roda no harness
bug nao confirmado dentro do bound        -> sem contraexemplo no limite usado
harness invalido                          -> erro de sintaxe/modelo
harness unsupported                       -> ESBMC nao suporta o recurso usado
abstraction gap                           -> abstracao nao preserva a hipotese
```

A frase importante para o paper:

```text
Confirmation on a synthesized harness is evidence about the abstraction, not a
full proof of the original Python program.
```

Em portugues:

```text
A confirmacao em um harness sintetizado e uma evidencia sobre a abstracao, nao
uma prova completa do programa Python original.
```

## 6. Componentes necessarios

Uma implementacao V2 provavelmente precisaria de:

- Detector de trechos-alvo: identifica funcoes, branches ou expressoes
  suspeitas.
- Gerador de harness: cria um arquivo Python autocontido para o ESBMC.
- Gerador de stubs: troca chamadas externas por valores nondet com `assume`.
- Checador de compatibilidade: rejeita harnesses com recursos nao suportados.
- Executor ESBMC: roda o harness com flags adequadas.
- Validador de abstracao: registra quais suposicoes foram feitas para evitar
  que uma confirmacao no modelo seja apresentada como prova direta do codigo
  original.

## 7. Classificacoes sugeridas

Alem das classificacoes da V1, a V2 precisaria separar:

| Classificacao | Significado |
|---|---|
| `confirmed_on_abstraction` | ESBMC confirmou a hipotese no harness gerado |
| `safe_on_abstraction` | ESBMC nao encontrou violacao dentro do bound |
| `unsupported_harness` | O harness usa recurso nao suportado pelo ESBMC |
| `invalid_harness` | O harness gerado nao executa/nao parseia |
| `abstraction_gap` | A abstracao removeu informacao essencial do codigo original |
| `timeout` | ESBMC excedeu o limite de tempo |

O resultado `confirmed_on_abstraction` deve ser tratado com cuidado: ele
confirma uma propriedade do modelo, nao necessariamente do programa original.

## 8. Riscos metodologicos

- A LLM pode criar um harness que muda a semantica do codigo.
- Stubs muito permissivos podem gerar falsos positivos.
- Stubs muito restritivos podem esconder bugs reais.
- O ESBMC pode confirmar uma violacao que so existe na abstracao.
- Comparar resultados exige ground truth mais rico, incluindo o vinculo entre
  codigo original, hipotese, abstracao e propriedade formal.

## 9. Possivel pergunta de pesquisa

> LLMs conseguem transformar hipoteses de bugs em codigo Python complexo em
> harnesses verificaveis pelo ESBMC, preservando informacao suficiente para
> confirmar bugs reais com baixa taxa de falsos positivos?

## 10. Relacao com a V1

A V1 continua sendo a base experimental mais controlada:

```text
hypothesis generation + formal confirmation on original functions
```

A V2 seria uma extensao natural:

```text
hypothesis generation + harness synthesis + formal confirmation on abstractions
```

Por isso, a V2 deve ser apresentada como trabalho futuro ou como uma segunda
fase experimental, nao como parte dos resultados atuais.
