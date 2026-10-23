# CPython: TypeError (object of type 'C' has no len()) na linha do while.
# ESBMC master 7da3564: aborta com "Couldn't convert expression in unrecognised format" (cpp_throw), código 134.
# Reduzido do harness do nm_real_11 (LocalCache, base OrderedDict trocada por classe vazia). Sem a linha do
# super, o programa vira o 47.
class Base:
    pass


class C(Base):
    def put(self, key: str) -> None:
        while len(self) >= self.limit:
            pass
        super(C, self).put(key)


C().put(nondet_str())
