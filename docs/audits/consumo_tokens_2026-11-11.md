# Auditoria de consumo de tokens e custo

Data: 2026-11-11. Branch: `feat/harness-de-agente`, commit `40f72ae`. Nenhuma chamada paga foi feita. Todos os números vêm de arquivos que já existem no repo.

## 1. Fontes e escopo

- `artifacts/**/llm_telemetry.json`: 71 arquivos, 17.549 chamadas registradas. É a fonte principal.
- `artifacts/**/v2_verify_report.json`: resultado por hipótese, com `llm_calls` e veredito. Foi usado para calcular chamadas por hipótese.
- `docs/experimentos/**/llm_telemetry.json`: 36 arquivos, não somados aqui (ver seção 6).
- `.claude/worktrees/**`: 216 cópias de telemetria. Excluídas, porque provavelmente duplicam rodadas. Não verifiquei uma a uma.
- Ficaram de fora 2.321 chamadas com erro e 68 com timeout. Estão contadas no total, mas não separadas por motivo.

Uma correção ao que eu tinha dito antes: a tabela inicial usava `v2_report.json`. Esse arquivo é um snapshot parcial, com `coverage: partial` e `verification.n = 0`. O relatório real é `v2_verify_report.json`.

## 2. Onde o custo está registrado e onde ele se perde

Este é o principal achado de instrumentação, e ele invalida a leitura de custo feita até agora.

1. **Custo sai zerado para o Claude por assinatura.** `pricing.call_cost` devolve `0.0` para `claude_cli` e `codex` (`src/research_pipeline/llm/pricing.py`, bloco `SUBSCRIPTION_PROVIDERS`). Isso significa "cobrado pela assinatura", não "custo zero".
2. **O CLI informa um custo que o pipeline descarta.** `backends/claude_cli.py:151-160` lê `total_cost_usd` do envelope JSON e devolve em `cost_usd`, mas `response_event` nunca usa esse campo. Não há como recuperar esse valor de rodadas antigas: nenhum log guardou o envelope bruto (busca por `total_cost_usd` em `artifacts`, `logs` e `docs` deu zero).
3. **Tokens de cache não são lidos no `claude_cli`.** O mesmo trecho só guarda `input_tokens` e `output_tokens`. Os campos `cache_creation_input_tokens` e `cache_read_input_tokens` são ignorados. Por isso `prompt_tokens` aparece minúsculo: 14.792 tokens de entrada para 11.753 chamadas do `claude_cli`. Isso é o tamanho da parte não cacheada, não da entrada real.
4. **Preço ausente para OpenAI e Gemini.** `call_cost` só tem tabela para Anthropic. Para `openai`, `google` e `chat_completions`, `cost_usd` é `None`. Somar `None` como zero produziu o total de US$ 0,00 na primeira agregação, o que é enganoso.
5. **Contagem não fecha entre dois arquivos.** Na rodada `v2/final-2026-10-17`, a telemetria tem 1.924 chamadas. Os resultados somam 1.193 `llm_calls` na verificação e 451 de detecção, 1.644 no total. As 280 restantes provavelmente são chamadas com erro, que não entram em `results`. Não confirmei isso.

## 3. Consumo por provedor, modelo e etapa

Dados das 71 rodadas em `artifacts/`:

| Provedor | Modelo | Etapa | Chamadas | Erros | Tokens de entrada | Tokens de saída |
|---|---|---|---|---|---|---|
| claude_cli | claude-sonnet-5-5 | synthesis | 8.218 | 842 | 14.792 (subcontado) | 4.526.832 |
| openai | gpt-4o-mini | synthesis | 3.991 | 253 | 7.053.841 | 494.474 |
| claude_cli | claude-sonnet-5-5 | detection | 3.535 | 188 | 12.210 (subcontado) | 4.254.641 |
| codex | (padrão) | synthesis | 700 | 159 | 9.401.192 | 249.584 |
| openai | gpt-4o-mini | detection | 503 | 3 | 872.519 | 144.026 |
| chat_completions | gemini-2.5-flash | detection | 194 | 159 | 60.871 | 24.736 |
| openai | gpt-5.5 | detection | 126 | 98 | 53.341 | 63.187 |
| google | gemini-3.1-flash-lite | synthesis | 121 | 0 | 367.720 | 48.082 |
| claude_cli | (padrão) | detection | 48 | 8 | 136 | 144.900 |
| chat_completions | qwen3-coder:30b | detection | 48 | 48 | 0 | 0 |

