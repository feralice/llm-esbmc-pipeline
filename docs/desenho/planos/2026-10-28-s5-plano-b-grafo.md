# S5, plano B: grafo de chamadas na ordenação, no contexto, no agente e nos smells

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** usar o grafo de chamadas que o modo scan já monta (`scan/callgraph.py`) nos quatro pontos que a literatura conferida em 28/10 aponta, cada um atrás de uma flag ou variante, para medir contra a versão sem grafo.

**Architecture:** um módulo novo, `scan/graph_metrics.py`, concentra o que se calcula sobre o grafo: centralidade, fatias de fluxo de dados, smells de arquitetura e métricas de Feature Envy. Quem usa: a ordenação do scan (`scan/pipeline.py`), uma variante de prompt nova (A20), uma ferramenta de consulta copiada para a pasta de cada caso do agente e um relatório de smells do scan. Nada muda no comportamento padrão: tudo entra por flag ou variante.

**Tech Stack:** Python 3.12, `ast`, `networkx` 3.6.1 (já instalado, passa a constar no `requirements.txt`), pytest.

**Spec:** linha S5 de `docs/projeto/PLANO_2026-10-19.md`, itens 5 a 8, com as referências conferidas: Zimmermann e Nagappan (ICSE 2008), LLMxCPG (USENIX Security 2025), LocAgent (ACL 2025), CKGFuzzer (ICSE 2025), Arcan (ICSA Workshops 2017), iSMELL (ASE 2024).

## Global Constraints

- Branch `master`, sem branch por feature. Commit só com o ok da Fernanda, sem coautoria; corpo da mensagem em arquivo, `git commit -F`.
- Comportamento padrão inalterado: a ordenação do scan só muda com `--scan-rank pagerank`, o contexto só com a variante `A20`, o agente só com `--graph-tool` e os smells só com `--scan-smells`.
- Prompts e textos para o agente em inglês; documentos dela em português, sem travessão.
- Suíte completa (`timeout 600 .venv/bin/python -m pytest -q`) antes de cada commit.
- Sem chamada a LLM nos testes.

## Review Focus

- Grafo vazio ou função sem chamadores: centralidade, fatia e métricas devolvem valores neutros, sem exceção. Teste nas Tarefas 1, 2 e 5.
- Recursão e ciclos de chamada: o PageRank converge e a fatia não entra em laço. Teste nas Tarefas 1 e 2.
- Arquivo do dataset com uma função só (o caso comum de `funcao_com_bug`): a variante A20 não pode deixar o prompt maior que o A12 que ela substitui. Teste na Tarefa 2.
- Ferramenta de consulta com nome que não existe ou ambíguo: responde "not found" ou lista as opções, nunca quebra o agente. Teste na Tarefa 3.
- Import circular entre módulos de pacote que só aparece por import tardio dentro de função: conta como ciclo, como `_bindings` já faz. Teste na Tarefa 4.

---

### Tarefa 1: Centralidade na ordenação do scan (item 5)

**Files:**
- Create: `src/research_pipeline/scan/graph_metrics.py`
- Modify: `src/research_pipeline/scan/pipeline.py` (`rank_key`, `select_targets`, `plan_scan`), `src/main.py` (flag `--scan-rank`), `requirements.txt`
- Test: `tests/test_scan_graph_metrics.py`, `tests/test_scan_pipeline.py`

**Interfaces:**
- Consumes: `CallGraph` (`functions`, `calls`, `callers()`).
- Produces: `pagerank(graph: CallGraph) -> dict[str, float]` (chave = `FunctionNode.key`, soma 1 sobre as funções do grafo); `select_targets(graph, *, limit=None, rank: str = "callers")`; `Target.centrality: float`.

- [ ] **Step 1: testes que falham**
  - `test_pagerank_ranks_the_most_called_helper_first`: grafo de 3 funções em que `a` e `b` chamam `h`; `pagerank` dá a maior nota a `h`.
  - `test_pagerank_handles_recursion_and_empty_graphs`: função que chama a si mesma converge; grafo sem arestas dá notas iguais; grafo vazio dá `{}`.
  - `test_select_targets_by_pagerank_keeps_risky_first`: com `rank="pagerank"`, funções com divisão ou subscrito continuam antes; entre elas, a de maior centralidade vem primeiro.
  - `test_default_rank_is_unchanged`: sem `rank`, a ordem é a de hoje.
