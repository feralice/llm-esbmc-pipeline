# Design: trazer as ferramentas ESBMC do Claude para o Codex

## Intenção

Disponibilizar no Codex as instruções e os fluxos ESBMC que hoje estão espalhados pela extensão do projeto e pelo perfil Claude da Fernanda. A extensão atual do Claude deve continuar utilizável. O pacote deve servir tanto à pesquisa `llm_esbmc` quanto a tarefas no repositório upstream do ESBMC.

## Escopo

Incluir no pacote:

- Os fluxos locais `/verificar-repo` e `/self-healing`, hoje em `extension/commands/`.
- A skill de arquitetura e uso do pipeline, em `.claude/skills/llm-esbmc-pipeline/`.
- O guia local de ESBMC-Python, em `~/.claude/skills/esbmc-python-guide/`.
- O plugin `esbmc-plugin` versão 1.1.0 já instalado no perfil Claude: skill de verificação, comandos `verify` e `audit`, exemplos, referências e scripts. Preservar a atribuição ao autor e ao repositório de origem.
- Os agentes `esbmc-verifier`, `esbmc-coverage-pr` e `creduce-reducer` do perfil Claude.

Não incluir agentes ou plugins genéricos do perfil, credenciais, histórico de sessões nem configurações pessoais sem relação com ESBMC. As regras acadêmicas existentes em `AGENTS.md` continuam valendo.

## Abordagens

1. **Pacote compatível com Claude e Codex (escolhida).** Manter os comandos Claude e adicionar manifests e skills que o Codex reconheça no mesmo pacote. Há uma fonte principal para os fluxos e a extensão existente continua disponível.
2. **Pacote exclusivo do Codex.** Criar uma cópia independente do conteúdo. É mais simples no Codex, mas as instruções e correções passam a divergir entre dois pacotes.

## Desenho

- Usar `extension/` como raiz do pacote compartilhado, mantendo `.claude-plugin/plugin.json` e `commands/` para o Claude Code e adicionando o manifesto compatível com Codex e as skills portáveis.
- Converter cada comando Claude em uma skill acionável no Codex: `verify`, `audit`, `verificar-repo` e `self-healing`. No Claude, os comandos slash continuam disponíveis; no Codex, os fluxos são acionados pelas skills.
- Empacotar as instruções dos três agentes como skills de papel distintas. O formato de plugin documentado pelo Codex fornece skills e ferramentas MCP, mas não importa automaticamente os arquivos de agente do Claude. Portanto, preservar cada procedimento e seu escopo numa skill nomeada; delegação a subagentes Codex continua dependendo do contexto e das ferramentas disponíveis na sessão.
- Levar exemplos, scripts e referências junto da skill `esbmc-verification`, mantendo os caminhos relativos válidos e a atribuição upstream.
- Incluir o guia `esbmc-python-guide` como referência específica de Python. Quando ele divergir da orientação geral do plugin upstream, deixar explícito que os gotchas verificados localmente para Python orientam a análise deste projeto.
- Manter `AGENTS.md` como instrução do repositório Codex e `CLAUDE.md` como instrução do Claude. Só alterar esses arquivos se a instalação do pacote exigir um apontamento curto para a skill correspondente.
- Instalar o pacote no Codex pelo marketplace local da cópia do projeto, para que as skills fiquem disponíveis em novas conversas. A instalação altera a configuração local do Codex fora do repositório e será executada após a aprovação do desenho.

## Limites e cuidados

- Os comandos Codex são skills, não comandos slash idênticos aos do Claude.
- Os arquivos de agente Claude não se tornam agentes Codex independentes só por serem copiados. A migração preserva seu conteúdo como workflows nomeados.
- A migração não executa benchmarks nem chamadas a modelos; o custo e os resultados dos experimentos continuam sujeitos às instruções de cada workflow e à confirmação da Fernanda.
- Não fazer commits.

## Resultado esperado

Um pacote ESBMC instalado no Codex e ainda carregável pelo Claude, com sete skills de conhecimento/fluxo (`llm-esbmc-pipeline`, `esbmc-python-guide`, `esbmc-verification`, `verify`, `audit`, `verificar-repo`, `self-healing`) e três skills de papel (`esbmc-verifier`, `esbmc-coverage-pr`, `creduce-reducer`), além dos recursos de apoio do plugin upstream.
