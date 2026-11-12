# Contexto de integração com frameworks no scan — plano de implementação

> **Para execução futura:** usar `superpowers:executing-plans`, tarefa por tarefa. Este documento não autoriza execução agora. Fernanda pediu somente o plano, para aplicar depois.

**Objetivo:** fornecer ao scan evidências sobre como uma função recebe suas entradas, incluindo configurações de integração e documentação, e registrar quais evidências chegaram à análise.

**Arquitetura:** acrescentar uma coleta de contexto exclusiva do scan, habilitada explicitamente. O primeiro suporte de integração será AWS SAM com eventos `Api`, motivado pelos dois candidatos revisados. A coleta será estática, com origem e limites registrados; os vereditos existentes continuarão separados da avaliação do contexto do projeto.

**Tecnologias:** Python 3.11+, análise AST existente, leitura de JSON e análise de nós YAML sem executar construtores. Para YAML, prever dependência opcional `PyYAML>=6.0` no extra `scan-context`; não instalar nada durante a preparação deste plano.

**Base:** [nota com a evidência e as possíveis melhorias](../../projeto/nota_contexto_framework_scan_amazon_2026-11-11.md). As decisões de desenho abaixo são propostas técnicas da IA para avaliação de Fernanda; não são decisões científicas atribuídas a ela.

## Restrições gerais

- Agora: somente este plano. Não alterar `src/`, `tests/`, dependências, configuração, prompts, caches, caderno de reparos, executável do ESBMC ou processos em andamento.
- Não interromper, retomar, reconfigurar ou repetir o E2E dos 47 da disciplina. Não usar seu diretório de saída para testar esta melhoria.
- Implementar e testar somente depois que o E2E terminar, em checkout isolado, com ambiente, caches e saídas separados. Não instalar dependências na `.venv` usada pelo E2E.
- Não fazer commit sem pedido explícito. Não abrir issue, PR ou publicar comentários.
- Não executar código dos repositórios analisados, instalar suas dependências ou executar seus testes. Os fixtures serão dados estáticos.
- Não usar API paga. Nenhuma chamada real à LLM nos testes padrão; uma medição posterior só pode usar o backend e a autenticação autorizados na ocasião.
- Começar com `--scan-repository-context off|evidence`, padrão `off`, exclusivo de `scan`. Com a opção desligada, preservar os prompts e fingerprints anteriores.
- Não aplicar esta melhoria automaticamente a `hybrid`, `benchmark` ou à medição dos 47. Alterar esses modos requer escopo e avaliação próprios.
- Não mudar o significado de `CONFIRMED`, `final_verdict`, o replay ou as regras de compatibilidade do ESBMC neste trabalho.
- Exemplos de eventos não são contratos universais. Não transformar a presença de uma chave num exemplo em uma precondição obrigatória.
- Não descartar hipóteses ou acrescentar restrições ao harness automaticamente a partir de documentação. O objetivo inicial é fornecer e registrar evidência, não decidir alcançabilidade em geral.

## Evidência que motiva o plano

Sample: `aws-samples/sam-python-crud-sample`, commit `f91982d24775dce644283b9ae33deb78e49c49fc`.

- `a734f0e75358`: `update_activity/app.py:9`, `message['httpMethod']`.
- `d01563c5cc67`: `delete_activity/app.py:9`, mesma expressão.
- Os contraexemplos precisam de `httpMethod` ausente. As rotas declaradas no SAM usam o formato de evento do API Gateway, que fornece esse campo.
- Ambos registram zero chamadores Python e especificações sem restrições de entrada. A ligação declarada em YAML não entrou no grafo.
- O coletor atual de documentação do agente retornou zero trechos para ambos. O motor `engine` não recebeu documentação do sample. O `error+kb` consulta o ESBMC, não o contrato do serviço usado pelo alvo.

Esses casos mostram uma lacuna de contexto. Não medem precisão nem demonstram ganho de uma implementação ainda inexistente. A [conferência original](../../../artifacts/scan_amazon_2026-11-11/sam-python-crud-sample/confirmed_context_review.json) permanece separada dos vereditos brutos.

## Abordagens consideradas

