# Verificação de bugs em software Python de sistemas ciber-físicos e embarcados - Plano de Projeto

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aplicar a metodologia já existente de detecção e verificação de bugs guiada por LLM (research_pipeline, modo `hybrid`/V2) a um corpus pequeno (5 a 10 casos) de bugs reais minerados de software Python de sistemas ciber-físicos ou embarcados, como projeto da disciplina PGENE601/PPGINF554, produzindo um relato comparativo entre esse corpus e o corpus geral já avaliado no V2.

**Architecture:** Nenhuma mudança de arquitetura no pipeline. A pipeline já existente (`src/main.py --mode hybrid`, `research_pipeline/scan/`) roda sem alteração sobre um novo diretório de dataset (`dataset/disciplina_pgene601/geral/`), seguindo o mesmo esquema de `manifest.json` já usado em `dataset/v2_real_world/manifest.json` (campos `id`, `detection_file`, `harness_file`, `categories`, `expression`, `provenance`, `oracle`). O trabalho novo é inteiramente de dados (seleção de corpus, mineração de bugs, preparação de arquivos de detecção neutros) e de análise (comparação de métricas, discussão de limitações), não de código de pipeline.

**Tech Stack:** Python 3.9+, ESBMC-Python (frontend Python do ESBMC), o backend de LLM já configurado no `.env` (qualquer um dos suportados: openai, anthropic, google, ollama, codex ou claude_cli).

**Spec:** Definida nesta conversa, sem documento de especificação separado. Resumo: o método de síntese de harness guiada por LLM, já validado em Python de propósito geral (dataset V2), deve ser reavaliado sobre software Python de contexto ciber-físico ou embarcado, para verificar se a taxa de confirmação formal se mantém e se surgem categorias de bug ou limitações específicas do domínio.

## Global Constraints

- Escopo fixo em 5 a 10 bugs reais no corpus geral novo, mais até 3 bugs de
  condição de corrida ou deadlock num dataset separado, só se o candidato
  escolhido tiver esse tipo de bug documentado; não expandir para um dataset
  do tamanho do V2 (120 casos). O objetivo do projeto da disciplina é mostrar
  transferência de método, não construir um dataset grande.
- O dataset de condição de corrida e deadlock fica em diretório próprio
  (`dataset/disciplina_pgene601/concorrencia/`), separado do corpus geral
  (`dataset/disciplina_pgene601/geral/`), porque usa flags de verificação diferentes
  (`--data-races-check`, `--deadlock-check`, `--context-bound`) das já
  documentadas por categoria no `README.md` do projeto. Cada item desse
  dataset carrega o campo `recommended_flags` no próprio `manifest.json`, no
  mesmo formato de texto livre já usado em `dataset/v2_real_world/manifest.json`
  (ex.: item `oob_real_02`, campo `recommended_flags` com a flag e a razão
  entre parênteses).
- Reaproveitar a arquitetura de `research_pipeline/` sem reescrever; qualquer ajuste de código deve ser mínimo e justificado por uma limitação real encontrada durante a mineração ou a execução, não por preferência de estilo.
- As datas de entrega vêm do cronograma fixo de PGENE601/PPGINF554 e não são renegociáveis pela aluna: Dev(1) 01 e 06/10, Dev(2) 08 e 13/10, Dev(3) 15 e 20/10, Dev(4) 22 e 27/10, Dev(5) 29/10 e 03/11, artigo 05/11 a 08/12.
- Documentos entregues ao professor seguem tom acadêmico formal, sem travessão (—) e sem caminho de arquivo ou comando exposto; a versão de trabalho detalhada (com comandos e caminhos) fica separada, neste repositório.
- Nenhum commit ou push deste projeto sem pedido explícito.

---

### Task 0: Proposta de uma página para o ponto de controle de hoje (22/09)

**Files:**
- Create: `docs/projeto/proposta_projeto_cps_2026-09-22.md`

**Interfaces:**
- Produces: o texto de uma página que a aluna vai apresentar na aula síncrona de hoje, cobrindo pergunta de pesquisa, corpus candidato e critério de seleção, recorte e cronograma resumido.

