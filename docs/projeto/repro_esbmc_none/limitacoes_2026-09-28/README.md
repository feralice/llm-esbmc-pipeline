# ESBMC-Python: operações com None e afins ainda não detectadas (inclusive com a PR #8014)

Data: 28/09/2026. Cada arquivo é um reprodutor mínimo. Rodar com `./rodar.sh` (ESBMC do PATH) ou `./rodar.sh /caminho/do/esbmc`.

Versões comparadas:

- **8.5.0**: release oficial (`/usr/local/bin/esbmc`).
- **PR #8014**: build do branch `fix/python-optional-is-none`, commit `2a30b76640` (`~/esbmc-src/build/src/esbmc/esbmc`).

Flags: `--z3 --unwind 6 --timeout 120s`. O CPython foi rodado forçando o caminho com `None` (`nondet_bool()` retornando `False`).

| Arquivo | Operação | CPython | ESBMC 8.5.0 | PR #8014 | Esperado |
|---|---|---|---|---|---|
| `01_methNone.py` | `e.shutdown()` com `e = None` | `AttributeError` | SUCCESSFUL | SUCCESSFUL | FAILED |
| `02_mul.py` | `t * s` com `t = None` | `TypeError` | erro do Z3 (`ast is not an expression`) | SUCCESSFUL | FAILED |
| `03_ge.py` | `n >= limit` com `limit = None` | `TypeError` | SUCCESSFUL | SUCCESSFUL | FAILED |
| `04_inNone.py` | `tag in classes` com `classes = None` | `TypeError` | exceção interna (`irep2_cast_error`) | idem | FAILED |
| `05_callstr.py` | `t.path()` com `path` sendo `@property` que retorna `str` | `TypeError` | SUCCESSFUL | SUCCESSFUL | FAILED |
| `06_floatstr.py` | `float("abc")` | `ValueError` | SUCCESSFUL | SUCCESSFUL | FAILED |
| `07_unbound.py` | `return k` depois de laço sobre dict vazio | `UnboundLocalError` | FAILED no `assert` seguinte (valor arbitrário, não `UnboundLocalError`) | idem | FAILED com `UnboundLocalError` |
| `08_getattr_d.py` | `getattr(t, "total", None)` | sem erro (retorna `None`) | `Unsupported function 'getattr' is reached` | idem | SUCCESSFUL |

`SUCCESSFUL` nas linhas 01 a 06 é falso negativo: o programa quebra no CPython, e o ESBMC diz que está seguro.

## Casos do dataset afetados

| Reprodutor | Casos de `dataset/v2_real_world` |
|---|---|
| 01 (método em None) | `nm_real_01`, `nm_real_24` |
| 02 (`None * n`) | `nm_real_02` |
| 03 (comparação com None) | `nm_real_11` |
| 04 (`in None`) | `nm_real_23` |
| 05 (chamar string) | `tm_real_12` |
| 06 (`float("abc")`) | `tm_real_09` |
| 07 (variável não ligada) | `vm_real_02` |
| 08 (`getattr` com default) | `nm_real_09`, `nm_real_25` (o fix usa `getattr`) |
