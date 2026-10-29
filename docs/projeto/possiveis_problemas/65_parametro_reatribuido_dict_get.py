# CPython: executa sem erro (k recebe True do dicionário).
# ESBMC master 4a356e33eb: "ERROR: Member 'is_none' is not a field of pointer_struct" e "SMT solver failed".
# Gatilho: parâmetro que chega como str reatribuído ao Optional de dict.get(). No nível do módulo passa.
# Reduzido de av_real_01 (youtube-dl cli_bool_option: param = params.get(param)).
def f(d, k):
    k = d.get(k)
    assert k is not None


f({"x": True}, "x")
