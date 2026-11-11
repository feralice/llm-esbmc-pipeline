# Auditoria de arquitetura e limpeza do repositório

Data: 2026-11-11. Branch: `feat/harness-de-agente`, commit `40f72ae`. Árvore de trabalho limpa no início.

Esta auditoria é a Fase 1 do plano de estabilização. Nenhum arquivo foi apagado nem alterado no código. Os itens marcados como "decisão" dependem da autora.

## 1. Mapa do repositório

| Área | Conteúdo | Tamanho | Situação |
|---|---|---|---|
| `src/research_pipeline/verify/` | motor de verificação (harness, sondas, ESBMC, replay, diagnóstico) | 12,0 mil linhas, 45 módulos, 51 arquivos de sonda | núcleo; mais da metade do código |
| `src/research_pipeline/llm/` | backends (Anthropic, OpenAI, Codex, Claude CLI), prompts, custo | 2,3 mil linhas | núcleo |
| `src/research_pipeline/scan/` | modo scan (grafo de chamadas, métricas) | 1,3 mil linhas | ativo |
| `src/research_pipeline/maintenance/` | autocorreção (self-healing) | 0,9 mil linhas | ativo |
| `src/research_pipeline/verification/` | só `esbmc_runner.py` | 0,4 mil linhas | pacote com um módulo (ver item 3.3) |
| `src/research_pipeline/smells/` | filtro de code smells | 0,2 mil linhas | ativo, duplica parte de `smell_policy.py` |
| `src/main.py` | ponto de entrada (modos hybrid, benchmark, scan) | 1,3 mil linhas | grande demais, mistura CLI e orquestração |
| `scripts/` | 53 scripts de experimento e análise, 24 deles `v2_*` | 6,7 mil linhas | muitos utilitários de uma rodada |
| `tests/` | 126 arquivos | 1785 testes passando, 1 pulado | rede de segurança boa |
| `dataset/` | casos reais, smells, PGENE601, V1 sintético | 75 MB versionados | preservar |
| `reports/json/` | 1030 relatórios de rodadas | 4,5 MB | preservar |
| `docs/` | experimentos (316 arquivos), projeto (54), histórico (19), desenho (21) | 31 MB | parte é histórico, parte é fonte de verdade |
| `archive/` | V1 (verificação formal anterior) | 0,4 MB | preservar, é arquivo |
| `artifacts/` | saídas grandes (v2 1,3 GB, pgene601 247 MB), ignorado pelo git | 1,6 GB | fora do git; não tocar sem plano |
| `outputs/`, `logs/`, `artigos_estudo/` | saídas de rodadas e material de estudo | 13 MB + 2 MB + 2 MB | preservar; `outputs/` está no `.gitignore` |

Tags de congelamento: `harness-freeze-2026-10-15`, `v2`, `v2-congelado-2026-11`, `v2-congelado-2026-11b`, `v2-congelado-2026-11c`. Qualquer remoção de código precisa garantir que as rodadas congeladas continuem reproduzíveis a partir dessas tags.

## 2. Estado verificado agora

- Testes: `pytest` com o `pytest.ini` do repo deu 1785 aprovados, 1 pulado, em 4 min 22 s. Esta é a linha de base para qualquer mudança.
- Lint: `ruff check src scripts tests` reporta 296 ocorrências. O repo não tem `pyproject.toml` nem `ruff.toml`, então a configuração efetiva vem de fora do repositório. Antes de qualquer limpeza automática, a regra precisa ser fixada no repo.
- Ocorrências de lint que são reais e seguras de corrigir: 19 de `F841` (variável não usada), 1 de `F401` (import não usado em `tests/test_verify_pinned.py`), 72 de `RUF100` (`noqa` que não serve mais), 42 de `I001` (ordem de imports).
- Ocorrências que parecem erro e não são: cerca de 50 `F821` em `verify/probes/*.py`. Esses arquivos são entradas para o ESBMC (usam `nondet_int`, `__ESBMC_assume`), não código que roda no CPython. Precisam de exceção por caminho, não de correção.
- Ocorrências `S102` (`exec`) são intencionais: `differential_worker.py` e `replay_worker.py` executam harness isolado. Estão justificadas no código com `noqa`.
- Arquivo na raiz ignorado pelo git: `teste.py` (104 bytes). Não é referenciado por nada.

