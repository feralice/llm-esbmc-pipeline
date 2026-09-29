# V2: verificação de hipótese de bug no código real (desenho)

Desenho do motor de verificação da V2 (`src/research_pipeline/verify/`), definido em 29/09/2026.
Ele substituiu a cascata anterior de estratégias (harness escalar, driver escrito pela LLM,
reescrita pela LLM), removida do código; o histórico fica no git. Guia de uso em
[`README.md`](README.md).

## 1. Fluxo

```
código real
  -> [LLM] detecção: onde está o bug                      (inalterada, prompt atual)
  -> [AST] aterramento: a expressão existe naquela função?  (determinístico)
  -> [AST] recorte: função alvo + definições que ela usa    (determinístico, verbatim)
  -> [LLM] especificação de entrada (JSON, não código)      (até 1 + 2 reparos)
  -> [código] montagem do harness a partir do JSON          (determinístico)
  -> ESBMC oficial 8.5 (/usr/local/bin/esbmc)
  -> [CPython] reexecução concreta do mesmo harness          (validação por execução)
  -> veredito final (tabela da seção 5)
```

## 2. Regras que garantem que o bug verificado é o da hipótese

1. **A LLM nunca escreve código.** No passo de síntese ela devolve só um JSON:
   tipo de cada parâmetro sem anotação, tipo de cada atributo `self.x` que o método lê,
   e pré-condições opcionais. O harness é montado por código a partir desse JSON.
2. **O código original entra byte a byte.** O recorte (`context_module`) copia o texto
   do arquivo. Transformações permitidas, todas determinísticas e registradas em `transforms`:
   - método alvo: o `__init__` da classe é trocado por um que cria cada atributo lido com valor
     nondet do tipo informado (`receiver_init_replaced`/`receiver_init_added`); métodos que o alvo
     não alcança são removidos; constantes de classe mantêm o valor real;
   - decoradores do alvo viram linhas em branco (`decorators_removed`), mantendo a numeração;
   - import de biblioteca que o ESBMC não modela vira stub (`stubbed_imports`, seção 4.1).
   O método alvo nunca muda. Alvo `__init__`, `classmethod`, `async`, decorador externo em outro
   método e leitura de membro herdado de base do módulo são recusados como `UNSUPPORTED`.
3. **A hipótese é congelada.** `BugHypothesis` é imutável e tem `hypothesis_id`
   (hash de arquivo, função, linha e expressão). O reparo recebe a hipótese, mas não a devolve.
4. **Confirmação exige a linha da hipótese e a mesma falha.** O ESBMC-Python reporta exceções
   não tratadas com `line 0`, então a localização vem da reexecução no CPython: o traceback precisa
   ter um frame da função alvo (nome e intervalo de linhas) dentro do trecho da expressão suspeita,
   e a exceção reproduzida precisa ser a que o ESBMC reportou (`uncaught exception: X`,
   `X: ...`, divisão por zero, ponteiro nulo equivale a `AttributeError`/`TypeError`).
5. **SUCCESSFUL não é repetido.** Só se tenta de novo quando a falha é de montagem ou de
   conversão. Repetir até dar FAILED seria forçar a confirmação.

## 3. Por que reexecutar no CPython (medido em 2026-09-29, ESBMC 8.5.0 oficial)

| Programa | Python real | ESBMC 8.5 | Tipo de erro do ESBMC |
|---|---|---|---|
| `while defs and defs[-1] >= d: defs.pop()` | seguro | FAILED (`IndexError`) | falso positivo |
| `v: Optional[int] = None; v + 1` | `TypeError` | SUCCESSFUL | falso negativo |
| `None if nondet_bool() else nondet_str()` | n/a | artefato `expired variable pointer` | artefato de modelagem |
| `a // b` com `a, b` sem anotação | `ZeroDivisionError` | FAILED, `line 0` | sem localização |

Com isso, "ESBMC disse FAILED" não basta para dizer que o bug existe, e "SUCCESSFUL" não
basta para dizer que não existe. A validação por execução segue Beyer et al. (TAP 2018).

