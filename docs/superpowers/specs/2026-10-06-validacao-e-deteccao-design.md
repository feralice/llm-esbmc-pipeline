# Validação dos vereditos e melhoria da detecção (V2)

Data: 2026-10-06. Escopo: partes **V** (validação) e **3** (detecção) do roteiro combinado em 06/10.
As partes 1 (grafo no arquivo), 2 (harness novo, abordagem híbrida), 4 (grafo no repositório e
modo scan) e 0 (processos órfãos) têm especificação própria; a 0 entra aqui como pré-requisito
porque a validação roda longas sequências de ESBMC.

## 1. Objetivo

Responder duas perguntas, nesta ordem, usando o dataset `dataset/bugs_reais` (289 bugs, gabarito
com `failure_kind` e `crash_expressions`):

1. **Os vereditos do pipeline são confiáveis?** Um `CONFIRMED` é o código original quebrando, e um
   "seguro" significa que o caminho do bug foi de fato examinado.
2. **Como fazer a LLM achar mais bugs?** Medindo cada mudança de prompt isoladamente (ablação),
   para saber o que ajudou de verdade.

Fora de escopo: mudar o harness (parte 2), o grafo (partes 1 e 4), corrigir o ESBMC (os 17
reprodutores de `docs/projeto/possiveis_problemas` já estão com o orientador).

## 2. Ponto de partida (medido em 04 a 06/10)

Rodada `artifacts/v2/full-2026-10-05-regrounded` (Claude Sonnet 5.5 via `claude_cli`, nível 1, 277
arquivos) e agente `artifacts/v2/agent-2026-10-05-sonnet` mais `agent-2026-10-06-e2e`.

| Bugs que quebram (82) | |
|---|---|
| LLM não reportou nada | 18 |
| LLM reportou outra linha da função | 18 |
| LLM achou a linha (causa ou quebra) | 46 |
| Confirmados na linha (nível 1 + agente) | 7 |

Nos de resultado errado (166): nada reportado 63, outra linha 69, linha certa 34. Média de 1,9
achados por função. Padrão observado nas falhas: a LLM não considera parâmetros que podem ser
`None` (`nm_real_07`, `nm_real_10`, `nm_real_20`).

## 3. Parte 0 (pré-requisito): processos órfãos

Quando o agente estoura o tempo, o ESBMC que ele disparou continua rodando, ignora `SIGTERM` e
acumula memória (21 de 23 GB em 06/10; travamento do WSL em 29/09). Correção: o agente e tudo o
que ele dispara rodam num grupo de processos próprio; no tempo esgotado, o grupo inteiro recebe
`SIGKILL`. Critério: depois de uma rodada longa não sobra nenhum `esbmc` mais velho que o limite
do caso.

## 4. Parte V: validação

Tudo aqui roda **sem chamar a LLM**: reaproveita os programas e especificações salvos nas rodadas
(como `scripts/v2_replay_specs.py` e `scripts/v2_agent_reverify.py` já fazem).

### V1. Preservação (a LLM não alterou a função)

- **O que checa:** a função verificada no programa do harness é a mesma do arquivo original,
  comparada pela AST sem docstrings. A única diferença aceita são as reescritas do catálogo de
  equivalência (hoje, `%` em `compat.py`), registradas em `transforms`.
- **Onde:** já existe no agente (`target_preserved`). Falta aplicar a todo veredito do nível 1 e
  reportar a taxa.
- **Regra:** veredito com função alterada fora do catálogo não conta como `CONFIRMED` nem como
  "seguro"; vira `TARGET_ALTERED`, contado à parte.

### V2. Vacuidade (o "seguro" examinou o caminho do bug?)

- **O que checa:** se a linha da hipótese é alcançável sob as pré-condições do harness.
- **Como:** numa cópia do programa, insere `__ESBMC_unreachable()` imediatamente antes do
  statement da hipótese e roda o ESBMC com `--enable-unreachability-intrinsic`, mesmo
  `--unwind` e mesmo solver do veredito original. Testado no ESBMC 8.5.0 instalado em 06/10.
- **Leitura:**
  - `reachability: unreachable code reached` violado: **alcançável**, o veredito não é vazio;
  - verificação bem-sucedida sem nenhuma `unwinding assertion` violada: **inalcançável**, o
    "seguro" era vazio;
  - `unwinding assertion` violada, tempo esgotado ou erro: **inconclusivo** (nunca "vazio").
- **Proibido:** `--no-unwinding-assertions` junto com a checagem (dá "inalcançável" falso em laço
  truncado; regra da CLAUDE.md global).
- **Aplica-se a:** todo `NOT_CONFIRMED` e `ESBMC_MISSED`, e por amostra aos `CONFIRMED` (como
  sanidade: tem que dar alcançável).
- **Regra nova de veredito:** `NOT_CONFIRMED` inalcançável vira `NOT_CONFIRMED_VACUOUS`.

### V3. Teste de mutação (o harness detecta bug quando existe?)

