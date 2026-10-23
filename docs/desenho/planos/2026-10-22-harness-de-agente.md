# Harness de agente: plano de implementação

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: usar superpowers:subagent-driven-development (recomendado) ou
> superpowers:executing-plans para executar tarefa por tarefa. Os passos usam caixas (`- [ ]`) para
> acompanhamento.

**Objetivo:** o pipeline faz sozinho o que o `/esbmc` faz na mão: leva o código real ao ESBMC com o plugin, se
corrige com o erro do ESBMC, registra cada rodada e só confirma um bug quando o comportamento no caminho do bug
não mudou, entregando o teste pytest gerado pelo próprio ESBMC.

**Arquitetura:** o braço de agente que já existe (`verify/agent_arm.py`, `scripts/v2_agent_arm.py`) ganha
skills do projeto copiadas para a pasta de cada caso, um `esbmc` de fachada que grava cada rodada, e um fiscal
maior (mypy, teste diferencial em dois níveis, pytest do ESBMC). O caderno de reparos é um arquivo revisado pela
Fernanda. A comparação final roda os dois braços numa amostra fixa.

**Tecnologias:** Python 3.12, pytest, mypy 2.1 (já no `.venv`), Claude Code CLI (`claude -p`) com o plugin
`esbmc-plugin` 1.1.0, ESBMC master compilado com Bitwuzla.

**Desenho:** [`docs/desenho/specs/2026-10-22-harness-de-agente-design.md`](../specs/2026-10-22-harness-de-agente-design.md)

**Fora deste plano:** o motor reserva (API com ferramentas) é rodada própria, com plano próprio depois
da comparação; abrir as issues no ESBMC segue o fluxo de `possiveis_problemas`.

## Restrições globais

- Trabalhar direto em `master` (regra do repositório); commit sem coautoria do Claude; nunca squash.
- Sem travessão em nenhum texto (código, docs, mensagens de commit).
- ESBMC de medição: `~/esbmc-master/build-bw/src/esbmc/esbmc` (master limpo, Bitwuzla), sempre com
  `--no-pointer-check --no-align-check`; patch no ESBMC nunca nesse checkout.
- Toda rodada registra o commit do ESBMC, a versão das skills e do caderno, e entra em
  `docs/experimentos/README.md` (data, pasta, commit, comando, resultado).
- Rodada que chama o `claude -p` usa a assinatura: avisar a Fernanda antes. API paga só com confirmação.
- Testes automatizados nunca chamam o `claude` nem a API: o agente entra como função falsa (como em
  `tests/test_verify_agent_arm.py`).
- Suíte completa antes de cada commit: `timeout 600 .venv/bin/python -m pytest -q -p no:cacheprovider`.

## Foco de revisão

1. **O agente não escreve `harness.py`, ou escreve um que importa módulo local:** o caso termina em
   `AGENT_FAILED` com motivo, e as rodadas gravadas até ali continuam no resultado (Tarefa 3).
2. **O ESBMC cai no meio do laço** (código 134 ou 139, `Couldn't convert expression`): a rodada fica marcada
   `crash` e o caso vira candidato a reprodutor, nunca `CONFIRMED` (Tarefa 3).
3. **mypy ausente ou estourando o tempo:** o aviso vira `mypy: não medido`, sem derrubar o caso (Tarefa 4).
4. **O original real não importa** (dependência ausente, efeito colateral de rede): o nível vira `stubs` e a
   preservação `nao_medida`, sem exceção escapando (Tarefa 6).
5. **O limite da assinatura acaba no meio da rodada:** o script retoma do `agent_results.json` sem refazer casos
   prontos e sem trocar de motor (Tarefa 9).

---

### Tarefa 1: ESBMC de medição e remedição do gerador de pytest

