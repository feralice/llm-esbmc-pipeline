# CPython: TypeError (object of type 'C' has no len()).
# ESBMC master 4a356e33eb: FAILED com AttributeError (self.limit) em vez do TypeError de len(self); com limit
# definido, só unwinding assertion (o len vira strlen). Rascunho de issue: issues/47_len_without_dunder_len.md.
class C:
    def put(self, key: str) -> None:
        while len(self) >= self.limit:
            pass


C().put(nondet_str())
