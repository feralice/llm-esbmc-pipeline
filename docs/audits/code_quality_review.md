# Auditoria de qualidade, manutenção, arquitetura e testes

Data: 11/11/2026. Snapshot: `40f72ae50498c40a35cd97031b1e09956d4049dc`.

## 1. Resumo executivo

O repositório tem contratos pequenos, separação útil entre detecção e verificação e uma suíte extensa. A prioridade de manutenção, contudo, deve ser corrigir falhas de contenção de execução e de comunicação de erros antes de reorganizar arquivos ou corrigir estilo.

Principais achados:

| ID | Prioridade | Problema | Evidência principal |
|---|---|---|---|
| Q01 | **P0, condicionado à execução de origem/harness não confiável** | O replay permite escrita fora da pasta temporária; a importação diferencial também executa efeitos do módulo original | `verify/sandbox.py:50`, `verify/replay.py:140`, `verify/differential_worker.py:83` |
| Q02 | **P1** | O comando de rodada final retorna sucesso mesmo após falhas das etapas 2–5 | `scripts/run_final.sh:31`, `:36`, `:40`, `:44`, `:46` |
| Q03 | **P1** | JSON malformado pode se transformar em detecção concluída sem achados e sem erro no registro | `llm/backends/chat_completions.py:129`, `scan/pipeline.py:314` |
| Q04 | **P2** | Timeout do runner ESBMC não encerra descendentes de um wrapper | `verification/esbmc_runner.py:81` |
| Q05 | **P2** | Prazo total e opções de execução não chegam integralmente ao agente API | `verify/agent_arm.py:218`, `:243`, `:808`; `src/main.py:649` |
| Q06 | **P2** | A composição de detecção/síntese diverge entre os modos para backends diferentes | `src/main.py:840`, `:935` |
| Q07 | **P1 de manutenção** | A CLI e o núcleo de tentativas concentram decisões e dependências difíceis de testar em conjunto | `src/main.py:902`, `verify/loop.py:196`, `verify/agent_arm.py:471` |
| Q08 | **P2** | Ambiente, instruções de instalação e ferramentas de qualidade não estão inteiramente reproduzíveis | `requirements.txt:1`, `README.md:167`, `tests/test_smell_filter.py:99` |
| Q09 | **P2** | Há dívida de contratos de tipos e dependências internas bidirecionais | Mypy: 320 diagnósticos em 37 arquivos; grafo de imports na seção 5 |
| Q10 | **P2/P3** | Persistem comentários obsoletos, pequenos clones e avisos de organização | Seções 3 e 6 |
| Q11 | **P2** | Launcher depende de um interpretador em caminho fixo e anuncia agendamento mesmo quando ele não existe | `maintenance/execution.py:279`, `:283`; teste real com retorno 127 |

P0 significa risco concreto de segurança/perda de dados, P1 significa defeito relevante ou manutenção de alto risco, P2 dívida estrutural/robustez e P3 detalhe local. A prova de Q01 criou somente diretórios de teste em `/tmp`; não apagou nem alterou dados científicos. Não se demonstrou corrupção de resultados históricos nem exploração anterior. Q03 demonstra perda de informação de erro; não determina quantos resultados existentes foram afetados.

### Escopo e preservação

Esta é uma auditoria técnica solicitada por Fernanda. Não contém novas hipóteses científicas, decisões de metodologia ou conclusões sobre a eficácia dos experimentos. Foram preservados código, prompts, datasets, ground truth, resultados, logs, artefatos e tags. Não houve refatorações, remoções no repositório, commits, instalação de dependências ou chamadas pagas.

A análise executável ocorreu no worktree independente `/home/fernanda/.codex/worktrees/98b1/llm_esbmc`, criado no commit acima. A redação e as sondas ficaram em `/tmp/llm-esbmc-quality-20261111`; somente este relatório é entregue ao diretório solicitado. O checkout principal já tinha alterações em `llm/pricing.py`, `llm/telemetry.py` e documentos não versionados em `docs/audits/`. Durante o trabalho surgiram outras alterações concorrentes, inclusive em main, backends, llm_client e testes. Nenhuma foi incluída nas medições ou editada por esta auditoria. Os números descrevem o snapshot, não alterações concorrentes posteriores. Na conferência final, o checkout principal já estava em `ade6f14`; esse avanço não foi incluído na auditoria. Os caminhos `llm/`, `verify/`, `verification/`, `scan/`, `maintenance/`, `models.py`, `preprocess.py` e `smell_policy.py` usam o prefixo `src/research_pipeline/`; nomes `test_*.py` usam `tests/`.

Este relatório aprofunda [a auditoria arquitetural anterior](architecture_audit.md), sem reproduzir seu inventário integral. Algumas recomendações daquela auditoria precisam ser corrigidas: as 19 ocorrências F841 são sondas; já existe `LLMAnalyzer`; os dois pacotes de verificação têm funções distintas; as duas trilhas de smells não são equivalentes; já há hashes de prompts. As correções estão detalhadas abaixo.

## 2. Indicadores e método

### Ferramentas e recorte

Foram usados Python 3.12, Ruff 0.16.5, Mypy 2.1.0, pytest 9.0.3, AST da biblioteca padrão e NetworkX 3.6.1 já instalado. Não estavam disponíveis `coverage.py`, `pytest-cov`, Radon, Bandit, Vulture e pip-audit. Nenhum deles foi instalado. Não foi feita consulta a bases de vulnerabilidades; este relatório não afirma ausência de CVEs.

O inventário cobre Python em `src/`, `scripts/` e `tests/`. Datasets e código histórico não foram lintados como código do produto. As 51 sondas de `verify/probes/` foram contadas separadamente e excluídas das conclusões sobre qualidade de Python convencional.

| Indicador | Resultado |
|---|---:|
| Arquivos rastreados no snapshot | 4.352 |
| Arquivos Python em `src/` | 149, incluindo 51 programas de sonda |
| Código Python de produto sem sondas | 98 arquivos; 19.334 linhas físicas |
| Funções/métodos, incluindo funções locais, sem sondas | 966 |
| Funções com anotação de retorno | 913/966; presença não comprova correção do tipo |
| Scripts | 53 arquivos, dos quais 51 Python e 24 com prefixo `v2_` |
| Testes | 125 arquivos Python, incluindo `conftest.py`; 1.786 casos coletados |
| Funções de produto com CC maior que 10 | 37 |
| Maior CC medida | 39, `main.mode_v2` |
| Maior função | 373 linhas, `main.mode_v2` |
| Tratadores amplos de exceção em produto | 24; não são automaticamente defeitos |
| Ciclos somente entre imports diretos no corpo do módulo | 0 detectados |
| Componentes cíclicos incluindo imports locais | 1, com 8 módulos |
| Nomes de funções/classes repetidos no topo do mesmo módulo | 0 detectados |
| Grupos de corpos idênticos de funções com pelo menos 8 linhas | 2; nenhum grupo nos testes por esse critério |
| Ruff, regras efetivas | 296 diagnósticos: 146 em src, 93 em scripts, 57 em tests |
| Mypy, execução exploratória não estrita | 320 diagnósticos em 37 arquivos de 98 analisados |

### Como interpretar as medidas

**Linhas** incluem comentários e linhas vazias. **CC** é a complexidade ciclomática reportada por Ruff/C901, uma aproximação da quantidade de caminhos de decisão; não mede por si só qualidade ou validade científica. Para obter valores de todas as funções, foi usado limite zero; para destacar excessos, limite 10.

**Cog\***, usado no ranking, é uma heurística local de esforço cognitivo, não uma medida oficial Sonar/Cognitive Complexity: soma `1 + profundidade de decisão` para `if`, laços, condicionais de expressão, `except` e `match`; soma 1 por expressão booleana e por `break`/`continue`. Funções/classes locais são medidas separadamente. Ajuda a localizar aninhamento, mas não tem limiar universal e não permite comparação com ferramentas externas. Ruff em preview apontou ainda 4 excessos de blocos aninhados e 28 excessos de variáveis locais em `src/scripts`.