**Arquivos:**
- Modificar: `~/esbmc-master/esbmc.sh` (fora do repositório) para chamar `build-bw`
- Modificar: `src/research_pipeline/verification/esbmc_runner.py:13-16` (comentário do `DEFAULT_ESBMC`)
- Criar: `docs/projeto/possiveis_problemas/48_pytest_metodo.py`, `49_pytest_varios_args.py`, `50_pytest_str.py`
- Modificar: `docs/projeto/possiveis_problemas/README.md` (seção "Gerador de pytest no master")

**Interfaces:**
- Produz: `esbmc.sh` aponta para o build com Bitwuzla; a decisão "gerador funciona com receptor e com vários
  argumentos: sim/não", usada na Tarefa 7.

- [ ] **Passo 1:** só depois que o teste A/B de 22/10 terminar, trocar o caminho em `~/esbmc-master/esbmc.sh`
  para `build-bw` e apontar `~/.local/bin/esbmc` para o mesmo binário.
- [ ] **Passo 2:** conferir. Rodar `~/esbmc-master/esbmc.sh <programa com divisão por zero>`; esperado:
  `Solving with solver Bitwuzla 0.9.0` e `VERIFICATION FAILED`.
- [ ] **Passo 3:** escrever os três programas: método de classe com receptor e um `ZeroDivisionError`; função
  livre com três argumentos `nondet_int()` em que só o terceiro dispara o erro; função com `nondet_str()` que
  falha numa string específica.
- [ ] **Passo 4:** rodar cada um com `--generate-pytest-testcase --pytest-output-dir <scratch> --unwind 5` e
  depois `pytest` no teste gerado. Anotar no README: o teste foi gerado? roda? falha com a exceção certa? algum
  nome interno (`x&0#1`) ou argumento faltando?
- [ ] **Passo 5:** o que falhar vira rascunho em `possiveis_problemas/issues/`, no formato dos existentes.
- [ ] **Passo 6:** commit dos reprodutores, do README e do comentário.

### Tarefa 2: Skill de regras do harness na pasta de cada caso

**Arquivos:**
- Criar: `src/research_pipeline/verify/skills/regras-harness/SKILL.md`
- Criar: `src/research_pipeline/verify/skills/reparos-aprendidos/SKILL.md` (começa vazio, com cabeçalho e versão)
- Modificar: `src/research_pipeline/verify/agent_arm.py` (prompt e cópia das skills)
- Teste: `tests/test_verify_agent_arm.py`

**Interfaces:**
- Produz: `SKILLS_DIR: Path` e `install_project_skills(case_dir: Path, skills_dir: Path = SKILLS_DIR) -> dict[str, str]`
  (nome da skill para o sha256[:12] do `SKILL.md`), chamada por `run_agent_arm` quando `project_skills=True`
  (parâmetro novo, padrão `False`). O dicionário vai para `result["skills"]`.

- [ ] **Passo 1: teste que falha.** `test_project_skills_are_installed_in_the_case_folder`: chama
  `install_project_skills(tmp_path)` e confere que existem `tmp_path/.claude/skills/regras-harness/SKILL.md` e
  `.../reparos-aprendidos/SKILL.md`, e que o retorno tem as duas chaves com 12 caracteres hexadecimais.
- [ ] **Passo 2:** rodar `.venv/bin/python -m pytest tests/test_verify_agent_arm.py -k project_skills -q`;
  esperado: falha por nome indefinido.
- [ ] **Passo 3:** escrever o `SKILL.md` de regras, em inglês (língua do prompt atual), com: corpo da função
  copiado do original e, se o ESBMC recusar algo dentro dele, simplificar só aquela construção, mantendo a
  expressão suspeita e os ramos até ela; stubs mínimos que suportam toda operação que o alvo aplica e nunca
  levantam exceção; sem `assert`, sem guarda na expressão suspeita, sem importar módulo local; se o ESBMC cair
  (código 134 ou 139, ou `Couldn't convert expression`), parar e responder `ESBMC_CRASH`. As pegadinhas do
  ESBMC-Python entram só depois de conferidas no master atual (cada uma com o comando que a demonstra).
