# Self-healing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao LLM a chance de consertar as falhas que hoje param antes dele (grounding, dependência, recusa do
frontend), com conhecimento tirado do checkout do ESBMC e código real das funções chamadas via grafo.

**Architecture:** Um wrapper `verify_with_healing` em volta de `verify_hypothesis`: quando o veredito é
consertável, um `Healer` produz um `Patch` (edições no texto-fonte em memória mais definições acrescentadas),
o código valida o patch e o verify roda de novo, até 3 rodadas. O conhecimento vem de um índice lexical do
checkout do ESBMC, refeito quando o commit muda.

**Tech Stack:** Python 3.12, `ast`, pytest, `LLMClient` (`claude_cli`), ESBMC master `5d17828`.

**Spec:** `docs/superpowers/specs/2026-10-19-self-healing-design.md`

## Global Constraints

- Nome do mecanismo: self-healing. Status novo: `LLM_ONLY`.
- No máximo 3 rodadas de conserto por hipótese (além das 2 do loop de spec).
- B1: profundidade 2.
- B3: no máximo 2 trechos do README e 3 testes de regressão por consulta; busca lexical, sem embeddings.
- Stub escrito pelo LLM devolve só `nondet_*` (ou `None` com `-> None`); sem `raise`, sem `assert`.
- O corpo da função alvo nunca muda (`astutil.body_signature` igual); só a assinatura pode ganhar anotações.
- A métrica avalia a hipótese original; o arquivo original nunca é alterado.
- Trabalho em `master`, sem commit até a Fernanda pedir. Testes: `.venv/bin/python -m pytest -q`.

## Review Focus

- Patch cujo `old` não aparece no fonte, ou aparece mais de uma vez: recusar o patch, não aplicar o primeiro.
- LLM devolve texto fora do formato JSON pedido: contar como rodada gasta, sem exceção que derrube o lote.
- Checkout do ESBMC ausente ou sem `regression/python`: índice vazio, healing segue sem B3.
- Grafo com duas definições do mesmo nome (ambíguo): não inclui nenhuma, cai para stub.
- Hipótese de resultado errado (A15) consertada: o oráculo de valor e o controle com a corrigida continuam valendo.

---

### Task 1: Pré-requisitos no master

**Files:**
- Modify: `tests/test_verify_esbmc_integration.py:238`
- Investigate: `src/research_pipeline/verify/string_witness.py`, `tests/test_verify_string_witness.py`

- [ ] **Step 1:** Mudar a expectativa de `metodo_append` para `ACEITA` no master (o 27 foi corrigido), com
  comentário de uma linha citando o commit `5d17828`.
- [ ] **Step 2:** Reproduzir `string_witness` vazio com `esbmc` do master no programa do teste e achar a causa
  (formato do `--generate-pytest-testcase` mudou ou o witness não sai). Consertar o parser se o formato mudou;
  se o ESBMC deixou de gerar, registrar e manter o teste marcado como `xfail` com o motivo.
- [ ] **Step 3:** `.venv/bin/python -m pytest -q tests/test_verify_esbmc_integration.py tests/test_verify_string_witness.py` passa.

### Task 2: Índice de conhecimento do ESBMC (B3)

**Files:**
- Create: `src/research_pipeline/verify/esbmc_knowledge.py`
- Test: `tests/test_esbmc_knowledge.py`

**Interfaces:**
- Produces: `KnowledgeIndex(commit: str, sections: list[Snippet], tests: list[Snippet])`;
  `Snippet(source: str, title: str, text: str)`; `build_index(esbmc_root: Path) -> KnowledgeIndex`;
  `load_index(esbmc_root: Path, cache_dir: Path) -> KnowledgeIndex` (refaz quando o commit muda);
  `lookup(index: KnowledgeIndex, message: str, code: str, max_chars: int = 4000) -> str`;
  `esbmc_root_of(esbmc_command: list[str]) -> Path | None` (sobe do binário até achar `src/python-frontend`).

