# Execução técnica do plano 2 de 14/11/2026

Plano: `docs/projeto/PLANO_CODEX_2_2026-11-14.md`.

P1, P2, P3 e P5 estão implementadas. O script de atualização da seção 5 foi preparado, sem executar a atualização. A entrega para neste ponto, conforme a seção 6 do plano. O ESBMC não foi atualizado ou recompilado. Nenhuma chamada à LLM, scan, rodada real, commit, tag ou envio ao GitHub foi feito.

## O que mudou

### P1: perfil congelado

O perfil `--profile congelado` reúne estas opções para os experimentos V2, nos modos `hybrid` e `benchmark`:

| Opção | Valor do perfil |
|---|---|
| Isolamento da chamada Claude | Ligado |
| Coleta automática de lições | Desligada |
| Retentativas operacionais | 2 |
| Trabalhadores paralelos | 1 |
| Autocura | `error+kb` |
| Exigência de ESBMC recente em relação ao checkout local | Ligada |
| Cache da base de conhecimento por conteúdo | Ligado |
| Avaliação por função | Ligada |

As opções explícitas vencem o perfil, inclusive quando têm o valor padrão. Foi corrigida uma diferença do código anterior: por exemplo, `--profile medicao --operational-retries 0` antes acabava com duas retentativas; agora mantém zero. Sem perfil, os valores padrão permanecem iguais. `padrao` continua sem acrescentar uma chave de perfil à configuração.

No perfil congelado, `--no-claude-isolated`, `--no-kb-content-cache` e `--no-evaluate-by-function` permitem desligar explicitamente essas opções. O isolamento só é aplicado pelo backend Claude CLI. O efeito do isolamento sobre hooks e configuração global ainda não foi medido.

### P2: procedência do ESBMC

O novo módulo `verify/esbmc_provenance.py` registra:

- Caminho, hash SHA-256, data e versão do binário. O hash identifica seu conteúdo.
- Caminho e hash do wrapper, quando o comando usa um script intermediário.
- Raiz do checkout, commit, data do commit e presença de alterações locais.
- Hash do README e dos documentos centrais disponíveis da base de conhecimento.
- Hash do conteúdo usado pelo índice, incluindo exemplos de regressão.

No perfil congelado, a checagem ocorre antes de construir os clientes da LLM. A rodada para com uma mensagem pedindo recompilação se a data do binário for anterior à do commit local. A procedência fica na configuração do relatório, no checkpoint e na impressão digital usada para retomar. Recompilar ou substituir o binário no meio da rodada impede reaproveitar silenciosamente o checkpoint. Comando encontrado pelo `PATH` é convertido para o caminho conferido, também usado para localizar a base de conhecimento.

Essa checagem compara o binário com o checkout **local**. Ela não consulta o servidor remoto e não comprova, pela data sozinha, que o binário foi compilado exatamente daquele código. Alterações locais são registradas; não são apagadas ou corrigidas automaticamente. Atualizar o checkout continua sendo uma etapa separada, autorizada por Fernanda.

### P3: cache da base de conhecimento

O teste confirmou que o cache anterior não se renovava quando um documento mudava sem novo commit. Com `--kb-content-cache`, a chave inclui o conteúdo dos documentos e exemplos usados no índice. Uma mudança nesses arquivos produz outro índice, mesmo mantendo o commit.

A opção fica ligada no perfil congelado. Sem ela, o cache conserva sua chave e seu comportamento anteriores, conforme a exigência de manter o padrão inalterado. A correção não acrescenta documentos extras nem muda a busca por trechos.

### P5: avaliação por função

A opção `--evaluate-by-function`, ligada pelo perfil congelado, acrescenta `evaluation.by_function`. Não substitui as métricas de linha, expressão ou localização.

Cada caso rotulado conta uma única vez:

- `apontado`: há hipótese em uma das funções do rótulo, mesmo se a expressão for outra. Inclui hipóteses retidas, limitadas ou retiradas pela revisão.
- `apontado_e_reproduzido`: além disso, uma hipótese naquela função tem replay da exceção esperada.
- `confirmado_esbmc`: entre esses casos reproduzidos, há confirmação pelo ESBMC.

O relatório também contém os casos individuais e uma tabela de dados separada, `mesmo_padrao_em_outra_funcao`, derivada do gabarito das funções tocadas pelo patch. Os casos `pymodbus_2977`, `pycomm3_331` e `gps_127` ficam fora dessa tabela até a avaliação de Fernanda. Eles continuam na avaliação principal de funções rotuladas.

