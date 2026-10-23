# Draft issue for ESBMC (not posted)

Reproducer: `45_nondet_str_contraexemplo.py (earlier draft: ../rascunho_issue_nondet_str.md)`. Measured on 22/10/2026. Suggested labels: python, enhancement.

---

**Title:** [python] Counterexample does not show the value of a nondet_str()

### Summary
When a property fails because of a string from `nondet_str()`, the counterexample does not print the
string. For `nondet_int()` it prints the value. Without the value, the counterexample cannot be replayed in
CPython.

### Reproducer
```python
s: str = nondet_str()
assert s != "ab"
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check` (Z3 build; the Bitwuzla build with `--bitwuzla` gives the same result; same result with `--unwind 10` and without `--multi-property`)

### Expected
A state with the string, as for integers: the same program with `x: int = nondet_int()` and `assert x != 5`
prints `x = 5`. For example: `s = "ab"`.

### Actual
`VERIFICATION FAILED`, and the trace has no state with the value of `s`:
```
[Counterexample]
State 1 file main.py line 2 column 0 thread 0
Violated property:
  file main.py line 2 column 0
  assertion return_value$_strcmp$1 != 0
```
With `--compact-trace`, the only state for `s` is a pointer: `s = &main.py:1$nondet_str$1[0]`.

### Version
ESBMC master 7da3564989 (22 Oct 2026), x86_64 Linux. (also ESBMC 8.6.0 release)
