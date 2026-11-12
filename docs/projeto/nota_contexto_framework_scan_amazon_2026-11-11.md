# Nota: contexto de framework no scan Amazon — 11/11/2026

Registro técnico solicitado por Fernanda. Possíveis melhorias para avaliar depois; nenhuma implementada nesta nota.

## Evidência observada

No piloto de `aws-samples/sam-python-crud-sample`, commit
`f91982d24775dce644283b9ae33deb78e49c49fc`, dois candidatos receberam `CONFIRMED` para
`message['httpMethod']`, na linha 9 de `src/update_activity/app.py` e de
`src/delete_activity/app.py`. Ambos precisam de um evento sem a chave `httpMethod`.

O `template.yaml` liga os handlers a rotas de API Gateway, cujo formato de evento inclui essa chave.
Esses contraexemplos não demonstram falha nas rotas configuradas. Os vereditos brutos foram preservados;
não há justificativa, com essa evidência, para abrir issue no sample.

## Lacuna de contexto identificada

- A rodada usou `engine`. Os dois resultados registram `call_sites: 0`, `caller_guards: []` e
  especificações com `assumptions: []`. A ligação declarada no YAML não entrou como chamador Python.
- O contexto de documentação do repositório está ligado ao modo `agent`. Definir
  `--agent-backend codex` não ativa esse modo.
- A coleta de documentação considera README e arquivos de texto em `doc/` e `docs/`; não coleta
  `template.yaml` ou os eventos JSON. Uma consulta local do coletor retornou zero trechos para ambos os handlers.
- O conhecimento usado em `error+kb` é documentação e exemplos do ESBMC, não o contrato de entrada do sample.

## Possíveis melhorias a avaliar

1. Levar o contexto de integração com frameworks à detecção e à especificação: relacionar handler,
   configuração e exemplos de evento, sempre registrando arquivo, linha e origem da informação.
   Exemplos, sozinhos, não devem virar restrições universais de entrada.
2. Mostrar no relatório qual contexto foi efetivamente encontrado e utilizado. Ausência de chamadores
   no grafo não estabelece que a função aceite qualquer entrada.
3. Manter a reprodução no programa gerado separada da avaliação de compatibilidade com o contrato
   do projeto. Quando faltar evidência, registrar a pendência, sem inventar precondições nem apagar o achado.

Os dois casos têm a mesma causa de contexto; não constituem medição de precisão nem demonstram ganho
de uma mudança futura. Relaciona-se à [proposta sobre estado alcançável](proposta_veredito_estado_alcancavel_2026-11-10.md).

## Fontes e limites

- [Conferência dos dois candidatos e referências locais](../../artifacts/scan_amazon_2026-11-11/sam-python-crud-sample/confirmed_context_review.json).
- [AWS: formato do evento da integração proxy](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html#api-gateway-simple-proxy-for-lambda-input-format).
- [AWS SAM: integração proxy padrão](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-using-start-api.html).

Uso de IA: Codex conferiu artefatos, código e documentação oficial e redigiu esta nota técnica.
Não houve execução direta do sample, implantação, publicação de issue ou implementação de melhoria.
As sugestões permanecem para avaliação de Fernanda; não são decisões científicas atribuídas a ela.
