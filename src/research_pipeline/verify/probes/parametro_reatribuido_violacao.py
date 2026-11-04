# Regra compat_rebound_parameter. Gêmeo de parametro_reatribuido_valor com o assert invertido.
def f(d, k):
    k = d.get(k)
    assert k is None


f({"x": True}, "x")
