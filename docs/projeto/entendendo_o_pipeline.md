# Entendendo o pipeline (estado de 30/09/2026)

Documento de estudo. Explica o que o pipeline faz, passo a passo, com um exemplo real, onde fica
cada coisa no código, e as respostas para as perguntas mais prováveis da reunião.

---

## 1. A ideia em uma frase

A LLM lê código Python real e diz **onde** acha que está um bug; o pipeline transforma esse trecho
num programa que o ESBMC consegue verificar, **sem mudar o código**; e o bug só conta como
confirmado se o **ESBMC** e a **execução real no Python** mostrarem a mesma falha na mesma linha.

---

## 2. Vocabulário

| Termo | O que é |
|---|---|
| **Hipótese** | o palpite da LLM: arquivo, função, expressão suspeita e explicação. Fica "congelada": não muda depois. |
| **AST** | a árvore sintática do código Python (módulo `ast`). Usada para achar a expressão e recortar o código sem interpretar texto. |
| **Aterramento** | conferir, pela AST, que a expressão apontada existe mesmo dentro da função. |
| **Recorte** | cópia da função e de tudo que ela usa (outras funções, classes, constantes), sem o resto do arquivo. |
| **Substituto (stub)** | versão falsa de uma biblioteca que o ESBMC não conhece. Ex.: `tornado` vira uma classe vazia; `np.diff` vira uma função que devolve "qualquer lista de float". |
| **`nondet_int()`, `nondet_bool()`...** | "valor qualquer desse tipo". O ESBMC considera **todos** os valores possíveis ao mesmo tempo. |
| **Harness** | o programa completo que vai para o ESBMC: substitutos + código real recortado + chamada da função. |
| **Driver** | a parte do harness que cria as entradas e chama a função (`_esbmc_main`). |
| **Especificação (spec)** | o JSON que a LLM devolve com os tipos das entradas. |
| **ESBMC** | o verificador formal (versão 8.5.0 oficial, em `/usr/local/bin/esbmc`). Procura uma entrada que faça o programa falhar. |
| **CPython** | o Python normal. Usado para executar o mesmo harness com valores concretos (a "reexecução"). |
| **Veredito** | o resultado final de cada hipótese (seção 6). |

---

## 3. O desenho completo

```
                 ┌──────────────────────────────────────────┐
                 │  Código Python real (arquivo do repo)    │
                 └────────────────────┬─────────────────────┘
                                      │
  ┌───────────────────────────────────▼───────────────────────────────────┐
  │ ① DETECÇÃO (LLM)                                                       │
  │   uma chamada por função; devolve:                                     │
  │   função · expressão suspeita · explicação · categoria (só metadado)   │
  └───────────────────────────────────┬───────────────────────────────────┘
                                      │  hipótese congelada
  ┌───────────────────────────────────▼───────────────────────────────────┐
  │ ② ATERRAMENTO (AST)                                                    │
  │   a expressão existe dentro da função?                                 │
  │   não ──► GROUNDING_FAILED (localização inválida)                      │
  └───────────────────────────────────┬───────────────────────────────────┘
                                      │
  ┌───────────────────────────────────▼───────────────────────────────────┐
  │ ③ RECORTE + SUBSTITUTOS + COMPATIBILIDADE (programa)                   │
  │   • copia função, classe e dependências, verbatim                      │
  │   • remove métodos que a função não usa                                │
  │   • bibliotecas desconhecidas ──► substitutos automáticos              │
  │   • regras gerais: property, apelido de método, sys, tipos de lib...   │
  │   não dá ──► UNSUPPORTED (limite) ou MISSING_DEPENDENCY (falta código) │
  └───────────────────────────────────┬───────────────────────────────────┘
                                      │
  ┌───────────────────────────────────▼───────────────────────────────────┐
  │ ④ ESPECIFICAÇÃO (LLM)                                                  │
  │   só JSON: tipos dos parâmetros, atributos e retornos dos substitutos  │
  │   JSON inválido 3 vezes ──► SPEC_FAILED                                │
  └───────────────────────────────────┬───────────────────────────────────┘
                                      │
  ┌───────────────────────────────────▼───────────────────────────────────┐
  │ ⑤ MONTAGEM DO HARNESS (programa)                                       │
  │   substitutos + código real + driver (_esbmc_main)                     │
  └───────────────────────────────────┬───────────────────────────────────┘
                                      │
  ┌───────────────────────────────────▼───────────────────────────────────┐
  │ ⑥ ESBMC  (--unwind 5 --multi-property)                                 │
  │   rejeitou o programa (erro de conversão)? ──► erro volta ao ④ (≤ 2x) │
  │   tempo esgotado ──► ESBMC_TIMEOUT · falha interna ──► ESBMC_ERROR     │
  └───────────────────────────────────┬───────────────────────────────────┘
                                      │ violação encontrada / seguro
  ┌───────────────────────────────────▼───────────────────────────────────┐
  │ ⑦ REEXECUÇÃO NO CPYTHON                                                │
  │   o mesmo programa, trocando cada nondet_* por valores concretos       │
  └───────────────────────────────────┬───────────────────────────────────┘
                                      │
  ┌───────────────────────────────────▼───────────────────────────────────┐
  │ ⑧ VEREDITO                                                             │
  │   ESBMC e execução: mesma exceção, linha da hipótese ──► CONFIRMED     │
  │   só o ESBMC aponta ──────────────────────────────────► UNVALIDATED   │
  │   só a execução reproduz ─────────────────────────────► ESBMC_MISSED  │
  │   exceção em outra linha ─────────────────────────────► OTHER_FAILURE │
  │   nenhum dos dois ────────────────────────────────────► NOT_CONFIRMED │
  └───────────────────────────────────────────────────────────────────────┘
```