- [ ] **Step 1: Escrever a proposta**

Conteúdo do arquivo, em tom acadêmico formal, sem travessão e sem caminho de arquivo:

```markdown
# Proposta de projeto: verificação formal guiada por LLM em software Python de sistemas ciber-físicos e embarcados

## Pergunta de pesquisa

O método de detecção e verificação de bugs guiado por LLM, já validado em
software Python de propósito geral, mantém uma taxa de confirmação formal
comparável quando aplicado a software Python que controla ou interage com
sistemas ciber-físicos e embarcados?

## Motivação

Python é hoje usado nesse domínio por meio de interpretadores para
microcontrolador (MicroPython, CircuitPython) e de bibliotecas cliente de
robótica (pacotes Python do ROS2). O método de síntese de harness e
verificação formal já desenvolvido nunca foi avaliado sobre esse tipo de
código, cujo comportamento costuma depender de hardware, temporização e
protocolos de comunicação, características ausentes no corpus já testado.

## Corpus proposto

Cinco a dez bugs reais, com commit de correção documentado, minerados de um
entre estes candidatos: bibliotecas de dispositivo do CircuitPython, o
próprio interpretador MicroPython, ou pacotes cliente Python do ROS2. A
escolha final depende de qual candidato tiver histórico de bugs
suficientemente documentado para permitir a mineração com a mesma exigência
de proveniência já usada no projeto (função, expressão e commit de origem
confirmados). Além das oito categorias já usadas no corpus geral, este
projeto também considera condição de corrida e deadlock como categorias
candidatas, já que o frontend Python do ESBMC verifica `threading.Thread` e
`threading.Lock` com as flags `--data-races-check` e `--deadlock-check`, e
esse tipo de bug é comum em código de sistema ciber-físico com leitura
concorrente de sensor ou callback assíncrono.

## Método

Reaplicação do método já existente: a LLM localiza a função, a categoria e a
expressão suspeitas a partir do código neutro; um harness com entradas
simbólicas é sintetizado; o ESBMC verifica formalmente a hipótese; uma etapa
de ablação confirma se alguma pré-condição assumida mascarou o bug.

## Entregável final

Relato comparativo entre a taxa de confirmação formal nesse corpus e a
taxa já obtida no corpus geral, incluindo discussão das limitações do
verificador especificamente para código de contexto embarcado.
```

- [ ] **Step 2: Revisar contra as regras de escrita da aluna**

Conferir manualmente: nenhum travessão no texto, nenhum item de lista
consecutivo com o mesmo padrão gramatical, nenhum caminho de arquivo ou
comando de terminal exposto (esta é a versão para o professor, não a versão
de trabalho).

- [ ] **Step 3: Apresentar oralmente no ponto de controle de hoje**

Sem commit necessário neste passo; o arquivo fica como registro no
repositório de trabalho.

---

### Task 1: Seleção do corpus e mineração dos bugs (Dev 1, 01 e 06/10)

**Files:**
- Create: `dataset/disciplina_pgene601/geral/manifest.json`
- Create: `dataset/disciplina_pgene601/geral/README.md`
- Create: `dataset/disciplina_pgene601/geral/bugs/` (um arquivo `.py` por caso, harness humano de referência)
- Create: `dataset/disciplina_pgene601/geral/detection/` (um arquivo `.py` por caso, código neutro sem pista do bug)
- Create: `dataset/disciplina_pgene601/concorrencia/manifest.json` (só se o Step 1 achar bug de condição de corrida ou deadlock no candidato escolhido)
- Create: `dataset/disciplina_pgene601/concorrencia/README.md`
- Create: `dataset/disciplina_pgene601/concorrencia/bugs/`
- Create: `dataset/disciplina_pgene601/concorrencia/detection/`

