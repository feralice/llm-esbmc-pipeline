# Limite observado no gerador de Pytest do ESBMC

## Resultado

O ESBMC 8.5.0 consegue gerar um contra-teste Pytest válido para um harness com
nome de módulo Python válido (`pytest_name_probe.py`). Porém, no arquivo
`4_inline_nondet_ok.py`, ele produz:

- `from 4_inline_nondet_ok import *`, que não é uma importação Python válida;
- o identificador SSA `s&0#1` em `@pytest.mark.parametrize` e na assinatura da
  função, que também não é um identificador Python válido.

Isso é um defeito do artefato emitido pelo gerador externo, não uma confirmação
executável do pipeline.

## Reprodução

```bash
esbmc --incremental-bmc --max-k-step 5 \
  --generate-pytest-testcase \
  --pytest-output-dir /tmp/esbmc-pytest \
  docs/projeto/repro_esbmc_none/4_inline_nondet_ok.py
```

Arquivo emitido:

```python
from 4_inline_nondet_ok import *

@pytest.mark.parametrize("s&0#1", [-1])
def test_test_function(s&0#1):
    test_function(s&0#1)
```

## Tratamento no projeto

`generate_pytest_testcase` agora aplica `ast.parse` ao arquivo recém-criado.
Quando o artefato é inválido, registra `status="invalid_generated_test"` e o
caminho do arquivo, mantendo intacta a classificação formal produzida pelo
ESBMC. O artefato fica disponível para auditoria, mas não deve ser apresentado
como teste reproduzível até ser corrigido ou regenerado.
