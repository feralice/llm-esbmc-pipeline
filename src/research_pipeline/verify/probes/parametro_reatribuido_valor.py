# Regra compat_rebound_parameter. Origem: docs/projeto/possiveis_problemas/65_parametro_reatribuido_dict_get.py.
def f(d, k):
    k = d.get(k)
    assert k is not None


f({"x": True}, "x")