**I/O** significa quantidade de módulos internos que importam o arquivo / quantidade de módulos internos importados por ele, inclusive imports locais. Não inclui chamadas por subprocesso, scripts externos ou imports dinâmicos. Portanto um worker com I=0 não é código morto. **H3M** conta commits que mencionam o caminho desde 11/08/2026 (janela de três meses), sem seguir renomes e sem ponderar tamanho do diff. É frequência de alteração, não churn de linhas nem comparação justa entre arquivos de idades diferentes.

O ranking combina essas medidas com responsabilidade, risco do comportamento e dificuldade de teste. Não é uma ordenação por tamanho nem uma fórmula de qualidade científica.

### Comandos principais

Com `PY` e `RUFF` apontando aos executáveis da `.venv` já existente do checkout principal, e o diretório atual no worktree:

```bash
PYTHONDONTWRITEBYTECODE=1 "$PY" -m pytest --collect-only -q -p no:cacheprovider
"$RUFF" check --no-cache src scripts tests --output-format=json
"$RUFF" check --no-cache --isolated src scripts tests --output-format=json
"$RUFF" check --no-cache --isolated --select E4,E7,E9,F src scripts tests --output-format=json
"$RUFF" check --no-cache --isolated --select C901 \
  --config 'lint.mccabe.max-complexity=0' src scripts --output-format=json
"$RUFF" check --no-cache --isolated \
  --select C901,PLR0911,PLR0912,PLR0913,PLR0915,B,S,UP,RUF \
  --config 'lint.mccabe.max-complexity=10' src scripts tests --output-format=json
"$RUFF" check --no-cache --isolated --preview --select PLR0914,PLR1702 src scripts
"$PY" -m mypy --cache-dir=/tmp/llm-esbmc-quality-20261111/mypy-cache \
  --ignore-missing-imports --follow-imports=silent --exclude '/probes/' src
git log --since=2026-08-11 --format= --name-only -- src scripts
```

A execução ampliada original também selecionou PLR0914/PLR1702 sem preview; Ruff informou que não teriam efeito. Elas foram executadas novamente com preview, separadamente. Os códigos de saída não zero de Ruff/Mypy representam diagnósticos, não falha de instalação. A execução de testes e sua instrumentação estão na seção 7.

Os JSONs brutos, saída do Mypy, coleta, execução dos testes, métricas AST e sondas ficaram em `/tmp/llm-esbmc-quality-20261111`. Essa pasta é evidência temporária desta sessão, não um artefato científico versionado ou um requisito para compreender os achados.

## 3. Resultado do lint e tipagem

### Regras efetivas: 296 avisos

| Regra/categoria | Quantidade | Interpretação após inspeção |
|---|---:|---|
| RUF100, `noqa` sem efeito nesta seleção | 72 | Organizar somente após fixar regras; não prova que a justificativa de execução seja dispensável |
| F821, nome não definido | 56 | **Todos em sondas ESBMC**; intrínsecos e nomes de teste intencionais |
| I001, imports | 42 | Organização, prioridade P3; conferir imports com efeitos antes de reordenar |
| S102, `exec` | 27 | Predominantemente execução intencional de programas/fixtures; avaliar fronteira de isolamento, não remover o mecanismo |
| UP045, Optional | 20 | Estilo de anotação; depende de estabelecer versão Python suportada |
| F841, variável não utilizada | 19 | **Todos em sondas**; atribuições podem observar uma exceção; não remover |
| UP031, formatação `%` | 14 | Conferir strings de teste/código gerado; não reescrever exemplos da semântica que está sendo testada |
| FURB167 | 10 | Sugestões locais de comparação de tipos; conferir contexto antes de aceitar |
| B023, captura de variável de laço | 6 | Nos casos inspecionados, consumo ocorre dentro da mesma iteração; não se demonstrou bug de late binding |
| ISC004 / UP035 / TRY004 | 4 / 4 / 4 | Revisão local de concatenação, import e tipo de exceção; sem correção automática global |
| RUF059 / UP012 / BLE001 | 3 / 2 / 2 | Desempacotamento/estilo; BLE001 aqui captura exceções para comparar comportamentos nos testes |
| Demais | 11 | DTZ006, FURB188, C401, SIM102, RUF010, PLR0124, PLW1510, B017, FLY002, F401, C408: uma de cada |

A execução com `--isolated` retornou os mesmos 296 diagnósticos. Portanto não se confirmou a afirmação anterior de que o conjunto depende de configuração externa. Confirma-se que o projeto não versiona configuração própria nem versão Ruff em requisitos de desenvolvimento. Não inferir a origem das regras apenas pelo número de avisos.

A seleção explícita `E4,E7,E9,F` produziu 201 ocorrências: E402=91, F821=56, F841=19, E702=15, E731=11, E741=8, F401=1. É outra política, não 201 defeitos adicionais. A seleção ampliada produziu 3.234, dos quais 2.771 eram S101 (`assert`), sobretudo testes. Não somar execuções com sobreposição nem classificar asserts de pytest como vulnerabilidades.

Dos 41 C901 acima de 10 na seleção ampliada, 37 estão no produto e 4 em scripts. As outras contagens estruturais foram PLR0913=76, PLR0911=29, PLR0912=22 e PLR0915=11. Muitas assinaturas usam parâmetros keyword-only explícitos; a quantidade isolada não justifica esconder opções em um objeto genérico.

### Exemplos de falsos positivos e um aviso real simples

- `verify/probes/none_int_local.py:9`: `code = int(status)` é F841, mas executar `int(None)` é o objeto da sonda. Atribuição sem uso posterior não significa código morto. O catálogo tem digest das fontes em `verify/capabilities.py:118`; editar a sonda muda a identidade da capacidade avaliada.
- `verify/grounding.py:119` e `:145`: a classe Visitor captura `method`, mas é instanciada e usada antes de avançar a iteração. `verify/rounds.py:87` lê `folder` imediatamente. `tests/test_verify_compat_boundary.py:212` chama a função dentro do laço. Não foi encontrada closure que escape desses laços.
- `verify/replay_worker.py:206`: `v == v` exclui NaN deliberadamente. Substituir por `True` destruiria a intenção.
- `tests/test_verify_compat_boundary.py:66` e `:213`: capturar `Exception` e devolver seu tipo compara original e reescrito; não é silêncio sobre erro operacional.
- `tests/test_verify_pinned.py:2`: import `subprocess` não utilizado, F401, candidato real de baixa prioridade. Não foi removido.
- `tests/test_verify_agent_arm.py:624`: `pytest.raises(Exception)` é amplo; testar a exceção/causa esperada tornaria a regressão mais precisa. Risco baixo, mas conferir o contrato antes de estreitar.

### Mypy: sinais e limites

Os 320 diagnósticos se distribuem em arg-type=90, attr-defined=87, operator=41, union-attr=27, index=20, return-value=15, assignment=14, misc=10, var-annotated=9, call-overload=5, list-item=1 e type-var=1. Maiores concentrações: grounding=44, slicing=43, compat=39, main=26 e render=25.

Não são 320 bugs confirmados. Há três classes a tratar separadamente:

1. **Contrato inconsistente real:** `ChatCompletionsAnalyzer._extract_json_payload`, `llm/backends/chat_completions.py:137`, promete `dict` e devolve `[]` na linha 147. Fixar um resultado/erro coerente e testar resposta vazia, JSON inválido e forma inesperada. Q03 trata a perda de erro da outra função de extração.
2. **Modelagem insuficiente de AST:** `ast.AST` genérico não garante `.body/.name`, e `end_lineno` é opcional no tipo. Muitos usos vêm de `ast.parse`, que fornece posições. Refinar o tipo após checagens com isinstance e anotar os visitantes; não espalhar `cast`/`type: ignore` para deixar o contador verde.
3. **Inferência larga de dicionários e atributos dinâmicos:** checkpoint em `scan/pipeline.py:335` e atributo `verify.label` em `verify/agent_scan.py:70` funcionam nos testes, mas seu contrato não está expresso. Usar tipos locais explícitos/TypedDict ou um callable com metadados onde realmente necessário. Anotações não exigem mudar o JSON público.

