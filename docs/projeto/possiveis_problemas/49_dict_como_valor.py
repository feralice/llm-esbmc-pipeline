# CPython: executa (d["a"] começa como {} e recebe "b").
# ESBMC master 7da3564: FAILED com `uncaught exception: KeyError` na linha 7 (falso positivo).
# defaultdict(list) e defaultdict(int) funcionam. `f(dict)` com o nome solto dá `Variable 'dict' is not defined`,
# e trocar por defaultdict(lambda: {}) aborta com `list indices must be integers or slices, not str`.
from collections import defaultdict
d = defaultdict(dict)
d["a"]["b"] = 1
assert d["a"]["b"] == 1