## 4. Especificação de entrada (saída da LLM)

```json
{
  "params": {"depth": "int", "items": "list[str]"},
  "attributes": {"previous_defs": "list[int]", "name": "Optional[str]"},
  "stubs": {"to_bytes": "str", "np.count": "int"},
  "assumptions": ["depth >= 0"]
}
```

### 4.1 Stubs de biblioteca

Nome importado de módulo sem modelo no ESBMC-Python 8.5 (modelados: `cmath`, `collections`,
`dataclasses`, `datetime`, `decimal`, `enum`, `heapq`, `math`, `os`, `queue`, `random`, `re`,
`string`, `sys`, `threading`, `time`, `typing`, `unittest`) tem o import removido e ganha stub:

| Uso no recorte | Stub | Tipo |
|---|---|---|
| `f(x)` ou `mod.f(x)` | função ou método estático que devolve nondet | campo `stubs` da LLM |
| `mod.X` ou `NOME` como valor | constante nondet | campo `stubs` da LLM |
| base, anotação, `X[...]`, 2º argumento de `isinstance` | `class X: pass` | nenhum |
| `raise`/`except`, nome terminado em `Error`/`Exception`/`Warning` | `class X(Exception)` | nenhum |
| decorador, cadeia `mod.a.b`, `*args` na chamada | recusado (`UNSUPPORTED`) | |

Uma confirmação que passa por stub vale como "se a biblioteca devolver esse valor". O resultado
registra `stubbed_imports`, e a análise separa confirmações com e sem stub.

Tipos aceitos (subconjunto que o ESBMC 8.5 converteu nos testes): `int`, `float`, `bool`,
`str`, `list[T]` com `T` escalar, `Optional[T]` com `T` desses. Outro tipo encerra o caso
como `UNSUPPORTED` (motivo `type`). `Optional` é gerado com `if nondet_bool():`, nunca com
ternário (artefato acima). Listas usam `nondet_list(3, elem_type=nondet_T())`.
Cada pré-condição deve ser uma expressão Python que só usa nomes de parâmetros ou
atributos; vira `__ESBMC_assume(...)`.

## 5. Veredito final

| Veredito | Condição | Conta na RQ3? |
|---|---|---|
| `CONFIRMED` | ESBMC FAILED (propriedade real) e a reexecução reproduz a mesma exceção na linha da hipótese | sim |
| `ESBMC_MISSED` | ESBMC SUCCESSFUL, mas a reexecução reproduz na linha da hipótese | não (falso negativo do ESBMC, reportado à parte) |
| `UNVALIDATED` | ESBMC FAILED, reexecução não reproduz ou reproduz outra exceção (possível falso positivo) | não |
| `OTHER_FAILURE` | a reexecução só reproduz exceção em outra linha | não |
| `NOT_CONFIRMED` | ESBMC SUCCESSFUL e a reexecução não reproduz | não |
| `GROUNDING_FAILED` | expressão não está na função (alucinação) | não |
| `MISSING_DEPENDENCY` | nome indefinido ou import não resolvido no recorte | não |
| `UNSUPPORTED` | tipo fora da lista ou erro de conversão sem reparo | não |
| `SPEC_FAILED` | a LLM não produziu especificação válida em 3 tentativas | não |
| `ESBMC_TIMEOUT` / `ESBMC_ERROR` | tempo esgotado / falha interna, `VERIFICATION UNKNOWN` | não |

## 6. Laço de reparo (limitado)

```
tentativa 0: spec = LLM(hipótese, recorte)
para k em 0..2:
    problemas = validar(spec)                  -> se houver: reparo com a lista de problemas
    programa  = montar(recorte, spec)
    r         = ESBMC(programa)
    se r é erro de conversão reparável         -> reparo com a mensagem do ESBMC
    se r é import/dependência/timeout          -> fim (MISSING_DEPENDENCY / ESBMC_TIMEOUT)
    senão                                      -> reexecução no CPython, veredito, fim
```

## 7. O que muda nas perguntas de pesquisa

