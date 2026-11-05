# Continuidade do pipeline — 04/11/2026

Este arquivo registra o estado observado nesta sessão para outra IA continuar. É um registro técnico feito por IA, ainda sem revisão de Fernanda. Resultados relatados por agentes estão identificados como tal e precisam ser conferidos antes de uso científico.

## Atualização da sessão Codex (depois da passagem original)

- **Lotes E, B, A e D integrados parcialmente no worktree principal, sem commit.** Os patches vieram dos worktrees listados abaixo. Conflitos foram conciliados em `main.py`, `scan/pipeline.py`, `verify/agent_arm.py`, `verify/loop.py`, `verify/replay.py` e clientes Claude. Arquivos `.rej` gerados durante a aplicação foram removidos após conciliação. Os worktrees originais foram preservados.
- Arquivos novos trazidos: `hypothesis_cap.py`, `pricing.py`, `v2_consult.py`, testes respectivos, `.gitattributes`, relatórios B/E. O item 24 do lote A foi editado em `.claude/skills/llm-esbmc-pipeline/skill.md`: os modos foram conferidos com `src/main.py --help`; ainda falta testar o uso da skill por outro agente. O lote C **ainda não foi feito**.
- Testes focados: E 50/50, B 73/73, A 187/187. Para D, 120/121 passaram no sandbox; a única falha foi escrita bloqueada em `~/.cache`. O teste que falhou foi repetido com permissão e passou 1/1. A bateria combinada teve 264/265, com a mesma falha ambiental em outro caminho de cache. **Suíte completa iniciada com permissão, sessão de comando 49034; recolher resultado antes de afirmar aprovação.**
- O checkpoint `artifacts/pgene601/codex-2026-11-03/v2_checkpoint.json` foi conferido e ainda tem `status: running`. A mudança do fingerprint do lote E impede sua retomada com o código novo; preservar o artefato e decidir como concluir a rodada com o código anterior antes de usá-la como evidência. Não rodar LLM paga sem autorização.
- #9843: subagente conferiu a reprodução do erro Bitwuzla no binário congelado e `VERIFICATION SUCCESSFUL` no build corrigido. Passaram 15/15 regressões novas, 339/339 regressões Python relacionadas, checagem CPython geral, clang-format e `git diff --check`. O portão de cobertura Mode B segue **sem medição** porque o build usa GCC e `ENABLE_COVERAGE=OFF`. Não houve commit/PR.
- Consulta direta `gh issue view 9843 --repo esbmc/esbmc --json number,state,title,url,updatedAt` confirmou a issue #9843 **OPEN**. Fernanda pediu avaliar se a correção está pronta para subir; o subagente foi acionado novamente para cobertura Mode B, revisão final e regressões de índice negativo/fatia. Aguardar esse resultado antes de responder que está pronta.

## Decisões de Fernanda e limites

- Fazer **todas as melhorias do plano antes dos experimentos**, nesta ordem: **8a, 8b, 8c, grafo consultável, extensão e Codex**. A varredura adicional de 04/11 encontrou 25 melhorias técnicas, listadas em `docs/projeto/PLANO_2026-10-19.md`, seção “Melhorias encontradas em 04/11”; elas foram distribuídas em lotes A a E e ainda precisam ser integradas.
- Preservar como referência a tag `v2-congelado-2026-11b` e o ESBMC `d520a903ae`. Melhorias posteriores são variantes a comparar com essa referência; fazer um novo congelamento somente depois de concluí-las.
- O self-healing continua corrigindo o harness; `--heal error+kb` é o padrão decidido para `--mode hybrid` e scan. A nota anterior de 03/11 foi ajustada em `docs/experimentos/README.md`.
- Não fazer commit sem pedido explícito. Não iniciar chamadas pagas de LLM/API sem autorização. Não mexer em `~/esbmc-master`, pois sustenta o binário congelado e a referência do pipeline. Não abrir PR da issue #9843 sem mostrar antes os resultados a Fernanda.
- A autoria, a análise dos resultados e as decisões científicas são de Fernanda. Ler `docs/escrita/revisar-escrita-academica/SKILL.md` e sua referência integral antes de escrever material acadêmico.

## Estado observado do repositório principal

- Diretório: `/home/fernanda/mestrado/llm_esbmc`; branch `feat/harness-de-agente`; `git worktree list` mostrou HEAD `dc64068`. A mudança de HEAD em relação ao início da conversa deve ser investigada antes de integrar alterações.
- Alterações locais: `docs/projeto/PLANO_2026-10-19.md` (tabela dos 25 itens) e `docs/experimentos/README.md` (decisão sobre self-healing). Há dois PDFs não rastreados na raiz; preservar, sem remover nem adicionar automaticamente.
- A pasta `docs/experimentos/melhorias_2026-11-04/` ainda não existe no worktree principal. Os relatórios B e E estão **nos worktrees dos agentes**, não integrados.
- Nenhuma suíte integrada foi executada nesta sessão e os cinco lotes não foram revisados em conjunto. Não anunciar as 25 melhorias como concluídas.