- [ ] **Step 1: Testes** com um checkout falso em `tmp_path`: README com seções "Features Supported" e
  "Limitations"; `regression/python/a/main.py` + `test.desc` `CORE`; `regression/python/b` com `KNOWNBUG`.
  - `test_build_index_keeps_core_tests_and_drops_knownbug`: `b` fora, `a` dentro.
  - `test_lookup_ranks_by_message_words`: mensagem com `annotation` traz a seção que fala de anotação primeiro.
  - `test_lookup_caps_snippets`: no máximo 2 seções e 3 testes.
  - `test_load_index_rebuilds_on_new_commit`: commit novo, cache refeito.
  - `test_missing_checkout_gives_empty_index`.
- [ ] **Step 2:** Rodar e ver falhar.
- [ ] **Step 3:** Implementar. Seções = cabeçalhos `##`/`###` do `src/python-frontend/README.md`; testes =
  `regression/python/*/test.desc` cuja primeira linha é `CORE` ou `THOROUGH`. Pontuação: palavras (≥ 3 letras,
  minúsculas, sem stopwords simples) em comum entre a consulta e o snippet, com peso maior para nomes de nós
  do AST e métodos extraídos de `code`. Commit via `git -C root rev-parse HEAD`. Cache em JSON.
- [ ] **Step 4:** Testes passam.

### Task 3: Patch e validação

**Files:**
- Create: `src/research_pipeline/verify/healing.py`
- Test: `tests/test_healing_patch.py`

**Interfaces:**
- Produces: `Patch(edits: tuple[tuple[str, str], ...] = (), definitions: str = "", hypothesis_function: str = "",
  hypothesis_expression: str = "")`; `apply_patch(source: str, patch: Patch) -> str` (levanta `PatchError`);
  `patch_problems(original: str, patched: str, function: str) -> list[str]`.

- [ ] **Step 1: Testes**
  - `test_edit_must_match_once`: `old` ausente ou repetido → `PatchError`.
  - `test_definitions_appended_after_imports`.
  - `test_target_body_change_is_rejected`: mudar uma linha do corpo → problema citando a função.
  - `test_signature_annotation_is_allowed`.
  - `test_stub_with_concrete_return_is_rejected`: `def f() -> list: return []` → problema.
  - `test_stub_with_nondet_return_is_accepted`; `test_stub_with_raise_is_rejected`.
- [ ] **Step 2:** Rodar e ver falhar.
- [ ] **Step 3:** Implementar. Validação das definições: toda função acrescentada tem `return` só de chamada
  `nondet_*`, de `None` (com `-> None`) ou de instância de classe acrescentada no mesmo patch; nenhuma tem
  `raise`/`assert`. Corpo da alvo comparado com `body_signature`.
- [ ] **Step 4:** Testes passam.

### Task 4: Healer (LLM) e código real pelo grafo (B1, B2)

**Files:**
- Modify: `src/research_pipeline/verify/healing.py`
- Create: `src/research_pipeline/prompts/healing_prompt.txt`
- Test: `tests/test_healing_healer.py`

**Interfaces:**
- Consumes: `Patch`, `lookup`, `CallGraph` (`scan/callgraph.py`).
- Produces: `HEALABLE = frozenset({GROUNDING_FAILED, MISSING_DEPENDENCY, UNSUPPORTED})`;
  `graph_definitions(names: set[str], graph: CallGraph, depth: int = 2, max_chars: int = 20000) -> str`;
  `class Healer: __init__(self, llm, knowledge: KnowledgeIndex | None, graph: CallGraph | None = None)`;
  `Healer.propose(h: BugHypothesis, source: str, verdict: str, reason: str, previous: list[dict]) -> Patch | None`.

- [ ] **Step 1: Testes** com LLM falso (devolve JSON fixo):
  - `test_grounding_patch_keeps_literal_expression`: o LLM devolve função e expressão; expressão que não está
    no código → `None`.
  - `test_missing_dependency_uses_graph_before_llm`: grafo com a definição de `helper` em outro arquivo →
    `Patch.definitions` traz o código real e o LLM não é chamado.
  - `test_ambiguous_graph_name_falls_back_to_llm`.
  - `test_unsupported_prompt_carries_knowledge`: o prompt enviado contém o texto devolvido por `lookup`.
  - `test_unparseable_reply_returns_none`.