- **RQ1 (detecção):** medida por localização (função + expressão), com a categoria como
  análise secundária. Usa `_bug_detection_metrics` que já existe.
- **RQ2 (síntese):** hipóteses do gabarito como entrada controlada (decisão pendente com o
  orientador). Métrica: `success@k` = chegou a um veredito do grupo verificado
  (`CONFIRMED`, `ESBMC_MISSED`, `UNVALIDATED`, `OTHER_FAILURE`, `NOT_CONFIRMED`)
  em até k chamadas.
- **RQ3 (ponta a ponta):** contagem de `CONFIRMED` nos 104 casos, com todos os vereditos
  somando 104.
- **Ablação principal:** reparo com retorno do ESBMC contra 3 amostras independentes
  com o mesmo orçamento (Olausson et al., ICLR 2024).

## 8. Referências verificadas (DBLP, ACM DL, arXiv, 2026-09-29)

- Beyer, Dangl, Lemberger, Tautschnig. *Tests from Witnesses: Execution-Based Validation of
  Verification Results.* TAP 2018, LNCS 10889. doi:10.1007/978-3-319-92994-1_1.
  Uso: validar contraexemplo executando o programa.
- Clarke, Grumberg, Jha, Lu, Veith. *Counterexample-Guided Abstraction Refinement.* CAV 2000,
  LNCS 1855, pp. 154-169. Uso: contraexemplo espúrio de abstração.
- Olausson et al. *Is Self-Repair a Silver Bullet for Code Generation?* ICLR 2024.
  Uso: reparo precisa ser comparado com amostragem de mesmo custo.
- Chen et al. *Evaluating Large Language Models Trained on Code.* arXiv:2107.03374, 2021.
  Uso: estimador de pass@k / success@k.
- Zhang et al. *How Effective Are They? Exploring Large Language Model Based Fuzz Driver
  Generation.* ISSTA 2024. doi:10.1145/3650212.3680355. Uso: geração de driver por LLM
  falha em APIs complexas; consultas repetidas e iterativas ajudam.
- Amusuo, Liu, Calvo Mendez, Metzman, Chang, Davis. *FalseCrashReducer: Mitigating False
  Positive Crashes in OSS-Fuzz-Gen Using Agentic AI.* arXiv:2510.02185, 2025.
  Uso: drivers gerados produzem falhas espúrias por estado de entrada irreal.
- Wu, Barrett, Narodytska. *Lemur: Integrating Large Language Models in Automated Program
  Verification.* ICLR 2024. Uso: LLM propõe, verificador decide.
- Farias et al. *ESBMC-Python: A Bounded Model Checker for Python Programs.* ISSTA 2024
  (tool demo). doi:10.1145/3650212.3685304.
- Widyasari et al. *BugsInPy: a database of existing bugs in Python programs to enable
  controlled testing and debugging studies.* ESEC/FSE 2020. doi:10.1145/3368089.3417943.

## 9. Limitações declaradas

- Estado do receptor (atributos) é sobreaproximado: uma confirmação em método vale
  "se o objeto puder estar nesse estado". A viabilidade do estado não é provada
  (mesmo problema do FalseCrashReducer).
- A reexecução enumera valores pequenos (inteiros de -1 a 2, listas de até 2 itens,
  `None` primeiro, até 400 execuções). Não achar reprodução não prova ausência.
- O isolamento da reexecução é um subprocesso local com limite de tempo e memória, sem
  contêiner. Código com `import` fora da lista segura, `open`, `eval` e similares não é
  executado (`host_replay_problem`).
- Uma confirmação com stub depende de a biblioteca poder devolver o valor usado; a análise
  deve separar confirmados com e sem `stubbed_imports`.
- Classe que se instancia com argumentos dentro do próprio método alvo não funciona com a casca
  (o `__init__` substituto não recebe argumentos); o caso sai `UNSUPPORTED`.
- O ESBMC roda com `--unwind N` (não `--incremental-bmc`: com `--multi-property` ele imprime
  FAILED e UNKNOWN juntos, medido em 2026-09-29); um bug que exige mais de N iterações sai
  `NOT_CONFIRMED`.
