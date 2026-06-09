# Proposta V2 — Síntese de Harnesses Guiada por LLM

> Nota de desenho para uma evolução futura do projeto. Este documento não
> descreve o pipeline V1 atual — descreve uma direção de pesquisa possível.

---

## 1. Motivação

O pipeline V1 avalia uma configuração controlada:

```
função Python simples e compatível
  → LLM propõe hipótese local de bug
  → filtro AST valida se a expressão existe
  → ESBMC roda no arquivo original com --function e parâmetros nondet
  → benchmark compara com ground truth
```

Essa abordagem é adequada para o benchmark atual, mas não resolve o problema
de código Python complexo do mundo real. Projetos reais frequentemente usam
I/O, bibliotecas externas, objetos dinâmicos, frameworks, banco de dados,
rede, decorators, async/await e outros recursos que o frontend Python do ESBMC
não suporta de forma ampla.

A V2 investigaria a LLM como ponte entre código Python complexo e um modelo
verificável pelo ESBMC.

---

## 2. Ideia Central

Na V2, a LLM não apenas apontaria uma hipótese de bug — ela também tentaria
produzir uma abstração verificável:

```
código Python complexo
  → LLM identifica trecho suspeito
  → LLM extrai uma fatia verificável
  → LLM substitui dependências por stubs/nondet/assume
  → LLM gera harness compatível com ESBMC
  → ESBMC confirma ou rejeita a hipótese
```

Em outras palavras, a contribuição potencial seria transformar uma hipótese
informal sobre código real em um programa pequeno, autocontido e verificável.

---

## 3. Diferença para a V1

| Aspecto | V1 atual | V2 proposta |
|---|---|---|
| Entrada | Função simples e compatível | Código Python mais complexo |
| Papel da LLM | Propor hipótese local | Propor hipótese + abstração/harness |
| Código verificado | Arquivo original | Modelo/harness sintetizado |
| Dependências externas | Fora do escopo | Substituídas por stubs ou nondet |
| ESBMC | `--function` no original | Verificação do harness gerado |
| Risco principal | Hipótese falsa da LLM | Abstração incorreta ou incompleta |

A V1 não faz harness synthesis, model extraction ou stubbing. A V2 teria esses
elementos como objeto de pesquisa.

---

## 4. Exemplo Conceitual

Código original:

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

Esse código é ruim para verificar diretamente porque depende de objetos e
serviços externos. Uma abstração verificável poderia ser:

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

O ESBMC verificaria o modelo, não o sistema original completo.

---

## 5. Limites Práticos do ESBMC-Python

A V2 precisa partir de uma premissa metodológica explícita: o ESBMC-Python não
é um interpretador/verificador completo para qualquer programa Python. Ele é
mais adequado para programas pequenos, autocontidos e com comportamento
simbolicamente modelável.

Portanto, a V2 não deve prometer verificar projetos Python complexos de ponta a ponta.
O objetivo realista seria extrair de código complexo um modelo pequeno o suficiente para o ESBMC verificar.

### 5.1 O que Tende a Funcionar

Casos com maior chance de serem verificáveis:

- Funções puras ou quase puras
- Código com tipos primitivos: `int`, `float`, `bool`, `str`
- Propriedades locais expressas com `assert`
- Operações aritméticas, comparações e condicionais
- Loops com bound pequeno via `--unwind`
- Listas, tuplas, dicionários e strings quando usam operações modeladas
- Funções em que parâmetros podem ser substituídos por valores nondet
- Bugs como divisão por zero, out-of-bounds, assertion violation e overflow

### 5.2 O que Deve Ser Abstraído

Em código real, muitos elementos devem virar stubs, nondet ou assumptions:

| Elemento no código real | Abstração possível |
|---|---|
| Entrada de usuário | `nondet_int`, `nondet_bool`, `nondet_*` |
| Arquivo / JSON / CSV | Valores simbólicos com `assume` |
| Banco de dados | Stub que retorna valor nondet dentro de um intervalo |
| API HTTP | Stub com status/value nondet |
| Objeto complexo | Campos primitivos relevantes |
| Biblioteca externa | Modelo pequeno da função usada |
| Configuração global | Constantes ou parâmetros simbólicos |

