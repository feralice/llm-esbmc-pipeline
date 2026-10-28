# CPython: AttributeError ('R' object has no attribute 'prev') na última linha.
# ESBMC master 4a356e33eb: VERIFICATION SUCCESSFUL, um falso negativo.
# O atributo é criado fora do __init__ só no objeto a; o ESBMC passa a tratar 'prev' como existente em
# toda instância de R. Sem a linha de a, ou com b no lugar de a, o ESBMC acusa AttributeError.
# Reduzido de nm_real_12: o PamdRule real não chama super().__init__, então o primeiro nó não tem prev.
class R:
    pass


a = R()
b = R()
a.prev = None
b.prev