Na etapa de detecção, replay e confirmação ficam como `null`, isto é, não medidos. Os nomes das exceções são comparados exatamente: um nome genérico `error` não comprova `struct.error`. Um replay marcado como falha em outra linha conta apenas quando essa linha está dentro da função alvo, para não contar um erro na preparação do programa como reprodução do caso.

## Medição por leitura do relatório de 07/11

Fonte: `artifacts/pgene601/ajustes-2026-11-07/v2_verify_report.json`, com 123 hipóteses verificadas. Não houve nova execução dessas hipóteses.

| Medida por função | Casos |
|---|---:|
| Casos avaliados | 47 |
| Apontados | 47 |
| Apontados e reproduzidos com a exceção esperada | 8 |
| Reproduzidos e confirmados pelo ESBMC | 5 |
| Casos na tabela separada de funções irmãs | 0 |

Os oito casos reproduzidos foram `cps_pythoncan_1293`, `cps_blinka_434`, `cps_opcua_671`, `cps_pycomm3_331`, `cps_gps_60`, `cps_gpiozero_716`, `cps_simpleio_43` e `cps_paho_118`.

As métricas anteriores recalculadas ficaram exatamente iguais às gravadas. Como apoio, a detecção antiga por expressão equivalente contou 38 casos, e a confirmação antiga por expressão equivalente contou 5. Esses números usam regras diferentes das novas contagens por função; não são resultado de uma melhoria medida na LLM.

Os dados completos, as métricas antigas e os hashes dos arquivos de entrada estão em `docs/experimentos/AVALIACAO_FUNCOES_2026-11-14.json`. A leitura não mede generalização, alcance pelo código real, efeito do isolamento, ganho do cache ou efeito de contexto adicional.

## Script de atualização preparado

Foi escrito `scripts/atualizar_esbmc.sh`. O modo `--check` apenas lê a configuração dos solvers e a procedência. Sem escolher um modo, o script termina sem atualizar nada. O modo `--execute` deve ser usado somente depois de Fernanda autorizar.

O script foi escrito para conferir Bitwuzla e Z3 no cache de `build-bw`, recusar checkout com alterações locais, testar antes e depois o programa já confirmado de `cps_simpleio_43`, executar `git pull --ff-only`, compilar com `ninja -C build-bw esbmc` e registrar uma linha em `docs/experimentos/ESBMC_VERSOES.md` após as checagens passarem. Esse registro ainda não foi criado, pois a atualização não ocorreu.

Os logs antigos mostram Ninja em `build-bw`, Bitwuzla 0.9.0 e Z3 4.13.3. O cache consultado confirma os dois solvers ligados e `RelWithDebInfo`. Os logs não contêm a linha completa da configuração original; o script reutiliza o cache existente para conservar as opções e os caminhos de dependências. Não inventa uma nova configuração.

Se a compilação incremental não atualizar a data do binário, mas o commit for mais novo, o script para na checagem de data. Uma recompilação limpa pode ser necessária; o script não altera datas para contornar essa checagem. O fluxo real de atualização e o teste real antes e depois ainda não foram executados ou validados nesta entrega.

## Testes e como conferir

Os testes das funcionalidades novas reproduziram ausências ou falhas antes das correções. Testes adicionais conferiram integração e compatibilidade. A revisão automatizada encontrou dois ajustes necessários: recusar o perfil congelado no scan e incluir hipóteses retiradas pela revisão nas métricas novas. Ambos foram reproduzidos com testes e corrigidos.

Comando dos testes por arquivo:

```bash
python -m pytest -q tests/test_profiles.py tests/test_esbmc_provenance.py tests/test_esbmc_knowledge.py tests/test_v2_evaluator.py tests/test_verify_report.py tests/test_main_v2.py tests/test_healing_healer.py tests/test_atualizar_esbmc.py tests/test_healing_loop.py tests/test_scan_pipeline.py
```

Resultado final: **189 testes passaram em 7,35 segundos**. A suíte completa e o `pylint` não foram executados, conforme a etapa de entrega prevista no plano. Os testes de procedência usam um repositório git temporário e um script que imita o binário. O teste do atualizador usa apenas `--check` com esse binário falso. Os testes da LLM usam analisadores falsos.