1. **Aumentar a profundidade do grafo ou usar PageRank:** pode ajudar quando há chamadores Python; não recupera, por si só, uma ligação declarada no YAML. PageRank altera a ordenação das funções.
2. **Usar apenas o modo agente existente:** já consulta parte da documentação, mas não resolveu a recuperação dos trechos destes handlers e não coleta os arquivos SAM/eventos. Não basta trocar a flag.
3. **Coletar evidências de integração e fornecê-las por opção do scan:** abordagem proposta. Preserva a rodada padrão e permite inspecionar o contexto antes de gastar chamadas. Não exige resolver todos os frameworks.

Ficam fora: busca automática na internet, suporte geral a todos os frameworks, execução do alvo, inferência automática de contratos e reclassificação dos vereditos antigos.

## Pontos de revisão

1. Dois handlers com o mesmo nome em arquivos diferentes: associar pelo caminho do módulo e pela função, não apenas por `lambda_handler`.
2. Configuração dinâmica, integração customizada ou múltiplas entradas: registrar ambiguidade; não presumir contrato único.
3. Exemplo JSON ou README desatualizado: manter a categoria e a origem da evidência, sem promover exemplos a garantias.
4. Arquivos grandes, links para fora do clone, YAML com ciclos ou texto com instruções: limitar leitura e tratar tudo como dado não confiável.
5. Mudança de contexto durante retomada: impedir mistura de detecção/verificação feitas com evidências diferentes. Desligado, preservar compatibilidade com os checkpoints anteriores.

## Tarefa 1 — coletar e associar evidências sem executar o alvo

**Arquivos:** criar `src/research_pipeline/scan/repository_context.py` e `tests/test_scan_repository_context.py`; declarar o extra opcional `scan-context` em `pyproject.toml` somente na implementação futura.

**Interfaces propostas:**

- `Evidence(path: str, start_line: int, end_line: int, kind: str, text: str)`; `kind` distingue `integration_config`, `documentation` e `example`.
- `FunctionContext(key: str, status: str, evidence: tuple[Evidence, ...], diagnostics: tuple[str, ...])`; estados: `matched`, `unresolved` e `not_found`.
- `RepositoryContextSnapshot`: contexto por chave do grafo, inventário das fontes lidas e `digest` determinístico.
- `collect_repository_context(root: Path, graph: CallGraph) -> RepositoryContextSnapshot`.
- `render_repository_context(context: FunctionContext) -> str`.

- [ ] Criar fixtures mínimos de `template.yaml`, handlers, README e eventos JSON, sem imports ou execução dos arquivos alvo. Copiar apenas os trechos necessários do sample, atribuindo URL e commit.
- [ ] Escrever testes que falhem para associação dos dois handlers homônimos aos seus próprios `CodeUri`/`Handler`/eventos, preservando método, rota, arquivo e linha.
- [ ] Cobrir associação sem menção literal a `lambda_handler` no README: primeiro localizar a função pela configuração, depois recuperar trechos relacionados por caminho ou recurso.
- [ ] Implementar o suporte inicial a SAM com `CodeUri` e `Handler` literais, evento `Api` e rota/método literais. Não afirmar formato proxy conhecido quando houver integração customizada ou resolução pendente.
- [ ] Ler YAML como nós, sem construir objetos de tags. Não resolver `!Ref`, `!Sub`, macros ou caminhos remotos; registrar o que não foi resolvido. JSON é somente dado de exemplo.
- [ ] Limitar a coleta a README, `doc/`, `docs/`, templates SAM na raiz e `events/*.json`: até 2.000 arquivos, 128.000 bytes por arquivo, 40 níveis e 10.000 nós YAML. Ignorar links simbólicos e caminhos fora da raiz, com motivo registrado. Detectar ciclos de aliases.
- [ ] Limitar a quatro trechos e 4.800 caracteres por função; registrar truncamento. O hash inclui conteúdo e inventário das fontes consultadas, inclusive configuração de integração não resolvida.
- [ ] Cobrir caminhos escapando da raiz, arquivos ilegíveis/grandes, YAML inválido, aliases cíclicos, handlers dinâmicos, duas entradas para a mesma função e instruções dentro de comentários/documentação. Nenhum desses casos pode gerar contrato inferido silenciosamente.
- [ ] Se a opção for pedida e faltar o parser YAML, produzir erro de configuração claro antes de chamar a LLM. Não fazer instalação automática.
- [ ] Executar no ambiente isolado: `.venv/bin/python -m pytest -q tests/test_scan_repository_context.py`. Esperado: todos os testes novos passam; zero chamadas reais à LLM.

