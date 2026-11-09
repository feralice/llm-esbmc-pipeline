# Draft issue for ESBMC (not posted)

Reproducer: `76_bytes_vazio_indice_falso_negativo.py` (this folder). Measured on 08/11/2026, ESBMC master `822227ff96`, rechecked on `95f025adf4` (same result). Suggested labels: python, bug.
GitHub search on 08/11 (all 851 issues with the `python` label, filtered by title): no issue about indexing `bytes`.
Classification: has a workaround (`len(d) > 0 and d[0] == b"P"`), but the verifier answers safe where the code is not.

---

**Title:** [python] `d[0] == b"P"` on possibly empty bytes generates no VCC: the IndexError is lost

### Reproducer
```python
def f(d: bytes) -> int:
    if d[0] == b"P":
        return 1
    return 0


f(b"")
```

### Command
`esbmc main.py --unwind 5 --no-pointer-check --no-align-check`

### Expected
CPython raises `IndexError` (index out of range). Expected `VERIFICATION FAILED` with an IndexError.

### Actual
`Generated 0 VCC(s), 0 remaining after simplification` and `VERIFICATION SUCCESSFUL` (a false negative). `x = d[0]` alone and `d[0] == 80` are reported correctly; the comparison with a one-byte `bytes` literal seems to be folded before the index check. This is a hypothesis, I did not read the frontend.