Uma adoção incremental deve começar pelos contratos puros e fronteiras de backend, com orçamento explícito para dívida existente. Não impor `--strict` a todo o projeto em uma única mudança.

## 4. Os 15 arquivos mais difíceis de manter

Os caminhos abaixo são relativos ao repositório. `%L` é a medição de linhas descrita na seção 7; não equivale a cobertura de ramos. I/O e H3M foram definidos na seção 2. A posição considera também risco, testes e coesão.

| # | Caminho e linha da função de maior CC | Linhas | CC máx. | Cog* máx. | Função máx. (linhas) | I/O | H3M | %L (atingidas/elegíveis) |
|---|---|---:|---:|---:|---:|---|---:|---|
| 1 | `src/main.py:902` | 1306 | 39 | 108 | 373 | 0/24 | 69 | 90.8% (890/980) |
| 2 | `src/research_pipeline/verify/agent_arm.py:471` | 810 | 25 | 61 | 128 | 7/21 | 32 | 91.3% (544/596) |
| 3 | `src/research_pipeline/verify/loop.py:196` | 476 | 32 | 113 | 159 | 4/20 | 22 | 95.5% (358/375) |
| 4 | `src/research_pipeline/verify/grounding.py:632` | 761 | 25 | 85 | 130 | 6/7 | 18 | 96.9% (567/585) |
| 5 | `src/research_pipeline/verify/render.py:278` | 590 | 21 | 52 | 95 | 7/7 | 14 | 95.3% (428/449) |
| 6 | `src/research_pipeline/verify/compat.py:856` | 1009 | 19 | 44 | 60 | 3/2 | 11 | 94.7% (727/768) |
| 7 | `src/research_pipeline/verification/esbmc_runner.py:241` | 422 | 25 | 84 | 127 | 8/1 | 18 | 91.3% (283/310) |
| 8 | `src/research_pipeline/verify/slicing.py:306` | 642 | 18 | 76 | 54 | 4/1 | 7 | 97.0% (447/461) |
| 9 | `src/research_pipeline/scan/pipeline.py:148` | 513 | 8 | 34 | 52 | 1/18 | 34 | 94.7% (372/393) |
| 10 | `src/research_pipeline/verify/sandbox.py:69` | 139 | 25 | 134 | 61 | 3/0 | 6 | 89.0% (81/91) |
| 11 | `src/research_pipeline/verify/esbmc_run.py:91` | 200 | 31 | 79 | 110 | 7/3 | 7 | 94.5% (138/146) |
| 12 | `src/research_pipeline/verify/differential.py:234` | 281 | 9 | 18 | 48 | 1/8 | 4 | 88.8% (191/215) |
| 13 | `src/research_pipeline/scan/callgraph.py:251` | 528 | 14 | 47 | 31 | 8/1 | 6 | 97.0% (417/430) |
| 14 | `src/research_pipeline/verify/healing.py:436` | 507 | 12 | 32 | 54 | 2/9 | 10 | 95.1% (351/369) |
| 15 | `src/research_pipeline/verify/llm_client.py:159` | 384 | 11 | 30 | 74 | 3/3 | 4 | 62.7% (185/295) |

Responsabilidades, dependências, duplicações e recomendação concreta por arquivo:

1. **`src/main.py` — risco alto.** Faz parsing, composição de clientes, resolução de caminhos, fingerprints, checkpoint/retomada, revisão, seleção, execução, avaliação e apresentação. Importa 24 módulos internos, incluindo backends, scan, motor e avaliadores. Duplica composição com diferenças observáveis entre `mode_scan:814` e `mode_v2:902` (Q06). Extrair primeiro um resolvedor puro de configuração e depois persistência; manter a API/CLI. Testar defaults, backends mistos, interrupção e retomada com clientes falsos.
2. **`verify/agent_arm.py` — risco alto.** Reúne execução Claude/Codex/API, materialização de ferramentas, preservação de fonte, ESBMC, replay e consolidação. Depende de 21 módulos internos e muitos comandos externos; repete montagem de comandos/clientes presente nos backends. Separar avaliação de harness da execução específica de agente, mantendo resultados e rótulos. Priorizar prazos/opções de Q05 e contratos de falha; não alterar estratégia experimental.
3. **`verify/loop.py` — risco alto.** `verify_hypothesis:196` ocupa 159 linhas e decide grounding, especificação, renderização, tentativas, ESBMC, replay e veredito. Usa 20 módulos internos. A sequência reaparece parcialmente no braço de agente, com controles distintos; não presumir equivalência. Extrair preparação e avaliação de uma tentativa com resultado tipado. Comparar dicionários de saída e motivos de término para todos os vereditos existentes.
4. **`verify/grounding.py` — risco alto.** Resolve função/método, atributos, imports, chamadas externas e forma do recorte; `ground:632` tem CC25. Depende de AST, slicing, regras e fatos de chamadores. Há Visitors locais parecidos, mas nenhuma duplicação integral que autorize fusão automática. Separar análise de atributos e montagem do objeto Grounded; preservar spans e texto original. Regressões de shadowing, async, decoradores, herança e imports.
5. **`verify/render.py` — risco alto.** Constrói harness, drivers, stubs, valores e mapa de linhas; `_stubs:278` tem CC21. Recebe Grounded/InputSpec e depende de regras/compatibilidade. Comparado ao agente, o produto é semelhante mas as garantias diferem. Separar render de dados/stubs em funções puras pequenas; testar AST, bytes significativos e correspondência de linhas, sem reescrever prompts nem políticas de stub.
6. **`verify/compat.py` — risco alto.** Concentra transformações de linguagem/AST de naturezas diferentes, em 1.009 linhas; `rename_builtin_named_methods:856` tem CC19. Depende de astutil e nomes qualificados. Os visitantes repetem operações AST; compartilhar somente utilitários com semântica idêntica. Não substituir `%` em fixtures para satisfazer UP031. Extrações devem demonstrar preservação de valores, exceções, precedência, Unicode e linhas.
7. **`verification/esbmc_runner.py` — risco alto.** Executa uma chamada, interpreta propriedades/status e grava logs. `_extract_esbmc_details:241` tem CC25; 8 consumidores internos. Não é duplicata da política de tentativas. Existe duplicação funcional da gestão de subprocesso com `verify/procs.py`, com contratos diferentes (Q04). Separar parser puro e execução, conservando saída parcial, flags e interpretação de timeout.
8. **`verify/slicing.py` — risco alto.** Descobre dependências e decide o que preservar do módulo, com efeitos de atribuições/escopos. `_plan:306` tem CC18; depende de AST/astutil, é usado por grounding/preservação/contexto. Compartilha domínio com análise de contexto, mas não se demonstrou clone equivalente. Extrair classificação de bindings/efeitos sem mudar a política. Testes com efeitos de módulo, escopos, alias e rebinding são essenciais.
9. **`scan/pipeline.py` — risco alto.** Seleção, plano, detecção, checkpoint, verificação, smells e relatórios; CC máxima só 8, mas 18 dependências internas e 34 alterações no período. Exemplo de arquivo que tamanho/CC isolados subestimam. Repete infraestrutura de persistência/composição do modo hybrid. Extrair serialização e relatório, preservando fingerprints. A área de estimativa de tokens/custos fica fora desta proposta e da implementação desta missão.
10. **`verify/sandbox.py` — risco alto/crítico pelo comportamento.** Só 139 linhas, porém `host_replay_problem:69` tem CC25 e Cog*134. Acumula política de imports, introspecção, os, async e limites de processo; depende apenas de AST, mas governa replay e diferencial. Regras repetidas para acesso direto/nomeado já divergem (Q01). Uma política auxiliar comum ajuda, mas não substitui isolamento do sistema operacional. Testes adversariais e escrita sentinela controlada antes de aceitar código externo.
11. **`verify/esbmc_run.py` — risco alto.** `check:91`, 110 linhas/CC31, combina escolha de solver, bounds, loops de biblioteca, incremento e melhor evidência. Depende do runner baixo nível, diagnóstico e regras. Não duplicar/remover controles por semelhança textual com agente. Extrair decisões puras de próxima tentativa e seleção de resultado; testes de saída parcial e timeout em cada transição.
12. **`verify/differential.py` — risco alto.** Alinha AST, gera sequências, compara recorte e módulo real e executa worker. CC9 e 281 linhas não refletem o risco da importação real. Depende de agent_arm, replay, sandbox e preservação, participando de ciclo local. Remover dependência em helper privado de agent_arm mediante extração mínima e corrigir fronteira de Q01. Testes de efeito de import, indisponibilidade e divergência sem mudar critérios científicos.
13. **`scan/callgraph.py` — risco médio/alto.** Resolve funções, imports, escopos, bindings e call sites. `_bindings:251` tem CC14; recebe 8 imports internos, inclusive fora do modo scan. Classe de resolução tem responsabilidade coesa, mas combina fases que devem ser testáveis separadamente. Separar coleta e resolução somente se isso simplificar os testes; preservar ordenação, qualnames e exclusões. Não é necessário um framework de grafos.
14. **`verify/healing.py` — risco alto.** Diagnostica reparos, valida patch, preservação, contexto e execução de nova tentativa. `verify_with_healing:436` tem CC12 e usa 9 módulos internos. Reconstrói parte do fluxo do loop, com validações adicionais legítimas. Isolar validação de patch e execução de tentativa, mantendo caderno/registro e respostas existentes. Testes de reparo rejeitado, fonte alterada e retorno parcial sem LLM real.
15. **`verify/llm_client.py` — risco médio/alto.** Uma classe configura seis backends, protocolos HTTP diferentes, CLIs, parsing, temporários e falhas. Máxima CC11, 384 linhas, mas matriz de falhas extensa. Compartilha transportes com analisadores, sem compartilhar esquema de saída. Extrair apenas transporte/execução comprovadamente comum depois de testes de contrato; manter síntese e detecção distintas. Não tocar telemetria, preços ou otimização de contexto nesta missão.