A impressão digital sem as opções novas foi comparada com a fórmula anterior. A avaliação nova foi comparada com a avaliação antiga tanto em dados fabricados quanto no relatório de 07/11. Também foram conferidos Ruff, `git diff --check` e a sintaxe Bash do atualizador.

Para repetir somente a avaliação do relatório salvo, sem chamar a LLM:

```bash
PYTHONPATH=src python - <<'PY'
import json
from pathlib import Path
from research_pipeline.verify.report import evaluate_verify

report = json.loads(Path('artifacts/pgene601/ajustes-2026-11-07/v2_verify_report.json').read_text())
detection = report['detection']
evaluation = evaluate_verify(
    report['results'], detection['candidates'],
    'dataset/disciplina_pgene601/ground_truths.json',
    report['config']['input_files'], detection['rejected_findings'],
    evaluate_by_function=True,
    additional_findings=[*detection.get('capped_candidates', []), *detection.get('review_dropped', [])],
)
print(json.dumps(evaluation['by_function'], ensure_ascii=False, indent=2))
PY
```

## Decisões de implementação

1. O cache por conteúdo e a avaliação por função têm opções próprias, desligadas por padrão e ligadas pelo perfil congelado. Isso concilia P3 e P5 com a regra geral de não mudar o padrão. Consequência: fora do perfil, a pessoa precisa ativar essas opções para obter os comportamentos novos.
2. O perfil congelado é restrito aos modos V2 `hybrid` e `benchmark`, onde o plano exige registro em `v2_checkpoint.json`. O scan recusa esse perfil antes de selecionar funções ou construir clientes. Consequência: usar esse perfil no scan exigirá implementação futura de procedência e retomada nesse modo.
3. A exceção é comparada pelo nome exato disponível no replay. O intervalo da função serve apenas para distinguir falha na função de falha na preparação. Consequência: um registro antigo que omite o módulo da exceção não recebe crédito por uma exceção qualificada sem evidência suficiente.
4. As hipóteses retiradas pela revisão ou pelo limite entram somente nas métricas novas. Os cálculos antigos recebem as mesmas entradas de antes. Consequência: os dois critérios podem produzir contagens diferentes, como previsto na regra de Fernanda.
5. A versão do ESBMC atualizada pelo script só é acrescentada ao registro após passar a checagem de data e o teste de regressão. Isso evita uma entrada que pareça aprovada quando o teste falhou; os logs da tentativa permanecem disponíveis para conferência.

A revisão também considerou corretos o `null` na detecção sem replay, a exclusão dos três casos de patch largo e a mudança autorizada na precedência de flags. A limitação antiga de localizar a base de conhecimento por comando sem caminho completo foi resolvida no perfil congelado pela normalização do comando; fora dele, a descoberta anterior foi preservada. Quem usar apenas a opção de cache com um comando no `PATH` deve fornecer o caminho completo para garantir a descoberta. A lógica interna de M1 a M3 e as tarefas opcionais não fizeram parte da revisão deste plano.

## O que fica pendente

A próxima decisão é autorizar ou não a atualização real do ESBMC. Depois vem a autorização para a seção 7 do plano: suíte completa com limite de dez minutos, `pylint`, registro de modelos e tokens com versão do ESBMC, e pedidos separados para commit e tag. A seção 10 do plano de 12/11 só será atualizada com o estado final depois dessas etapas. Nenhuma delas foi antecipada.

P4, P6 e P7 não foram implementadas. A licença do plugin, o efeito de hooks e configurações globais no isolamento, a utilidade de A11 e a comparação entre bases de conhecimento continuam sem medição nesta execução.

Os 47 continuam sendo um conjunto de desenvolvimento. O portão de evolução reconhece limitações de independência, mas não as impede; avaliar nos mesmos casos usados para criar lições não substitui validação em conjunto separado. Os scans da Amazon tinham A12 ligado e ainda produziram falsos positivos. A futura ablação com A11 mede contexto de arquivo no modo dataset e não pressupõe benefício de acrescentar contexto.

## Uso de IA

Codex implementou código e testes, preparou o script de atualização, recalculou métricas em um relatório existente e escreveu este registro técnico. Um agente de IA revisou as alterações obrigatórias; o script de atualização, preparado depois, recebeu conferência de leitura, teste do modo de leitura e checagem de sintaxe. Não houve revisão humana declarada, execução paga ou interpretação científica. A definição da regra de acerto e as decisões científicas são de Fernanda.