## Tarefa 2 — ligar o contexto à detecção e à especificação por opção do scan

**Arquivos:** `src/research_pipeline/cli_args.py`, `src/main.py` somente no despacho/validação do scan, `src/research_pipeline/scan/pipeline.py`, `src/research_pipeline/verify/loop.py`, `src/research_pipeline/verify/agent_scan.py`; novos testes em `tests/test_scan_repository_context.py` e testes existentes de scan/agente.

**Interfaces propostas:**

- `ScanPlan.repository_context`: snapshot opcional, padrão `None`.
- Provedor de contexto com `__call__(hypothesis: BugHypothesis) -> str` e `config_label` contendo versão e hash do snapshot.
- `run_verify(..., repository_context=None)` resolve o trecho por hipótese. `verify_hypothesis(..., repository_context: str = "")` acrescenta o trecho ao contexto da especificação somente quando não vazio. Não importar o coletor SAM no motor compartilhado.
- `agent_verifier(..., repository_context=None)` usa a mesma evidência atribuída quando habilitada; com `None`, mantém o comportamento existente.

- [ ] Escrever teste com analisador e especificador falsos, capturando o que receberam: em `evidence`, ambos recebem a configuração do handler correto, com origem e categoria; em `off`, recebem exatamente os prompts antigos.
- [ ] Acrescentar `--scan-repository-context off|evidence`. Rejeitar valor `evidence` em `hybrid` e `benchmark` antes de qualquer chamada ou escrita de checkpoint; o padrão `off` não altera esses modos.
- [ ] Na detecção, anexar o bloco ao contexto da unidade somente dentro do caminho do scan. Identificá-lo como evidência externa ao grafo, sem inventar chamadores Python.
- [ ] Na especificação, passar o bloco por hipótese e preservá-lo nos reparos que voltam a gerar especificações. Não acrescentar `assume`, tipos ou chaves obrigatórias por código a partir dos exemplos/documentos.
- [ ] Delimitar o bloco como `UNTRUSTED_REPOSITORY_CONTEXT`; informar que o conteúdo é dado para conferir e não instrução. Preservar caminhos e linhas dos trechos.
- [ ] Cobrir o modo agente com a opção habilitada e evitar duplicação dos mesmos trechos. Não tornar o agente obrigatório para usar o contexto.
- [ ] Testar que entrada ambígua continua explicitamente ambígua, que exemplos não se tornam garantias e que um candidato não é removido automaticamente por discordar de um documento.
- [ ] Rodar os testes focados de contexto, scan, especificação e agente, com LLM falsa. Conferir também a passagem do contexto pelas novas tentativas do motor.

## Tarefa 3 — tornar o contexto auditável e proteger a retomada

**Arquivos:** `src/research_pipeline/scan/pipeline.py`, `src/research_pipeline/verify/agent_scan.py`, `tests/test_scan_pipeline.py`, `tests/test_verify_agent_scan.py` e `docs/projeto/scan_codex.md`.

**Saída proposta:** `scan_repository_context.json`, apenas quando habilitado, contendo versão, hash, inventário de fontes, contextos por função, diagnósticos e truncamentos. O `scan_report.json` ganha uma seção opcional com referências a esse arquivo e indicação das etapas às quais o contexto foi enviado.

- [ ] Escrever testes que falhem para persistência de origem, contexto vazio, ambiguidade e truncamento. Distinguir `sent_to_detection`/`sent_to_specification` de qualquer afirmação de que a LLM considerou a evidência corretamente.
- [ ] Registrar o contexto coletado já na simulação, sem `--yes`, para permitir conferência antes de gastar chamadas.
- [ ] Incluir versão, modo e hash do contexto nos fingerprints da detecção e da verificação habilitadas. Não confiar na representação textual de um `dict` ou endereço de objeto como identidade da configuração.
- [ ] Testar mudança em template, README e evento selecionado: a retomada não pode reutilizar silenciosamente resultados de contexto antigo. Mudança do conjunto de arquivos consultados também altera o hash.
- [ ] Com a opção desligada, omitir os novos componentes do fingerprint: checkpoints e prompts antigos devem continuar compatíveis. Testar esse comportamento explicitamente.
- [ ] Preservar `verdict`, contagens e resultados brutos. A seção de contexto não pode promover `CONFIRMED` a “bug real”, substituir avaliação humana ou apagar hipóteses.
- [ ] Documentar o comando optativo, o extra de dependência, os limites de recuperação, a diferença entre grafo/documentação/contrato e as limitações do suporte SAM inicial.
- [ ] Rodar os testes de relatório e retomada; verificar que nenhum teste toca as saídas do E2E dos 47 ou caches compartilhados.