- [ ] **Step 2:** Rodar e ver falhar.
- [ ] **Step 3:** Implementar. Prompt único com seções por tipo de falha; resposta JSON
  `{"function", "expression", "edits": [{"old","new"}], "definitions"}`. Grounding: mandar a lista de funções
  do arquivo e o código da função de nome mais parecido. Dependência: nomes extraídos do `reason`; primeiro
  `graph_definitions`, depois o LLM. Recusa: mensagem + linha do programa + `lookup`.
- [ ] **Step 4:** Testes passam.

### Task 5: Wrapper, `LLM_ONLY` e funil

**Files:**
- Modify: `src/research_pipeline/verify/healing.py`, `src/research_pipeline/verify/outcome.py`,
  `src/research_pipeline/verify/loop.py` (só se precisar expor algo), `scripts/v2_funnel.py`
- Test: `tests/test_healing_loop.py`, `tests/test_v2_funnel.py` (se existir; senão no mesmo arquivo)

**Interfaces:**
- Produces: `verify_with_healing(h, *, healer: Healer | None, rounds: int = 3, spec_llm_after_heal=None,
  **verify_kwargs) -> VerifyResult`; `LLM_ONLY = "LLM_ONLY"` em `outcome.VERDICTS`;
  `VerifyResult.healing: list[dict]` (rodada, veredito antes, patch, problemas).

- [ ] **Step 1: Testes** com `verify_hypothesis` falso:
  - `test_healable_verdict_gets_rounds_then_llm_only`: 3 rodadas sem veredito → `LLM_ONLY`, motivo final guardado.
  - `test_checked_verdict_is_not_healed`: `NOT_CONFIRMED` volta direto.
  - `test_result_keeps_original_hypothesis`.
  - `test_invalid_patch_spends_a_round`.
  - `test_without_healer_is_identity`.
  - funil: `LLM_ONLY` cai em estágio novo `so_llm`, entre `esbmc_recusou` e `esbmc_rodou_sem_confirmar`.
- [ ] **Step 2:** Rodar e ver falhar.
- [ ] **Step 3:** Implementar. Fonte consertada só em memória; depois de um patch, a spec vem de
  `spec_llm_after_heal` quando dado (a spec salva pode não servir mais).
- [ ] **Step 4:** Testes passam; suíte inteira passa.

### Task 6: Ligação nas entradas

**Files:**
- Modify: `scripts/v2_replay_specs.py`, `src/main.py` (e2e V2 e scan), `src/research_pipeline/verify/agent_arm.py`
- Test: `tests/test_v2_replay_specs.py` (novo, só o parse de flags e a estimativa)

- [ ] **Step 1:** `v2_replay_specs.py`: `--heal {none,error,error+kb}`, `--heal-backend`, `--heal-model`,
  `--strategy {repair,resample}`, `--esbmc-root` (padrão: `esbmc_root_of`), `--estimate` (imprime quantas
  hipóteses são consertáveis e o máximo de chamadas, e sai).
- [ ] **Step 2:** `src/main.py`: mesmas flags `--heal*` no e2e V2 e no scan; no scan o `Healer` recebe `plan.graph`.
- [ ] **Step 3:** `agent_arm.py`: acrescentar o bloco de `lookup` ao prompt do agente, junto das notas de 8.5.
- [ ] **Step 4:** Suíte inteira passa; `pylint` sem erro novo nos arquivos tocados.

### Task 7: Medição e registro

- [ ] **Step 1:** Montar a base (hipóteses na linha, bugs não confirmados, veredito consertável) a partir da
  rodada final e salvar a lista de ids.
- [ ] **Step 2:** Braço 0 (master, sem B) com `--estimate` e depois a rodada. Sem LLM.
- [ ] **Step 3:** Estimar e **avisar a Fernanda** antes dos braços 1, 2 e 3 (usam a assinatura).
- [ ] **Step 4:** Funil e controle com a versão corrigida em cada braço.
- [ ] **Step 5:** Registrar a Fase 23 em `docs/experimentos/README.md` (data, pasta, commit, comando, resultado).
- [ ] **Step 6:** Scan em Adafruit_CircuitPython_GPS com e sem B, depois pynmea2, com estimativa avisada antes.