**Interfaces:**
- Consumes: nenhuma dependência de tarefa anterior.
- Produces: `dataset/disciplina_pgene601/geral/manifest.json` no mesmo esquema de
  `dataset/v2_real_world/manifest.json` (`id`, `detection_file`,
  `harness_file`, `categories`, `expression`, `provenance` com `project`,
  `buggy_commit`, `fixed_commit`, `source_file`, `source_function`, `oracle`
  com `kind` e `expression`). `dataset/disciplina_pgene601/concorrencia/manifest.json`
  segue o mesmo esquema, mais o campo `recommended_flags` em cada item
  (texto livre com a flag e a razão, no mesmo formato do item `oob_real_02`
  de `dataset/v2_real_world/manifest.json`). Tarefas seguintes (2 a 5) leem
  os dois manifestos e os arquivos de `detection/` de cada um.

- [ ] **Step 1: Avaliar viabilidade de mineração dos três candidatos**

Para cada candidato (CircuitPython, MicroPython, pacotes Python do ROS2),
verificar no rastreador de issues e no histórico de commits do projeto: (a)
existe um número razoável de issues fechadas com referência a um commit de
correção; (b) o commit de correção isola uma função ou um trecho pequeno,
sem exigir reescrever uma classe inteira; (c) a função corrigida não depende
de acesso direto a hardware que o ESBMC-Python não consegue modelar (leitura
de registrador, interrupção); (d) verificar também, como critério extra, se
o projeto tem bugs de condição de corrida documentados envolvendo
`threading.Thread` ou `threading.Lock` puro (sem `RLock`, sem kwarg
`daemon=`, sem `args=` como lista), já que esse é o subconjunto que o
frontend Python do ESBMC verifica hoje. Registrar o resultado dessa
avaliação nas primeiras linhas de `dataset/disciplina_pgene601/geral/README.md`, com o
candidato escolhido e a justificativa.

- [ ] **Step 2: Minerar de 5 a 10 bugs do candidato escolhido**

Para cada bug: identificar o commit buggy e o commit de correção, a função
de origem, o arquivo de origem e a expressão exata que causa o defeito,
seguindo o mesmo padrão de proveniência de
`dataset/v2_real_world/manifest.json`.

- [ ] **Step 3: Escrever o harness de referência e o arquivo de detecção de cada caso**

Em `dataset/disciplina_pgene601/geral/bugs/<id>.py`, reproduzir a função buggy com um harness
mínimo que comprove o bug sob o ESBMC-Python (entradas simbólicas com
`nondet_*()`, `assert` ou violação nativa, seguindo os mesmos padrões
documentados no skill de uso do ESBMC-Python). Em
`dataset/disciplina_pgene601/geral/detection/<id>.py`, manter apenas a função original, sem
comentário ou docstring que revele a categoria do bug.

- [ ] **Step 4: Escrever `dataset/disciplina_pgene601/geral/manifest.json`**

Um item por caso, no mesmo formato de `dataset/v2_real_world/manifest.json`,
incluindo `evaluation_policy` com `patch_context_items` vazio, a menos que
algum caso exija contexto do patch para fazer sentido, como aconteceu com
três casos do V2.

- [ ] **Step 5: Confirmar os harnesses manualmente com o ESBMC**

Rodar cada arquivo de `dataset/disciplina_pgene601/geral/bugs/` diretamente pelo ESBMC e
confirmar que o veredito é uma violação real, não uma falha de sintaxe ou um
falso positivo do harness. Registrar o comando e o veredito de cada caso na
versão de trabalho (não na proposta formal).

- [ ] **Step 6: Se o Step 1 achou bug de condição de corrida, minerar até 3 casos em `dataset/disciplina_pgene601/concorrencia/`**

Repetir os Steps 2 a 5 para até 3 bugs de condição de corrida ou deadlock,
restritos ao subconjunto que o frontend Python do ESBMC verifica hoje
(`threading.Thread` com `target=` e `args=` como tupla, `threading.Lock`,
sem `RLock` e sem kwarg `daemon=`). Em cada item de
`dataset/disciplina_pgene601/concorrencia/manifest.json`, preencher `recommended_flags`
como texto livre, por exemplo:

```json
"recommended_flags": "--incremental-bmc --data-races-check --context-bound 2 (necessário porque o corpus geral usa --assign-param-nondet, que não modela threads; confirmado com o exemplo threading_thread_race_fail do próprio ESBMC)"
```