Nos itens 2–15, caminhos sem `src/research_pipeline/` usam esse prefixo. As dependências completas e a métrica por caminho foram calculadas a partir de AST, não inferidas de tamanho. `spec.py` (CC18) e `caller_facts.py` (Cog*64) também merecem atenção, mas ficaram abaixo dos arquivos com maior acoplamento, frequência de mudança ou risco de execução nesta seleção de 15.

## 5. Arquitetura, interfaces e SOLID

### Separações existentes que convém manter

`models.py:20`, `:53` e `:74` define dados sem depender dos provedores externos. `llm/protocols.py:8` já define `LLMAnalyzer`; a factory retorna esse contrato em `llm/backends/factory.py:38`. `verify/loop.py:55` define `SpecLLM`. `verify/esbmc_run.py:91` admite runner injetável e `verify/orchestrator.py:20` recebe braços/persistência como funções. São interfaces pequenas úteis à inversão de dependências e aos testes.

A factory conhecer os clientes concretos é apropriado para composição. Não há motivo para acrescentar `ModelProvider`, um contêiner de injeção ou uma hierarquia de serviços apenas para renomear abstrações já presentes. Não foram demonstradas violações de substituição de Liskov ou de segregação de interfaces por simples contagem de métodos/parâmetros.

O domínio de análise de funções/achados é relativamente independente. O núcleo de verificação usa majoritariamente `SpecLLM` e runner, porém `verify/agent_arm.py` e `verify/llm_client.py` misturam adaptação de provedores com orquestração. A oportunidade incremental é extrair pequenas fronteiras com testes de contrato, sem mover todo o projeto para uma árvore abstrata de Clean Architecture.

### Onde a dependência se torna difícil de acompanhar

O grafo de imports diretos no topo dos módulos não apresentou ciclo. Incluindo imports locais, há um componente bidirecional com:

```text
maintenance.learning, maintenance.proposals,
verify.agent_arm, verify.differential, verify.healing,
verify.lessons, verify.loop, verify.pytest_gen
```

Exemplos de ligações: `verify/differential.py:19` importa agent_arm; o braço usa diferencial por import local. O caderno de reparos conecta a verificação à área maintenance, que volta a importar suas lições. Imports locais evitam inicialização circular imediata, mas não eliminam acoplamento. Não foi reproduzido `ImportError`; chamar isso de falha de importação atual seria excessivo. Remover dependências em helpers privados e manter armazenamento de lições atrás de callbacks pequenos reduz o componente gradualmente.

`llm/prompts.py:10` usa grafo/contexto de `scan`, e o motor também usa esse grafo; `scan/callgraph.py:17` usa informação de async em `verify.astutil`. O pacote scan reúne um modo de execução e infraestrutura compartilhada. Documentar essa propriedade antes de avaliar uma extração de análise estática comum, preservando imports de compatibilidade.

### `verify/` e `verification/`: camadas, não duplicação demonstrada

`verification/esbmc_runner.py:40` executa uma chamada e interpreta saída bruta. `verify/esbmc_run.py:17` importa esse runner; `check:91` implementa política de tentativas. O nome de dois pacotes é confuso, mas fundi-los tem prioridade menor do que Q04 e os parsers/testes de contrato. Se houver futura mudança nominal, manter reexports e consumidores atuais.

Alterar HEAD não modifica árvores de tags congeladas. O risco real de uma movimentação são imports de consumidores atuais e caminhos registrados em artefatos. As tags existentes devem permanecer intactas e a reprodução deve usar o checkout e ambiente correspondentes.

### `smells/` e `smell_policy.py`: políticas diferentes

`smell_policy.py:34` mede três smells por AST e `:57` aplica thresholds; alimenta também o prompt legado em `llm/prompts.py:14`. `smells/filter.py:20` modela candidatos de ferramentas externas, `:53` filtra via LLM, `:96` avalia rótulos e `:144` adapta Ruff para scan/PySmell. Entradas, limiares e finalidade diferem. **Não recomendar unificação como limpeza neutra:** pode mudar o que está sendo medido. Documentar distinção e testar cada contrato.

### Prompts: inventário e identidade já existentes

Há detecção atual/legada em `prompts/system_prompt_v2.txt`/`system_prompt.txt`, composição em `llm/prompts.py:78`, variantes em `llm/prompt_variants.py` e `prompts/v2_variants/`; especificação/valor em `verify/loop.py:48`; reparo em `verify/healing.py:47`; revisão em `hypothesis_review.py:19`; smells em `smells/filter.py:17`; agente em `verify/agent_arm.py:109` e skills cujo hash é registrado em `:122`.

`src/main.py:519`–546 já registra hashes do prompt base, esquema, especificação, composição de variantes, revisão, propriedade de valor e pool quando aplicáveis. A distribuição por papel não prova ausência de versionamento. A recomendação de manutenção é um índice de origem, consumidor e identidade registrada, mais testes dos hashes existentes. Mover, reescrever ou centralizar conteúdo de prompts fica fora deste escopo e exigiria avaliação própria de equivalência.

### Concentração na CLI: Q07

**Evidência:** `build_parser:98`, 270 linhas; `mode_v2:902`, 373 linhas/CC39; main tem I/O=0/24 e H3M=69. **Impacto:** mudanças em opções atingem configuração, persistência e execução, gerando deriva como Q06; testes precisam substituir nomes internos do entrypoint. **Solução:** extrair resolvedor puro e persistência, um lote por vez, mantendo CLI e funções importadas pelos testes. **Risco:** médio/alto por fingerprints, paths e defaults. **Testes:** matriz de argumentos, saídas/checkpoints equivalentes, exceções/interrupção/retomada e fixture offline ponta a ponta. Não alterar seleção, política de confirmação, métricas ou experimentos.

## 6. Duplicação, código potencialmente morto e legibilidade

O agrupamento de `ast.dump` de corpos de funções, sem posições/docstring e com pelo menos 8 linhas físicas, encontrou somente dois grupos exatos:

| Local | Evidência | Avaliação / ação futura |
|---|---|---|
| `maintenance/execution.py:201` e `:243` | Dois callbacks locais `evaluate`, 17 linhas cada, com o mesmo corpo | P2 local; extrair avaliação comum somente mantendo contexto/efeitos e resultados dos gates |
| `preprocess.py:58` e `:67` | Visitors sync/async, 8 linhas cada | P3; um alias/helper pode bastar, com testes de funções assíncronas |

Não é uma medição de porcentagem total de duplicação: clones com nomes/constantes diferentes e blocos parciais escapam ao método. Duplicações funcionais mais relevantes são composição da CLI (Q06), gestão de subprocessos (Q04/Q05) e transporte HTTP/CLI entre backends/síntese. Esquemas de detecção e síntese são distintos; compartilhar transportes não autoriza fundir protocolos.

Não foram detectadas definições de topo sobrescrevendo nomes anteriores. Ausência de import/referência não comprova que um script CLI esteja morto. Os workers `replay_worker.py`, `differential_worker.py` e ferramentas geradas são acionados por caminho/comando, não necessariamente por import Python. Nenhum módulo ativo foi classificado como removível só por fan-in zero.

Há comentários obsoletos verificáveis: `verify/llm_client.py:56` descreve o cliente como OpenAI-backed, mas o construtor admite seis backends; `src/main.py:630` chama o padrão de release, enquanto `verification/esbmc_runner.py:14` documenta checkout master. `scan/pipeline.py:49` fala em A5, porém `:50` inclui A12. A correção é esclarecer o comportamento existente e sua condição, sem mudar modelo/prompt ou reconstruir história científica. Risco baixo; conferir documentação e CLI contra o código.

Nomes curtos (`h`, `n`, `t`) em transformações AST têm contexto local e não são defeito por si. Onde uma função mistura papéis e mantém muitos dicionários, como no loop/agente, renomear valores para `hypothesis`, `attempt` e `replay_result` pode ajudar depois de separar responsabilidades. Não fazer renomeação estética ampla que dificulte comparação com o snapshot congelado.

## 7. Testes, cobertura e confiabilidade

### Resultado observado agora

| Execução | Resultado | Interpretação |
|---|---|---|
| Coleta do snapshot | 1.786 casos, 1,96 s | Mesmo total de casos da referência 1.785+1 |
| Suíte completa instrumentada, sandbox ativo | **1.780 aprovados, 5 falhas, 1 pulado**, 356,66 s | Não é uma suíte verde |
| Reexecução somente das cinco falhas, com permissão de escrita para caches | **4 aprovados, 1 falha**, 0,58 s | Quatro falhas eram restrições de ambiente; uma revela pressuposto do launcher |

Não houve uma segunda execução completa. Portanto não declarar “1.785 testes aprovados agora”. O conjunto das execuções mostra 1.784 casos aprovados ao menos uma vez, 1 falha de portabilidade ainda presente nessa configuração e 1 pulado; esse agregado não é o resultado de uma única suíte.

`pytest.ini:4` exclui `live_llm`. Além disso, o runner temporário retirou variáveis de chave de API conhecidas, bloqueou conexões socket de rede e execução real das CLIs codex/claude/gemini/ollama no processo de testes. Registrou **zero tentativas bloqueadas** na execução completa. Os testes revisados usam respostas falsas para provedores. As integrações reais executadas foram locais, com ESBMC, CPython, Ruff, Git e Mypy. Não houve chamada paga. O bloqueio temporário não é uma nova política implementada no repositório nem um sandbox de descendentes. A suíte foi iniciada por `PYTHONDONTWRITEBYTECODE=1 "$PY" /tmp/llm-esbmc-quality-20261111/run_tests.py`, que chama pytest com `-q -p no:cacheprovider --basetemp=<pasta temporária> --durations=20`.

### As cinco falhas e seu controle

| Teste | Falha inicial | Reexecução | Conclusão |
|---|---|---|---|
| `test_maintenance_execution.py:248`, `test_real_launcher_exits_without_running_maintenance_for_an_empty_queue` | Launcher encerrou com 127, esperado 0 | Persiste | Worktree não tem `.venv/bin/python`; Q11 abaixo |
| `test_scan_pipeline.py:645`, `test_scan_smells_send_ruff_candidates_through_the_llm_filter` | Zero candidatos, esperado um | Aprovado | Ruff falhou ao criar cache no checkout somente leitura; plan_scan registra tool_error |
| `test_scan_pipeline.py:669`, `test_scan_smells_judge_the_code_seen_at_plan_time_and_count_what_was_not_kept` | Zero candidatos, esperado um | Aprovado | Mesma restrição de cache; não é demonstração de regressão do filtro |
| `test_smell_filter.py:99`, `test_ruff_reports_become_candidates_with_their_enclosing_code` | Ruff retornou 2 por `.ruff_cache` não gravável | Aprovado | Dependência do executável/cache real, não falha de análise Python |
| `test_v2_agent_arm_script.py:78`, `test_flags_reach_the_arm_and_default_stays_on` | Não pôde gravar em `~/.cache/llm_esbmc/esbmc_knowledge` | Aprovado | Teste escreve cache global e depende de permissão fora de tmp_path |

O sandbox bloqueou escritas em caminhos externos aos diretórios autorizados. A reexecução com permissão foi limitada a esses cinco testes, mantendo bloqueio de rede/CLIs de LLM. Não foi criado ambiente virtual nem alterado código para mascarar a falha restante.

**Q11 — P2, dependência de caminho fixo e agendamento sem validação.** `maintenance/execution.py:279` executa `root/.venv/bin/python`, em vez de permitir o interpretador ativo/configurado. `:283` descarta stdout/stderr e `:284` devolve `scheduled=True` mesmo quando o filho vai morrer por executável ausente. A reprodução é o teste acima em worktree usando um Python válido externo ao repositório: o processo de shell nasce, mas termina 127. A mesma premissa aparece em `run_suite:53` e `_launch_automatic_worker:304`.

**Impacto:** testes e manutenção não são portáveis para venv externo; agendamento não informa a falha de inicialização. **Solução futura:** configuração explícita de interpretador (ou sys.executable quando apropriado), validação antes de lançar e diagnóstico de falha de inicialização. **Risco:** baixo/médio; o subprocesso precisa usar um ambiente com as dependências corretas, não qualquer Python encontrado no PATH. **Testes:** ambiente externo, executável ausente, fila vazia, fila pendente, inicialização com erro e identidade do interpretador. Testar sem criar arquivos de configuração globais.

### Cobertura medida, com limites explícitos

Como coverage.py/pytest-cov não estavam instalados, a execução completa usou um tracer local baseado em `sys.settrace`. Para cada arquivo de produto, o denominador veio das linhas executáveis que a biblioteca padrão `trace._find_executable_linenos` extrai do compilador; posições zero artificiais foram descartadas. O numerador é o conjunto dessas linhas observado no **processo principal** dos testes. Linhas vazias/comentários não entram; isso não é cobertura de ramos, condições nem subprocessos.

Resultado: **12.765/14.194 linhas elegíveis (89,9%)**, nos 98 arquivos sem sondas, na execução que teve cinco falhas de ambiente. A seção 4 apresenta os 15 valores individuais. Não houve nova medição de cobertura na reexecução dos cinco testes.

Pontos que merecem testes adicionais:

- `llm/backends/anthropic.py`: 43.6% por esse método; `analyze` e transporte não foram exercitados diretamente em boa parte (`:42` em diante). A síntese Anthropic em outro cliente ter testes não cobre esse analisador.
- `llm/backends/openai.py`: 52.5%; boa parte de `analyze` e caminhos de HTTP/retry ausente. Usar respostas HTTP locais falsas/fixtures reais sanitizadas, sem API.
- `verify/llm_client.py`: 62.7%; `_post_json:330` não foi atingido, assim como vários caminhos de erro/CLI. As regras de prazo, shape e falha precisam matriz offline.
- `verify/graph_tool.py`: 52.8%; subprocesso real não é acompanhado pelo tracer principal. Combinar a observação com `tests/test_verify_graph_tool.py`, não concluir falta de testes pelo número isolado.
- `verify/replay_worker.py` e `differential_worker.py`: 0% no tracer principal, **por execução em subprocesso**. Há testes reais que os acionam. Medir subprocessos/branches exige instrumentação própria posterior; não rotular workers como não testados ou mortos.

