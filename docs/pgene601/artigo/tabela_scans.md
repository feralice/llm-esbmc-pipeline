# Scans em repositórios reais

Levantamento dos arquivos existentes, preparado com apoio do Codex. As contagens são de hipóteses e vereditos do pipeline, não de defeitos reais. Um harness é o programa montado para executar a função sob condições escolhidas; reproduzir nele não garante que essas condições ocorram no projeto. Os commits abaixo são os HEADs das cópias locais conferidas; a identidade exata da árvore usada em cada scan, incluindo eventuais mudanças locais naquela ocasião, é não conferida.

| Repositório e pasta | Commit local conferido | Funções analisadas | Hipóteses enviadas à verificação | Vereditos por tipo | Modelo / backend | Tokens ou custo registrados |
|---|---|---:|---:|---|---|---|
| pymodbus, `artifacts/scan_pymodbus_codex_2026-11-10/` | `c50599b80752255517c2370cf3b62b0cb8c61f32` | 20, conforme registro anterior | não conferido para a rodada atual; registro anterior descreve 10 verificadas | parcial anterior: 3 `UNSUPPORTED`, 3 `UNVALIDATED`, 2 `REPRODUCED_CPYTHON`, 1 `STUB_INDUCED`, 1 `PIPELINE_ERROR`; não é resultado final | Codex / `codex`; modelo exato não conferido | não conferido |
| pyserial, `artifacts/scan_pyserial_2026-11-10/` | `a5c48d445fbc1943d4fabf8d9090a50fda3172fd` | 20 | 32 | `CONFIRMED` 2, `UNVALIDATED` 3, `OTHER_FAILURE` 3, `NOT_CONFIRMED` 1, `ESBMC_TIMEOUT` 3, `ESBMC_ERROR` 2, `LLM_ONLY` 17, `BOUND_INCONCLUSIVE` 1 | `claude_cli`, modelo exato não registrado no relatório | detecção 27.464 tokens; verificação 49.029; custo registrado 0, não comprova ausência de custo da assinatura |
| aws-cost-explorer-report, `/mnt/e/scan_amazon/cost-explorer_2026-11-10/` | `fbb04e0977352fd2e89c3eb369d1e847fe988942` | 7 | 6 | `ESBMC_TIMEOUT` 1, `LLM_ONLY` 5 | modelo e backend não conferidos | detecção 6.337 tokens; verificação 16.642; custo registrado 0, modo de cobrança não conferido |
| aws-glue-samples, `/mnt/e/scan_amazon/glue_haiku_lote1/` | `406ae649637555548e174c07a5f923e5b4003ca0` | 15 | 16 | `CONFIRMED` 1, `UNVALIDATED` 2, `OTHER_FAILURE` 3, `LLM_ONLY` 10 | `haiku`; backend não conferido | detecção 74.322 tokens; verificação 66.922; custo registrado 0, modo de cobrança não conferido |
| aws-secrets-manager-rotation-lambdas, `/mnt/e/scan_amazon/rotation_haiku_lote1/` | não preenchido | em andamento | em andamento | em andamento | não preenchido | não preenchido |

Fontes: `scan_summary.md` e `scan_report.json` de cada pasta com resultado; para pymodbus, `docs/experimentos/scan_pymodbus_codex_2026-11-10.md`. Rotation não tinha `scan_summary.md` na conferência. No pymodbus, o checkpoint atual contém detecção parcial e nenhum veredito; arquivos `scan_verify_discarded_*.json` preservam tentativas anteriores, que não devem ser somadas. O registro descreve outros resultados parciais, mas não localizei um relatório JSON completo para eles.

## Análise das hipóteses

As linhas indicam a classificação da evidência disponível, não uma conclusão sobre todas as formas de uso. Não executei ESBMC nem uma nova varredura.

### pymodbus

