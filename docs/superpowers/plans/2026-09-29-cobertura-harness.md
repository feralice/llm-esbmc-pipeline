# Cobertura do harness: plano de implementação

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: superpowers:executing-plans (ou subagent-driven-development). Passos em checkbox (`- [ ]`).

**Objetivo:** fazer mais hipóteses chegarem ao veredito do ESBMC, corrigindo as falhas que são do
harness (recorte, stubs, validação da especificação), sem tocar no que é limite do ESBMC 8.5.

**Arquitetura:** nada muda no fluxo (LLM aponta, AST aterra, recorte + stubs, LLM dá tipos em JSON,
harness por código, ESBMC, reexecução no CPython). Cada tarefa é uma regra geral em um módulo de
`src/research_pipeline/verify/`, valendo para qualquer arquivo Python, nunca um caso específico.

**Tecnologia:** Python 3.12, `ast`, pytest, ESBMC 8.5.0 em `/usr/local/bin/esbmc`.

**Desenho de referência:** `docs/v2/desenho_motor_verify.md`.

## Restrições globais

- Só começar depois que as rodadas rep3 (reparo e amostragem) e o braço do agente terminarem: os
  processos novos importam `src/` ao iniciar, e as 3 repetições precisam do mesmo código.
- O corpo da função alvo nunca muda. Toda transformação vira uma entrada em `transforms`.
- Trabalhar direto em `master`; commits só com autorização explícita da Fernanda, sem coautoria de IA.
- Testes: `PYTHONPATH=src .venv/bin/python -m pytest -q` (438 passando hoje). Lint: `pylint` nos
  arquivos tocados.
- Não abrir issue no ESBMC.
- Rodadas pagas (gpt-4o-mini) só com confirmação dela.

## Evidência (rep1 com reparo, 125 hipóteses do gabarito)

| Falha | Casos | Causa medida | Tarefa |
|---|---|---|---|
| recorte recusado ("cannot be sliced verbatim") | 9 | código de topo não copiado mexe em dado copiado (`pl_sb_irregular.update(...)`, `_table_formats = {...DataRow(...)}`) ou `global` em função não copiada | 1 |
| `Function "property" not found` | 3 | `url = property(_get_url, ...)` no corpo da classe | 2 |
| `Base class not found: HTTPConnection` | 2 | `class X(httputil.HTTPConnection)`: base de biblioteca com 2 níveis não é achatada | 3 |
| `Cannot open file: .../sys.json`, `Module 'Cookie' not found` | 3 | `sys` está em `MODELED_MODULES` mas o 8.5 não o carrega; import py2 dentro de `try` | 4 |
| SPEC_FAILED por `unknown stub` / `unknown attribute` | 8 | a LLM manda chave a mais e a validação recusa o JSON inteiro | 5 |
| `undefined name(s)` sem arquivo completo | 7 | falta o arquivo em `detection_full/`: é dado, fica fora deste plano | |

Limites do ESBMC encontrados no levantamento, fora deste plano (viram reprodutores na Tarefa 6):
função usada como valor (`functools.partial`, `getattr(obj, "localize")`, `tqdm.format_interval`
atribuído a variável), `OrderedDict` como base, `super()` em alguns contextos.

## Foco de revisão

1. Fechamento do recorte crescendo sem limite: um módulo com muito código de topo pode puxar quase
   tudo; o resultado ainda deve ser verbatim e continuar sem `if __name__` nem chamadas soltas que
   não tocam nome copiado.
2. `@property` quando o alvo é o próprio getter: não pode sumir a função alvo.
3. Chave desconhecida ignorada que era um erro de digitação de uma chave obrigatória: a obrigatória
   continua faltando e continua sendo recusada.
4. Base achatada que também é usada como valor no mesmo arquivo.
5. Remover `sys` de `MODELED_MODULES` sem quebrar os casos que hoje passam com `sys`.

---

### Tarefa 1: recorte por fechamento em vez de recusa

**Arquivos:**
- Modificar: `src/research_pipeline/verify/context.py` (`context_module`, `_pruned_code_touches`)
- Teste: `tests/test_verify_context.py`

**Interfaces:** `context_module(source: str, function: str) -> str` mantém a assinatura. Continua
devolvendo `""` quando a raiz não é única.