## 3. Principais problemas

### 3.1 Ponto de entrada inchado

`src/main.py` tem 1306 linhas. Ele declara argumentos de CLI, monta configuração e chama os três modos. Quem lê o arquivo para entender um modo precisa atravessar os outros dois. Separar em `cli.py` (argumentos) e um módulo por modo reduz o acoplamento sem mudar comportamento.

### 3.2 Duas trilhas de "smell" e de prompt

- Smells: `src/research_pipeline/smells/filter.py` e `src/research_pipeline/smell_policy.py` convivem, com prompts próprios em `prompts/smell_*.txt`.
- Prompts: parte no código (`llm/prompts.py`), parte em `.txt` (`prompts/`), parte em `prompts/v2_variants/` lido por `llm/prompt_variants.py`. Não há um ponto único de versionamento de prompt. Isso já foi pedido no prompt mestre (prompts versionados e com hash).

### 3.3 Pacote `verification/` com um módulo

`verification/esbmc_runner.py` é importado por `main.py`, por `maintenance/limits.py`, por `verify/agent_arm.py` e por sete scripts `v2_*`. O mesmo papel (chamar o ESBMC) também aparece espalhado em `verify/`. Consolidar em um único lugar é candidato a refatoração, mas mexe em caminhos usados pelas rodadas congeladas. Só depois de teste de regressão.

### 3.4 Scripts de uma rodada

`scripts/` tem 24 scripts `v2_*` e vários utilitários de uma análise específica. Três scripts não são citados em nenhum outro arquivo do repo:

- `scripts/funil.py`: mostra em que etapa cada bug para (detecção, veredito do ESBMC, confirmação). Criado em `0ad73d7`. É ferramenta de análise, não lixo.
- `scripts/patch_rule.py`: testa se uma falha some na versão corrigida do arquivo. Criado em `0ad73d7`.
- `scripts/sample_off_line.py`: amostra hipóteses que erram a linha do bug, para rotulação manual. Criado em `85bb975`.

Nenhum dos três deve ser apagado sem a autora dizer. Eles parecem ferramentas da análise de 08/11 e podem entrar na documentação de reprodução.

### 3.5 Raiz do repositório

- `analise-verificao-formal.md` (15 KB, versionado): revisão de laboratórios de verificação formal em outras universidades. Não é código. Candidato a `docs/` ou ao `archive/`.
- `kbs2026.pdf` (10 MB, versionado): PDF citado em `docs/projeto/notas_pyra_2026-11-09.md`. Arquivo grande na raiz. Candidato a `docs/referencias/` ou ao Git LFS se o repo for público.
- `UFAM-2026-Cordeiro.pdf` (1,7 MB, versionado): não encontrei referência no repo. Precisa de confirmação de para que serve.
- `Diretrizes para o Uso de LLMs na Escrita da Dissertação_vfinal.pdf`: referenciado pelo `CLAUDE.md` do projeto. Manter.
- `teste.py`: lixo ignorado pelo git. Pode apagar (decisão).

### 3.6 Documentação acumulada

`docs/projeto/` tem quatro arquivos `HANDOFF*` e dois `rascunho_issue_*`. Os rascunhos de issue do ESBMC já devem ter sido abertos (ver memória de issues). Os handoffs antigos são histórico. A regra de não reescrever docs existentes continua valendo: a proposta é mover para `docs/historico/`, não editar.

## 4. Riscos para a validade científica

- Remover código ou sondas muda o `catalog_digest` de `capabilities.py`. Isso muda a identidade de uma rodada. Antes de mexer em `verify/probes/`, conferir se o digest das tags congeladas ainda bate.
- Mudar nome ou caminho de `esbmc_runner.py` quebra os scripts de reprodução das tags `v2-congelado-*`.
- Mudar prompts (mesmo mover de `.py` para `.txt`) pode mudar o hash de prompt usado no cache e nas métricas. A mudança precisa ser provada como neutra com a mesma saída.
- Limpeza de lint pode alterar comportamento (por exemplo, remover um `import` que tem efeito colateral). Cada correção automática precisa de teste de regressão.
- Os resultados congelados vivem em `artifacts/` (fora do git). Qualquer limpeza que apague essa pasta destrói evidência. Não apagar sem backup e sem decisão da autora.

