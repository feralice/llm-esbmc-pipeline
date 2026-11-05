# Rascunho: pytest gerado chama função com argumentos extras

Observado no ESBMC 8.6.0, master `451f54cab6`, em 05/11/2026. A busca por PRs
abertos com `pytest nondet arguments` não retornou resultados. A issue fechada
[#7188](https://github.com/esbmc/esbmc/issues/7188) também relata chamadas com
quantidade incorreta de argumentos no pytest gerado. Conferir se este caso tem
a mesma causa antes de abrir uma nova issue.

Salve como `inverse.py`:

```python
def inverse(n: int):
    return 100 // n

inverse(__VERIFIER_nondet_int())
```

Execute `esbmc inverse.py --unwind 5 --no-slice --no-unwinding-assertions --generate-pytest-testcase --pytest-output-dir out`.
Para executar o teste com Python, remova a chamada `inverse(__VERIFIER_nondet_int())`
do arquivo original após a geração. O teste gerado chama `inverse(arg0, arg1)`, mas a função
recebe um argumento. Assim, o teste falha com `TypeError`, sem reproduzir a
divisão por zero. O comportamento esperado é uma chamada com um argumento que
reproduza a divisão por zero. Conferir também issues fechadas e PRs relacionados
antes de enviar este rascunho.