Regra nova: um comando de topo que não seria copiado, mas grava um nome copiado, lê um dado de
módulo copiado, ou uma função com `global` sobre nome copiado, passa a ser **copiado junto** (com
suas dependências), até o conjunto parar de crescer. Guarda `if __name__` nunca entra.

- [ ] **Passo 1: testes que falham**

```python
def test_statement_that_mutates_kept_data_is_kept_not_refused():
    source = (
        "TABLE = {}\n"
        "TABLE.update({'a': 1})\n"
        "print('noise')\n"
        "def target(k):\n"
        "    return TABLE[k]\n"
    )
    module = context_module(source, "target")
    assert "TABLE.update({'a': 1})" in module
    assert "print('noise')" not in module


def test_assignment_reading_kept_data_is_kept_with_its_dependencies():
    source = (
        "from collections import namedtuple\n"
        "Row = namedtuple('Row', 'a b')\n"
        "FORMATS = {'simple': Row(1, 2)}\n"
        "def target(r):\n"
        "    return Row(r, r)\n"
    )
    module = context_module(source, "target")
    assert "FORMATS = {'simple': Row(1, 2)}" in module


def test_function_rebinding_kept_global_is_kept():
    source = (
        "COUNT = 0\n"
        "def bump():\n"
        "    global COUNT\n"
        "    COUNT += 1\n"
        "def target():\n"
        "    return 10 // COUNT\n"
    )
    module = context_module(source, "target")
    assert "def bump():" in module


def test_main_guard_is_never_pulled_in():
    source = (
        "DATA = []\n"
        "def target():\n"
        "    return DATA[0]\n"
        "if __name__ == '__main__':\n"
        "    DATA.append(1)\n"
    )
    assert "__main__" not in context_module(source, "target")
```

- [ ] **Passo 2: rodar e ver falhar**

`PYTHONPATH=src .venv/bin/python -m pytest tests/test_verify_context.py -q`
Esperado: os 3 primeiros FALHAM (hoje devolvem `""`), o 4º passa.

- [ ] **Passo 3: implementar**

Em `context.py`, trocar a recusa por fechamento. `_touches(node, names, data)` reaproveita o corpo
do laço de `_pruned_code_touches`; funções com `global` sobre nome copiado entram como candidatas.

```python
def _touches(node: ast.stmt, names: set[str], data: set[str]) -> bool:
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
        return False
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        rebinds = {n for g in ast.walk(node) if isinstance(g, ast.Global) for n in g.names}
        return bool((rebinds | {node.name}) & names)
    if isinstance(node, ast.ClassDef):
        return node.name in names
    stored = {c.id for c in ast.walk(node) if isinstance(c, ast.Name) and isinstance(c.ctx, ast.Store)}
    written = (stored | _defined_names(node)) if isinstance(node, _DEFINITIONS) else stored
    return bool(written & names or _loaded_names(node) & data)


def _closure(tree: ast.Module, candidates: list[ast.stmt], root: ast.stmt) -> set[int]:
    kept, pending = {id(root)}, [root]
    while True:
        while pending:
            needed = _loaded_names(pending.pop())
            for node in candidates:
                if id(node) not in kept and _defined_names(node) & needed:
                    kept.add(id(node))
                    pending.append(node)
        names = set().union(*(_defined_names(n) for n in tree.body if id(n) in kept))
        data = _data_names(tree) & names
        extra = [n for n in tree.body if id(n) not in kept and not _is_main_guard(n)
                 and _touches(n, names, data)]
        if not extra:
            return kept
        for node in extra:
            kept.add(id(node))
            pending.append(node)
```

Em `context_module`, substituir o bloco de `kept`/`pending` e a chamada a `_pruned_code_touches`
por `kept = _closure(tree, candidates, roots[0])`. Apagar `_pruned_code_touches` (sem outros
chamadores: conferir com `grep -rn _pruned_code_touches src tests`).

- [ ] **Passo 4: rodar e ver passar**

`PYTHONPATH=src .venv/bin/python -m pytest tests/test_verify_context.py tests/test_verify_grounding.py -q`
Esperado: tudo passa. Se algum teste antigo esperava `""` por "código podado mexe em dado", ele
descreve a regra antiga: ajustar para esperar o comando copiado.