- [ ] **Passo 4:** implementar `install_project_skills` (cópia da árvore, hash do conteúdo) e, no `_PROMPT`,
  trocar as regras repetidas por "Follow the regras-harness and reparos-aprendidos skills". Com
  `--setting-sources project` o Claude Code carrega o `.claude/` da pasta do caso, então o modo isolado continua.
- [ ] **Passo 5: teste que falha.** `test_run_agent_arm_records_skill_versions`: com agente falso que escreve um
  harness válido, `run_agent_arm(..., project_skills=True)` devolve `result["skills"]` com as duas versões e o
  prompt recebido pelo agente menciona `regras-harness`.
- [ ] **Passo 6:** implementar, rodar os dois testes (passam) e a suíte completa.
- [ ] **Passo 7:** commit.

### Tarefa 3: Rodadas do self-healing gravadas por um `esbmc` de fachada

**Arquivos:**
- Criar: `src/research_pipeline/verify/rounds.py`
- Modificar: `src/research_pipeline/verify/agent_arm.py` (`claude_agent` põe a fachada no `PATH`; `run_agent_arm`
  lê as rodadas)
- Teste: `tests/test_verify_rounds.py`

**Interfaces:**
- Produz:
  - `install_round_logger(case_dir: Path, esbmc: str) -> Path`: cria `case_dir/bin/esbmc` (script) que copia o
    `.py` recebido para `case_dir/rounds/NNN/input.py`, roda o ESBMC real com os mesmos argumentos, grava
    `output.txt` e `exit_code`, e devolve a saída e o código do ESBMC real. Retorna `case_dir/bin`.
  - `@dataclass Round: index: int; source: str; output: str; exit_code: int; kind: str` com `kind` em
    `verdict | refused | crash | timeout`.
  - `read_rounds(case_dir: Path) -> list[Round]`, em ordem.
  - `result["rounds"]`: lista de `{"index", "kind", "warnings"}` (os avisos vêm da Tarefa 4).

- [ ] **Passo 1: testes que falham.**
  - `test_logger_records_each_call_and_passes_output_through`: instala a fachada apontando para um "ESBMC"
    falso (script que imprime `VERIFICATION FAILED` e sai com 1), chama a fachada duas vezes com arquivos
    diferentes; `read_rounds` devolve 2 rodadas com o conteúdo de cada arquivo, `kind == "verdict"`, e a saída
    da fachada é igual à do falso.
  - `test_crash_exit_codes_are_classified`: falso que sai com 134 dá `kind == "crash"`; 139 também; saída com
    `Couldn't convert expression` também.
  - `test_refusal_without_verdict_is_refused`: saída com `ERROR:` e sem `VERIFICATION` dá `kind == "refused"`.
- [ ] **Passo 2:** rodar `-k rounds`; esperado: falha de import.
- [ ] **Passo 3:** implementar `rounds.py`. A fachada é um script `sh` gerado (o `Bash(esbmc:*)` liberado ao
  agente já cobre o nome `esbmc`); `claude_agent` passa a receber `case_dir` no `PATH` antes do diretório do
  ESBMC real quando a gravação estiver ligada (parâmetro `log_rounds: bool = False` em `run_agent_arm`).
- [ ] **Passo 4:** teste `test_agent_without_harness_keeps_its_rounds` (foco 1): agente falso que chama a
  fachada uma vez e não escreve `harness.py`; o resultado é `AGENT_FAILED` e `result["rounds"]` tem 1 rodada.
- [ ] **Passo 5:** teste `test_crash_round_never_confirms` (foco 2): a última rodada é `crash`; o veredito final
  não é `CONFIRMED` e `result["esbmc_crash"]` é `True`.
- [ ] **Passo 6:** rodar os testes (passam) e a suíte; commit.

### Tarefa 4: Avisos baratos por rodada (corpo, stub, mypy)

**Arquivos:**
- Criar: `src/research_pipeline/verify/warnings.py`
- Teste: `tests/test_verify_warnings.py`