- [ ] **Step 2:** rodar; esperado: FAIL.
- [ ] **Step 3:** `pagerank` com `networkx.pagerank` sobre o grafo dirigido chamador → chamado (só arestas resolvidas, sem `MODULE_CALLER`). No `rank_key`, com `rank="pagerank"`, trocar `-target.callers` por `-target.centrality`. Gravar `rank` e as notas em `scan_selection.json`. Acrescentar `networkx==3.6.1` ao `requirements.txt`.
- [ ] **Step 4:** rodar; esperado: PASS.
- [ ] **Step 5:** commit.

### Tarefa 2: Fatia de fluxo de dados dos chamadores, variante A20 (item 6)

**Files:**
- Modify: `src/research_pipeline/scan/graph_metrics.py`, `src/research_pipeline/llm/prompts.py`, `src/research_pipeline/llm/prompt_variants.py`
- Test: `tests/test_scan_graph_metrics.py`, `tests/test_prompt_variants.py`

**Interfaces:**
- Produces: `caller_slices(graph: CallGraph, key: str, *, max_chars: int = 3_000) -> str`: para cada chamada da função, só as linhas do chamador das quais os argumentos dependem (fatia para trás, dentro do chamador, pelos nomes atribuídos), mais a linha da chamada; variante `"A20"` registrada em `VARIANTS`, com a seção `<UNTRUSTED_CONTEXT_CALLER_SLICES>`.

- [ ] **Step 1: testes que falham**
  - `test_slice_keeps_only_the_lines_the_arguments_depend_on`: no chamador `n = len(xs); log("x"); k = n - 1; f(xs, k)`, a fatia de `f` tem as linhas de `n`, `k` e a chamada, e não tem `log`.
  - `test_slice_follows_reassignment_and_stops_at_parameters`: um nome reatribuído duas vezes traz as duas linhas; um parâmetro do chamador aparece como `# parameter` e a fatia para ali.
  - `test_slice_of_function_without_callers_is_empty` e `test_slice_survives_loops_in_the_caller` (atribuição dentro de `for` não trava).
  - `test_a20_prompt_is_not_larger_than_a12_on_a_single_function_file`.
- [ ] **Step 2:** rodar; esperado: FAIL.
- [ ] **Step 3:** implementar a fatia sobre o `ast` do chamador: partindo dos nomes usados nos argumentos, voltar pelas atribuições (`Assign`, `AugAssign`, `AnnAssign`, alvos de `for`) que definem esses nomes antes da linha da chamada, até ponto fixo. A A20 usa o mesmo caminho que a A12 para achar o grafo (`file_callers` em `prompts.py`) e o mesmo texto de contexto, trocando o bloco inteiro pela fatia. Texto da seção em inglês, no formato da `_CALLEES` da A19.
- [ ] **Step 4:** rodar; esperado: PASS.
- [ ] **Step 5:** commit.

### Tarefa 3: Grafo consultável pelo agente do harness (item 7)

**Files:**
- Create: `src/research_pipeline/verify/graph_tool.py` (script autocontido, copiado para a pasta do caso)
- Modify: `src/research_pipeline/verify/agent_arm.py` (`run_agent_arm(..., graph_tool: bool = False)`, instalação e linha no prompt), `scripts/v2_agent_arm.py` (flag `--graph-tool`, campo `graph_tool` em `variant` e `COMPARED_FIELDS`)
- Test: `tests/test_verify_graph_tool.py`, `tests/test_verify_agent_arm.py`, `tests/test_v2_agent_arm_script.py`

**Interfaces:**
- Produces: na pasta do caso, `graph.py` com os comandos `python graph.py callers NAME`, `callees NAME`, `class NAME` e `where NAME`, lendo `graph.json` (o `CallGraph.to_dict()` do arquivo `original.py`, mais o código de cada função e classe). Saída em texto curto: chamada com as linhas ao redor, ou o código da classe.

- [ ] **Step 1: testes que falham**
  - `test_callers_prints_each_call_site_with_context`, `test_class_prints_its_source`.
  - `test_unknown_name_says_not_found`, `test_ambiguous_name_lists_the_options`.
  - `test_graph_tool_is_installed_and_named_in_the_prompt`: com `graph_tool=True`, a pasta do caso tem `graph.py` e `graph.json` e o prompt cita `python graph.py`; com `False`, nada disso.
  - `test_graph_tool_flag_reaches_the_arm` no script.
