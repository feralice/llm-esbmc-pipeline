# Draft issue for ESBMC (not posted)

Reproducer: `77_bytearray_nao_suportado.py` (this folder). Measured on 08/11/2026, ESBMC master `822227ff96`, rechecked on `95f025adf4` (same result). Suggested labels: python, bug.
GitHub search on 08/11 (all 851 issues with the `python` label, filtered by title): no issue about `bytearray` (open or closed).
Classification: no behaviour-preserving workaround.

---

**Title:** [python] Support `bytearray` (feature request)

### Reproducer
```python
def f(n: int) -> int:
    b = bytearray()
    b.append(n)
    return len(b)


assert f(1) == 1
```

### Command
`esbmc main.py --unwind 5 --no-pointer-check --no-align-check`

### Expected
CPython runs without error. Expected `VERIFICATION SUCCESSFUL`.

### Actual
`ERROR: bytearray is not supported; use bytes for an immutable byte sequence`. The refusal is intentional (PR #5515 replaced a SIGABRT by this message), so this is a request for a model. Real code that builds packets (MQTT clients, CAN log readers) uses `bytearray` for mutation; `bytes` is not a faithful rewrite.