Resumo:
- **Synthesis é 73% das chamadas** (18.144 de 24.688 nas linhas com etapa). Detecção é 27%.
- **Tokens de saída do Claude por assinatura** somam cerca de 8,8 milhões (sonnet, detecção e síntese). Isso é o que o CLI reportou.
- **Qualquer custo em dólar da assinatura é desconhecido.** Não temos o `total_cost_usd`.
- **Modelos de API (OpenAI, Gemini) usaram pouco**: cerca de 7,9 M de entrada e 0,6 M de saída com gpt-4o-mini. Sem tabela de preço no repo, não calculo US$ aqui.

Estimativa de referência, só com o que o repo já tem: 8,8 M tokens de saída do Sonnet 5.5 a US$ 10 por milhão (tabela `pricing.py`, cotação de 2026-10-06) dão cerca de **US$ 88 só de saída**. A entrada não entra porque não foi medida. Se a mesma carga fosse para a API, o custo real seria maior que isso, mas não sei quanto.

## 4. Onde as chamadas se gastam

Por hipótese, na rodada `v2/final-2026-10-17` (742 hipóteses, 1.193 chamadas de verificação):

| Veredito | Hipóteses | Chamadas | % das chamadas | Chamadas por hipótese |
|---|---|---|---|---|
| UNSUPPORTED | 288 | 756 | 63,4% | 2,62 |
| SPEC_FAILED | 37 | 111 | 9,3% | 3,00 |
| MISSING_DEPENDENCY | 108 | 86 | 7,2% | 0,80 |
| NOT_CONFIRMED | 47 | 56 | 4,7% | 1,19 |
| UNVALIDATED | 43 | 54 | 4,5% | 1,26 |
| CONFIRMED | 40 | 48 | 4,0% | 1,20 |
| GROUNDING_FAILED | 116 | 0 | 0% | 0 |

A rodada `pgene601/rodada-final-2026-11-09` mostra o mesmo padrão: `LLM_ONLY` (54 de 109 hipóteses) consome 63,8% das chamadas.

Leitura: **a maior parte do gasto vai para hipóteses que o ESBMC nunca chega a verificar.** O verdict `UNSUPPORTED` aparece com 2,6 chamadas em média, e não separei quantas dessas chamadas são de reparo (self-healing) e quantas são de especificação. A causa observada pelo código: `verify_with_healing` tenta até `3 × heal_rounds` reparos, com `heal_rounds = 3` por padrão (`src/main.py:274`, `src/research_pipeline/verify/healing.py:438`). Ou seja, até 9 chamadas de síntese por hipótese.

A síntese também gasta com poucos resultados: `v2/final-2026-10-15` tem 741 chamadas de síntese para 564 hipóteses e 14 confirmadas.

**Custo por bug confirmado (mesma rodada, sem preço):** 1.924 chamadas / 40 confirmados ≈ 48 chamadas por CONFIRMED. Este número mede volume, não precisão: não sei quantos dos 40 são corretos.

## 5. Retries e reexecução

- O `run.sh` da rodada final faz até 30 tentativas, com espera de 30 minutos entre elas, quando a assinatura atinge o limite. Cada retomada reexecuta hipóteses que foram cortadas (`status.log` mostra 7 tentativas só em 19/10).
- Na detecção, 102 de 350 chamadas falharam com `claude -p saiu com código 1`, na rodada que parou por limite. Essas falhas são retries implícitos, e não estão separadas no custo.
- Há 2.321 erros e 68 timeouts no total. Não há campo `motivo_retry` na telemetria.

## 6. Repetição entre experimentos

Pelo menos 20 rodadas `det-*` rodaram detecção sobre os mesmos 50 casos com variantes de prompt diferentes. Cada uma gasta cerca de 54 chamadas de detecção. Também há várias rodadas `exp-oracle-*` sobre os mesmos 116 casos (repair, resample, fixed, em repetições). Não verifiquei se as entradas são idênticas entre rodadas. Um cache por hash resolveria só as entradas idênticas, e não sei quantas são.

## 7. Modelo caro em tarefa simples

Não há evidência de que tarefas auxiliares (classificação, extração de contexto) usem modelo caro: no pipeline atual a detecção e a síntese usam o mesmo modelo configurado. Não confirmei isso no código de todos os caminhos, então deixo em aberto.

## 8. O que falta para medir o custo de verdade

