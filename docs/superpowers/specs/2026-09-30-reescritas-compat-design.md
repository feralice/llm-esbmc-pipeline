# Reescritas de compatibilidade por regra fixa (caminho 2)

Data: 30/09/2026. Status: aguardando revisão da Fernanda.

## Objetivo

Aumentar o número de hipóteses `CONFIRMED` do motor verify sem perder a garantia de que o bug
confirmado existe no código original. O meio é reescrever construções Python que o ESBMC-Python
recusa por construções equivalentes que ele aceita.

Decisões já tomadas:

- A reescrita é feita **por regra fixa em código**, nunca pela LLM. Cada regra é uma equivalência
  da definição da linguagem (ou do ambiente do harness, como thread única).
- Regras genéricas, nunca específicas de um caso do dataset. O dataset só serve para descobrir
  quais construções aparecem.
- O CPython continua sendo o juiz final: `CONFIRMED` exige que a reexecução reproduza a exceção na
  linha da hipótese, como hoje.
- A métrica que decide se valeu a pena é o **delta de `CONFIRMED`**. Alcance (quantos casos passam
  da recusa do ESBMC) é reportado depois, como métrica intermediária.

## Ponto de partida

`src/research_pipeline/verify/compat.py` já aplica duas regras exatas sobre o módulo recortado,
dentro de `ground()`: `"%s..." % (a, b)` vira concatenação com `str()`, e `alias = metodo` em corpo
de classe vira um `def` que delega. As reescritas são feitas na mesma linha, para a numeração não
mudar, e ficam registradas em `transforms`.

Na rodada de 30/09 (`artifacts/v2/exp-oracle-repair-cobertura`, 125 hipóteses), as recusas do ESBMC
com regra exata possível são:

| Construção | Hipóteses | Exemplo |
|---|---|---|
| `"...%s..." % x` com operando que não é tupla literal | 4 | `nm_real_03`, `nm_real_04`, `ip_real_07`, `vm_real_05` |
| `Warning`, `DeprecationWarning`, `NotImplemented` não definidos | 2 | `ip_real_19`, `ip_real_24` |
| `threading.RLock()` / `threading.local()` | 2 | `nm_real_09`, `ip_real_28` |
| `f(*xs)` com `xs` de tamanho conhecido | até 4 | `tm_real_01` (a confirmar na implementação) |

Teto: até 12 hipóteses passam da recusa atual. Quantas chegam a `CONFIRMED` depende dos erros
seguintes e só a medição responde; zero é um resultado possível.

## Regras

### R1: `%s` com um único operando

`"...%s..." % x` vira `"..." + str(x) + "..."` **somente quando o tipo de `x` é conhecido e não é
tupla**. Para um `x` que não é tupla, a documentação do Python ("printf-style String Formatting")
define o resultado como `str(x)`. Para tupla, o resultado depende do tamanho, e a regra não se
aplica.

Um helper genérico que trata os dois casos (`isinstance(x, tuple)`) foi testado e derruba o ESBMC
8.5.0 com falha de segmentação. Por isso a regra exige prova estática de que `x` não é tupla. Os
casos aceitos são:

- literal de string ou número;
- resultado de método de `str` (`"|".join(...)`, `s.strip()`, `s.lower()` etc.);
- chamada a stub ou função cuja anotação de retorno é um tipo que não é tupla;
- parâmetro da função de entrada cujo tipo foi declarado pelo harness (`new_path: str`);
- variável local cujas atribuições, todas, caem em um dos casos acima.

Qualquer outro operando fica como está. Os tipos dos parâmetros e dos stubs só existem depois do
harness, então a R1 roda **sobre o programa renderizado**, no fim de `render_program()`, e não em
`ground()`. A reescrita continua na mesma linha.

Ficam de fora:

- `%d`, porque `"%d" % "5"` levanta `TypeError` e `str(int("5"))` não. É o caso da quinta recusa
  de `%` na rodada, `nm_real_05` (`"<%d %s>" % (...)`).
- `%r` e `%` sobre operando de tipo desconhecido.
- `%(chave)s`.

### R2: nomes embutidos ausentes

Quando o módulo usa `Warning`, uma subclasse de aviso embutida (`DeprecationWarning`,
`UserWarning`, `RuntimeWarning`, `FutureWarning`, `PendingDeprecationWarning`) ou `NotImplemented`
e não os define, o prelúdio do harness passa a definir:

```python
class Warning(Exception):
    pass


class DeprecationWarning(Warning):
    pass


class _NotImplementedType:
    pass


NotImplemented = _NotImplementedType()
```

São definidas apenas as classes usadas, com a mesma relação de herança do CPython. Testado no
ESBMC 8.5.0: com `Warning` definido, o ESBMC acusa `DeprecationWarning` e a exceção real do mesmo
programa. Sem `Warning`, ele recusa com `Base class not found: Warning`.

`unicode` fica de fora: no Python 3 ele não existe, e definir esse nome trocaria um `NameError`
real por outro comportamento.

### R3: travas e estado por thread

`threading.Lock()`, `threading.RLock()` e `threading.local()` viram instâncias de uma classe do
prelúdio que não faz nada (`__enter__`/`__exit__` vazios; atributos livres no caso de `local`). A
equivalência vale porque o harness executa em uma única thread: sem concorrência, adquirir e
liberar uma trava não muda nenhum valor. A substituição da chamada é feita na mesma linha. Testado
no ESBMC 8.5.0: o `ZeroDivisionError` dentro de um `with` sobre a trava substituta é encontrado.

### R4: desempacotamento de tamanho conhecido

`f(*xs)` vira `f(xs[0], xs[1], ...)` quando `xs` é um nome atribuído uma única vez no mesmo escopo
a uma tupla ou lista literal, e não é alterado entre a atribuição e a chamada (sem `append`,
`extend`, `pop`, atribuição por índice ou nova atribuição). Desempacotar uma sequência de tamanho
`n` em uma chamada equivale a passar seus `n` elementos por posição. Na mesma linha.

### Fora do escopo

- `async def` (trocar por `def` muda o valor de retorno da função).
- `@dataclass` (um caso; exigiria gerar `__init__`, `__eq__` e `__repr__`).
- `*args` em chamadas externas: limite do gerador de stubs, não do ESBMC.
- Fatias 2-D de numpy, `__dict__`, `sorted(key=)` e outros casos únicos.

## Rastreabilidade

Cada regra aplicada entra em `transforms` (`compat_percent_single:N`, `compat_builtin_names:N`,
`compat_thread_lock:N`, `compat_star_call:N`). O relatório de medição separa as confirmações que
dependem de alguma reescrita das que não dependem.

## Medição

Script novo `scripts/v2_replay_specs.py`, sem chamada de LLM:

1. Lê um `v2_verify_report.json` e, para cada hipótese, pega o JSON de tipos da última tentativa
   que passou na validação do spec.
2. Refaz `ground()` → `render_program()` (agora com as regras) → ESBMC → reexecução no CPython,
   com as mesmas flags do motor.
3. Imprime, nesta ordem: delta de `CONFIRMED`, depois mudança de veredito por hipótese, depois
   alcance.

Como o JSON de tipos é o mesmo da rodada original, qualquer diferença vem só das reescritas.
Hipóteses sem JSON válido salvo são contadas à parte e não são re-executadas.

**Controle:** o mesmo script roda sobre `artifacts/v2/exp-oracle-fixed-cobertura` (versões
corrigidas). Um `CONFIRMED` novo no controle indica que alguma regra mudou o comportamento; a
regra é revista antes de qualquer número ser reportado.

## Testes

- Para cada regra, um teste que executa original e reescrito no CPython com um conjunto de valores
  e exige a mesma saída ou a mesma exceção.
- Para cada exclusão (`%d`, operando de tipo desconhecido, tupla, `unicode`, `xs` alterada), um
  teste que garante que a regra **não** dispara.
- Os reprodutores `docs/projeto/possiveis_problemas/17_formatacao_percent.py` e
  `16_desempacotar_args.py` são adaptados para testes de ponta a ponta da R1 e da R4: depois da
  reescrita, o ESBMC deve aceitar o programa.
- A suíte atual continua passando.

## Critério de sucesso

- Nenhum `CONFIRMED` novo no controle das versões corrigidas.
- Delta de `CONFIRMED` na rodada `exp-oracle-repair-cobertura` medido e reportado, qualquer que
  seja o valor.
- Suíte completa e `pylint` sem erros novos.
