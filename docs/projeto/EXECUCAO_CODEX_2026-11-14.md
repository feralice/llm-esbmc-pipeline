# Execução técnica do plano de 14/11/2026

Plano: `docs/projeto/PLANO_CODEX_2026-11-14.md`.
Estado: M1, M2 e M3 implementadas e verificadas nos arquivos afetados. O congelamento ainda não foi realizado.

## O que mudou

- M1: `--scan-context-retry`, desligada por padrão, permite uma nova detecção da função com até três definições do repositório quando o filtro aponta contexto ausente. Exige `--scan-prefilter`. Prefere a mesma classe, depois o mesmo módulo. Cada definição inclui arquivo e linha e tem limite de 4.000 caracteres. A primeira resposta é salva antes da chamada adicional. Se a chamada falha, a retomada preserva a primeira resposta e tenta apenas a etapa pendente. Uma resposta adicional concluída não provoca outra refação, mesmo que ainda peça contexto.
- M2: `--scan-dedupe`, desligada por padrão, agrupa hipóteses com a mesma função por estrutura sintática e a mesma expressão normalizada. A estrutura sintática é a representação do código que ignora espaços e comentários. A comparação também remove a docstring da função. O primeiro arquivo na ordem estável representa o grupo; as demais hipóteses continuam listadas e recebem, no texto, o veredito do representante. Os identificadores das hipóteses não mudam. O agrupamento ocorre depois da detecção, portanto não economiza chamadas de detecção nesta implementação.
- M3: os três relatórios avisam, quando há `CONFIRMED`, que a confirmação ocorreu no programa de teste isolado, chamado harness. A entrada pode não ser produzida pelo projeto real. O aviso pede leitura do código e reprodução fora desse programa antes de reportar. Os nomes de veredito e os campos numéricos não foram alterados por esta tarefa.

Sem as duas flags, suas chaves não entram na configuração nem na impressão digital. Os testes comparam a impressão digital com a fórmula anterior, com e sem pré-filtro. Com a refação ligada, a impressão digital também inclui as fontes do grafo para impedir reaproveitamento após mudar uma definição auxiliar.

## Decisões de implementação

1. O item 4 de M1 pede simultaneamente retirar as hipóteses antigas de `held` e impedir que desapareçam de `candidates` ou `held`. Para manter o registro completo sem enviar a suspeita antiga à verificação, ela permanece em `held`, com `retried: true`, identificada como histórico nos dois relatórios. A nova resposta tem seus próprios candidatos e entradas retidas. Consequência: a contagem de `held` inclui esse histórico quando a flag está ligada.
2. Com a refação ligada, qualquer mudança nas fontes do grafo invalida a retomada. É uma regra conservadora para proteger o contexto extra; pode recusar uma retomada mesmo quando a mudança foi em uma função que não seria enviada. Com a flag desligada, a impressão digital permanece igual à anterior.
3. Nenhuma branch, commit, tag ou envio ao GitHub foi feito. As alterações preexistentes e os novos arquivos produzidos em outras atividades foram preservados.

## Medição sem LLM

Comando executado:

```bash
python scripts/medir_dedupe.py /mnt/e/scan_amazon/lote3/aws-secrets-manager-rotation-lambdas_2026-11-14/scan_report.json
```

Das 35 hipóteses gravadas, 2 são duplicatas por esse critério, deixando 33 representantes. Foram encontrados dois grupos, cada um com duas hipóteses. Todos os arquivos de origem estavam disponíveis. Os dois grupos comparam `get_secret_dict` nas pastas `SecretsManagerRDSDb2RotationMultiUser` e `SecretsManagerRDSDb2RotationSingleUser`, para expressões distintas. As demais cópias não foram agrupadas pelo critério estrito.

Esta medição usa os arquivos de origem presentes no momento da execução. Não comprova economia de tempo ou de tokens em uma nova rodada, nem redução de falsos positivos. Não houve nova detecção ou verificação real.

O script `scripts/medir_prefiltro.py` e o filtro original ficaram inalterados. No mesmo relatório, o script contou 35 hipóteses, nenhuma queda e nenhum `CONFIRMED` perdido. Isso descreve somente esse relatório.

O ganho real da refação com contexto ainda não foi medido. Exige chamada à LLM e fica para depois do congelamento, com autorização de Fernanda.

## Verificação executada

Os testes novos falharam antes da implementação. A revisão automatizada identificou três falhas na primeira versão da refação: perda da resposta inicial quando a cota interrompia a segunda chamada, erro da segunda chamada omitido da contagem e impressão digital que ignorava alterações nas definições extras. Os três casos foram reproduzidos com testes, corrigidos e passaram.

Comando final dos testes por arquivo:

```bash
python -m pytest -q tests/test_scan_context_retry.py tests/test_scan_dedupe.py tests/test_scan_confirmation_notice.py tests/test_verify_run_report.py tests/test_relatorio_scans.py tests/test_scan_pipeline.py tests/test_scan_prefilter.py tests/test_main_v2.py
```

Resultado: 139 testes passaram em 13,94 segundos. Não é a suíte completa. Os analisadores usados nesses testes são falsos, sem chamadas à LLM.

Ruff passou nos arquivos Python alterados nesta implementação. `git diff --check` passou. O ambiente consultado não tem `pylint` instalado, portanto essa checagem permanece pendente.

## Pendências para congelar

O arquivo `artifacts/pgene601/ruido-status.log` ainda não estava presente na última conferência. A r1 tinha seis registros de saída com código 3, de 07:11 a 09:41 de 14/11/2026, no horário registrado no arquivo, associado a limite de uso da LLM. Não havia relatório final da r1 nem pasta da r2. A rodada e seus arquivos não foram modificados.

Pelas condições das seções 3 e 7 do plano, ficaram pendentes:

1. Conferir o término da rodada de ruído e seu estado de erro.
2. Executar a suíte completa com limite de dez minutos e `pylint` nos arquivos alterados.
3. Atualizar o registro de modelos e tokens com as duas rodadas concluídas.
4. Executar a comparação pareada entre r1 e r2 e registrar os números e os limites da medida, sem interpretação científica.
5. Pedir autorização explícita para commit e, depois, para a tag `v2-congelado-2026-11d`.
6. Atualizar a seção 10 do plano de 12/11 com o estado final, depois dessas etapas.

Continuam como trabalho futuro: crítico de hipótese, alcance pela entrada pública, modelo barato na detecção e checagem de campos opcionais contra o modelo de serviço do botocore. Nada disso foi implementado nesta execução.

## Uso de IA

Codex implementou código, escreveu e executou testes, mediu o agrupamento em dados já gravados e produziu este registro técnico. Um agente de IA fez a revisão automatizada das alterações. Isso não constitui revisão humana nem interpretação científica dos resultados. As decisões científicas e a avaliação dos resultados continuam com Fernanda.