Cobertura alta de sandbox/grounding não prova segurança ou preservação em todos os casos: Q01 escapou apesar de muitos caminhos exercitados. Percentual de linhas é um indicador de execução, não de força das asserções.

### Fragilidade, duplicação e mocks

A busca textual encontrou monkeypatch/mock em 41 de 124 arquivos `test_*.py`. Isso não mede quantidade de mocks por teste nem prova excesso. Em backends, runners e limites de uso, simular a fronteira é necessário para não gastar e para testar falhas de forma determinística. Fragilidade aparece quando o teste substitui detalhes do entrypoint ou caminhos globais, como `tests/conftest.py:11` substituindo resolve_rules em main e o cache de conhecimento não redirecionado em `tests/test_v2_agent_arm_script.py:24`.

Os dois fixtures globais têm propósito legítimo: impedir sondas reais por meio de main e copiar o caderno para temporário (`tests/conftest.py:18`). A compensação recomendada é ter testes de integração explícitos para a composição que esses fixtures escondem, não removê-los da suíte padrão.

O agrupamento de corpos AST idênticos com pelo menos 8 linhas não encontrou testes duplicados. Isso não exclui duplicações menores/semânticas. Os muitos casos parametrizados de compatibilidade e intrínsecos cobrem fronteiras diferentes; não são duplicação descartável apenas pelo formato parecido.

Exemplos a fortalecer:

- `tests/test_llm_backends.py:116` passa exatamente com o silêncio de Q03. Corrigir o contrato e seu teste, mantendo o caso de zero achados válido.
- `tests/test_verify_sandbox.py:56` testa self.__dict__ legítimo, mas faltam rebinding de self, aliases de imports e introspecção indireta, além de contenção de escrita real.
- `tests/test_verify_esbmc_integration.py:126` aceita qualquer um de CONFIRMED/NOT_CONFIRMED/UNVALIDATED e só rejeita UNSUPPORTED. É um smoke test de compatibilidade útil, mas não prova o resultado da propriedade. Manter esse papel claro e adicionar casos de contrato com resultado exato quando a propriedade for o objetivo.
- `tests/test_verify_agent_arm.py:624` aceita Exception ampla; outra falha incidental pode satisfazer a asserção.
- `tests/test_verify_procs.py:16`/`:29` e `test_verify_round_warnings.py` usam relógio real; testes de término de árvore precisam de processos reais, mas sincronização por arquivo/pipe reduz dependência de tempo arbitrário. Não foi observada flutuação nessas execuções.

### Integração, determinismo e lacunas

A suíte padrão inclui ESBMC real se o wrapper existir (`tests/test_verify_esbmc_integration.py:15`), teste de wrapper master (`:242`) e teste que procura ESBMC no PATH (`tests/test_verify_string_witness.py:61`). A disponibilidade e a identidade do binário mudam os skips e os tempos. Não assumir que “pytest padrão” significa somente unitários. Separar marcadores de integração local e registrar versão/flags do verificador melhora reprodução sem mudar critérios científicos.

Os testes mais lentos nesta execução foram um witness por propriedade (75,43 s), lista aninhada com stub (56,54 s) e loop protegido (21,16 s). O tempo total é do ambiente com instrumentação e não compara desempenho com a auditoria anterior. O resultado não estabelece estabilidade estatística: a suíte inteira rodou uma vez.

Há controles positivos: ordenação de arquivos/calls em `scan/callgraph.py:136/:503`, RNG local com seed em `verify/replay_worker.py:293`, hashes de fontes/prompts e checkpoints atômicos em `src/main.py:440` e `scan/pipeline.py:449`. Não se demonstrou não determinismo geral. Faltam, para os defeitos reproduzidos, testes adversariais de confinamento, falhas por etapa do shell, erro de parsing persistido, prazo total versus timeout individual, configuração mista e ausência de interpretador local.

O conhecimento ESBMC usa cache global por commit em `verify/esbmc_knowledge.py:21/:86`. Nos testes, injetar pasta temporária evita dependência de estado/permissões do usuário. O teste real de Ruff deve declarar seu requisito e usar cache temporário. Essas são melhorias de isolamento dos testes, sem alterar o detector científico.


## 8. Segurança e robustez: evidência, impacto e correção proposta

### Q01 — P0 condicionado: contenção insuficiente de código não confiável

**Evidência:** `verify/sandbox.py:50` permite `self.__dict__` apenas pelo nome sintático `self`; `:99` valida imports from contra uma lista incompleta; `:122` aceita atributos literais em getattr sem aplicar todas as restrições de acesso direto. `verify/replay.py:140` executa o worker com ambiente vazio, temporário, limites de CPU/memória/processos e namespace de rede quando disponível, mas sem restringir escrita no sistema de arquivos.

A reprodução controlada usou `import random; self = random` e, dentro da função, `self.__dict__['_os'].mkdir(caminho_temporario_externo)`, seguida de divisão por zero. O filtro devolveu string vazia (aceito); o worker criou o diretório fora de seu temporário e retornou `reproduced/ZeroDivisionError`. O namespace de rede estava ativo. Também foram aceitos pelo filtro `from random import __builtins__ as b` e getattr com nomes `gi_frame`/`f_builtins`; essas duas variantes não foram usadas para escrita.

Há outra entrada independente: `_real_problem` em `verify/differential.py:231` verifica o harness; `verify/differential_worker.py:83` importa o módulo original inteiro. Um módulo original com criação de diretório no nível superior executou esse efeito e a comparação devolveu `preservada`.

**Impacto:** origem/harness não confiável pode gravar onde a usuária tem permissão, incluindo arquivos de experimentos. Execução de código é intencional; a insuficiência da fronteira de isolamento é o defeito. A prova não demonstra perda de dados nem ataque anterior.

**Solução sugerida:** corrigir as três inconsistências do filtro e colocar replay/importação real/teste gerado sob restrição de escrita imposta pelo sistema operacional. Sem essa fronteira, não aceitar que a lista de bloqueios AST prove segurança para origem externa. A indisponibilidade deve ser explícita.

**Risco da mudança:** médio/alto; dependências que criam caches e casos antes aceitos podem passar a indisponíveis. Registrar esse efeito operacional sem reclassificar resultados antigos silenciosamente. **Testes necessários:** bypasses, arquivo sentinela externo que permaneça íntegro, efeitos de importação, exemplos puros, falta de suporte de isolamento e comportamento dos temporários.

### Q02 — P1: comando final com sucesso falso

**Evidência:** `scripts/run_final.sh:7` usa `set -u`; só a etapa 1 trata retorno não zero (`:26`). As etapas 2–5 (`:31`, `:36`, `:40`, `:44`) não checam retorno, e `:46` imprime `done`.

**Reprodução:** cópia do shell em `/tmp`, relatório mínimo preexistente para pular a etapa 1 e `PY` falso retornando 42 em todas as chamadas seguintes. Quatro falhas ficaram no log; o script imprimiu `done` e terminou com **0**. Não houve ESBMC ou LLM.

**Impacto:** uma rodada sem controle/validação pode parecer concluída para usuária/automação. **Solução:** verificar e propagar retorno por etapa; anunciar conclusão só quando todas as etapas necessárias tiverem sucesso. **Risco:** baixo/médio operacional; preservar retomada e distinguir saída preexistente de etapa validada. **Testes:** falhar cada etapa isoladamente, verificar rc, logs e ausência de done; retomada e percurso totalmente bem-sucedido com executáveis falsos.

### Q03 — P1: falha de parsing registrada como detecção vazia bem-sucedida

**Evidência:** `llm/backends/chat_completions.py:129` captura JSON inválido, grava warning e retorna `[]` (`:134`). `scan/pipeline.py:296` registra erro apenas quando `analyze` levanta exceção; ao receber lista vazia retorna `error=''` em `:314`. O teste `tests/test_llm_backends.py:116` fixa explicitamente esse retorno vazio para conteúdo malformado.