- [ ] **Step 2:** rodar; esperado: FAIL.
- [ ] **Step 3:** implementar. Linha do prompt, em inglês: "Before writing a stub, ask the call graph of original.py how the code really uses a name: `python graph.py callers NAME`, `callees NAME`, `class NAME`, `where NAME`. Build stubs and inputs from what real callers pass."
- [ ] **Step 4:** rodar; esperado: PASS.
- [ ] **Step 5:** commit.

### Tarefa 4: Smells de arquitetura no scan, sem LLM (item 8, parte 1)

**Files:**
- Modify: `src/research_pipeline/scan/graph_metrics.py`, `src/research_pipeline/scan/pipeline.py`, `src/main.py` (flag `--scan-smells`)
- Test: `tests/test_scan_graph_metrics.py`

**Interfaces:**
- Produces: `architecture_smells(graph: CallGraph) -> list[dict]` com `{"smell": "cyclic_dependency" | "hub_like_dependency", "modules": [...], "evidence": str}`; com `--scan-smells`, o scan grava `scan_smells.json`.

- [ ] **Step 1: testes que falham**
  - `test_cycle_between_two_modules_is_reported`: `a` chama `b` e `b` chama `a` (inclusive por import dentro de função).
  - `test_hub_like_needs_both_high_fan_in_and_fan_out`: um módulo com fan-in e fan-out acima do limiar é hub; um com só fan-in alto não é.
  - `test_no_smells_on_an_acyclic_project`.
- [ ] **Step 2:** rodar; esperado: FAIL.
- [ ] **Step 3:** grafo de módulos a partir das chamadas resolvidas entre módulos diferentes. Ciclo = componente fortemente conexo com mais de um módulo (`networkx.strongly_connected_components`). Hub = fan-in e fan-out acima da mediana do projeto e somando mais que a metade dos módulos, a regra do Arcan sobre o grafo de dependências.
- [ ] **Step 4:** rodar; esperado: PASS.
- [ ] **Step 5:** commit.

### Tarefa 5: Feature Envy com métricas do grafo no prompt (item 8, parte 2)

**Files:**
- Modify: `src/research_pipeline/scan/graph_metrics.py`, `src/research_pipeline/scan/pipeline.py`
- Create: `src/research_pipeline/prompts/smell_feature_envy.txt`
- Test: `tests/test_scan_graph_metrics.py`, `tests/test_scan_pipeline.py`

**Interfaces:**
- Produces: `feature_envy_metrics(graph: CallGraph, key: str) -> dict` com `own_accesses` (atributos e métodos de `self`), `foreign_accesses` por classe ou parâmetro e `foreign_calls` por módulo; `envy_candidates(graph) -> list[str]`, os métodos em que algum `foreign_accesses` supera `own_accesses`; com `--scan-smells`, cada candidato vai ao LLM com o prompt `smell_feature_envy.txt` e as métricas, e a resposta (smell sim ou não, para qual classe mover, justificativa) entra em `scan_smells.json`.

- [ ] **Step 1: testes que falham**
  - `test_metrics_count_self_and_foreign_accesses`: em `Pedido.total`, `self.itens` conta como próprio e `cliente.nome`, `cliente.cpf` como de `cliente`.
  - `test_envy_candidates_need_more_foreign_than_own`.
  - `test_method_without_self_access_has_zero_own_and_is_not_crashed`.
  - `test_scan_smells_sends_only_candidates_to_the_llm`: com um LLM falso, só os candidatos viram chamada, e o resultado vai para `scan_smells.json`.
- [ ] **Step 2:** rodar; esperado: FAIL.
- [ ] **Step 3:** implementar. O prompt (inglês) mostra o método, a classe dele e a tabela de métricas, e pede JSON `{"feature_envy": bool, "move_to": str, "reason": str}`, seguindo o iSMELL (saída de ferramenta no prompt). Sem gabarito de smells, o resultado é exploratório e sai marcado assim no arquivo.
- [ ] **Step 4:** rodar; esperado: PASS.
- [ ] **Step 5:** commit.

### Tarefa 6: Registro

**Files:**
- Modify: `docs/experimentos/README.md`, `docs/projeto/PLANO_2026-10-19.md` (estado de S5)

- [ ] **Step 1:** registrar o que entrou e como cada parte será medida em S6: A20 contra A5 e A19 na comparação pareada do S3; `--graph-tool` como variante no S2; `--scan-rank pagerank` e `--scan-smells` no piloto do scan (AWS), sem gabarito.
- [ ] **Step 2:** commit.