### 5.3 O que Deve Ficar Fora do Escopo Inicial

- Frameworks web completos: Django, Flask, FastAPI em execução real
- I/O real: arquivos, rede, sockets, subprocessos
- Banco de dados real
- Pandas, TensorFlow, PyTorch, scikit-learn e bibliotecas grandes
- `async`/`await`
- `eval`, `exec`, reflexão e monkey patching
- Decorators/metaclasses/descriptors complexos
- Dependências dinâmicas carregadas em runtime
- Concorrência Python real

### 5.4 Escopo Recomendado para uma V2 Inicial

```
funções Python reais ou semi-reais
  com dependências externas simples
  convertidas em harnesses autocontidos
  para confirmar bugs locais verificáveis
```

Categorias iniciais recomendadas:

- `division_by_zero`
- `out_of_bounds`
- `assertion_violation`
- `integer_overflow`
- `none_misuse`
- `type_mismatch`
- `invalid_precondition`

### 5.5 Como Reportar Resultados

Os resultados da V2 deveriam separar claramente:

| Resultado | Significado |
|---|---|
| `confirmed_on_abstraction` | ESBMC confirmou a hipótese no harness gerado |
| `safe_on_abstraction` | ESBMC não encontrou violação dentro do bound |
| `unsupported_harness` | O harness usa recurso não suportado pelo ESBMC |
| `invalid_harness` | O harness gerado não executa ou não parseia |
| `abstraction_gap` | A abstração removeu informação essencial do código original |
| `timeout` | ESBMC excedeu o limite de tempo |

> Confirmação em um harness sintetizado é uma evidência sobre a abstração,
> não uma prova completa do programa Python original.

---

## 6. Componentes Necessários

Uma implementação V2 provavelmente precisaria de:

- **Detector de trechos-alvo:** identifica funções, branches ou expressões suspeitas
- **Gerador de harness:** cria um arquivo Python autocontido para o ESBMC
- **Gerador de stubs:** troca chamadas externas por valores nondet com `assume`
- **Checador de compatibilidade:** rejeita harnesses com recursos não suportados
- **Executor ESBMC:** roda o harness com flags adequadas
- **Validador de abstração:** registra quais suposições foram feitas

---

## 7. Classificações Sugeridas

Além das classificações da V1, a V2 precisaria separar:

| Classificação | Significado |
|---|---|
| `confirmed_on_abstraction` | ESBMC confirmou a hipótese no harness gerado |
| `safe_on_abstraction` | ESBMC não encontrou violação dentro do bound |
| `unsupported_harness` | O harness usa recurso não suportado pelo ESBMC |
| `invalid_harness` | O harness gerado não executa ou não parseia |
| `abstraction_gap` | A abstração removeu informação essencial do código original |
| `timeout` | ESBMC excedeu o limite de tempo |

---

## 8. Riscos Metodológicos

- A LLM pode criar um harness que muda a semântica do código
- Stubs muito permissivos podem gerar falsos positivos
- Stubs muito restritivos podem esconder bugs reais
- O ESBMC pode confirmar uma violação que só existe na abstração
- Comparar resultados exige ground truth mais rico, incluindo o vínculo entre código original, hipótese, abstração e propriedade formal

---

## 9. Possível Pergunta de Pesquisa

> LLMs conseguem transformar hipóteses de bugs em código Python complexo em
> harnesses verificáveis pelo ESBMC, preservando informação suficiente para
> confirmar bugs reais com baixa taxa de falsos positivos?

---

## 10. Relação com a V1

A V1 continua sendo a base experimental mais controlada:

```
hipótese da LLM + confirmação formal no arquivo original
```

A V2 seria uma extensão natural:

```
hipótese da LLM + síntese de harness + confirmação formal na abstração
```

Por isso, a V2 deve ser apresentada como trabalho futuro ou como uma segunda
fase experimental, não como parte dos resultados atuais.
