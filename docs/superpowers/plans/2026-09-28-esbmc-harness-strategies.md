# Plano de Implementação: Categorias de Harness Orientadas ao ESBMC

> **Para execução por agentes:** usar a habilidade `superpowers:executing-plans` para implementar este plano tarefa por tarefa.

**Objetivo:** Fazer com que as quatro categorias orientadas ao ESBMC sejam a saída de classificação da LLM na V2, mantendo `single` e `two_stage` como condições experimentais comparáveis.

**Arquitetura:** A detecção preserva localização, expressão, explicação e uma das quatro categorias: `native_runtime`, `explicit_assertion`, `differential_assertion` ou `unsupported`. A síntese usa essa categoria para escolher o caminho do harness. Labels de oito categorias dos datasets antigos permanecem somente como compatibilidade para relatórios históricos e síntese de candidatos conhecidos. O texto da propriedade do ESBMC continua sendo evidência formal; localização é a métrica primária de detecção e a categoria é um dado secundário da pesquisa.

**Tecnologias:** Python 3, dataclasses, schemas de saída estruturada em JSON, pytest e a CLI Python existente do ESBMC.

**Especificação:** `docs/superpowers/specs/2026-09-28-esbmc-harness-strategies-design.md`

## Restrições gerais

- Manter `single` e `two_stage` disponíveis e comparáveis.
- Manter chamadas a modelos reais fora da suíte padrão de testes.
- Preservar a desserialização de checkpoints e relatórios antigos.
- Emitir somente as quatro categorias orientadas ao ESBMC nas novas detecções V2; aceitar as oito categorias antigas apenas ao carregar dados legados.
- Não usar a categoria como verdade da detecção; avaliar a localização separadamente.
- Rejeitar `unsupported` em vez de fabricar um harness.

## Pontos para revisão

- Um checkpoint antigo sem a categoria do harness deve ser carregado com um valor de migração explícito — teste da Tarefa 1.
- Uma classificação em dois estágios sem categoria deve ser rejeitada, e não roteada silenciosamente — teste da Tarefa 2.
- `native_runtime` e `differential_assertion` devem seguir caminhos diferentes de harness — teste da Tarefa 3.
- Os prompts de `single` e `two_stage` devem expor os mesmos quatro valores — testes da Tarefa 2.
- As métricas de detecção devem continuar corretas quando a categoria estiver errada — regressão existente do evaluator e teste da Tarefa 4.

## Tarefa 1: contrato do candidato e registro de categorias

**Arquivos:** `src/research_pipeline/llm/categories.py`, `src/research_pipeline/scan/pipeline.py`, `src/main.py`, `tests/test_scan_pipeline.py`, `tests/test_main_v2.py`

**Interfaces:**
- Adicionar `HARNESS_STRATEGIES` com exatamente `native_runtime`, `explicit_assertion`, `differential_assertion` e `unsupported`.
- Adicionar `harness_strategy: str` a `ScanCandidate`, serializado em `to_dict`/`from_dict`.
- Carregar candidatos antigos por meio de um adaptador determinístico baseado no campo de categoria legado.

- [ ] Escrever testes que falhem para serialização, carregamento legado e rejeição de categoria inválida.
- [ ] Executar os testes direcionados e confirmar a falha.
- [ ] Implementar o registro, o campo da dataclass, o adaptador de migração e a serialização dos checkpoints da CLI.
- [ ] Executar os testes direcionados e confirmar a aprovação.

## Tarefa 2: schemas de detecção e prompts

**Arquivos:** `src/research_pipeline/llm/schema.py`, `src/research_pipeline/llm/staged.py`, `src/research_pipeline/llm/prompts/system_prompt.txt`, `src/research_pipeline/scan/synth.py`, `src/research_pipeline/prompts/synth_prompt.txt`, `driver_prompt.txt`, `synth_prompt_loop.txt`, e os testes correspondentes.

**Interfaces:**
- A nova saída estruturada da V2 expõe exatamente as quatro categorias orientadas ao ESBMC.
- Labels antigos de oito categorias continuam aceitos somente pelos parsers de compatibilidade e carregadores de relatórios antigos.
- Os prompts de `single` e `two_stage` tratam a categoria como hipótese de estratégia, e o texto da propriedade do ESBMC como evidência autoritativa após a verificação.

- [ ] Adicionar testes que falhem para schema, parser, os quatro valores e rejeição de categoria ausente.
- [ ] Executar os testes direcionados e confirmar a falha.
- [ ] Implementar as mudanças de schema e prompt sem chamadas à API real.
- [ ] Executar os testes direcionados e confirmar a aprovação.

## Tarefa 3: roteamento do harness por categoria

**Arquivos:** `src/research_pipeline/scan/pipeline.py`, `src/research_pipeline/scan/compat.py`, `src/research_pipeline/scan/driver_check.py` se necessário, e os testes correspondentes.

**Interfaces:**
- `run_pipeline_scan` consome `ScanCandidate.harness_strategy`.
- `native_runtime` tenta a verificação nativa ou da função real.
- `explicit_assertion` usa a síntese escalar.
- `differential_assertion` exige o aterramento das duas saídas.
- `unsupported` retorna uma classificação explícita de não suportado.

- [ ] Adicionar testes de roteamento com chamadas do ESBMC e do sintetizador simuladas.
- [ ] Executar os testes de roteamento e confirmar a falha.
- [ ] Implementar o despacho mínimo por categoria e preservar retries e ablações existentes.
- [ ] Executar os testes de roteamento e confirmar a aprovação.

## Tarefa 4: avaliação e relatórios de migração

**Arquivos:** `src/research_pipeline/v2_evaluator.py`, `src/main.py`, `src/research_pipeline/report.py` se necessário, e os testes correspondentes.

**Interfaces:**
- As métricas de detecção continuam baseadas em localização.
- Os relatórios expõem separadamente a classificação da LLM, `esbmc_category` e o texto da propriedade.
- Relatórios antigos mantêm o campo de categoria original.

- [ ] Adicionar testes de separação entre classificação, evidência e resultado da detecção.
- [ ] Executar os testes direcionados e confirmar a falha.
- [ ] Implementar os campos dos relatórios e preservar os diagnósticos existentes de evidência de categoria.
- [ ] Executar os testes direcionados e confirmar a aprovação.

## Tarefa 5: verificação completa e preparação da comparação

- [ ] Executar `pytest -q` e registrar o resultado.
- [ ] Executar uma comparação sem rede dos schemas de `single` e `two_stage`.
- [ ] Confirmar que nenhum teste padrão faz chamada a modelo real.
- [ ] Revisar o diff e deixar intactas as alterações do usuário que não têm relação com esta funcionalidade.
