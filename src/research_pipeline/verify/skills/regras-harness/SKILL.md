---
name: regras-harness
description: Fixed rules for writing harness.py so ESBMC-Python runs real code from original.py. Use when asked to build a verification harness.
---

# Rules for harness.py

Version: 1

1. Copy the body of the target function from original.py unchanged. You may add type annotations to its signature.
2. If ESBMC rejects a construct inside that body, simplify only that construct. Keep the function name, signature, the suspect expression and the branches that lead to it.
3. Write the minimal stubs (classes, helper functions) the target needs. A stub must support every operation the target applies to its value (len, iteration, indexing, comparison, arithmetic) and must never raise.
4. Do not add assert statements. Do not guard the suspect expression.
5. Keep every stub inside harness.py. Do not create or import other local modules: the CPython replay runs harness.py alone.
6. End harness.py with a driver that calls the target with nondeterministic inputs, at module level.
7. Define a callee before its caller. ESBMC fails with "Cannot unpack empty" when a tuple returned by a function defined later is unpacked.
8. Run ESBMC on harness.py and fix it until it reaches VERIFICATION FAILED or VERIFICATION SUCCESSFUL instead of a conversion error.
9. If ESBMC crashes (exit code 134 or 139, or the message "Couldn't convert expression"), stop and reply ESBMC_CRASH. Do not rewrite the harness to dodge a crash.
10. Reading or writing an attribute of None does not raise AttributeError in ESBMC. Do not rely on it to expose a bug.