- [ ] **Passo 5: conferir nos 9 casos reais**

```bash
PYTHONPATH=src .venv/bin/python - <<'EOF'
from research_pipeline.verify.context import context_module
for f, fn in [("oob_real_05","lib2to3_parse"),("tm_real_08","simple_separated_format"),
              ("nm_real_09","tqdm"),("nm_real_20","engine"),("av_real_05","tqdm"),
              ("oob_real_12","fast_float"),("oob_real_13","tokenize"),
              ("ip_real_15","EmptyLineTracker"),("ip_real_32","date_convert")]:
    src = open(f"dataset/v2_real_world/detection_full/{f}.py", encoding="utf-8", errors="replace").read()
    print(f, len(context_module(src, fn).splitlines()), "linhas")
EOF
```
Esperado: nenhum com 0 linhas.

---

### Tarefa 2: `property` vira atributo de entrada

**Arquivos:**
- Modificar: `src/research_pipeline/verify/grounding.py` (`_class_level_values`, `ground`)
- Modificar: `src/research_pipeline/verify/slicing.py` (`prune_class`)
- Teste: `tests/test_verify_grounding.py`

**Interfaces:**
- Produz: `_properties(cls: ast.ClassDef) -> set[str]` em `grounding.py`: nomes ligados por
  `x = property(...)` no corpo da classe ou por método com `@property`.
- `prune_class(module, class_name, reachable, drop_init=True, properties=frozenset())` remove também
  as definições desses nomes e acrescenta `properties_as_attributes:<nomes>` em `transforms`.

Só vale para `entry == "method"` (existe shell para receber o atributo). Se o alvo for o próprio
getter, não há remoção dele.

- [ ] **Passo 1: testes que falham**

```python
PROPERTY_SOURCE = '''class Request:
    def _get_url(self):
        return self._url

    url = property(_get_url)

    @property
    def body(self):
        return self._body

    def follow(self, n):
        return self.url[n] + self.body
'''


def test_property_becomes_receiver_attribute():
    h = BugHypothesis(file="r.py", function="Request.follow", suspect_expression="self.url[n]")
    g = ground(h, PROPERTY_SOURCE)
    assert isinstance(g, Grounded)
    assert {"url", "body"} <= set(g.receiver_attrs)
    assert "property(" not in g.module and "@property" not in g.module
    assert any(t.startswith("properties_as_attributes:") for t in g.transforms)


def test_property_getter_as_target_is_kept():
    h = BugHypothesis(file="r.py", function="Request.body", suspect_expression="self._body")
    g = ground(h, PROPERTY_SOURCE)
    assert isinstance(g, Grounded)
    assert "def body(self):" in g.module
```

(Conferir a assinatura real de `BugHypothesis` em `hypothesis.py` e completar os campos
obrigatórios como nos testes existentes do arquivo.)

- [ ] **Passo 2: rodar e ver falhar**

`PYTHONPATH=src .venv/bin/python -m pytest tests/test_verify_grounding.py -q -k property`

- [ ] **Passo 3: implementar**

```python
def _properties(cls: ast.ClassDef) -> set[str]:
    names = set()
    for node in cls.body:
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name) and node.value.func.id == "property"):
            names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        elif isinstance(node, ast.FunctionDef) and any(
                isinstance(d, ast.Name) and d.id == "property" for d in node.decorator_list):
            names.add(node.name)
    return names
```

- `_receiver_attrs`: `_loaded_self_attrs(cls, method) - (_class_level_values(cls) - _properties(cls))`.
- `ground`: para `entry == "method"`, calcular `props = _properties(cls) - {function.name}` e passar
  a `prune_class(..., properties=props)`.
- `prune_class`: além dos métodos removidos, apagar as linhas dos `Assign` e `FunctionDef` cujo
  nome está em `properties` (mesma técnica de `del lines[...]`, por `_first_line` decrescente).

- [ ] **Passo 4: rodar e ver passar**

`PYTHONPATH=src .venv/bin/python -m pytest tests/test_verify_grounding.py tests/test_verify_render.py -q`

- [ ] **Passo 5: ESBMC aceita o programa**

Rodar `scripts/v2_verify_smoke.py` (sem LLM, especificação placeholder) em `nm_real_05.py` /
`Response.follow` e conferir que a mensagem `Function "property" not found` sumiu.

