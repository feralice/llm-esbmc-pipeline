# V2 verificação de hipótese: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** trocar a cascata de 6 estratégias do `scan/` por um caminho único: hipótese congelada → recorte verbatim → especificação de entrada em JSON pela LLM → harness montado por código → ESBMC → reexecução no CPython → veredito.

**Architecture:** pacote novo `src/research_pipeline/verify/`, um arquivo por responsabilidade. Reaproveita `scan/context.py::context_module`, `scan/rewrite_guard.py::_find_function/_expression_nodes/_undefined_globals`, `scan/replay.py::host_replay_problem`, `scan/capability.py::diagnose_esbmc`, `verification/esbmc_runner.py::run_esbmc_direct` e o transporte HTTP de `scan/synth.py::HarnessSynthesizer`. Ligado ao `src/main.py` por `--v2-engine verify`.

**Tech Stack:** Python 3.12, `ast`, pytest, ESBMC 8.5.0 oficial (`/usr/local/bin/esbmc`).

**Spec:** `docs/superpowers/specs/2026-09-29-v2-verificacao-de-hipotese-design.md`

## Global Constraints

- Sem commit sem pedido explícito da usuária; sem `Co-Authored-By` de IA; trabalhar em `master` (sem branch neste repo).
- Nenhuma chamada paga de API sem aprovação de custo; testes usam LLM falsa.
- Não mexer em `dataset/v2_real_world/{detection,bugs}/`, `manifest.json`, `ground_truths.json`.
- Nada do gabarito (`bugs/`, `ground_truths.json`) alimenta prompt, exceto no modo de síntese isolada já existente.
- Texto para a usuária sem travessão.
- Suíte: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider`.
- Testes que chamam ESBMC real são marcados e pulam quando `/usr/local/bin/esbmc` não existe.

## Review Focus

- Método de classe cujo `__init__` exige argumentos: o método alvo deve sair byte a byte igual no programa montado.
- Hipótese cuja expressão aparece duas vezes na função: escolher a ocorrência mais próxima da linha informada.
- Especificação com tipo fora da lista ou pré-condição com chamada: rejeitar antes do ESBMC.
- Programa com `import` de módulo externo: não executar no host; veredito sem reexecução.
- Exceção reproduzida numa linha fora do trecho da hipótese: `OTHER_FAILURE`, nunca `CONFIRMED`.

---

### Task 1: hipótese congelada e aterramento

**Files:** Create `src/research_pipeline/verify/__init__.py`, `verify/hypothesis.py`, `verify/grounding.py`; Test `tests/test_verify_grounding.py`.

**Interfaces (Produces):**
- `BugHypothesis(file: str, function: str, suspect_expression: str, line: int = 0, trigger_condition: str = "", category: str = "")`, frozen; property `hypothesis_id -> str`; `BugHypothesis.from_candidate(candidate: ScanCandidate, line: int = 0)`.
- `ground(h: BugHypothesis, source: str) -> Grounded | GroundingFailure`.
- `Grounded(function: str, class_name: str | None, method_name: str, span: tuple[int, int], suspect_lines: tuple[str, ...], params: tuple[Param, ...], receiver_attrs: tuple[str, ...], module: str, needs_shell: bool)`; `Param(name: str, annotation: str | None)`.
- `GroundingFailure(reason: str)`.

- [ ] Testes: expressão presente → `span` correto; ausente → `GroundingFailure`; duas ocorrências → a mais próxima de `h.line`; método → `receiver_attrs` = atributos `self.x` lidos pelo método e pelos métodos `self.m()` que ele chama; `module` contém o texto verbatim da função.
- [ ] Rodar e ver falhar; implementar; rodar e ver passar.

### Task 2: especificação de entrada

**Files:** Create `verify/spec.py`; Test `tests/test_verify_spec.py`.

**Interfaces (Produces):**
- `InputSpec(params: dict[str, str], attributes: dict[str, str], assumptions: tuple[str, ...])`; `parse_spec(text: str) -> InputSpec` (levanta `ValueError`).
- `TypeShape(kind: str, elem: str | None = None, optional: bool = False)`; `parse_type(text: str) -> TypeShape | None`.
- `spec_problems(spec: InputSpec, grounded: Grounded) -> list[str]`.

- [ ] Testes: `Optional[list[int]]`, `int | None`, `list[str]` aceitos; `dict[str,int]` e `Foo` recusados; parâmetro sem tipo e sem anotação → problema; pré-condição com chamada ou nome desconhecido → problema; JSON inválido → `ValueError`.

### Task 3: montagem do programa

**Files:** Create `verify/render.py`; Test `tests/test_verify_render.py`.

**Interfaces (Produces):** `render_program(grounded: Grounded, spec: InputSpec) -> Program`; `Program(source: str, driver_start: int, transforms: tuple[str, ...])`.

- [ ] Testes: função livre → `main()` com nondet por tipo e chamada; `Optional` gerado com `if nondet_bool():` (sem ternário); método com construtor com argumento → `__init__` trocado, método alvo inalterado (comparar texto), transform `receiver_init_replaced` registrado; métodos não dunder não alcançáveis removidos; pré-condições viram `__ESBMC_assume`.

### Task 4: reexecução concreta no CPython

**Files:** Create `verify/replay.py`, `verify/replay_worker.py`; Test `tests/test_verify_replay.py`.

**Interfaces (Produces):** `concrete_replay(program: Program, grounded: Grounded, *, max_runs: int = 400, timeout_seconds: int = 20) -> ReplayVerdict`; `ReplayVerdict(status: str, exception_type: str = "", line: int | None = None, runs: int = 0, reason: str = "")` com `status` em `reproduced | other_failure | not_reproduced | unavailable`.

- [ ] Testes: divisão por zero alcançável → `reproduced`; guarda que impede → `not_reproduced`; exceção em outra linha → `other_failure`; `import os` → `unavailable`; assume violado descarta a execução.

### Task 5: decisão sobre o resultado do ESBMC

**Files:** Create `verify/outcome.py`; Test `tests/test_verify_outcome.py`.

**Interfaces (Produces):** constantes de veredito da spec §5; `classify_esbmc(result: ESBMCDirectResult) -> EsbmcReading`; `EsbmcReading(kind: str, message: str)` com `kind` em `violation | safe | repairable | missing_dependency | timeout | error`; `final_verdict(reading: EsbmcReading, replay: ReplayVerdict) -> str`.

- [ ] Testes: tabela da spec §5 linha a linha; `unwinding assertion` sozinho não conta como violação; `Cannot open file` → `missing_dependency`.

### Task 6: laço com a LLM

**Files:** Create `verify/loop.py`, `src/research_pipeline/prompts/input_spec_prompt.txt`; Modify `scan/synth.py` (extrair `complete(system, user, *, json_mode=False) -> SynthResult` de `synthesize`); Test `tests/test_verify_loop.py`.

**Interfaces (Produces):** `verify_hypothesis(h: BugHypothesis, *, llm, source_path: Path, esbmc_command: list[str], bound: int, timeout_seconds: int, work_dir: Path, max_repairs: int = 2) -> VerifyResult`; `VerifyResult.to_dict()`; `run_verify(hypotheses, **kw) -> list[VerifyResult]`.

- [ ] Testes com LLM falsa e ESBMC falso: especificação inválida → reparo com a lista de problemas → válida; erro reparável → nova tentativa com a mensagem; SUCCESSFUL → para sem reparo; 3 falhas → `SPEC_FAILED`; `hypothesis_id` igual em todas as tentativas.

### Task 7: ligação no `main.py` e relatório

**Files:** Modify `src/main.py`; Test `tests/test_verify_cli.py`.

- [ ] `--v2-engine {legacy,verify}` (padrão `legacy`), `--verification-sources DIR` (troca o arquivo pelo de `DIR` com o mesmo nome quando existir).
- [ ] Relatório `v2_verify_report.json`: config (com versão do ESBMC), vereditos por caso, contagem por veredito, métricas de localização (`_bug_detection_metrics`).

### Task 8: rodada de fumaça sem API

- [ ] Script `scripts/v2_verify_smoke.py`: hipóteses do gabarito em 10 casos de `detection_full/`, especificação escrita por uma LLM falsa que devolve tipos das anotações; ESBMC real. Registrar vereditos.
- [ ] Suíte completa verde; `pylint` nos arquivos novos.
