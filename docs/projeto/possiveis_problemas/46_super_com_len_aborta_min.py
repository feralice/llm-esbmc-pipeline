# CPython: AttributeError ('C' object has no attribute 'limit') na linha do while.
# ESBMC master 7da3564: aborta com "Couldn't convert expression in unrecognised format" (cpp_throw), código 134.
# Não precisa de super nem len: basta uma exceção na condição do while e outra propriedade depois do laço.
class C:
    pass


c = C()
while c.limit:
    pass
x = 1 // 0
