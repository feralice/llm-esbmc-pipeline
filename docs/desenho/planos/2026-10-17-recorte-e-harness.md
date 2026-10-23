# Recorte pelo caminho e correções do harness: plano

> Executado inline (superpowers:executing-plans), TDD em cada tarefa.

**Spec:** `docs/desenho/specs/2026-10-17-recorte-e-harness-design.md`

## Global Constraints

- Toda transformação preserva a numeração das linhas do módulo.
- Nenhuma chamada de LLM; nenhum commit sem a Fernanda.
- Suíte inteira em duas partes, cada uma com `timeout 10m`.

## Tarefas

1. **R5** `render._annotation`: `kind == "none"` vira `None`. Teste em `tests/test_verify_render.py`.
2. **R6** remover anotações em texto do módulo recortado (`grounding.ground`, antes do render). Teste em
   `tests/test_verify_grounding.py`: `def f(data: "DataFrame")` some do módulo e as linhas ficam iguais.
3. **R1** `fold_dead_guards(source)` em `verify/dead_guards.py`, aplicado em `ground` antes de
   `context_module`. Testes: `TYPE_CHECKING`, `sys.version_info < (3,)`, `and` com operando decidido, `elif`,
   linhas preservadas, programa sem guarda intocado.
4. **R2 + R3** em `slicing.prune_class`: métodos especiais removíveis sem gatilho saem; métodos chamados por
   métodos especiais mantidos ficam. Testes com classes mínimas (`with` presente e ausente; `__getitem__`
   chamando `self._empty_batch`).
5. **R4** atributos de classe sem uso na classe do receptor saem. Teste: atributo usado fica, sem uso sai.
6. **R7** nomes `compat_chr|ord|str|basestring` externos ligados ao builtin em `stub_imports`. Teste: o
   programa não declara stub de `compat_chr` e `compat_chr(0x110000)` levanta `ValueError` no replay.
7. Medição: `v2_replay_specs.py` nos 28 bugs (ids únicos, um diretório por pedaço), auditoria de controle,
   registro no README (Fase 20) e no documento do piloto.

## Review Focus

- Um método especial removido ainda chamado implicitamente (ex.: `__iter__` fora da lista) mudaria o
  comportamento: a lista do R2 é fechada.
- Guarda decidida com efeito colateral no teste (`if f() and PY2:`): o R1 só troca o teste quando todos os
  operandos não decididos podem ser descartados sem chamada (`and` com `False` antes de qualquer chamada).