**Onde a LLM entra:** só em ① e ④. Em nenhum momento ela escreve código.

**Dois modos de rodar:**
- **ponta a ponta** (RQ1 e RQ3): começa em ①, a LLM acha o bug sozinha;
- **só verificação** (RQ2): pula ① e usa a localização do gabarito, para medir a verificação
  separada da detecção.

---

## 4. Um exemplo real, do começo ao fim (tornado, `av_real_02`)

**① Detecção.** Saída real do gpt-4o-mini:
- função: `WebSocketHandler.set_nodelay`
- expressão: `assert self.stream is not None`
- explicação: "não há guarda que valide `self.stream` antes do `assert`; ele pode ser `None`"

**② Aterramento.** A AST encontra `assert self.stream is not None` dentro de `set_nodelay`. Ok.

**③ Recorte.** Transformações registradas:
- `unreachable_methods_removed`: 22 métodos que `set_nodelay` não usa foram tirados;
- `stubbed_imports: tornado`: a biblioteca virou substituto;
- `external_chains_flattened`: `tornado.web.RequestHandler` virou `tornado_web_RequestHandler`;
- `receiver_init_replaced`: o `__init__` original foi trocado por um vazio (o estado do objeto vem
  do harness).

**④ Especificação.** A LLM respondeu:
```json
{"params": {"value": "bool"}, "attributes": {}, "stubs": {}, "assumptions": []}
```

**⑤ Harness montado** (resumido; a docstring e as linhas em branco de preenchimento foram omitidas):
```python
class tornado_web_RequestHandler:          # substituto
    pass

class WebSocketHandler(tornado_web_RequestHandler):
    def __init__(self) -> None:            # construtor vazio
        pass
    stream = None                          # atributo real da classe
    def set_nodelay(self, value: bool) -> None:
        assert self.stream is not None     # linha 127 (mesma do arquivo original)
        self.stream.set_nodelay(value)

def _esbmc_main() -> None:                 # driver
    value: bool = nondet_bool()
    _receiver = WebSocketHandler()
    _receiver.set_nodelay(value)

_esbmc_main()
```

**⑥ ESBMC:** `assertion !(ISNONE(stream))`, ou seja, `stream` pode ser `None`.

**⑦ CPython:** `AssertionError` na linha 127, na primeira tentativa.

**⑧ Veredito: CONFIRMED.** Mesma exceção, na linha da hipótese.

---

## 5. O harness em detalhe

### 5.1 Quem decide o quê

| Parte | Quem decide | Como |
|---|---|---|
| quais bibliotecas viram substituto | programa | a AST mostra os imports e como cada nome é usado |
| tipo do valor que cada substituto devolve | LLM | no JSON (`"stubs"`) |
| recorte do código | programa | cópia verbatim, mais as regras de compatibilidade |
| tipos das entradas | LLM | no JSON (`"params"`, `"attributes"`) |
| pré-condições (opcional) | LLM | no JSON (`"assumptions"`), só com as entradas e `len()` |
| driver | programa | sempre o mesmo molde |