1. Gravar `total_cost_usd`, `cache_creation_input_tokens` e `cache_read_input_tokens` por chamada no backend `claude_cli`. Isso é mudança pequena, não altera o veredito, e é pré-requisito para qualquer número de custo.
2. Tabela de preço para OpenAI e Gemini, com data de cotação, ou marcar `cost_usd` como desconhecido em vez de somar zero.
3. Registrar o motivo de cada retry e separar erro de limite de erro de ferramenta.
4. Medir o tamanho real da entrada do CLI (o prompt enviado), não só o que o provedor reporta.

## 9. Oportunidades candidatas (ainda não medidas)

Estas são hipóteses. Nenhuma foi testada, e cada uma precisa de comparação com a linha de base antes de ser aceita.

- **Triagem antes do reparo.** Hipóteses cujo primeiro veredito é `UNSUPPORTED` ou `GROUNDING_FAILED` podem não receber reparo. Pelos dados, isso poderia economizar até 63% das chamadas de verificação. Precisa checar se alguma hipótese `UNSUPPORTED` virava `CONFIRMED` depois de reparo. Dá para medir nos resultados existentes.
- **Teto de reparos por hipótese.** Hoje são até 9. Testar 1 ou 2 e comparar `CONFIRMED` e falsos positivos.
- **Cache por hash** da entrada e do prompt, para os casos repetidos da seção 6.

## 10. Decisões que preciso de você

1. **Orçamento.** Quais limites você quer: tokens por chamada, por caso, por experimento, custo em dólar, número de retries, chamadas por hipótese? Sugestão para começar: teto de 2 reparos por hipótese, com medição antes de baixar mais.
2. **Política de cache.** Cache por hash deve valer só para rodada congelada, ou também para rodada de desenvolvimento? Eu sugiro que rodada congelada use cache explícito, com a chave registrada no relatório.
3. **Preço.** Você aceita que `cost_usd` fique "desconhecido" para OpenAI e Gemini até termos a tabela, ou quer que eu pesquise a tabela atual com fonte?
4. **Primeiro passo.** Eu faria, nesta ordem: (a) instrumentação da seção 8, item 1, sem mudar comportamento; (b) medir a triagem da seção 9 nos resultados já existentes, sem nenhuma chamada nova; (c) só depois o orçamento e o cache. Você concorda com essa ordem?
5. **Chamadas pagas.** Nenhuma rodada nova será feita sem sua confirmação explícita. Os passos (a) e (b) não fazem chamada paga.

## 11. Atualização: P0 e P1 (sem chamadas pagas)

### 11.1 Correções ao que estava neste documento

- **Divergência 17.549 x 24.688 explicada.** A tabela da seção 3 usou só `artifacts/` (71 arquivos, 17.549 chamadas). Os 24.688 vêm de `artifacts/` (17.549) mais `docs/experimentos/` (36 arquivos, 7.139). O glob ignora `.claude/worktrees/`, por isso as 216 cópias de worktree não entram.
- **Custo zero era falso.** O `claude_cli` gravava `0.0` por assinatura, e OpenAI/Gemini gravavam `None` que era somado como zero. Essas linhas antigas agora contam como custo **desconhecido** (coluna `legacy`).

### 11.2 Telemetria corrigida (código)

Mudanças em `src/research_pipeline/llm/telemetry.py`, `pricing.py`, `backends/claude_cli.py`, `verify/llm_client.py` e `main.py`:

- Entrada total inclui cache de escrita e leitura, para o formato Anthropic. Antes, `prompt_tokens` ficava subcontado.
- `cache_creation_tokens` e `cached_tokens` (leitura) são gravados.
- `cost_usd` usa o custo informado pelo CLI (`total_cost_usd`) quando existe, senão a estimativa de tabela. `cost_source` diz qual foi (`cli_reported`, `estimated` ou nulo).
- `billed_usd` só é preenchido para cobrança por token (`billing == "api"`). Assinatura não conta como gasto.
- Custo ausente fica `None`. Codex, que antes dava `0.0`, agora dá `None`.
- Erros classificados em `error_kind`: `usage_limit`, `timeout` ou `error`.

O resumo por etapa (`_summarize_v2_telemetry`) ganhou `cost_reported_usd`, `cost_estimated_usd`, `billed_usd`, `cache_creation_tokens`, `usage_limit_calls` e `timeout_calls`.

Novo agregador `src/research_pipeline/llm/usage_summary.py` e script `scripts/telemetry_summary.py`, que reproduz a tabela sem scratchpad:

```
python scripts/telemetry_summary.py artifacts docs/experimentos
```

### 11.3 Testes