## Worktrees dos lotes (todas as alterações sem commit)

Todos ficam em `/home/fernanda/mestrado/llm_esbmc/.claude/worktrees/` e aparecem em `git worktree list`. Preservar cada pasta. Antes de aplicar patches, inspecionar os diffs e resolver arquivos compartilhados, especialmente `src/main.py`, `scan/pipeline.py`, `verify/replay.py` e `verify/agent_arm.py`.

| Lote | Worktree | Estado observado |
|---|---|---|
| A — infraestrutura, itens 13, 23–25 | `agent-a692d6cd972b77b28` | Muitas alterações de código/testes, `.gitattributes` e `pricing.py` novos; sem relatório encontrado. Inspecionar e testar. |
| B — scan, itens 6, 16–22 | `agent-a9f9feb399d7cd08e` | Código/testes e relatório `docs/experimentos/melhorias_2026-11-04/lote_B.md`. O relatório ainda contém `SUITE_PLACEHOLDER` na verificação; não considerar concluído. |
| C — compatibilidade/stubs, itens 4, 5, 10–12 | `agent-a6acc8d0dec8b2ac0` | Worktree sem alterações observadas. O agente foi interrompido por limite de API da sessão anterior; precisa ser retomado. |
| D — verify/agente, itens 7–9, 14–15 | `agent-a0a2e54902f901721` | Muitas alterações de código/testes e `scripts/v2_consult.py` novo; sem relatório encontrado. Inspecionar e testar. |
| E — detecção, itens 1–3 | `agent-aa614d42f3ee7d18d` | Código/testes e relatório `docs/experimentos/melhorias_2026-11-04/lote_E.md`. Relatório descreve medição offline e ressalvas; conferir antes de integrar. |

O relatório B informa que, apesar de sondas no ESBMC congelado, **funções `async` não voltaram à seleção**: o harness atual não as chama com `await`. O relatório E alerta que a correção do fingerprint torna checkpoints antigos com variantes incompatíveis para retomada, inclusive `artifacts/pgene601/codex-2026-11-03`, que ainda estava `running` quando o agente verificou. Conferir o estado atual dessa rodada antes de integrar E. Estas são observações dos agentes, não validação independente desta sessão.

## Issue ESBMC #9843 (`Optional[tuple]`)

- A pedido de Fernanda, os worktrees das issues #9841 e #9842 foram removidos pela sessão anterior. As branches vazias correspondentes podem ainda existir; não apagar sem necessidade.
- Worktree da #9843: `/home/fernanda/esbmc-wt/issue-9843`, branch `fix/issue-9843`, base observada `78e8e3a8f9`. Três arquivos C++ modificados (`converter_stmt.cpp`, `tuple_handler.cpp`, `.h`) e 15 diretórios de regressão não rastreados, total de 18 entradas no `git status --short`.
- Log do build: `/home/fernanda/esbmc-wt/build-9843.log`; terminou em `[604/607] Linking CXX executable src/esbmc/esbmc`, e a sessão anterior informou saída 0. **Não há nesta passagem resultado confirmado da regressão, revisão de código ou cobertura.** Recolher esses resultados no próprio worktree antes de considerar o PR.
- Não atualizar `~/esbmc-master`; usar apenas o worktree da issue para correção/teste. A sessão anterior informou que as issues #9841 e #9842 foram corrigidas pelo professor, mas essa informação não foi reverificada aqui no GitHub.

## Próximos passos concretos

1. Conferir `git status` e logs de cada worktree. Preservar alterações não commitadas. Ver se os agentes A e D deixaram resultados adicionais e terminar a verificação dos lotes B/E. Retomar C, interrompido.
2. Integrar os cinco lotes no worktree principal com revisão de conflitos e comportamento. Rodar testes focados de cada mudança e, depois da integração, a suíte inteira e análise estática disponível. Escrever relatórios finais em `docs/experimentos/melhorias_2026-11-04/`. Não afirmar resultados que não foram executados.
3. Continuar a melhoria 8a (ablação da pós-condição) e depois 8b, 8c, grafo, extensão e Codex, nessa ordem. O conteúdo exato está no plano. Não rodar experimentos pagos até terminar as melhorias e obter a autorização exigida.
4. Em paralelo à evolução do pipeline, concluir a verificação da #9843 no seu worktree, apresentar os resultados e só então tratar de PR com Fernanda.
5. Antes de qualquer novo congelamento, verificar que binário, código, tag, configuração e relatórios apontam para versões coerentes. Registrar comandos, saídas e limitações sem interpretar os achados por Fernanda.

## Consulta rápida

- Plano: `docs/projeto/PLANO_2026-10-19.md`.
- Histórico de experimentos: `docs/experimentos/README.md`.
- Desenho anterior do harness: `docs/projeto/HANDOFF_harness_de_agente.md` (histórico antigo; várias informações de estado nele estão desatualizadas).
- Reprodutor da #9843: `docs/projeto/possiveis_problemas/69_tupla_opcional_comparada.py` e os diretórios `regression/python/github_9843*` do worktree ESBMC.
