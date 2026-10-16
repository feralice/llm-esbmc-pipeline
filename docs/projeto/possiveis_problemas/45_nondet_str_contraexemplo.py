# CPython: com s = "ab", AssertionError.
# ESBMC v8.6: VERIFICATION FAILED, mas o contraexemplo não mostra o valor de s (nem com
# --compact-trace, que mostra só s = &...nondet_str$1[0]). Com int e nondet_int() mostra x = 5.
s: str = nondet_str()
assert s != "ab"