### 5.2 Como cada uso de biblioteca vira substituto

| Uso no código | Substituto gerado |
|---|---|
| chamada `lib.f(x)` | função que devolve "qualquer valor" do tipo dado pela LLM |
| constante `lib.X` | valor qualquer do tipo dado pela LLM |
| classe base, anotação, `isinstance(x, lib.T)` | classe vazia `lib_T` |
| exceção `except lib.Error` | subclasse de `Exception` |
| cadeia `a.b.c(...)` | renomeada para um nome de um nível (`a_b.c`) |
| `sys.exit`, `sys.maxsize`, `sys.version_info` | modelo fixo: `exit` encerra o caminho; valores iguais aos do Python da reexecução |

### 5.3 As regras de compatibilidade (30/09)

Cada uma reescreve uma construção que o ESBMC 8.5 recusa, sem mudar o comportamento:

1. **Código do módulo que altera um dado usado pela função** (ex.: `TABELA.update(...)` no topo do
   arquivo): passa a ser copiado junto, em vez de o recorte ser recusado.
2. **`x = property(...)` e `@property`**: `x` vira uma entrada do harness. Exceção: se a classe usa
   o setter da property, ela não é trocada (o setter pode converter o valor).
3. **`__repr__ = __str__`**: vira `def __repr__(self): return self.__str__()`, na mesma linha.
4. **Tipo de biblioteca com dois níveis** (`httputil.HTTPConnection`): vira uma classe única
   `httputil_HTTPConnection`, em todos os usos (inclusive quando também é construída).
5. **`sys` e imports dentro de `try`**: `sys` não carrega no ESBMC 8.5 (testado nos 18 módulos da
   lista; só ele falha); imports dentro de `try/except ImportError` também viram substitutos.

### 5.4 Como se sabe se a LLM errou o tipo

- **Tipagem do código vence:** se o parâmetro tem anotação no código, ela é usada; a LLM só
  preenche o que está em aberto.
- **JSON inválido** (tipo faltando, tipo não suportado, nome que não existe): o programa rejeita
  antes do ESBMC.
- **Tipo incompatível com o uso** (diz `int`, mas o código faz `x.split()`): o ESBMC rejeita com
  erro de tipo, e a mensagem volta para a LLM (até 2 reparos).
- **Tipo plausível, mas diferente do real** (`str` em vez de `bytes`; `Optional` quando nunca é
  `None`): **não é detectado**. Pode fazer o ESBMC testar um valor impossível. A execução usa os
  mesmos tipos, então não filtra. O que mede esse risco é o controle nas versões corrigidas (0
  confirmações falsas) e a regra de a falha ser na linha apontada. Melhoria futura: inferir os tipos
  pelas chamadas da função no repositório ou pelos testes do projeto.

### 5.5 Por que existe a reexecução no CPython

O ESBMC erra nos dois sentidos (seção 9). E o harness usa substitutos: se o substituto não se
comporta como a biblioteca real, o ESBMC pode achar um erro que não existe. A reexecução roda o
**mesmo** programa com valores concretos. Só confirma se os dois concordam.

Limite importante: como os dois rodam o mesmo harness, **um harness infiel engana os dois**. Por
isso existe o controle com versões corrigidas (seção 8) e foi feita uma revisão do código do
harness (seis riscos encontrados e corrigidos, por exemplo `sys.exit` que não encerrava o programa).

---

## 6. Todos os vereditos

| Veredito | Onde para | Significado |
|---|---|---|
| CONFIRMED | ⑧ | ESBMC e execução: mesma exceção, na linha da hipótese |
| UNVALIDATED | ⑧ | o ESBMC aponta, a execução não reproduz |
| ESBMC_MISSED | ⑧ | a execução reproduz, o ESBMC não aponta (falso negativo do ESBMC) |
| OTHER_FAILURE | ⑧ | a falha aparece em outra linha |
| NOT_CONFIRMED | ⑧ | nenhum dos dois encontra |
| GROUNDING_FAILED | ② | a expressão apontada não existe na função |
| UNSUPPORTED | ③ ou ⑥ | construção que o ESBMC não aceita (limite nomeado) |
| MISSING_DEPENDENCY | ③ | falta código que não está no arquivo |
| SPEC_FAILED | ④ | a LLM não produziu JSON válido em 3 tentativas |
| ESBMC_TIMEOUT / ESBMC_ERROR | ⑥ | o ESBMC estourou o tempo (180 s) ou falhou |
| NO_SOURCE | antes de ② | não há arquivo para verificar (usado no controle) |
| PIPELINE_ERROR | qualquer | erro inesperado (ex.: queda de rede na API) |