Importante: `recommended_flags` é um campo de documentação lido por uma
pessoa, não pelo pipeline automaticamente (o mesmo já vale para os itens do
V2 que usam esse campo). A Task 2 roda esse dataset como uma execução
separada da pipeline, com esses flags passados via `--esbmc-command`.

- [ ] **Step 7: Commit**

Perguntar à aluna antes de commitar, conforme a regra do projeto de nunca
commitar sem pedido explícito.

---

### Task 2: Primeira rodada e relato da etapa de detecção (Dev 2, 08 e 13/10)

**Files:**
- Create: `artifacts/disciplina_pgene601/geral/end-to-end/` (diretório de saída da execução do corpus geral)
- Create: `artifacts/disciplina_pgene601/concorrencia/end-to-end/` (diretório de saída da execução do corpus de concorrência, só se a Task 1 Step 6 tiver rodado)
- Create: `docs/projeto/dev2_deteccao_cps.md`

**Interfaces:**
- Consumes: `dataset/disciplina_pgene601/geral/manifest.json` e `dataset/disciplina_pgene601/geral/detection/` da
  Task 1; opcionalmente `dataset/disciplina_pgene601/concorrencia/manifest.json` e
  `dataset/disciplina_pgene601/concorrencia/detection/`.
- Produces: `artifacts/disciplina_pgene601/geral/end-to-end/v2_report.json` e, se aplicável,
  `artifacts/disciplina_pgene601/concorrencia/end-to-end/v2_report.json`, consumidos pelas
  Tasks 3, 4 e 5 (os mesmos relatórios, lidos em estágios diferentes).

- [ ] **Step 1: Rodar o pipeline ponta a ponta sobre o corpus geral**

```bash
PYTHONPATH=src .venv/bin/python src/main.py \
  --mode hybrid --v2-stage end-to-end \
  --input dataset/disciplina_pgene601/geral/detection \
  --ground-truth dataset/disciplina_pgene601/geral/manifest.json \
  --output-dir artifacts/disciplina_pgene601/geral/end-to-end \
  --verbose
```

Observação: `--ground-truth` neste comando aponta para o próprio manifesto,
já que a etapa de comparação com gabarito em `v2_evaluator.py` lê os campos
`id`, `detection_file` e `categories` diretamente dele quando não existe um
arquivo `ground_truths.json` separado; se a execução reclamar de arquivo
ausente, copiar o manifesto para `dataset/disciplina_pgene601/geral/ground_truths.json` mantendo
somente os campos `id` e `categories` de cada item.

- [ ] **Step 2: Se existir, rodar o pipeline sobre o corpus de concorrência com as flags certas**

O corpus geral roda com o bound e as flags padrão da pipeline
(`--assign-param-nondet`, ver `README.md` do projeto), que não modelam
threads. O corpus de concorrência precisa de `--data-races-check` e
`--deadlock-check`, então roda como uma execução separada com
`--esbmc-command` customizado:

```bash
PYTHONPATH=src .venv/bin/python src/main.py \
  --mode hybrid --v2-stage end-to-end \
  --input dataset/disciplina_pgene601/concorrencia/detection \
  --ground-truth dataset/disciplina_pgene601/concorrencia/manifest.json \
  --output-dir artifacts/disciplina_pgene601/concorrencia/end-to-end \
  --esbmc-command esbmc --incremental-bmc --data-races-check --deadlock-check --context-bound 2 \
  --verbose
```

- [ ] **Step 3: Extrair só a parte de detecção dos relatórios**

Em cada `v2_report.json` gerado (corpus geral e, se existir, corpus de
concorrência), ler o bloco `detection` (`hypotheses`, `candidates`,
`failed_units`) sem olhar ainda `results` ou `evaluation`, que pertencem à
síntese e à verificação, tratadas na Task 3.

- [ ] **Step 4: Escrever o relato do ponto de controle**

Em `docs/projeto/dev2_deteccao_cps.md`: quantas unidades foram analisadas em
cada corpus, quantas hipóteses a LLM gerou, quais categorias apareceram e se
alguma categoria nova, ausente da taxonomia atual, foi sugerida pela LLM.