---

### Tarefa 3: base de biblioteca com dois níveis vira classe stub

**Arquivos:**
- Modificar: `src/research_pipeline/verify/slicing.py` (`_flatten_chains`)
- Teste: `tests/test_verify_grounding.py` (ou o teste de slicing existente)

Hoje `_flatten_chains` só renomeia cadeias com 3 ou mais partes. Uma base de classe
`httputil.HTTPConnection` tem 2 partes e fica como atributo; o ESBMC procura `HTTPConnection` e não
acha. Regra: em posição de classe (`_in_class_position`), achatar também cadeias de 2 partes.

- [ ] **Passo 1: teste que falha**

```python
def test_two_level_library_base_class_is_flattened_to_a_stub():
    source = (
        "from tornado import httputil\n"
        "class Conn(httputil.HTTPConnection):\n"
        "    def read(self, n):\n"
        "        return 10 // n\n"
    )
    module, plan, transforms = stub_imports(source)
    assert "class Conn(httputil_HTTPConnection):" in module
    assert "httputil_HTTPConnection" in plan.classes
```

- [ ] **Passo 2: rodar e ver falhar.**

- [ ] **Passo 3: implementar.** Em `_flatten_chains`, trocar a condição `len(parts) < 3` por
  `len(parts) < (2 if _in_class_position(node, parents) else 3)`. O ramo de posição de classe já
  junta a cadeia inteira (`"_".join(parts)`).

- [ ] **Passo 4: rodar `tests/test_verify_*` inteiro e ver passar.**

- [ ] **Passo 5:** smoke em `av_real_11.py` / `HTTP1Connection._read_body` sem `Base class not found`.

---

### Tarefa 4: módulos que o ESBMC 8.5 não carrega

**Arquivos:**
- Modificar: `src/research_pipeline/verify/slicing.py` (`MODELED_MODULES`)
- Teste: `tests/test_verify_esbmc_integration.py`

- [ ] **Passo 1: medir antes de mudar.** Para cada módulo de `MODELED_MODULES`, gerar
  `import <m>` + uma função trivial e rodar `/usr/local/bin/esbmc`. Anotar quais dão
  `Cannot open file ... <m>.json`. Evidência atual: `sys` falha (2 casos).
- [ ] **Passo 2: teste que falha.** Um teste de integração (marcado como os demais que chamam o
  ESBMC) com `import sys` + `sys.maxsize` usado na função, esperando veredito do ESBMC e não
  `Cannot open file`.
- [ ] **Passo 3:** remover de `MODELED_MODULES` os módulos medidos como não carregáveis, com
  comentário de uma linha citando a data da medição.
- [ ] **Passo 4:** import dentro de `try/except ImportError` (padrão py2/py3, `Cookie`): conferir se
  `_unmodeled_imports` já o vê; se não, estender para imports dentro de blocos `try` de topo e
  testar com `try: import Cookie\nexcept ImportError: import http.cookies as Cookie`.
- [ ] **Passo 5:** rodar a suíte inteira.

---

### Tarefa 5: chave desconhecida é ignorada, não recusa o JSON

**Arquivos:**
- Modificar: `src/research_pipeline/verify/spec.py` (`spec_problems`), `loop.py` (registro)
- Teste: `tests/test_verify_spec.py`

Chave a mais não altera o programa (o render só usa as chaves conhecidas), então recusar o JSON
inteiro gasta uma chamada da LLM à toa. Chave obrigatória faltando continua sendo recusa.

- [ ] **Passo 1: testes que falham**

```python
def test_unknown_stub_and_attribute_are_ignored_not_rejected():
    spec = parse_spec('{"params": {"n": "int"}, "attributes": {"ghost": "int"},'
                      ' "stubs": {"lib.nope": "int"}, "assumptions": []}')
    assert spec_problems(spec, grounded_with_param_n) == []


def test_missing_required_stub_is_still_rejected():
    ...  # grounded com stub_keys=("lib.f",) e spec sem "lib.f": espera "stub 'lib.f': missing return type"
```

(Montar `grounded_with_param_n` com o helper já usado em `tests/test_verify_spec.py`.)