---

## 7. A categoria

**Antes (até 23/09):** a categoria (fora dos limites, `None`, divisão por zero...) escolhia a
estratégia de harness e definia se a detecção estava certa.

**Problema:** um bug cabe em mais de uma categoria. Um `None` que causa acesso fora dos limites é
"uso de `None`" ou "fora dos limites"? A LLM que achava a função certa com a outra categoria era
contada como erro, e o harness escolhido podia ser o errado.

**Depois (29/09):** a categoria virou só metadado. O harness passou a ser o mesmo para qualquer
bug, e a confirmação olha a exceção real.

**Agora (04/10):** a LLM não dá mais categoria. Para cada bug, ela diz se ele é verificável
formalmente (viola uma propriedade que o ESBMC checa sozinho) e qual é a propriedade. Só esses vão
ao ESBMC; os outros contam na detecção. A detecção é medida pela localização, e a decisão de mandar
ou não é medida como triagem, contra o campo `failure_kind` do gabarito.

| Categoria (rótulos no dataset) | Exceção que costuma confirmar |
|---|---|
| pré-condição inválida (30) | `ValueError`, `raise` do próprio código |
| uso indevido de `None` (28) | `AttributeError`, `TypeError` |
| fora dos limites (14) | `IndexError`, `KeyError` |
| violação de asserção (13) | `AssertionError` |
| resultado incorreto (13) | nenhuma: hoje não confirmável (ideia futura: pós-condição a partir da docstring) |
| tipo incompatível (12) | `TypeError` |
| variável errada (9) | depende do efeito |
| divisão por zero (4) | `ZeroDivisionError` |
| estouro de inteiro (2) | raro em Python, cujos inteiros não estouram |

São 125 rótulos para 116 bugs, porque alguns bugs têm duas categorias.

---

## 8. Dataset

| | Quantidade | Onde |
|---|---|---|
| Bugs reais no gabarito | 116, de 42 projetos | `dataset/bugs_reais/ground_truths.json` |
| Avaliáveis na detecção | 104 (12 precisam do patch para serem entendidos) | idem, `patch_context_items` |
| Arquivos da detecção | 116 | `dataset/bugs_reais/funcao_com_bug/` |
| Arquivo-fonte completo (usado na verificação quando existe; senão, usa-se o trecho do dataset, que também contém o bug) | 99 | `dataset/bugs_reais/arquivo_com_bug/` |
| Versão corrigida (controle) | 98 | `dataset/bugs_reais/arquivo_corrigido/` |
| Candidatos novos (fora do gabarito) | 199, validados por mantenedores (BugsInPy) | `dataset/coleta_bugsinpy/` |

Projetos com mais bugs: scrapy (15), thefuck (11), luigi (10), youtube-dl (9), tornado (8).

**Controle de falso positivo:** o pipeline roda nas versões **já corrigidas**. Ali não existe o bug,
então qualquer CONFIRMED é falso. Resultado: 0 em duas rodadas.

**Os 199 candidatos:** novos, sem repetir os 84 do BugsInPy que já estavam no gabarito. Função e
expressão foram atribuídas a partir da correção, mas ainda falta passar pelos portões de auditoria
(build do projeto e teste que falha antes da correção). Por enquanto servem para validar as regras
do harness em código que não foi usado para criá-las.

---

## 9. Resultados (números para a reunião)

**RQ1, a LLM encontra o bug?** (104 bugs, gpt-4o-mini)
- arquivo 98%, **função 97%**, categoria 49%;
- expressão 40% (equivalente) ou 20% (texto idêntico).

**RQ2, com a localização dada, o ESBMC confirma?** (125 hipóteses)
- 3 confirmados; veredito em até 3 chamadas da LLM: 11,4% em média (3 rodadas).

**RQ3, ponta a ponta:** 1 confirmado (tornado), 8% com veredito.

**Reparo contra amostragem** (3 rodadas, mesmo custo): mostrar o erro do ESBMC à LLM leva 11,4% ao
veredito, contra 4,4% sem mostrar; especificações inválidas 15 contra 37.