## Tarefa 4 — conferir compatibilidade e preparar uma medição pequena

**Arquivos:** testes acima e uma nova pasta de resultados, escolhida na execução futura. Não reutilizar `artifacts/scan_amazon_2026-11-11/` ou o diretório dos 47.

- [ ] Confirmar que o E2E dos 47 terminou antes de preparar o ambiente isolado de implementação. Registrar o commit usado por ele e preservar seus resultados.
- [ ] No checkout isolado, rodar antes/depois os testes que capturam os prompts de `hybrid`, `benchmark` e scan sem a nova opção. Esperado: igualdade de conteúdo e nenhuma mudança de comportamento padrão atribuível a esta melhoria.
- [ ] Executar os testes focados e depois a suíte padrão do projeto, sem habilitar `live_llm`: `.venv/bin/python -m pytest -q`. Relatar falhas preexistentes nominalmente; não corrigir problemas alheios neste escopo. Não rodar essa suíte agora ou no ambiente do E2E ativo.
- [ ] Fazer a primeira conferência do coletor com fixtures estáticos dos dois handlers. Esperado: a configuração correspondente chega a ambos os prompts; os limites e a origem ficam visíveis. Incluir controles de integração diferente/ausente para impedir associação indevida ao API Gateway.
- [ ] Preparar, sem executar automaticamente, uma comparação pequena com o mesmo commit do sample, modelo, seleção e limites: contexto desligado e habilitado, em saídas diferentes. Usar `--no-auto-lessons` e `--heal none` em ambos os braços para separar esta melhoria do custo dos reparos. Essas configurações diferem do piloto histórico e devem ser declaradas.
- [ ] Essa comparação exige autorização vigente para chamadas reais e conferência de cota. Não repetir os 47 como consequência automática deste plano.
- [ ] Registrar separadamente: evidência recuperada/enviada, hipóteses, vereditos, restrições produzidas pela LLM, chamadas, tokens, erros e avaliação de compatibilidade dos contraexemplos com o contrato. Não usar a retirada de um candidato como prova de melhoria.
- [ ] Não alterar a conclusão histórica dos dois candidatos nem chamar este conjunto de teste independente: o desenho foi motivado por eles. Fernanda decide posteriormente a medição de qualidade e se a melhoria deve alcançar outros modos.

## Critérios de entrega futura

- Contexto SAM recuperado com a origem correta para os dois handlers, incluindo o caso em que o nome da função não aparece na documentação.
- Contexto efetivamente enviado à detecção e à especificação, com trilha de auditoria e sem execução do alvo.
- Nenhuma restrição automática baseada somente em exemplos; configurações ambíguas permanecem visíveis.
- Modo padrão, `hybrid`, `benchmark`, critérios de veredito e resultados antigos preservados.
- Retomada protegida contra troca de evidência; custo medido separadamente, sem prometer ganho de precisão antecipadamente.
- Implementação, testes, medição e commits continuam pendentes. Esta entrega é somente o plano.

## Uso de IA e referências

Codex inspecionou o código do pipeline, a nota e os artefatos e redigiu esta proposta técnica. Não houve implementação, instalação, teste ou nova rodada de LLM/ESBMC como parte da elaboração do plano. A revisão e as decisões científicas permanecem com Fernanda.

- [Nota e fontes verificadas do caso](../../projeto/nota_contexto_framework_scan_amazon_2026-11-11.md).
- [AWS: formato de entrada da integração proxy](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html#api-gateway-simple-proxy-for-lambda-input-format).
- [AWS SAM: integração proxy padrão](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-using-start-api.html).
