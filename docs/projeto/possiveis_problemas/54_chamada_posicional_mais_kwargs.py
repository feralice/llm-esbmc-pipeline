# CPython: executa sem erro (g recebe a=1; o dicionário vazio não acrescenta nada).
# ESBMC master 4a356e33eb: aborta na conversão com
#   "ERROR: [json.exception.type_error.302] type must be string, but is null".
# Basta uma chamada a função do usuário com argumento posicional ou nomeado seguido de **dict;
# g(**d) sozinho não aborta. Reduzido de nm_real_08 (Request.url_for repassa **kwargs a app.url_for).
def g(a):
    return a


d = {}
g(1, **d)