**Reprodução sem API:** a função `_detect` recebeu um analisador falso que delegava à extração real. As respostas `not json at all` e `{"findings": []}` produziram exatamente `{"error":"","candidates":[],"held":[]}`. Um warning no console não torna o checkpoint distinguível.

**Impacto:** erro de leitura da resposta se perde no status persistido; pode ser interpretado como análise sem candidatos. **Solução:** resultado/erro explícito na fronteira de parsing, preservado no checkpoint e na retomada. Não mudar os critérios científicos de avaliação nesta correção técnica. **Risco:** médio, pois muda representação de falha e possibilidade de reprocessar uma etapa; não reinterpretar rodadas congeladas automaticamente. **Testes:** vazio válido, JSON inválido, ausência de choices/content, JSON com forma errada, status persistido e retomada. Outros backends devem cumprir o contrato, sem chamadas reais.

### Q04 — P2: processos filhos sobrevivem ao timeout

**Evidência:** `verification/esbmc_runner.py:81` usa subprocess.run com timeout; `:91` registra o timeout, sem gestão da árvore. `verify/procs.py:60` já implementa controle de grupo/descendentes, mas perde saída parcial ao retornar None no timeout.

**Reprodução:** wrapper Python falso abriu filho adormecido e esperou. O runner retornou timeout em 1 segundo, mas o filho continuou vivo; a sonda o encerrou no finally. Não foi observado no wrapper padrão atual, que usa exec; o caso importa para wrappers personalizados admitidos pelo sistema.

**Impacto:** consumo residual de recursos e interferência entre casos. **Solução:** runner comum que encerre árvore e preserve stdout/stderr parcial/código. **Risco:** médio/alto, pois saída parcial alimenta a leitura de contraexemplos; substituir diretamente por run_group perderia evidência. **Testes:** descendente comum, outra sessão, saída parcial, processo pai terminando primeiro e isolamento entre execuções independentes.

### Q05 — P2: prazo e configuração do agente não são uniformes

**Evidência:** `verify/agent_arm.py:218` calcula deadline e só o consulta no início da rodada (`:225`). `llm.complete` não recebe tempo restante; subprocess do ESBMC usa timeout fixo (`:243`). Uma LLM falsa imediata e um ESBMC falso que demorou 1,3 segundo retornaram DONE após 1,30 segundo com prazo total de 1 segundo.

Além disso, `src/main.py:649` e `:863` passam somente `esbmc[0]` a make_agent. O cliente criado em `verify/agent_arm.py:808` não recebe `--llm-timeout`; o loop API usa `esbmc_timeout=120` em vez de `--timeout`. A revalidação posterior recebe o comando completo. A perda dessas opções foi verificada estaticamente, não por execução de fluxo externo.

**Impacto:** limites anunciados e flags de um comando personalizado não governam toda a execução. **Solução:** propagar configuração completa e tempo restante a cada operação; distinguir orçamento total do limite por chamada. **Risco:** médio; propostas antes aceitas após o prazo passarão a expirar. **Testes:** LLM lenta, ESBMC lento, múltiplas rodadas, prazo consumido antes de iniciar subprocess e preservação de flags extras. Não revisar política de custo/tokens nesta missão.

### Q06 — P2: resolução divergente de modelo para backends mistos

**Evidência:** `src/main.py:939` reutiliza o modelo de detecção mesmo com outro backend de síntese; `mode_scan:840` usa default do backend de síntese quando são diferentes. O comentário `src/main.py:936` diz para reutilizar somente sem override, mas a expressão não cumpre isso para APIs distintas.

**Reprodução local:** CLI `--mode hybrid --backend google --model gemini --synth-backend openai`, com factories falsas interrompendo antes de qualquer chamada, construiu síntese `{backend: openai, model: gemini-2.5-flash}`. Com `--model` omitido o caso testado selecionou corretamente o default OpenAI: não generalizar o defeito a essa combinação.

**Impacto:** configuração admitida pode falhar ao ser usada e o comportamento difere do scan. **Solução:** resolvedor puro compartilhado de backend/modelo, após explicitar o contrato de defaults. **Risco:** médio por defaults/fingerprints; preservar modelos explicitamente escolhidos para síntese. **Testes:** matriz de backends iguais/diferentes, modelos omitidos/explícitos, aliases e CLIs com modelo vazio, sem API.

### Outras verificações de segurança

Subprocessos de produto inspecionados usam listas de argumentos; não foi demonstrada injeção por shell. O wrapper de rounds usa shlex para comando/caminhos (`verify/rounds.py:55`). Operações perigosas deliberadas não foram classificadas como vulnerabilidades só pelo nome da função.

`maintenance/automatic.py:24` recusa caminhos absolutos, `..`, arquivos fora do verificador e symlinks; `:54` exige scratch externo; `:59` exclui `.env`, `.aws`, `.ssh` e configurações locais da cópia; `:71` revalida mudanças no original antes de aplicar. São controles positivos, não uma autorização para aplicar patches nesta auditoria.

Temporários de replay usam TemporaryDirectory; saídas das CLIs usam NamedTemporaryFile e finally. O ambiente do replay é vazio e Python roda com `-I -S`. O isolamento de rede é oportunista (`verify/replay.py:96`), portanto não equivale a um sandbox de arquivos/processos completo. A correção de Q01 deve definir seu comportamento quando faltarem recursos do host.

Uma busca local por prefixos de credenciais OpenAI/Google/GitHub não encontrou candidatos nos arquivos de texto rastreados de até 2 MB, nas extensões de código/documentação/configuração examinadas. `.env` não foi lido. Isso não é varredura de todo o histórico, binários, logs locais ou formatos de segredo sem esses prefixos. Nenhum segredo foi impresso ou enviado para fora.

Não há evidência verificada de dependência vulnerável nesta análise. Sem banco de advisories e sem lock completo, não é possível concluir que o ambiente está livre de vulnerabilidades.

## 9. Plano de limpeza, sem remoções

| Item | Classificação | Evidência e condição para ação futura |
|---|---|---|
| `src/`, `tests/`, 51 sondas | **Manter / refatorar pontualmente** | Ativos; probes pertencem ao catálogo, não a limpeza automática |
| `dataset/`, ground truth, `reports/json/`, `docs/experimentos/`, `archive/` | **Manter** | Evidência e entradas científicas; gerado não significa dispensável |
| 763 logs rastreados | **Manter** | 634 em reports, 70 archive, 51 docs e 8 logs; não foi comprovado log indevidamente versionado |
| `artifacts/`, `outputs/`, `output/` do checkout principal | **Manter / requer investigação adicional do inventário** | Ignorados; não copiados ao worktree. Relacionar com rodadas e backup, sem inferir tamanho atual da auditoria anterior |
| `scripts/funil.py` | **Manter e documentar** | Análise por bug; usa calibrate_review. Ausência de referência externa não prova desuso |
| `scripts/v2_funnel.py` versus `funil.py` | **Requer investigação adicional** | Usam rotulação/localização diferentes; unificação pode mudar a interpretação |
| `scripts/patch_rule.py`, `sample_off_line.py` | **Manter e documentar** | Comparação buggy/fixed e amostragem para rotulação têm finalidade própria |
| Scripts de uma rodada | **Requer investigação adicional / mover para arquivo histórico após inventário** | Registrar entrada, saída, consumidor, rodada e dependência externa antes de decidir |
| `src/main.py`, arquivos do ranking | **Refatorar** | Lotes pequenos com controles de equivalência; nenhum foi alterado |
| `verification/`, `smells/`, `smell_policy.py` | **Manter responsabilidades** | Não se comprovou duplicação semântica que justifique fusão |
| `docs/projeto/HANDOFF*.md` antigos | **Mover para arquivo histórico, condicionado** | Distinguir instrução vigente de registro e preservar links; criar índice pode bastar |
| `docs/projeto/rascunho_issue_*.md` | **Requer investigação adicional** | Publicação das issues não foi confirmada; não supor obsolescência |
| `analise-verificao-formal.md`, 15.477 bytes | **Mover para documentação/histórico, condicionado** | Texto acadêmico; organizar sem apagar conteúdo nem atribuir obsolescência sem confirmação |
| `kbs2026.pdf`, 10.169.637 bytes | **Manter; organização opcional** | Referenciado em `docs/projeto/notas_pyra_2026-11-09.md:3`; tamanho na raiz não justifica apagar/migrar histórico |
| `UFAM-2026-Cordeiro.pdf`, 1.703.726 bytes | **Requer investigação adicional** | Finalidade não confirmada; manter até esclarecer |
| PDF de diretrizes acadêmicas, 164.800 bytes | **Manter** | Fonte das instruções de escrita |
| `teste.py`, scratch/cache/bytecode locais | **Candidato à remoção condicionada** | `teste.py` é ignorado e não está no snapshot; confirmar conteúdo/autoria/valor antes de qualquer ação |
| `requirements.txt` | **Refatorar declaração de ambiente** | Não remover dotenv/pytest/networkx: há usos. Ferramentas opcionais/dev precisam declaração própria |
| `.gitignore:30`, `.github/` | **Requer investigação adicional** | Ignore amplo pode impedir versionar CI. Nenhum workflow consta do snapshot; CI externa não foi inspecionada |
| `pytest.ini` | **Manter** | Define caminhos e exclusão de `live_llm`; não há configuração redundante demonstrada |
| Auditoria anterior e este relatório | **Manter com papéis distintos** | Inventário inicial versus evidências aprofundadas; nenhuma cópia de relatório anterior foi criada |

