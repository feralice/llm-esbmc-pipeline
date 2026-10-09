# Prompt para pedir uma segunda opinião a outro modelo

Copie tudo abaixo da linha para o outro modelo. Se ele tiver acesso ao repositório, diga também em
que pasta ele está; se não tiver, o texto basta.

---

Sou mestranda em verificação de software. Minha pesquisa combina um LLM com o ESBMC (model checker
limitado, frontend Python) para achar e **confirmar formalmente** bugs de execução em código Python
real. Preciso de ideias concretas para aumentar o número de bugs que o ESBMC confirma. Quero uma
segunda opinião crítica, não elogios.

## O método

1. **Detecção:** o LLM lê uma função real e aponta bugs (expressão, linha, propriedade violada) e
   diz se o bug é verificável pelo ESBMC.
2. **Harness (nível 1):** o LLM só informa os tipos das entradas em JSON; o código monta o programa
   para o ESBMC: recorte da função original, intacta, mais stubs para bibliotecas, mais um driver
   com entradas `nondet_*` e `__ESBMC_assume`.
3. **Verificação:** ESBMC 8.5.0 (`--unwind 5 --multi-property`, Bitwuzla, com Boolector e Z3 como
   reserva). Depois o CPython reexecuta o código original com os valores do contraexemplo. Só é
   `CONFIRMED` se o ESBMC aponta a violação e o CPython reproduz a mesma exceção na linha do bug.
4. **Orquestrador (quando o nível 1 trava):** lê a mensagem de erro e escolhe outra tentativa:
   agente (Claude Code, ou um LLM via API em ciclo com o ESBMC) que escreve o harness à mão; busca no
   CPython por uma entrada que quebre; ESBMC de novo com essa entrada fixada.
5. **Validação:** confere que a função verificada é a original (nenhuma alteração em 23 de 23), que um
   "seguro" alcança a linha do bug (3 eram vazios) e roda o mesmo harness na versão corrigida do bug
   (controle).

Regras que não posso quebrar: a função verificada não pode ser alterada (só o que está em volta
dela); regras gerais, nunca ajustadas a um caso do dataset; o pipeline não pode usar a versão
corrigida nem o patch para decidir (só para avaliar); evidência do CPython sozinha não conta como
confirmação formal.

## Dataset

289 bugs reais de projetos Python (a maioria de BugsInPy, mais alguns minerados: pandas, keras,
youtube-dl, scrapy, thefuck, black, tornado, matplotlib, fastapi, luigi...). Cada um tem a versão com
bug, a corrigida e o gabarito (função, expressão do bug, linha onde quebra, tipo de falha). Tipos de
falha: 178 dão resultado errado sem quebrar, 59 exceção local, 23 exceção modelável, 24 exceção que
depende do ambiente, 5 incertos.

## Números

- Detecção (Claude Sonnet): função do bug em 64%, linha em 30% (277 bugs). Com um prompt melhor, a
  linha sobe cerca de 50% numa amostra de 50.
- **Confirmados pelo ESBMC na linha do bug: 7.** Isso é a métrica principal e não sobe.
- Num conjunto de 20 casos em que o LLM já acertou a linha: 3 confirmados. Agentes, busca no CPython e
  entrada fixada acrescentaram 0 confirmações formais (a busca achou 3 quebras no CPython, que não
  contam).

## Por que o ESBMC não confirma (229 hipóteses de uma rodada completa)

| Motivo | Casos |
|---|---|
| ESBMC-Python recusa o programa (construção não suportada, exceção interna) | 72 |
| Falta contexto (módulo, classe ou função de fora do recorte) | 64 |
| O harness automático não sabe montar (função aninhada, `*args`, decorador, stub sem tipo) | 51 |
| O pipeline não acha a função ou a expressão no código | 17 |
| Harness com tipos errados | 10 |
| Já têm veredito | 15 |

Exemplos de recusa ou travamento do ESBMC-Python 8.5.0, com reprodutores mínimos:

- método chamado em `None`, comparação com `None`, `x + 1` com `x: Optional[int] = None`: o ESBMC diz
  "seguro" (falso negativo);