**Interfaces:**
- Consome: `Round` (Tarefa 3), `body_signature`/`find_function` (`verify/astutil.py`), `stub_cause` (já existe).
- Produz: `round_warnings(source: str, original: str, function: str, mypy_timeout: int = 60) -> list[str]`, com
  itens `body_changed`, `mypy_new:<mensagem sem número de linha>` ou `mypy: não medido`.
  `mypy_new_errors(original: str, harness: str, timeout: int = 60) -> list[str] | None` (None = não medido).

- [ ] **Passo 1: testes que falham.**
  - `test_mypy_flags_the_emptied_base_class`: original com `class C(collections.OrderedDict)` que usa
    `len(self)` e `super().__setitem__`; harness com a base trocada por classe vazia. `mypy_new_errors` contém
    um erro com `len` e um com `__setitem__` (o caso nm_real_11).
  - `test_identical_programs_have_no_new_errors`: mesmo programa nos dois lados dá `[]`.
  - `test_missing_mypy_is_not_measured` (foco 3): com `PATH` sem mypy e `sys.executable` trocado por um que não
    tem o módulo (monkeypatch do comando), o retorno é `None` e `round_warnings` traz `mypy: não medido`.
  - `test_body_change_is_flagged`: corpo do alvo diferente dá `body_changed`.
- [ ] **Passo 2:** rodar (falham).
- [ ] **Passo 3:** implementar. mypy roda como `sys.executable -m mypy --strict --no-error-summary` em arquivos
  temporários; mensagens comparadas sem caminho nem número de linha; `timeout` vira `None`.
- [ ] **Passo 4:** ligar em `run_agent_arm`: cada item de `result["rounds"]` ganha `warnings`.
- [ ] **Passo 5:** rodar (passam), suíte, commit.

### Tarefa 5: Amostra fixa para a comparação

**Arquivos:**
- Criar: `scripts/v2_harness_sample.py`
- Criar: `dataset/bugs_reais/amostra_harness.json` (gerado e commitado)
- Teste: `tests/test_v2_harness_sample.py`

**Interfaces:**
- Produz: `harness_sample(results: list[dict], items: dict[str, dict], size: int, seed: int) -> list[dict]`;
  arquivo com `{"seed", "size", "source_run", "hypotheses": [...]}`, uma hipótese por bug.

- [ ] **Passo 1: testes que falham.**
  - `test_sample_is_deterministic_for_a_seed`: duas chamadas com a mesma semente devolvem os mesmos ids.
  - `test_sample_keeps_only_at_line_exception_hypotheses`: hipótese fora da linha (`at_bug_line` falso) ou com
    `oracle == VALUE_ORACLE` nunca entra.
  - `test_one_hypothesis_per_bug`.
- [ ] **Passo 2:** rodar (falham); implementar; rodar (passam).
- [ ] **Passo 3:** gerar a amostra a partir de `artifacts/v2/final-2026-10-17/v2_verify_report.json`, tamanho
  30, semente 20261022, e commitar o JSON com o script.

### Tarefa 6: Teste diferencial em dois níveis

**Arquivos:**
- Criar: `src/research_pipeline/verify/differential.py`
- Teste: `tests/test_verify_differential.py`

**Interfaces:**
- Consome: `concrete_replay`, `ReplayVerdict` (`verify/replay.py`), `_replay_original` (`verify/agent_arm.py`),
  `Program` (`verify/render.py`).
- Produz:
  - `@dataclass DiffResult: level: str; agreed: int; total: int; divergences: list[dict]; preservation: str`,
    com `level` em `real | stubs` e `preservation` em `preservada | alterada | nao_medida`.
  - `differential(harness: str, original: str, h: BugHypothesis, seeds: dict[str, list], runs: int = 100,
    original_path: Path | None = None) -> DiffResult`.
  - Regra: qualquer divergência no caminho do bug (status, tipo da exceção ou linha relativa ao alvo onde ela
    nasce) dá `alterada`; a confirmação cai. `preservada` só no nível `real`; no nível `stubs` sem divergência, a
    preservação é `nao_medida`.

