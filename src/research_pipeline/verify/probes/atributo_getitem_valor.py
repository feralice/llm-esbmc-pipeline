# Regra compat_attribute_item. Origem: docs/projeto/possiveis_problemas/66_desempacotar_getitem_de_atributo.py.
class M:
    def __getitem__(self, idx: int) -> tuple[int, int]:
        return 1, 2


class N:
    m: M = M()


n = N()
a, b = n.m[0]
assert a == 1