- [ ] **Step 5: Commit**

Perguntar à aluna antes de commitar.

---

### Task 3: Síntese, verificação e relato de confirmação formal (Dev 3, 15 e 20/10)

**Files:**
- Modify: `docs/projeto/dev2_deteccao_cps.md` não é alterado; criar um novo arquivo.
- Create: `docs/projeto/dev3_verificacao_cps.md`

**Interfaces:**
- Consumes: `artifacts/disciplina_pgene601/geral/end-to-end/v2_report.json` e, se existir,
  `artifacts/disciplina_pgene601/concorrencia/end-to-end/v2_report.json`, já produzidos na
  Task 2 (mesmas execuções, sem rodar de novo).
- Produces: taxa de confirmação formal do corpus geral e, separadamente, do
  corpus de concorrência, usadas na comparação da Task 4.

- [ ] **Step 1: Ler o restante de cada relatório já gerado**

Em cada `v2_report.json`, ler `results` (classificação por caso:
`confirmed_native`, `confirmed_driver`, `confirmed_on_abstraction`,
`confirmed_unverified`, `over_restricted`, `esbmc_inconclusive`) e
`evaluation.end_to_end` (`tp`, `fp`, `fn`, `precision`, `recall`, `f1`). No
relatório do corpus de concorrência, também conferir se a mensagem de
violação contém "data race" ou "deadlock", confirmando que o veredito veio
da checagem de concorrência e não de outra propriedade.

- [ ] **Step 2: Calcular a taxa de confirmação formal de cada corpus**

Taxa de confirmação formal = número de casos confirmados (`confirmed_native`
mais `confirmed_driver` mais `confirmed_on_abstraction`) dividido pelo total
de casos do corpus, calculada separadamente para o corpus geral e para o de
concorrência.

- [ ] **Step 3: Escrever o relato do ponto de controle**

Em `docs/projeto/dev3_verificacao_cps.md`: a taxa calculada, quantos casos
ficaram inconclusivos e por quê, e se algum caso precisou de mais de uma
tentativa de síntese (`repaired_then_confirmed`) para ser confirmado.

- [ ] **Step 4: Commit**

Perguntar à aluna antes de commitar.

---

### Task 4: Comparação com o corpus geral do V2 (Dev 4, 22 e 27/10)

**Files:**
- Create: `docs/projeto/dev4_comparacao_v2_vs_cps.md`

**Interfaces:**
- Consumes: a taxa de confirmação formal do corpus novo (Task 3) e os
  números já publicados do corpus geral em
  `docs/projeto/complemento_apresentacao_2026-09-23.md` (recall ponta a
  ponta de 22,1% sobre 104 casos, 23 confirmações formais de 28 hipóteses
  corretas).
- Produces: uma tabela comparativa, usada como uma das seções do artigo (Task 6).

- [ ] **Step 1: Montar a tabela comparativa**

Colunas: corpus, número de casos, hipóteses corretas de função e categoria,
confirmações formais, taxa de confirmação formal, recall ponta a ponta. Uma
linha para o corpus geral do V2, outra para o corpus novo de sistemas
ciber-físicos e embarcados, e uma terceira linha para o corpus de
concorrência, se ele existir, com recall marcado como não comparável quando
`evaluate_detection` estiver desativado ou quando a etapa de detecção tiver
sido pulada nessa execução.

- [ ] **Step 2: Analisar se a distribuição de categorias muda**

Comparar a distribuição de categorias de bug entre os dois corpora (por
exemplo, se `integer_overflow` ou `assertion_violation` aparecem com mais
frequência no corpus embarcado, por causa de aritmética de ponto fixo ou de
verificação de limites de sensor).

- [ ] **Step 3: Escrever o relato do ponto de controle**

Em `docs/projeto/dev4_comparacao_v2_vs_cps.md`: a tabela, a análise de
distribuição de categorias, e uma primeira hipótese sobre a causa de
qualquer diferença observada na taxa de confirmação.

- [ ] **Step 4: Commit**

Perguntar à aluna antes de commitar.

---

### Task 5: Ablação e limitações específicas do domínio embarcado (Dev 5, 29/10 e 03/11)