## 5. O que deve ser preservado

- Tags `harness-freeze-2026-10-15`, `v2`, `v2-congelado-2026-11*`.
- `dataset/` inteiro, `reports/json/`, `archive/`, `outputs/`, `artifacts/`, `logs/`.
- `docs/experimentos/` e `docs/projeto/PLANO_2026-10-19.md`.
- Os 51 arquivos em `verify/probes/` (são carregadas pela tupla `PROBES` em `capabilities.py`).
- Os três PDFs de referência, até a autora decidir o destino.

## 6. Candidatos a refatoração (ordem sugerida)

1. Fixar a configuração do ruff no repo (`pyproject.toml`) com exceção para `verify/probes/` e `scripts/`. Sem mudança de comportamento.
2. Corrigir `F401`, `F841`, `RUF100` e `I001` com testes verdes antes e depois.
3. Separar `src/main.py` em `cli.py` e um módulo por modo.
4. Unificar smells (`smells/` e `smell_policy.py`).
5. Unificar prompts sob um registro com hash.
6. Mover `esbmc_runner.py` para `verify/` e deixar um alias temporário.

Cada item é um lote separado, com teste de regressão, e só entra depois de a autora aprovar a ordem.

## 7. Arquivos candidatos à remoção

| Arquivo | Ação proposta | Motivo | Quem decide |
|---|---|---|---|
| `teste.py` | apagar | ignorado pelo git, 104 bytes, sem referência | autora |
| `analise-verificao-formal.md` | mover para `docs/historico/` | análise de outras universidades, não é código | autora |
| `kbs2026.pdf` | mover para `docs/referencias/` | PDF de referência, não deve ficar na raiz | autora |
| `UFAM-2026-Cordeiro.pdf` | confirmar destino | sem referência no repo | autora |
| `docs/projeto/HANDOFF*.md` antigos | mover para `docs/historico/` | histórico de sessões | autora |
| `docs/projeto/rascunho_issue_*.md` | mover para `docs/historico/` após conferir issues no GitHub | rascunhos já virados em issue | autora |
| `scripts/funil.py`, `patch_rule.py`, `sample_off_line.py` | manter, documentar | sem referência, mas são ferramentas de análise | autora |

Nada desta tabela foi apagado.

## 8. Arquitetura-alvo recomendada

```
src/research_pipeline/
  cli/            argumentos e roteamento (antes em main.py)
  modes/          hybrid, benchmark, scan (um arquivo por modo)
  detection/      LLM, prompts registrados com hash, esquemas de saída
  verification/   ESBMC: runner, harness, sondas, interpretação do veredito
  evaluation/     métricas e comparação (único avaliador)
  smells/         um único caminho de filtro e política
  scan/, maintenance/   sem mudança de responsabilidade
```

Interfaces como `ModelProvider` e `FormalVerifier` só entram quando houver um segundo caso de uso concreto. Hoje há quatro backends de LLM, então `ModelProvider` já se justifica. Abstrações que não têm segundo uso devem ficar de fora.

## 9. Plano de migração incremental

- Fase 1 (esta auditoria): concluída.
- Fase 2, estabilização: configuração do ruff, correções de lint com testes, decisão sobre arquivos da raiz e da documentação. Sem mudar código de detecção.
- Fase 3, arquitetura: separar `main.py`, unificar smells e prompts. Cada passo com a suíte verde e com uma rodada de comparação mostrando saída idêntica.
- Fase 4 em diante (detecção, verificação, experimentos, relatórios): só depois que a autora fechar o escopo do próximo experimento.

## 10. Decisões pendentes da autora

1. Apagar `teste.py`?
2. Mover os dois PDFs e o `.md` da raiz para `docs/`?
3. Qual é `UFAM-2026-Cordeiro.pdf` e onde ele deve ficar?
4. Os três scripts sem referência entram na documentação de reprodução?
5. Aprova a ordem da seção 6?