- [ ] **Passo 1: testes que falham (nível stubs).**
  - `test_same_body_agrees_on_every_input`: harness com o corpo original; `agreed == total`, `level == "stubs"`,
    `preservation == "nao_medida"`.
  - `test_simplified_body_that_hides_the_bug_diverges`: harness cujo corpo trocou `a // b` por `a // 1`; há
    divergência e `preservation == "alterada"`.
  - `test_counterexample_comes_first`: a primeira entrada comparada é a sequência dos `seeds`.
- [ ] **Passo 2:** rodar (falham); implementar o nível stubs: sequências de entrada vindas dos `seeds` e de
  `concrete_replay(..., random_runs=1, seed=i)` para `i` em `range(runs)`, descartando execuções sem `inputs`;
  cada sequência roda com `inputs=` no harness e no harness com o corpo original (`_replay_original`).
- [ ] **Passo 3: testes que falham (nível real).**
  - `test_importable_free_function_runs_for_real`: `original_path` é um módulo só com biblioteca padrão e o alvo
    é função livre com parâmetros escalares; `level == "real"` e, sem divergência, `preservation == "preservada"`.
  - `test_unimportable_original_falls_back_to_stubs` (foco 4): módulo que importa um pacote inexistente; volta ao
    nível stubs, `preservation == "nao_medida"`, nenhuma exceção escapa.
- [ ] **Passo 4:** implementar o nível real só para função livre com parâmetros `int`, `float`, `bool`, `str`:
  importa o módulo original num subprocesso com o prefixo sem rede de `replay._no_network_prefix()` e chama a
  função com as mesmas sequências; qualquer outro formato fica no nível stubs.
- [ ] **Passo 5:** ligar em `evaluate_harness` (`result["differential"]`); `alterada` derruba `CONFIRMED` e
  `CONFIRMED_SIMPLIFIED` para `BEHAVIOUR_CHANGED` (constante nova em `agent_arm.py`).
- [ ] **Passo 6:** rodar (passam), suíte, commit.

### Tarefa 7: Teste pytest do ESBMC como prova executável

**Arquivos:**
- Modificar: `src/research_pipeline/verify/pytest_gen.py`
- Teste: `tests/test_verify_pytest_gen.py`

**Interfaces:**
- Consome: a decisão da Tarefa 1; `pytest_reproducer` (já existe, contorno da função solta).
- Produz: `esbmc_pytest(harness_path: Path, *, esbmc_command: list[str], bound: int, out_dir: Path,
  exception: str, timeout_seconds: int = 120) -> dict` com `{"status", "path", "reason", "route"}`;
  `status` em `reproduces | does_not_reproduce | not_generated`, `route` em `direct | free_function`.

- [ ] **Passo 1: testes que falham** (marcados para rodar só com o ESBMC instalado, como os testes de ESBMC
  existentes):
  - `test_direct_route_reproduces_a_free_function_bug`: harness com `ZeroDivisionError`; `status ==
    "reproduces"`, `route == "direct"`, o arquivo existe.
  - `test_falls_back_when_direct_generation_fails`: com o comando direto forçado a não gerar arquivo
    (monkeypatch), cai em `pytest_reproducer` e `route == "free_function"`.
- [ ] **Passo 2:** implementar: roda o ESBMC com `--generate-pytest-testcase --pytest-output-dir out_dir`, roda o
  teste gerado com `sys.executable -m pytest` e só aceita se ele falhar com `exception`; se a Tarefa 1 mostrou o
  gerador quebrado para o formato do harness, tenta o contorno.
- [ ] **Passo 3:** ligar em `run_agent_arm` para todo `CONFIRMED` (`result["pytest"]`); o teste gerado entra
  como primeira entrada do diferencial quando houver valores.
- [ ] **Passo 4:** rodar (passam), suíte, commit.

### Tarefa 8: Candidatos ao caderno de reparos

**Arquivos:**
- Criar: `scripts/v2_repair_candidates.py`
- Teste: `tests/test_v2_repair_candidates.py`