**Files:**
- Create: `docs/projeto/dev5_ablacao_limitacoes_cps.md`

**Interfaces:**
- Consumes: o campo de ablação de cada caso confirmado em
  `artifacts/disciplina_pgene601/geral/end-to-end/v2_report.json` (já gerado na Task 2, etapa de
  ablação roda automaticamente a menos que `--no-ablation` tenha sido
  passado, o que não é o caso aqui).
- Produces: a seção de discussão de limitações do artigo (Task 6).

- [ ] **Step 1: Ler os resultados de ablação de cada caso confirmado**

Para cada caso com `classification` igual a `confirmed_native`,
`confirmed_driver` ou `confirmed_on_abstraction`, verificar se a ablação
encontrou algum `__ESBMC_assume` que, removido, muda o veredito para
`over_restricted`.

- [ ] **Step 2: Levantar limitações do ESBMC-Python específicas do domínio embarcado**

Revisar as pegadinhas já documentadas do frontend Python do ESBMC (divisão
float não checada por padrão, `nondet_float()` incluindo NaN e Inf,
fatiamento de valor morto) e avaliar quais delas afetam especificamente
código que simula leitura de sensor, conversão de unidade física ou
aritmética de ponto fixo, comuns no corpus minerado.

- [ ] **Step 3: Se existir corpus de concorrência, documentar a fronteira de suporte usada**

Registrar explicitamente quais construções de `threading` foram usadas nos
casos minerados (`Thread` com `target=` e `args=` como tupla, `Lock`) e
confirmar que nenhum caso dependeu de construção não suportada pelo frontend
Python do ESBMC (`RLock`, kwarg `daemon=`, `args=` como lista, os padrões de
subclasse de `Thread` marcados como não suportados na suíte de regressão do
ESBMC). Isso não é uma limitação encontrada no projeto, é a fronteira já
conhecida do verificador, documentada para dar precisão ao relato.

- [ ] **Step 4: Escrever o relato do ponto de controle**

Em `docs/projeto/dev5_ablacao_limitacoes_cps.md`: quantos casos confirmados
tiveram pré-condição verificada pela ablação, quais limitações do
verificador foram observadas na prática e como elas se comparam às já
conhecidas do corpus geral.

- [ ] **Step 5: Commit**

Perguntar à aluna antes de commitar.

---

### Task 6: Redação do artigo (05/11 a 08/12, quatro pontos de controle)

**Files:**
- Create: `docs/projeto/artigo_cps_rascunho.md`

**Interfaces:**
- Consumes: as Tasks 1 a 5 completas (corpus, detecção, verificação, comparação, limitações).
- Produces: o rascunho final entregue na disciplina.

- [ ] **Step 1 (ponto de controle de 12 e 17/11): introdução e motivação**

Escrever, em `docs/projeto/artigo_cps_rascunho.md`, a introdução com a
pergunta de pesquisa (igual à da Task 0) e a motivação (Python em contexto
ciber-físico e embarcado via MicroPython, CircuitPython e ROS2), em tom
acadêmico, sem travessão.

- [ ] **Step 2 (ponto de controle de 19 e 24/11): método**

Adicionar a seção de método, descrevendo o pipeline de detecção, síntese de
harness, verificação formal e ablação já usado no corpus geral, sem incluir
caminho de arquivo ou comando; descrever em prosa o que cada etapa faz.

- [ ] **Step 3 (ponto de controle de 26/11 e 01/12): resultados**

Adicionar a seção de resultados com a tabela comparativa da Task 4 e as
métricas de ablação da Task 5, reescritas em prosa acadêmica a partir dos
relatos técnicos já produzidos.

- [ ] **Step 4 (ponto de controle de 03 e 08/12): discussão e conclusão**

Adicionar a discussão das limitações encontradas e a conclusão, respondendo
diretamente à pergunta de pesquisa da introdução: o método transferiu com
taxa comparável, transferiu com taxa menor, ou revelou uma categoria de
limitação que só aparece em código de contexto embarcado.

- [ ] **Step 5: Commit**

Perguntar à aluna antes de commitar.