- **Mutações naturais:** cada par versão com bug / versão corrigida. A matriz por hipótese é:
  confirma no bug e não no corrigido (sensível e específico); confirma nos dois (falso alarme,
  como `ir_real_03` e `bip_thefuck_11`); confirma em nenhum. Já temos os dados
  (`artifacts/v2/control-fixed-2026-10-06`); falta a matriz e o relatório.
- **Mutações artificiais:** para cada harness que chegou a um veredito, gera cópias da função com
  uma falha injetada perto da linha da hipótese e confere se o pipeline a detecta. Operadores,
  todos produzindo falhas que levantam exceção (o que o ESBMC pode ver):
  1. remover uma guarda (`if x is None: return ...`, `if not xs: return ...`);
  2. trocar um valor por `None` num argumento ou atribuição;
  3. somar 1 a um índice (`xs[i]` para `xs[i + 1]`);
  4. trocar `<` por `<=` numa condição de laço ou de índice.
  Mutante **morto** = o pipeline acusa violação e o CPython reproduz. **Taxa de mutação** por
  harness = mortos / gerados. Mutantes equivalentes (que não mudam o comportamento) são
  descartados pela reexecução no CPython: se nenhuma entrada quebra o mutante, ele não conta.
- **Leitura para a dissertação:** taxa alta significa que um "seguro" desse harness tem valor; taxa
  baixa aponta harness que não exercita o código.

### Entregas da V

- `scripts/v2_validate.py`: lê uma rodada e escreve `validation.json` com V1, V2 e V3 por hipótese.
- Seção `validation` no resumo: taxa de preservação, de vacuidade e de mutação, e os vereditos
  reclassificados.
- Testes unitários para cada leitura (alcançável, inalcançável, inconclusivo; cada operador de
  mutação; preservação com e sem reescrita do catálogo), cada um mostrado falhando sem a regra.

## 5. Parte 3: detecção

### Variantes (uma mudança por vez, contra a linha de base)

| Id | Mudança no prompt V2 | Hipótese |
|---|---|---|
| A0 | prompt atual (linha de base) | |
| A1 | tirar "prefira não reportar quando falta contexto": reportar e preencher `context_needed` | reduz os 18 "nada reportado" |
| A2 | checklist de partição de entradas: para cada parâmetro e atributo, considerar `None`, vazio, zero, tipo diferente, chave ausente, índice fora do intervalo | ataca o padrão do `None` |
| A3 | pedir até N hipóteses por função, ordenadas pela chance de serem bug | mais cobertura; o ESBMC filtra |
| A4 | k execuções independentes (k = 3) e união dos achados | variação da LLM vira cobertura |
| A5 | combinação das variantes que melhoraram | |

Regras: exemplos do checklist são genéricos e nunca tirados do dataset; nenhuma variante vê o
gabarito, o patch ou o arquivo corrigido.

### Execução

- Só a etapa de detecção, sem verificação: precisa de um modo que pare depois da detecção (hoje
  `--v2-stage end-to-end` sempre verifica). A verificação roda depois só na variante final.
- Modelo e backend iguais à linha de base: `claude-sonnet-5-5` via `claude_cli` (assinatura).
- Variação da LLM: A0 e a variante final rodam 2 vezes no dataset inteiro; o resultado reporta as
  duas.

### Métricas (por tipo de bug: quebra alcançável, quebra não modelável, resultado errado)

- função certa; linha certa (causa ou quebra); nada reportado;
- achados por função e achados fora do gabarito (custo de ruído);
- triagem (`evaluation.triage`);
- tempo e tokens por função (telemetria).

Critério de aceite de uma variante: aumenta a linha certa nos bugs que quebram acima da variação
entre as duas rodadas de A0, sem dobrar os achados por função.

## 6. Ordem e dependências

1. Parte 0 (processos órfãos).
2. V1 e V2 sobre as rodadas existentes; V3 com as mutações naturais.
3. V3 com mutações artificiais.
4. Modo "só detecção"; A0 (segunda rodada) e A1 a A4.
5. A5 e a rodada completa (detecção, verificação, agente) com a melhor variante, mais V em cima.

Nada disso começa antes de terminar a rodada do agente em andamento
(`artifacts/v2/agent-2026-10-06-e2e`), por cota e memória.

## 7. Registro

Toda rodada (validação, cada variante de detecção, cada repetição) entra em
`docs/experimentos/README.md` antes de o resultado ser discutido: data, pasta de saída, commit,
comando, entrada e resultado. Mudança não commitada usada numa rodada é anotada como tal.

## 8. Riscos

- **Checagem de alcance cara:** um ESBMC a mais por hipótese. Limite de 180 s, sequencial.
- **Mutantes que o ESBMC não aceita:** contam como "não gerado", não como "sobrevivente".
- **Cota da assinatura:** cada variante de detecção custa uma passada de 277 funções (cerca de
  300 chamadas). As rodadas retomam pelo checkpoint se a cota acabar.
- **Achados a mais com A1 e A3:** medidos pelo custo de ruído; a triagem e o ESBMC filtram.