- [ ] **Passo 2: rodar e ver falhar.**
- [ ] **Passo 3:** em `spec_problems`, apagar as linhas `unknown parameter`, `unknown attribute` e
  `unknown stub`; criar `ignored_keys(spec, grounded) -> list[str]` com essas chaves. Em
  `verify_hypothesis`, gravar `record["ignored"] = ignored_keys(...)` quando não vazio. Conferir que
  `render_program` e `resolved_types` não iteram sobre chaves do spec sem filtrar (senão uma chave a
  mais vira declaração).
- [ ] **Passo 4:** rodar `tests/test_verify_spec.py tests/test_verify_loop.py tests/test_verify_render.py`.

---

### Tarefa 6: medir antes e depois, documentar

- [ ] Rodar a suíte completa (`timeout 10m`) e `pylint` nos arquivos tocados.
- [ ] `scripts/v2_reverdict.py` não serve aqui (o programa muda); com confirmação dela, rodar a
  especificação com hipóteses do gabarito, reparo, na mesma config das repetições, saída
  `artifacts/v2/exp-oracle-repair-cobertura/`, e comparar `by_verdict` com a média das 3 repetições.
- [ ] **Validação fora da amostra (contra sobreajuste):** o levantamento usou o dataset V2 só para
  descobrir quais construções Python quebram; as regras não citam nenhum arquivo dele. Para provar que
  generalizam, medir também em código que não foi usado no levantamento: os 199 candidatos de
  `dataset/v2_candidates/` (etapa de precheck, sem LLM: quantos passam a gerar programa aceito) e,
  se ela quiser, um repositório real à escolha dela. Ganho só no V2 e nenhum fora dele = regra
  sobreajustada, e deve ser revista.
- [ ] **Modelo maior (aprovado por ela em 29/09):** depois do antes e depois com gpt-4o-mini, rodar
  o ponta a ponta com `--model gpt-5.5 --synth-model gpt-5.5` (o mesmo modelo do benchmark V1), saída
  `artifacts/v2/e2e-gpt-5.5-cobertura/`. Referência de volume: o ponta a ponta com gpt-4o-mini usou
  ~0,97 M tokens de entrada e ~0,08 M de saída. Comparar detecção (exata e equivalente) e CONFIRMED
  com o gpt-4o-mini na mesma versão do harness.
- [ ] Controle de confirmação falsa: rodar nas versões corrigidas (`fixed_full`, `--verification-sources-strict`)
  e exigir 0 `CONFIRMED`.
- [ ] Reprodutores novos em `docs/projeto/repro_esbmc_none/limitacoes_2026-09-29/`: função como valor
  (`functools.partial`, método referenciado sem chamada), `OrderedDict` como base.
- [ ] Atualizar `docs/v2/desenho_motor_verify.md` (regras de recorte, property, bases) e o slide de
  próximos passos.
- [ ] Commit por tarefa, só com autorização.

---

### Tarefa 7: detecção medida por expressão equivalente, além da exata

**Arquivos:**
- Modificar: `src/research_pipeline/v2_evaluator.py` (`_bug_detection_metrics`)
- Teste: `tests/test_v2_evaluator.py` (ou o teste atual do avaliador)

Hoje a expressão só conta se o texto for idêntico ao do gabarito. Medido na rodada ponta a ponta de
29/09 (104 itens): exata 19 (18%); equivalente ou contida 38 (37%); mesma linha 40 (38%). Exemplos
contados como erro hoje: `float(not_parsed)/float(num_substrings)` contra
`float(not_parsed) / float(num_substrings)` (só espaço) e `if ':' not in self._url:` contra
`':' not in self._url`.

Regra nova, reportada ao lado da exata (a exata não some, para comparar com relatórios antigos):
mesma função e (AST igual depois de tirar `if`/`return`/`elif`/`while` e `:` final, ou uma
expressão contida na outra). Chave nova no relatório: `expression_equivalent`.

- [ ] Testes: espaço diferente conta; `if X:` contra `X` conta; subexpressão conta; expressão de
  outra linha da mesma função não conta; função diferente não conta.
- [ ] Implementar `_equivalent(a: str, b: str) -> bool` e a métrica `expression_equivalent`.
- [ ] Recalcular os relatórios existentes sem LLM (`scripts/v2_reverdict.py` ou `evaluate_verify`)
  e atualizar o slide de RQ1 com as duas colunas.
