# Draft issue for ESBMC (not posted)

Reproducer: `repro.py` (reduced from Tarefa 10 passo 4 case `09c8208ce2b3`, `nl.mgrid[...]` in an NKI kernel).
Measured on 28/10/2026. Suggested labels: python, bug.
Has a behaviour-preserving workaround (annotated local alias, `repro_workaround.py`), so per the
"issue only without workaround" rule this may stay a draft.
GitHub search on 28/10 ("Cannot unpack pointer", open and closed): #4515 (closed, unpacking a tuple
*attribute*, `M, N = t.shape`, which now passes) and #8914 (open, unpacking an element of a mixed-type list
parameter). Neither covers unpacking the result of `__getitem__` called on an attribute.

---

**Title:** [python] Unpacking `obj.attr[i]` fails when `attr` is an instance with `__getitem__`

### Summary
Unpacking the tuple returned by a user `__getitem__` fails when the receiver is read from an attribute
(`n.m[0]`). The same call on a local or global variable converts. CPython runs the program without error.

### Reproducer
```python
class M:
    def __getitem__(self, idx: int) -> tuple[int, int]:
        return 1, 2


class N:
    m: M = M()


n = N()
a, b = n.m[0]
assert a == 1
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check`

### Expected
CPython runs without error. Expected `VERIFICATION SUCCESSFUL`.

### Actual
```
ERROR: Cannot unpack pointer - only tuples and arrays can be unpacked
```

| program | ESBMC | CPython |
|---|---|---|
| above | refused | passes |
| `self.m = M()` in `N.__init__` instead of class attribute | same error | passes |
| `t = n.m[0]` then `a, b = t` | same error | passes |
| `n.m.__getitem__(0)` explicitly | same error | passes |
| `mm = n.m` then `a, b = mm[0]` | same error | passes |
| `mm: M = n.m` then `a, b = mm[0]` | SUCCESSFUL | passes |
| `a, b = M()[0]` | SUCCESSFUL | passes |
| `t = n.m[0]`, `assert t[0] == 1` | `subscripting a value whose type is not known is not supported` | passes |

Same result with Bitwuzla and `--z3`.

### Version
ESBMC master 4a356e33eb (28 Oct 2026), Bitwuzla build, x86_64 Linux.
