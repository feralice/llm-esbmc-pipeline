# Gerador de pytest com nondet_str().
# ESBMC master 7da3564: com --unwind 5 o primeiro FAILED é `unwinding assertion` do strlen, e o teste gerado
# usa "" (não reproduz). Com --no-unwinding-assertions o FAILED é o ValueError e o teste usa "ab", que reproduz.
def f(s: str) -> int:
    if s == "ab":
        raise ValueError("ab")
    return len(s)


f(nondet_str())