Não há lista de arquivos comprovadamente obsoletos pronta para exclusão. Isso é um resultado da auditoria: falta evidência para eliminar módulos/scripts científicos com segurança. A organização visual da raiz tem prioridade menor que as falhas reproduzidas.

### Q08 — ambiente e documentação

`README.md:167` anuncia Python 3.9+, mas `itertools.pairwise` (`verify/astutil.py:10`) e zip strict (`verify/preservation.py:268`) exigem ambiente posterior. A metadata local de NetworkX 3.6.1, versão fixada em `requirements.txt:3`, declara `Requires-Python: !=3.14.1,>=3.11`. `README.md:177` omite NetworkX ao descrever dependências. O padrão ESBMC documentado em `README.md:181` difere de `verification/esbmc_runner.py:18`. `TUTORIAL.md:84` inverte o suporte Anthropic em detecção/síntese para hybrid.

Ruff é executável real em `tests/test_smell_filter.py:104`; a adaptação de produto em `smells/filter.py:138` procura a ferramenta e falha explicitamente se ausente, mas requirements não a declara. Não foi identificada dependência de produto declarada sem uso: dotenv carrega ambiente, pytest é teste e reproduz testes gerados, NetworkX sustenta métricas de grafo. O grande conjunto de pacotes instalado localmente não é prova de dependências necessárias do projeto.

**Impacto:** instalação limpa pode não reproduzir suíte/CLI. **Solução:** declarar versão Python compatível e conjunto dev/opcional reproduzível, fixar política de lint/tipos, corrigir guia operacional sem reescrever registros de experimentos. **Risco:** baixo/médio; não mudar a versão/seleção do Ruff usada como detector científico sob rótulo de lint. **Testes:** ambiente limpo com dependências declaradas, coleta/suíte offline, CLI help e smoke tests de scan sem `--yes`. Instalação limpa não foi executada nesta etapa.

## 10. Roadmap incremental e critérios de aceite

Todas as ações abaixo são propostas para uma etapa posterior. Nenhuma foi executada.

| Ordem | Lote | Prioridade | Risco da alteração | Testes e critério de aceite |
|---|---|---|---|---|
| 1 | Contenção CPython/importação real, Q01 | P0 condicionado | Médio/alto | Sentinela externa intacta; bypasses rejeitados/confinados; indisponibilidade explícita; casos puros preservados |
| 2 | Propagar falha do comando de rodada, Q02 | P1 | Baixo/médio | Cada etapa falsa falha com rc não zero e sem done; retomada continua correta |
| 3 | Distinguir falha de parsing e resultado vazio, Q03 | P1 | Médio | Registro/checkpoint conservam erro; vazio válido continua sucesso; sem reinterpretar resultados antigos |
| 4 | Tratar portabilidade do launcher e isolar caches dos testes, Q08/Q11/seção 7 | P1/P2 conforme causa | Baixo/médio | Dependências declaradas; separar falha de ambiente de regressão; executar sem credenciais/rede/LLM |
| 5 | Centralizar execução/tempo com contrato de logs, Q04/Q05 | P2 | Médio/alto | Sem descendente residual; timeout por chamada e total respeitados; saída parcial preservada |
| 6 | Resolvedor puro de backend/modelo, Q06 | P2 | Médio | Matriz de argumentos em hybrid/scan; defaults/fingerprints revisados, modelos explícitos preservados |
| 7 | Extrair configuração/persistência da CLI, Q07 | P1 de manutenção | Médio/alto | Interface CLI e JSON equivalentes; teste de interrupção/retomada; não tocar área concorrente de tokens/custos |
| 8 | Separar preparação/avaliação de tentativa e execução de agente | P1/P2 | Alto | Fixtures locais para vereditos/motivos, mesma fonte, spans e artefatos; comparação sem chamada paga |
| 9 | Melhorar contratos de tipos e remover arestas cíclicas pontuais, Q09 | P2 | Médio | Mypy por módulo, narrowing AST, contratos offline; saída pública inalterada |
| 10 | Pequenos clones, comentários e lint selecionado, Q10 | P2/P3 | Baixo | Correção localizada, sem probes/prompts/fixtures científicas; testes do comportamento afetado |
| 11 | Índices e organização histórica condicionada | P3 | Baixo | Links e caminhos de reprodução preservados; decisão sobre cada item do inventário; nenhuma remoção implícita |

**Q09, tratamento concreto:** priorizar o contrato de parsing em `llm/backends/chat_completions.py:137`, os dicionários de checkpoint em `scan/pipeline.py:335` e atributos de callable em `verify/agent_scan.py:70`. Risco baixo/médio se apenas expressar os tipos reais; alto se aproveitar a tarefa para mudar serialização. Testar os dados públicos e exceções além de executar Mypy. Imports locais cíclicos devem ser reduzidos por helpers/callbacks com necessidade comprovada, não por uma nova camada genérica.

**Q10, tratamento concreto:** callbacks idênticos em `maintenance/execution.py:201/:243`, visitors em `preprocess.py:58/:67` e comentários listados na seção 6. Risco baixo se mantidos efeitos, ordem e mensagens; os testes dos gates e pré-processamento devem continuar cobrindo sync/async. Formatação não deve alterar corpus, sondas ou exemplos usados para testar a própria linguagem.

O aceite de cada lote deve registrar commit base, ambiente e resultado dos testes pertinentes. Mudanças que alterem disponibilidade de execução, defaults ou status exigem explicar essa diferença antes de comparar novas rodadas com as congeladas. Conteúdo científico, critérios de confirmação, prompts, ground truth e otimização de tokens/custos permanecem decisões fora do plano de implementação desta auditoria.

### Transparência do uso de IA e pendências

Codex foi utilizado para inspecionar código, coordenar duas análises auxiliares somente leitura, executar ferramentas locais e reproduções inócuas, calcular indicadores e redigir esta auditoria técnica. O uso foi de análise e redação técnica, não apenas correção gramatical. Não houve laudo de detector de texto, consulta a serviços de detecção ou revisão humana declarada. Fernanda deve conferir achados, limites e prioridades antes de decidir mudanças; isso não transfere à IA autoria ou direção científica.

Permanecem fora da evidência: cobertura de ramos/subprocessos completa, instalação em ambiente novo, varredura de vulnerabilidades por advisories, segredos em todo o histórico, eficácia de isolamento em outros hosts e impacto quantitativo dos defeitos sobre resultados históricos. Nenhuma dessas lacunas foi preenchida com suposições.
