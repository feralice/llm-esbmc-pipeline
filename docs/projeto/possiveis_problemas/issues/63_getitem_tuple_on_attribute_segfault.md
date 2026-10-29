# Draft issue for ESBMC (not posted)

Reproducer: `getitem_tupla_em_atributo.py`. Measured on 28/10/2026. Suggested labels: python, bug.
GitHub search on 28/10 ("__getitem__", "SIGSEGV python __getitem__", "wrong sort", "getitem tuple key python"):
no open issue. Related, all closed: #4514, #4539, #4541, #4542 (user `__getitem__` on a local or a parameter;
this one is on an attribute).

---

**Title:** [python] Tuple subscript on an attribute whose class defines `__getitem__` crashes the SMT encoder

### Summary
`obj.attr[0, 1]`, where `attr` is an instance of a class with a user-defined `__getitem__`, makes ESBMC
crash with SIGSEGV while encoding (Bitwuzla), or abort with an ill-sorted term (Z3). The subscript seems
to be lowered as a list index instead of a `__getitem__` call: with a scalar key the same shape reports a
spurious out-of-bounds read in `__ESBMC_list_at`.

### Reproducer
```python
class Loc:
    def __getitem__(self, key) -> int:
        return 0


class Frame:
    def __init__(self) -> None:
        self.loc: Loc = Loc()


fr = Frame()
assert fr.loc[0, 1] == 0
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check`

### Expected
CPython runs without error (`Loc.__getitem__` is called with `(0, 1)` and returns 0). Expected
`VERIFICATION SUCCESSFUL`.

### Actual
```
Encoding remaining VCC(s) using bit-vector/floating-point arithmetic

ESBMC caught SIGSEGV: this is an internal error, not a verification result.
```
Exit code 139, with or without `--no-pointer-check --no-align-check`. The backtrace
(`--segfault-handler`) ends in `smt_solver_baset::convert_ast_node` at `smt_solver.cpp:1558`
(the `lessthan` case), called from `convert_assign`. With `--z3`:
```
ERROR: Z3 error operator is applied to arguments of the wrong sort encountered
```
Variations:
- `fr.loc[0]` (scalar key): no crash, but `VERIFICATION FAILED` with
  `dereference failure: Access to object out of bounds` in `__ESBMC_list_at` (false positive).
- `fr.loc["a"]`: `ERROR: TypeError ... list indices must be integers or slices, not str`.
- `loc: Loc = fr.loc` followed by `loc[0, 1]`: `VERIFICATION SUCCESSFUL`.

### Version
ESBMC master 4a356e33eb (27 Oct 2026), Bitwuzla build (Z3 4.13.3 also linked), x86_64 Linux.