**Harness revisado (30/09):** especificações inválidas caem de 15 para 7; confirmações iguais (3);
casos a mais chegam ao ESBMC e param no próximo limite dele. Sem LLM, chegam ao ESBMC: 77 para 84
de 99 no dataset, e 111 para 122 de 176 nos candidatos que não foram usados para criar as regras;
os vereditos ficam em 15 e 15 no dataset, e vão de 18 para 20 nos candidatos.

**Controle:** 0 confirmações falsas nas versões corrigidas (2 rodadas).

**Onde os casos param** (rodada de 30/09, 125 hipóteses, localização dada, harness revisado):

| Etapa | Casos |
|---|---|
| o harness não consegue montar o programa | 56 |
| a LLM não dá tipos válidos | 7 |
| falha de rede | 2 |
| o ESBMC recusa o programa | 39 |
| o ESBMC não termina (tempo ou inconclusivo) | 9 |
| o ESBMC responde (3 confirmados, 6 sem falha, 2 não reproduzidos, 1 em outra linha) | 12 |

Os 56 do harness: o recorte esquece um nome que a função usa (25); biblioteca sem substituto ou com
substituto errado (15); tipo de entrada que o harness não sabe gerar (9); outros (7). Os 39 recusados
pelo ESBMC foram classificados pela mensagem de erro e pela linha (seção 10); só o caso do `%` foi
reproduzido isolado até agora. Parte das recusas que pareciam do ESBMC eram, na verdade, substitutos
ou recortes errados do harness (11 casos), e estão contadas nos 56.

**Agente** (Claude Code + plugin ESBMC, 49 casos em que o pipeline parava): 4 confirmados sem
alterar a função; 17 continuam fora do alcance do ESBMC; 9 o ESBMC aponta e a execução não
reproduz; 6 o agente não terminou.

**Solver:** em 7 programas que estouravam o tempo de forma reproduzível, Boolector e Z3 terminaram 2;
o Bitwuzla (padrão), nenhum.

---

## 10. Limites do ESBMC-Python 8.5 que encontramos

| Tipo | Exemplo |
|---|---|
| falso positivo | `while defs and defs[-1] >= d: defs.pop()`: aponta `IndexError`, mas é seguro |
| falso negativo | `v: Optional[int] = None; v + 1`: não detecta o `TypeError` |
| recusa | `async`, `"%d" % x` com valor não constante, `type(x).__name__`, `x.__dict__`, `**kwargs` em classe base, `OrderedDict` como classe base, função usada como valor (`functools.partial`) |
| ausência | não existe `SystemExit`; o módulo `sys` não carrega |
| falha interna | falha de segmentação com expressão condicional sobre texto opcional |

Reprodutores mínimos: `docs/projeto/repro_esbmc_none/`.

---

## 11. Onde fica cada coisa no código

| Passo | Arquivo |
|---|---|
| comando principal | `src/main.py` (`--mode hybrid --v2-stage end-to-end` ou `synthesis`) |
| ① detecção | backends de LLM em `src/research_pipeline/llm/` |
| hipótese | `src/research_pipeline/verify/hypothesis.py` |
| ② aterramento | `src/research_pipeline/verify/grounding.py`, `astutil.py` |
| ③ recorte | `src/research_pipeline/verify/context.py` |
| ③ substitutos | `src/research_pipeline/verify/slicing.py` |
| ③ compatibilidade | `src/research_pipeline/verify/compat.py` |
| ④ especificação | `src/research_pipeline/verify/spec.py`, prompt em `src/research_pipeline/prompts/input_spec_prompt.txt` |
| ⑤ harness | `src/research_pipeline/verify/render.py` |
| ⑥ ESBMC | `src/research_pipeline/verification/esbmc_runner.py`, leitura do resultado em `outcome.py` |
| ⑦ reexecução | `src/research_pipeline/verify/replay.py`, `replay_worker.py` |
| laço das tentativas | `src/research_pipeline/verify/loop.py` |
| ⑧ veredito | `src/research_pipeline/verify/outcome.py` |
| métricas | `src/research_pipeline/v2_evaluator.py`, `src/research_pipeline/verify/report.py` |
| braço com agente | `src/research_pipeline/verify/agent_arm.py`, `scripts/v2_agent_arm.py` |

---

## 12. O que saiu do pipeline antigo, e por quê

