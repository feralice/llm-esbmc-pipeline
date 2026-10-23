# CPython: TypeError (object of type 'C' has no len()).
# ESBMC master 7da3564: VERIFICATION SUCCESSFUL (falso negativo).
class C:
    def put(self, key: str) -> None:
        while len(self) >= self.limit:
            pass


C().put(nondet_str())