- `tag in classes` com `classes = None`: exceção interna do ESBMC;
- `float("abc")`: "seguro";
- `"%s %s" % (a, b)` com valores nondet, `add(*xs)`, `async def`: recusados;
- `for p in lista_global: if p in s` com `s = None`: não termina em 60 s, enquanto a mesma checagem sem
  o laço termina em 2 s;
- strings `nondet_str()` dentro de `set`/`frozenset`: estoura tempo e memória (900 s, 4,5 GB).

## O que já tentei e não subiu a confirmação

- Agente escrevendo o harness à mão (Claude Code com plugin do ESBMC; LLM via API em ciclo com o
  ESBMC): esbarra nas mesmas recusas.
- Mais tempo (900 s): passa a faltar memória.
- Fixar no ESBMC a entrada que o CPython achou: continua estourando o tempo.
- Bound menor: o laço não completa e o caminho do bug fica inalcançável.

## O que estou considerando

- Harness para bugs de resultado errado: o LLM escreve uma pós-condição (`assert result != 'None'`), o
  ESBMC procura entradas que a violam e o CPython confirma; sem usar a versão corrigida para decidir.
- Compilar o ESBMC mais novo (há correções do frontend Python depois da 8.5.0).

## Onde está o código (se você tiver acesso à máquina)

- **ESBMC (código-fonte, master atualizado):** `/mnt/c/Users/ferna/esbmc` (no Windows,
  `C:\Users\ferna\esbmc`); também em https://github.com/esbmc/esbmc. Partes que interessam:
  - `src/python-frontend/`: conversão de Python para o modelo do ESBMC (onde estão as recusas);
  - `src/python-frontend/models/` e `src/c2goto/library/python/`: modelos de `str`, `list`, `dict`
    etc. (o `.lower()` e as listas são modelados ali, em laços);
  - `regression/python/`: testes do frontend Python, bons para ver o que é suportado.
  O binário usado é o 8.5.0 (`/usr/local/bin/esbmc`); há correções do frontend Python no master
  depois dele, ainda não compiladas.
- **Pipeline (código da pesquisa):**
  `/mnt/c/Users/ferna/Documents/mestrado/llm_esbmc/.claude/worktrees/validacao-deteccao`
  - `src/research_pipeline/verify/`: harness e verificação (`render.py` monta o programa,
    `slicing.py` faz o recorte e os stubs, `loop.py` coordena, `esbmc_run.py` roda o ESBMC,
    `replay.py`/`replay_worker.py` reexecutam no CPython, `routing.py`/`orchestrator.py` escolhem as
    novas tentativas, `pinned.py` fixa a entrada);
  - `src/research_pipeline/verify/esbmc_python_notes.md`: o que o ESBMC-Python aceita, segundo o
    que medimos;
  - `docs/projeto/possiveis_problemas/`: os 18 reprodutores mínimos de limites do ESBMC-Python, com
    README;
  - `docs/experimentos/README.md`: todas as rodadas e resultados;
  - `docs/ESTADO.md`: resumo do estado atual;
  - `artifacts/v2/full-2026-10-05-regrounded/`: a rodada completa, com os programas gerados em
    `artifacts/v2/full-2026-10-04-sonnet/programs/` (dá para rodar o ESBMC em qualquer um deles).
- **Dataset:** `dataset/bugs_reais/` dentro do pipeline (`arquivo_com_bug/`, `arquivo_corrigido/`,
  `ground_truths.json`).

## O que eu quero de você

1. Ideias concretas, em ordem de chance de aumentar as confirmações formais, para o harness ou para o
   uso do ESBMC, respeitando as regras acima. Para cada uma: o que mudar, por que funcionaria, como
   medir num conjunto pequeno, e o risco (inclusive de falso positivo ou de "trapaça" que invalide a
   confirmação).
2. Uma crítica do método: há algo que estou fazendo que impede o ESBMC de rodar e que eu não percebi?
3. Se a resposta honesta for que o limite é a ferramenta, diga isso e sugira como apresentar o
   resultado numa dissertação.