**Retry (gerar o harness de novo até o ESBMC achar erro):** removido. Tentando várias vezes, uma
hora sai um harness que "acha" erro mesmo sem bug; na rodada de 27/09 o pipeline antigo "confirmou" 47
de 135 suspeitas, mas só 2 eram o bug real (25 vinham de harness simplificado, 12 eram outros erros
sem conferência, 8 sem verificação completa). Hoje só existe o **reparo**: a LLM corrige o JSON quando o ESBMC **rejeita** o programa, no
máximo 2 vezes. Quando o ESBMC responde "seguro", nunca se tenta de novo.

**Ablação (rodar de novo sem as pré-condições da LLM):** removida no redesenho, porque as
pré-condições ficaram muito restritas (só entradas e `len()`, e o prompt proíbe excluir o gatilho
do bug). Ponto em aberto: em 19 de 125 hipóteses a LLM usou pré-condição, e alguma pode esconder o
bug (ex.: `len(self.url) > 0` se o bug for a URL vazia). Hoje não mudou nenhum resultado, porque
esses casos pararam antes do veredito, e o risco é só de **deixar passar** um bug, nunca de
confirmação falsa. Correção prevista: refazer sem pré-condição os casos "não confirmados".

**Categoria guiando o harness:** removida (seção 7).

## 13. Ideias para depois da reunião

**Mais de uma expressão por função.** Na rodada ponta a ponta, a LLM deu 138 hipóteses para 96
funções (35 funções com mais de uma). O ESBMC verifica a função inteira; quem exige a linha exata é
a nossa regra de veredito. Uma falha real na função certa, mas em outra linha, hoje vira "outra
falha" e não conta. Pergunta para o Lucas: deve contar, numa categoria separada? Cuidado: falha em
outra linha às vezes vem de um substituto grosseiro (caso `url_concat`).

**Gerador de pytest do ESBMC** (documentação: esbmc.github.io/docs/python/pytest-testgen/). O
gerador espera o `nondet` dentro da chamada da função, por exemplo
`classify_number(__VERIFIER_nondet_int())`. O nosso driver cria as variáveis antes, dentro do
`_esbmc_main`, e por isso o teste gerado no caso thefuck chamou `_esbmc_main(arg0, arg1)` e não
rodou (o contraexemplo, porém, estava certo: `script = "   "`). Mudança prevista, só para os casos
confirmados: montar o driver no formato da documentação. Ganhos:
- um pytest que reproduz cada bug confirmado (`--generate-pytest-testcase`);
- a reexecução com o contraexemplo exato do ESBMC (`--pytest-values-only`);
- testes de cobertura para a disciplina (`--branch-coverage`, `--k-path-coverage`).
Limite: se o bug acontece com qualquer entrada (caso tornado), não há valor a registrar e o gerador
não produz teste.

## 14. Perguntas prováveis e respostas curtas

**"A LLM escreve o harness?"** Não. Ela só aponta o bug e informa os tipos em JSON. O programa monta
o harness.

**"Vocês mudam o código analisado?"** Não. A função entra como está no repositório. O que muda é o
entorno: bibliotecas viram substitutos, e construções que o ESBMC recusa são reescritas de forma
equivalente, sempre fora da função e registradas.

**"Por que tão poucas confirmações?"** Porque a maioria dos casos para num limite do ESBMC-Python
antes de chegar ao veredito. Quando ele roda, a confirmação é confiável: 0 falsas no controle.

**"Como saber que uma confirmação não é falsa?"** Três proteções: o ESBMC e a execução real
precisam concordar; o pipeline roda nas versões corrigidas e não confirma nada lá; e o código do
harness foi revisado para caminhos de confirmação falsa.

**"Isso é específico do dataset?"** Não. As regras foram testadas em 199 bugs que não foram usados
para criá-las, e os mesmos erros desapareceram lá.

**"E a categoria?"** Virou metadado, porque um bug pode ter duas categorias e isso penalizava
detecções corretas.

**"Por que executar no Python se o ESBMC já verifica?"** Porque o ESBMC-Python 8.5 erra nos dois
sentidos: aponta `IndexError` num `pop()` protegido por `while` (falso positivo), não detecta
`None + 1` com `Optional[int]` (falso negativo), e acusou violação na versão já corrigida de
`cli_bool_option`. A execução real é a prova de que a falha acontece.

**"Cadê a ablação e o retry?"** Seção 12.

**"Qual o papel do agente?"** Um experimento: ele recupera casos que o método automático não
alcança (4 de 49), e o pipeline confere tudo que ele faz.
