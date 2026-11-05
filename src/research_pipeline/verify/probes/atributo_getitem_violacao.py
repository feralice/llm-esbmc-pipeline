# Regra compat_attribute_item. Gêmeo de atributo_getitem_valor com o assert trocado.
class M:
    def __getitem__(self, idx: int) -> tuple[int, int]:
        return 1, 2


class N:
    m: M = M()


n = N()
a, b = n.m[0]
assert a == 2