- `Log.build_msg`, `args[i + 1][0]`, `REPRODUCED_CPYTHON`: **defeito reproduzido no código real para a chamada concreta abaixo**. `pymodbus/logging.py:128` e `:136-140` acessam o primeiro caractere sem verificar se a string tem conteúdo. `Log.build_msg('{} {}', 0, '')` produz `IndexError`. O relatório anterior também registra a chamada por `Log.info`; o ESBMC não decidiu. Fernanda informou que abriu a [issue #3085](https://github.com/pymodbus-dev/pymodbus/issues/3085); o conteúdo da página não foi conferido nesta atualização. Frequência e contexto de uso não foram medidos.
- `pack_bitstring`, `REPRODUCED_CPYTHON`: **indeterminado**. O teste preservado em `agent_cases/5308cd3b73ee/pytest/test_replay.py` passa `None`; a chamada real também produz `TypeError`. Porém `pymodbus/pdu/utils.py:9` declara uma sequência de booleanos, e não está demonstrado que `None` seja entrada válida ou alcançável num uso suportado. Falta rastrear um caminho real com essa entrada e seus contratos. A exceção por entrada fora do tipo, por si, não prova defeito.
- `DecodePDU.add_sub_pdu`, atribuição à tabela, `CONFIRMED` arquivado (`0f66614870fb`): **falso positivo do harness para o fluxo de registro examinado**, com limite de escopo. O harness arquivado insere `None` na tabela e passa instâncias. O código real `pymodbus/pdu/decoders.py:17-18,47-51` declara tabela de dicionários e cria `{}` para uma chave nova; a assinatura recebe classes. Não identifiquei caminho normal que insira esse `None`. Como a tabela é mutável, isso não prova que nenhum código externo possa alterá-la. Não houve reprodução no projeto.
- `DecodePDU.add_sub_pdu`, acesso `req.function_code` (`215328cb93f9`), `UNVALIDATED` arquivado: **indeterminado**. A assinatura em `decoders.py:47` espera classe de PDU e a leitura ocorre em `:49`; o relatório registra `TypeError`, não reprodução da hipótese de atributo ausente. É necessário identificar a classe e a entrada do contraexemplo e verificar uma chamada real. A outra tentativa foi `STUB_INDUCED`, categoria distinta.
- `DecodePDU.add_sub_pdu`, acesso `req.sub_function_code` (`eb18942daf7a`), `UNVALIDATED` arquivado: **indeterminado**. A leitura ocorre em `decoders.py:51`; o relatório registra `TypeError` sem reprodução equivalente. Falta demonstrar uma classe recebida no fluxo real sem o atributo e isolar a causa da divergência.
- A mesma atribuição `0f66614870fb` também aparece como `UNVALIDATED` em outra tentativa arquivada. É a mesma hipótese, não outro defeito; o estado e o resultado dessa tentativa precisam ser reconstituídos antes de uma classificação mais ampla.

Comando executado nesta conferência para os três casos concretos, incluindo `iterbytes` do pyserial:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/home/fernanda/alvos/pymodbus:/home/fernanda/alvos/pyserial .venv/bin/python - <<'PY'
from pymodbus.logging import Log
from pymodbus.pdu.utils import pack_bitstring
from serial.serialutil import iterbytes
for label, fn in [('Log.build_msg', lambda: Log.build_msg('{} {}', 0, '')),
                  ('pack_bitstring', lambda: pack_bitstring(None)),
                  ('iterbytes', lambda: next(iterbytes(None)))]:
    try:
        print(label, 'retorno', fn())
    except Exception as e:
        print(label, type(e).__name__, str(e))
PY
```

Saída: `Log.build_msg IndexError string index out of range`; `pack_bitstring TypeError 'NoneType' object is not iterable`; `iterbytes TypeError 'NoneType' object is not subscriptable`.

### pyserial

- `rfc2217_set_control`, chave `control` (`48f8b0af4b96`), e `rfc2217_send_purge`, chave `purge` (`a7a990b400a1`), ambos `CONFIRMED`: **falso positivo do harness para o fluxo normal de abertura**. `serial/rfc2217.py:397` inicializa o atributo como `None`; `:449-453` constrói o dicionário com ambas as chaves; `:881-892` as lê. Os programas gerados substituem a inicialização por dicionário arbitrário. A observação não prova invariantes diante de mutação externa ou chamadas fora do ciclo normal. Não reproduzidos no código real com abertura de porta.
- `iterbytes`, fatia `b[i:i + 1]` (`9e86868d788e`), `UNVALIDATED`: **indeterminado**. `serial/serialutil.py:40-49` aceita a fatia sem validar o argumento; o teste direto acima mostra `TypeError` com `None`. O replay do harness usa objeto artificial sem suporte a subscript e o ESBMC relata também limites de laço e acesso; não há correspondência estabelecida. Falta demonstrar que `None` é entrada válida ou alcançável em chamada real.
- `Miniterm.update_transformations`, `EOL_TRANSFORMATIONS[self.eol]` (`d6833d552492`), `UNVALIDATED`: **indeterminado**. `serial/tools/miniterm.py:403-412` recebe `eol` e o armazena; `:354-358,462-465` usa as chaves previstas. A interface de linha de comando restringe as opções em `:926-930`, mas o construtor pode receber outros valores. O replay usa `None` e registra `KeyError`, enquanto o ESBMC registra `IndexError` e limites de laço. Falta verificar o contrato público e reproduzir o caso pelo uso real antes de chamá-lo defeito.
- `Serial._reconfigure_port`, `RFC2217_STOPBIT_MAP[self._stopbits]` (`b331bb35a65f`), `UNVALIDATED`: **indeterminado, com estado artificial possível**. `serial/serialutil.py:340-345` valida `stopbits` no setter antes de atribuí-lo; o harness substitui a inicialização e permite `None`, além de criar constantes simbólicas. O replay não reproduziu. Falta demonstrar o valor concreto que o ESBMC usou e se há caminho real que contorne o setter.

### aws-glue-samples

- `write_df_to_catalog`, `options['catalog.database']` (`3066409656c4`), `CONFIRMED`: **falso positivo do harness para os caminhos de linha de comando examinados**, com limite de escopo. `utilities/Crawler_undo_redo/src/scripts_utils.py:50-55` acessa a chave quando o dataframe não está vazio. `crawler_redo_from_backup.py:48-53` e `crawler_undo.py:95-101` a colocam nas opções; os chamadores passam esse dicionário. O harness permite opções sem a chave. Uma chamada direta diferente poderia omiti-la, mas não foi demonstrado que seja uso válido ou defeito no fluxo do projeto. Não houve reprodução no projeto com Glue.
- `catalog_dict`, filtro e seleção (`40feeb673efc`) e expansão `col.*` (`d2445c5fc3d3`, reparada como `6a062fe8fd63`), ambos `UNVALIDATED`: **indeterminado**. `scripts_utils.py:60-66` encadeia operações de dataframe; `:76-89` obtém dados de catálogo ou S3. Os dois replays falham porque o objeto artificial `_Opaque` não tem `select`, e o ESBMC registra tipo de método desconhecido. Isso evidencia limite do harness e da verificação, não prova que os dados reais tenham esquema inválido. Falta reproduzir com Spark/Glue e dados concretos, incluindo os contratos do formato de backup.

## Limitações e pendências

O relatório de pymodbus não preserva, no checkpoint atual, todos os vereditos descritos no registro anterior. As hipóteses acima foram identificadas pelos arquivos arquivados e testes gerados; pode haver outros casos daquele estado parcial que precisem ser recuperados. Não se deve contar `UNVALIDATED` como defeito confirmado. Para as hipóteses sem comando de reprodução acima, não houve reprodução direta nesta conferência. Os caminhos de código são relativos às cópias em `/home/fernanda/alvos/` e as pastas de resultados são as indicadas na tabela.
