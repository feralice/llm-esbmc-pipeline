# Manutenção e verificações locais

O plano implementado parte da [auditoria de qualidade](../audits/code_quality_review.md),
medida no snapshot `40f72ae`. As correções foram aplicadas sobre `ade6f14`, preservando
o trabalho de telemetria concluído nessa branch. O plano detalhado e suas condições
ficam em [2026-11-11-code-quality-implementation.md](../superpowers/plans/2026-11-11-code-quality-implementation.md).

## Verificação

Use Python 3.11+ e `requirements-dev.txt`. `make check` executa Ruff, Mypy e pytest.
O lint não trata datasets, histórico ou sondas ESBMC como código do produto.
O Mypy cobre nove módulos declarados; sua aprovação não significa que a dívida
de tipos do restante do projeto desapareceu. Não houve instalação em ambiente
novo nesta execução; os comandos foram verificados com as ferramentas já instaladas.
O gate Ruff seleciona `F`, `E9`, `B006` e `B008`: erros estáticos e defaults mutáveis.
Ordenação de imports, modernizações e outros avisos de estilo da auditoria não
foram transformados em correções automáticas do corpus ou em promessa de zero avisos.

Os testes padrão excluem `live_llm`. Fixtures também bloqueiam conexões reais e
CLIs de LLM, redirecionam caches das ferramentas e copiam o caderno de reparos.
Alguns testes usam ESBMC local e são pulados quando o binário necessário não existe.
Esse resultado depende da instalação local, que precisa ser registrada.

## Responsabilidades após as extrações

| Arquivo | Responsabilidade |
|---|---|
| `src/main.py` | Composição e orquestração dos modos; conserva os pontos de entrada anteriores |
| `cli_args.py` / `cli_config.py` | Argumentos, validação e resolução pura dos modelos |
| `storage.py` | Escrita atômica de JSON com o formato já usado pelos checkpoints |
| `verify/attempts.py` | Preparação e validação da especificação de uma tentativa |
| `verify/agent_validation.py` | Preparação do harness e controles puros de propriedades e stubs |
| `verify/source_replay.py` | Troca da função pelo original e utilitários de fonte, sem depender do agente |
| `verify/procs.py` | Ciclo de vida de comandos locais, incluindo descendentes e saída parcial |
| `verify/confinement.py` | Fronteira de escrita e syscalls dos workers, antes de carregar código externo |

Salvo `src/main.py`, os caminhos da tabela usam o prefixo `src/research_pipeline/`.
Detecção e síntese continuam com contratos separados; `verify/` faz a política de
verificação e `verification/esbmc_runner.py` adapta uma execução. `smell_policy.py`
e `smells/filter.py` conservam suas finalidades diferentes.

## Mudanças observáveis de operação

- JSON malformado, envelope vazio ou formato de findings incorreto é erro de
  detecção. Uma resposta válida `{"findings": []}` continua sendo sucesso sem
  candidatos. A retomada já existente tenta novamente os erros persistidos.
- `run_final.sh` termina com falha se qualquer etapa falhar; não anuncia `done`.
- O launcher usa o interpretador do projeto quando disponível, ou o Python ativo,
  e recusa um executável local inválido antes de anunciar agendamento.
- O agente API recebe flags e limites completos. O tempo restante limita as
  operações do cliente real, inclusive retries e leitura da resposta. O prazo
  absoluto usa a thread principal POSIX e não substitui um timer já ativo;
  quando isso não é possível, a chamada falha antes de acessar o provedor.
  Clientes falsos antigos de dois
  argumentos mantêm compatibilidade e têm o prazo conferido após a resposta.
- Ao trocar o backend de síntese, o modelo de detecção não é reutilizado em outro
  namespace; `--synth-model` explícito tem precedência. Defaults de CLI vazios
  permanecem vazios. Configurações diferentes não devem ser misturadas na retomada.
- Replay, importação diferencial e pytest gerado aplicam contenção antes de
  executar código externo. Pytest gerado roda numa cópia descartável, sem acesso
  de escrita aos artefatos originais. Hosts sem suporte devolvem indisponibilidade.

A contenção combina Landlock e seccomp, incluindo bloqueio de sinais a outros
processos e alteração de seus limites de recursos. A [documentação do kernel](https://docs.kernel.org/userspace-api/landlock.html)
explica os direitos de arquivo, a necessidade de consultar a ABI e as operações
não cobertas por Landlock; a política complementar bloqueia alterações de
metadados e criação de processos. Leitura não foi confinada para preservar
imports do módulo original. Não apresentar essa fronteira como isolamento de VM.

Os prompts, programas de sonda, critérios científicos de confirmação, datasets,
ground truth, resultados e tags não foram revisados ou reclassificados. Mudanças
de disponibilidade, status de erro e defaults precisam constar de novas rodadas;
nenhum resultado histórico foi reinterpretado automaticamente.

## Índice conservador de organização

| Área/item | Tratamento nesta implementação |
|---|---|
| `dataset/`, `reports/`, `logs/`, `archive/`, `docs/experimentos/` | Preservados como entradas, evidências ou histórico |
| `artifacts/`, `outputs/`, `output/` | Preservados; saídas locais não são material descartável por estarem ignoradas |
| `scripts/funil.py`, `patch_rule.py`, `sample_off_line.py` | Mantidos: análise por bug, controle buggy/fixed e amostragem para rotulação |
| `funil.py` versus `v2_funnel.py` | Sem fusão: critérios de rotulação/localização não são equivalentes |
| `HANDOFF*.md` e rascunhos de issues | Mantidos; conferir vigência, links e publicação antes de mover |
| PDFs e `analise-verificao-formal.md` da raiz | Mantidos; finalidade/localização não autoriza exclusão |
| Scratch, caches e bytecode locais | Não removidos; confirmar autoria e valor antes de uma limpeza futura |
| `.github/` ignorado | Mantido; gate local reproduzível em Makefile, sem presumir configuração de CI externa |

Esse índice atende à organização incremental sem transformar itens condicionais
da auditoria em autorização de remoção ou movimentação de registros científicos.

## Registro de execução

As mudanças permanecem locais na aba Changes para revisão. O registro temporário
de testes e decisões fica em `.superpowers/sdd/2026-11-11-code-quality-implementation/`.
Verificação final: `1.837 passed, 1 skipped` em 432,58 s; Ruff passou nas regras
declaradas e Mypy passou nos nove módulos configurados. O teste pulado é o mesmo
caso localmente condicionado documentado pela suíte; não foram feitas chamadas
pagas a LLM.

Codex foi utilizado para implementar correções, extrair responsabilidades,
escrever e executar testes locais e preparar esta documentação técnica. Isso
inclui análise e programação, não apenas correção gramatical. Não é uma revisão
humana nem uma conclusão sobre a validade dos resultados científicos.