**Interfaces:**
- Consome: `read_rounds` (Tarefa 3), `agent_results.json` (formato atual mais `rounds`, `differential`).
- Produz: `repair_candidates(case_dir: Path) -> list[dict]` com `{"caso", "rodada", "erro", "diff"}` para cada
  par de rodadas consecutivas em que a primeira foi `refused` e a seguinte chegou a `verdict`, descartando casos
  com `preservation == "alterada"`; o script escreve `candidatos.md` na pasta da rodada para a Fernanda revisar.

- [ ] **Passo 1: testes que falham.**
  - `test_refused_then_verdict_is_a_candidate`: pasta com rodadas `refused` → `verdict`; um candidato com a
    primeira linha `ERROR:` do erro e o diff unificado entre os dois `input.py`.
  - `test_changed_behaviour_is_never_a_candidate`.
  - `test_crash_is_never_a_candidate`.
- [ ] **Passo 2:** rodar (falham); implementar; rodar (passam).
- [ ] **Passo 3:** escrever no `SKILL.md` de `reparos-aprendidos` o formato de uma regra aprovada (erro, o que
  fazer, caso de origem, data da aprovação). Aprovar é editar esse arquivo à mão com a Fernanda; a versão é o
  hash que a Tarefa 2 já registra.
- [ ] **Passo 4:** suíte, commit.

### Tarefa 9: Flags no script e versões registradas

**Arquivos:**
- Modificar: `scripts/v2_agent_arm.py`
- Teste: `tests/test_v2_agent_arm_script.py`

**Interfaces:**
- Consome: Tarefas 2, 3, 6, 7.
- Produz: flags `--project-skills`, `--log-rounds`, `--differential`, `--pytest`, `--sample
  dataset/bugs_reais/amostra_harness.json`; o `variant` gravado ganha `esbmc_commit` (via `esbmc_root_of` e
  `git rev-parse HEAD` no checkout), `esbmc_version` e `skills` (versões).

- [ ] **Passo 1: testes que falham.**
  - `test_variant_records_esbmc_commit_and_skill_versions`: com agente falso, o primeiro resultado tem
    `variant["esbmc_commit"]` de 40 caracteres e `variant["skills"]` com as duas chaves.
  - `test_resume_skips_finished_cases` (foco 5): com um `agent_results.json` já contendo um caso, uma segunda
    execução chama o agente só para os outros.
  - `test_sample_flag_runs_only_sampled_hypotheses`.
- [ ] **Passo 2:** rodar (falham); implementar; rodar (passam); suíte; commit.

### Tarefa 10: Leitura do teste A/B, primeira revisão do caderno e rodada comparativa

Tarefa de pesquisa, com a Fernanda. Sem código novo.

- [ ] **Passo 1:** ler com a Fernanda as opiniões do consultor do teste A/B de 22/10
  (`scratchpad/spike/C/*/opiniao.md`) e registrar o teste em `docs/experimentos/README.md` (Fase 27).
- [ ] **Passo 2:** rodar o braço de agente com tudo ligado em casos **fora** da amostra (os 5 do teste A/B e os
  reprodutores), gerar `candidatos.md` (Tarefa 8) e revisar com a Fernanda; o que ela aprovar entra no caderno.
- [ ] **Passo 3:** congelar o caderno (commit; a versão fica no hash).
- [ ] **Passo 4:** avisar a Fernanda do uso da assinatura e rodar os dois braços na amostra: o motor de regras
  (harnesses da rodada final reavaliados com o fiscal novo por `scripts/v2_agent_reverify.py`; se o script não aceitar os
  programas do motor como harness, adaptá-lo é um passo com teste próprio antes da rodada) e o harness de
  agente (`scripts/v2_agent_arm.py --sample ... --project-skills --log-rounds --differential --pytest`).
- [ ] **Passo 5:** registrar em `docs/experimentos/README.md`, métrica final primeiro: bugs confirmados por
  braço; depois preservação (`preservada / alterada / nao_medida`), testes pytest que reproduzem, crashes do
  ESBMC e quantos viraram reprodutor.
