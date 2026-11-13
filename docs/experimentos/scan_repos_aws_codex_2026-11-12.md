# Registro e passagem: scans em repositórios AWS

Data: 12/11/2026. Registro técnico preparado com auxílio do Codex para permitir que outra IA
retome a análise. A interpretação científica dos resultados permanece pendente de conferência por
Fernanda.

## Objetivo e configuração

Foi solicitado usar o pipeline LLM + ESBMC-Python para procurar bugs em repositórios da organização
`aws-samples`, com Codex na detecção e na especificação, contexto estático do repositório ligado,
ESBMC com bound 5 e timeout 180 segundos. As chamadas reais foram iniciadas com `--yes` e usam a
conta Codex. O `--scan-verify` permaneceu no padrão `engine`; `--agent-backend codex` foi passado,
mas não ativa o modo agente sem `--scan-verify agent`.

Comandos principais:

```sh
.venv/bin/python -u src/main.py --mode scan \
  --input /home/fernanda/alvos/aws-secrets-manager-rotation-lambdas \
  --output-dir artifacts/scan_aws_codex_2026-11-12/rotation \
  --scan-rank pagerank --scan-limit 40 \
  --backend codex --synth-backend codex --agent-backend codex \
  --scan-repository-context evidence --esbmc-command \
  /home/fernanda/esbmc-master/build-bw/src/esbmc/esbmc \
  --bound 5 --timeout 180 --yes

.venv/bin/python -u src/main.py --mode scan \
  --input /home/fernanda/alvos/aws-glue-samples \
  --output-dir artifacts/scan_aws_glue_codex_2026-11-12 \
  --scan-limit 40 --scan-rank pagerank \
  --backend codex --synth-backend codex --agent-backend codex \
  --scan-repository-context evidence --esbmc-command \
  /home/fernanda/esbmc-master/build-bw/src/esbmc/esbmc \
  --bound 5 --timeout 180 --yes
```

## Repositórios analisados

1. `aws-samples/sam-python-crud-sample`, checkout em
   `/home/fernanda/amazon_scan/sam-python-crud-sample`. Piloto anterior, 5 funções. Dois candidatos
   sobre `message['httpMethod']` tiveram `CONFIRMED` no harness, mas dependiam de eventos sem essa
   chave; o `template.yaml` configura API Gateway e fornece a chave. A nota
   `docs/projeto/nota_contexto_framework_scan_amazon_2026-11-11.md` conclui que os candidatos não
   demonstravam falha nas rotas configuradas. Sem issue aberta.

2. `aws-samples/aws-secrets-manager-rotation-lambdas`, checkout em
   `/home/fernanda/alvos/aws-secrets-manager-rotation-lambdas`. Seleção de 40 funções; detecção
   bem-sucedida em 39, com 84 hipóteses. No último checkpoint consultado, 26 verificações estavam
   registradas: 3 `CONFIRMED`, 10 `PIPELINE_ERROR`, 4 `ESBMC_TIMEOUT`, 3 `UNVALIDATED`, 3
   `OTHER_FAILURE`, 2 `ESBMC_ERROR` e 1 `LLM_ONLY`. Portanto, o scan ainda estava parcial; não se
   deve chamar os três vereditos bugs reais sem conferir entradas e contratos no repositório.

   Os três `CONFIRMED` do motor/replay foram:
   - `SecretsManagerInfluxDBRotationMultiUser/lambda_function.py`, `get_perm_string_item`,
     `re.search(...)`: `TypeError` reproduzido. O formato documentado pede lista de textos, portanto
     a entrada numérica usada é malformada. Caminho observado: `create_custom_token_perms` percorre
     `permissions`, depois wrappers. Não achamos validação do tipo do item. Classificação prudente:
     sugestão de validar entrada malformada; não bug demonstrado para entrada válida.
   - `SecretsManagerMongoDBRotationSingleUser/lambda_function.py`, `secret['SecretString']`.
   - `SecretsManagerRDSMariaDBRotationSingleUser/lambda_function.py`, `secret['SecretString']`.

   Os dois últimos aguardam inspeção no código original, nos chamadores e no contrato de Secrets
   Manager. Ver detalhes em `artifacts/scan_aws_codex_2026-11-12/rotation/scan_checkpoint.json`.

   A sugestão para InfluxDB foi registrada em
   `artifacts/scan_aws_codex_2026-11-12/rotation/issue_suggestion.md`. Nenhuma issue foi publicada:
   a página do GitHub indicou que issue creation está restrita neste repositório, e `gh auth status`
   reportou token inválido para `feralice`.