- Suíte completa: **1795 aprovados, 1 pulado**, em 4 min 57 s. Antes eram 1785 aprovados.
- Testes novos: entrada com cache, custo informado, custo desconhecido, cobrança só para API, classificação de erros, linhas antigas, mudança no backend e na síntese (`llm_client`).
- Mutação: quebrei a chave `reported_cost_usd` no backend e no `llm_client`, e os testes novos falharam nos dois. Restaurei e voltou a passar.
- Lint: os 5 avisos de `ruff` nos arquivos tocados já existiam em linhas que não mudei.

**Limite:** nenhuma rodada nova foi feita, então nenhum custo novo foi medido. As 24.688 linhas existentes são todas `legacy`. A primeira medição real vai ser a próxima rodada paga que você autorizar.

### 11.4 Erros nas linhas antigas (24.688 chamadas)

| Tipo | Chamadas |
|---|---|
| Sucesso | 22.299 |
| Limite de uso da assinatura | 400 |
| Timeout | 68 |
| Outros erros | 1.921 |

Retries HTTP internos (`_post_json` em `openai.py` e `chat_completions.py`, 3 tentativas com espera) **não são registrados**. Uma chamada com 2 retries aparece como 1 linha. Isso fica como risco aberto, porque mudar esse laço altera comportamento.

### 11.5 P1: reconstrução retrospectiva (sem chamadas)

Hipóteses `UNSUPPORTED` em `v2/final-2026-10-17` (288):

- 252 gastaram 3 tentativas de especificação. Cada tentativa que rodou o ESBMC terminou em `tool_error` ou `unsupported_case`. Nenhuma virou violação.
- Os erros do ESBMC são, em sua maioria, do harness gerado (`NameError`, `Cannot unpack`, `Object not found`), não da hipótese. O `reading` da última tentativa foi `repairable` em 244 casos.

Limite de tentativas, mesma rodada (`final-2026-10-17`, 742 hipóteses):

| Tentativas permitidas | Hipóteses com veredito útil do ESBMC |
|---|---|
| 1 | 141 |
| 2 | 170 |
| 3 | 175 |

Quanto as rodadas extras custaram e trouxeram:

- Chamadas de tentativa a partir da segunda: **635** (das 1.193 de verificação, 53%).
- Hipóteses cuja 1ª tentativa do ESBMC falhou e foram recuperadas por rodada extra: **16**, das quais **4** viraram `CONFIRMED`.
- Razão bruta: 635 chamadas extras divididas por 4 `CONFIRMED` ganhos, ~159 chamadas por ganho. Conta todas as extras como custo desses 4, o que é uma cota superior.

Mesma análise em outras rodadas:

- `pgene601/rodada-final-2026-11-09`: 119 chamadas extras, 5 recuperadas, 1 `CONFIRMED`.
- `pgene601/congelado-c-2026-11-06`: 138 chamadas extras, 1 recuperada, 0 `CONFIRMED`.

**Leitura manual contra o ground truth** dos 6 `CONFIRMED` que só apareceram depois da 1ª tentativa, em `final-2026-10-17`:

- Batem com bugs rotulados: `cli_bool_option` (`assert isinstance(param, bool)`) e `HashExpander.do` (divisão por módulo).
- Incerto: `_unstack_multiple` (função bate, arquivo rotulado é outro).
- Não batem com a expressão rotulada: `Network.from_config`, `dispatch_to_series` e `YoutubeDL.build_format_selector`.

Essa leitura é minha, não métrica oficial, e não tem sinal de precisão por rodada. Não recomendo cortar reparos com base nisso sem medir precisão por rodada, como você pediu.

**Caveats da simulação:** assume que truncar a sequência de tentativas equivale a rodar com limite menor. Isso só vale se o laço parar do mesmo jeito. As tentativas também incluem reenvio por JSON inválido, não só reparos.

### 11.6 Duplicação entre rodadas

O mesmo conjunto de 47 casos da PGENE601 foi rodado várias vezes:

- `congelado-c-2026-11-05`: 176 chamadas de síntese.
- `congelado-c-2026-11-06`: 1.158 chamadas de síntese.

Mesmo código e mesmo conjunto, com 6,6 vezes mais chamadas de síntese. Isso mostra que o gasto varia muito entre rodadas, e que um cache por hash evitaria parte desse trabalho. Não medi quantas entradas são idênticas.

### 11.7 Próximo passo

Você decide:
1. Autoriza uma rodada pequena (5 casos, um modelo) para medir o custo real com a telemetria nova? Não faço chamada paga sem o seu OK.
2. Quer que eu meça precisão por rodada de reparo no ground truth, para decidir o limite com dado, antes de mexer no orçamento?
