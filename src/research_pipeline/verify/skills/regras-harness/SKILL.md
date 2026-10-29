---
name: regras-harness
description: Fixed rules for writing harness.py so ESBMC-Python runs real code from original.py. Use when asked to build a verification harness.
---

# Rules for harness.py

Version: 4

1. Copy the body of the target function from original.py unchanged, unless the task itself allows a simplification. You may add type annotations to its signature.
2. Write the minimal stubs (classes, helper functions) the target needs. A stub must support every operation the target applies to its value (len, iteration, indexing, comparison, arithmetic) and must never raise.
3. Do not add assert statements. Do not guard the suspect expression.
4. Keep every stub inside harness.py. Do not create or import other local modules: the CPython replay runs harness.py alone.
5. End harness.py with a driver that calls the target with nondeterministic inputs, at module level.
6. Define a callee before its caller. ESBMC fails with "Cannot unpack empty" when a tuple returned by a function defined later is unpacked.
7. Run ESBMC on harness.py and fix it until it reaches VERIFICATION FAILED or VERIFICATION SUCCESSFUL instead of a conversion error.
8. If ESBMC crashes (exit code 134 or 139, or the message "Couldn't convert expression"), stop and reply ESBMC_CRASH. Do not rewrite the harness to dodge a crash.
9. Reading or writing an attribute of None does not raise AttributeError in ESBMC. Do not rely on it to expose a bug.
10. In the driver, pass nondeterministic values as arguments or constructor fields. A module-level `s: str = nondet_str()` read inside a function aborts ESBMC ("Unexpected index type in computer_pointer_offset").
11. In the driver, call a function by its own name, not through a module-level alias: `op = f; g(op(1))` aborts ESBMC ("type mismatch: expected code"). Both are the same function, so behaviour is unchanged.
12. In stubs and the driver, do not use an attribute that may be missing as an operand of `or`/`and`; split the condition into `if`/`elif`. `if flag or obj.limit:` aborts ESBMC ("Can't generate zero for type empty"), and `x = False or obj.limit` inside a function wrongly verifies as safe.
13. To index or unpack `obj.attr[key]` when the class of `attr` defines `__getitem__`, read `attr` into a local variable first: `a = obj.attr; a[key]`. Through the attribute, ESBMC crashes on a tuple key and reports "Cannot unpack pointer" on unpacking.
14. In a stub, do not reassign a parameter to the result of `dict.get()`; use a new name. `k = d.get(k)` fails with "Member 'is_none' is not a field of pointer_struct".
15. A callable that a stub passes around is a module-level `def`, not a `lambda` inside a method: ESBMC rejects it with "Variable 'p' is not defined in function 'lam1'".
16. Stubs use the `math` module, never the `__ESBMC_*` functions: the CPython replay runs harness.py as plain Python.