3. `aws-samples/aws-glue-samples`, checkout em `/home/fernanda/alvos/aws-glue-samples`. Seleção de
   40 funções; detecção bem-sucedida em 36, com 71 hipóteses. A verificação tentou 12 hipóteses antes
   de parar: 11 `PIPELINE_ERROR` e 1 `LLM_ONLY`; nenhum `CONFIRMED`. Os erros Codex incluíram
   `Timeout ao chamar codex exec` e `workspace routing discovery failed`, antes de resultado útil
   do ESBMC. Último checkpoint: `artifacts/scan_aws_glue_codex_2026-11-12/scan_checkpoint.json`.
   A página de issues mostra botão “New issue” e issues abertas, mas não se publicou nada.

## Diagnóstico preliminar dos erros no Glue

Os erros vieram do backend Codex durante a etapa de especificação, chamada antes do ESBMC. Assim,
não são vereditos sobre o código Glue. O timeout e `workspace routing discovery failed` indicam
falha de roteamento/serviço da CLI ou de sua integração com o workspace. Ainda não foi feita uma
reprodução mínima fora do pipeline nem uma alteração corretiva. Investigar
`src/research_pipeline/verify/llm_client.py` e `src/research_pipeline/llm/backends/codex.py`, os
tempos configurados para chamadas de síntese e os argumentos/cwd usados pelo subprocesso. Ver
também a captura completa no checkpoint Glue.

## Pendências para a próxima IA

1. Conferir os dois `CONFIRMED` de `secret['SecretString']` no repositório completo e determinar se
   correspondem a respostas possíveis do cliente Secrets Manager ou apenas a harness inadequado.
2. Inspecionar cada `PIPELINE_ERROR` e separar erro de autenticação/limite, timeout e falha de
   roteamento; não contabilizar como bug do alvo.
3. Verificar se a execução Glue terminou e preservar os checkpoints. A sessão interativa de
   execução deixou de estar acessível; o checkpoint indicava 12 resultados registrados.
4. Investigar e corrigir a chamada Codex antes de repetir as hipóteses com `--resume`. Não aumentar
   timeout sem descobrir se a chamada está realmente trabalhando.
5. A evolução automática desejada por Fernanda é que o pipeline proponha e aplique suas próprias
   melhorias quando passarem pelo gate de qualidade. O mecanismo atual de auto-lessons só põe
   propostas em quarentena; não modifica nem valida o próprio código. Nesta rodada Glue não foi
   passado `--no-auto-lessons`, mas isso não equivale a auto-modificação validada.
6. Para publicar uma sugestão no GitHub, Fernanda precisa renovar a autenticação executando
   `gh auth login -h github.com` no terminal. Não pedir nem registrar o token em conversa.

## Uso de IA e limites

Codex operou a CLI do pipeline, leu checkpoints e código dos repositórios, conferiu páginas públicas
do GitHub, e preparou este registro. ESBMC e replay foram executados apenas nos casos indicados
pelos checkpoints. Não houve revisão humana independente, implantação, alteração nos repositórios
AWS, criação de issue ou commit. Os resultados precisam ser conferidos por Fernanda antes de uso
como conclusão de pesquisa.
