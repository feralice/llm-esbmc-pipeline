# Rascunho de issue para o pymodbus (NÃO publicado)

Para a Fernanda revisar. Só publicar com o OK dela. Conferido em 10/11/2026 no commit `c50599b8` (versão
`4.0.0dev17`, Python 3.12.3), que era o HEAD do upstream no `git fetch` feito nesse dia. A busca por issues
(`build_msg`, `Log IndexError`) não achou nenhuma igual. O repositório pede o modelo em
`.github/ISSUE_TEMPLATE/issue-template.md`: conferir os campos antes de publicar.

O que está provado e o que não está:
- Provado: os três resultados abaixo, rodados na cópia local do código.
- Não provado: nenhuma chamada de `Log.*` dentro do próprio pymodbus passa hoje uma string vazia ou começando
  com `:` em posição 2 ou depois (conferi à mão, não é uma análise completa). Então o título não diz que o
  pymodbus quebra no uso normal.

Como o scan achou: pipeline LLM + ESBMC-Python (hipótese da LLM, confirmada por execução direta em CPython, sem
harness). Declarar isso na issue só se ela quiser.

---

## Título

`Log.build_msg` raises on a string argument that is empty or starts with ":"

## Texto (no formato do modelo do repositório)

### Versions

- Python: 3.12.3
- OS: Linux (WSL2)
- Pymodbus: 4.0.0dev17 (commit c50599b8, development branch)
- Modbus Hardware (if used): none

### Pymodbus Specific

- Server: not used
- Client: not used (the problem is in `pymodbus/logging.py`)

### Description

`Log.build_msg` treats any `str` argument that follows another argument as a possible format marker (`":hex"`,
`":str"`, `":b2a"`). The check is `args[i + 1][0] == ":"`, so:

1. an empty string raises `IndexError`;
2. a string that starts with `":"` but is not one of the markers (for example `":502"`) falls into the final
   `else` branch, is treated as `":b2a"`, and raises `TypeError`.

`build_msg` runs when a log line is emitted, so a value that is empty or starts with a colon raises inside the
logging call. I did not find a call inside pymodbus that passes such a value in that position today; it affects
callers that pass free text as a later argument. Expected: the value is logged like any other argument.

A possible fix is to compare against the three markers instead of looking at the first character:

```python
if (
    i < count_args
    and isinstance(args[i + 1], str)
    and args[i + 1] in (":hex", ":str", ":b2a")
):
```

### Code and Logs

```python
from pymodbus.logging import Log

Log.build_msg("{} {}", 0, "")           # IndexError: string index out of range
Log.build_msg("{} {}", 0, ":8080")      # TypeError: a bytes-like object is required, not 'int'
Log.build_msg("{} {}", "host", ":502")  # TypeError: a bytes-like object is required, not 'str'
Log.build_msg("{} {}", 0, "ok")         # '0 ok'
```
