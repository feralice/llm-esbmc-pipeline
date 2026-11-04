# Draft issue for ESBMC (not posted)

Reproducer: `repro.py` (this folder). Measured on 28/10/2026. Suggested labels: python, bug.
GitHub search on 28/10 ("is_none is not a field of pointer_struct", "Member 'is_none'", "is_none",
"pointer_struct python", "dict.get parameter"): no matching issue, open or closed.
Classification: has a behaviour-preserving workaround (bind the result to a new name), see the end.

---

**Title:** [python] Reassigning a str parameter with `dict.get()` aborts the encoder: `Member 'is_none' is not a field of pointer_struct`

### Summary
When a function parameter that receives a `str` is rebound to the result of `dict.get()` (an
`Optional` value), ESBMC keeps the parameter's string type for the new value. The `is not None` check then
reads `is_none` from a pointer and the SMT encoder aborts. CPython runs the program without error.

### Reproducer
```python
def f(d, k):
    k = d.get(k)
    assert k is not None


f({"x": True}, "x")
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check`

### Expected
CPython runs without error (`k` becomes `True`). Expected `VERIFICATION SUCCESSFUL`.

### Actual
Exit code 2:
```
ERROR: Member 'is_none' is not a field of pointer_struct, whose members are: pointer_object, pointer_offset
ERROR: member name not found in struct type
  FAILED       [strlen.assertion.1]           line  93  unwinding assertion loop 4
  NOT CHECKED  [__ESBMC_list_at.assertion.1]  line 697  out-of-bounds read in list
  NOT CHECKED  [f.assertion.1]                line   3  assertion !k.is_none
ERROR: SMT solver failed
```
The `strlen` unwinding failure also suggests the rebound `k` is still treated as a `char *`.

| variant | ESBMC | CPython |
|---|---|---|
| reproducer above | abort (`is_none` on `pointer_struct`) | runs |
| `assert isinstance(k, bool)` instead of `is not None` | same abort | runs |
| `def f(k: str)` with `d = {"x": 1}` local, `k = d.get(k)` | same abort | runs |
| `v = d.get(k)`, `assert v is not None` (new name) | SUCCESSFUL | runs |
| same rebinding at module level (`k = "x"; k = d.get(k)`) | SUCCESSFUL | runs |

Same result with the Z3 build option `--z3`, with `--unwind 10` and without `--multi-property`.
Reduced from a harness of youtube-dl's `cli_bool_option`, which does `param = params.get(param)`.

### Version
ESBMC master 0945ac9 (3 Nov 2026; main reproducer re-checked, same result as on 4a356e33eb, 27 Oct), Bitwuzla build, x86_64 Linux.
