# Skill unificada do harness, independente de agente

Data: 2026-10-07. Pedido dela em 06/10: "unificar tudo em um lugar só, dentro do repo", sem se
prender a uma LLM ou ferramenta (Claude Code, Codex, Gemini CLI, Antigravity...).

## Problema

O que o agente sabe sobre a tarefa está espalhado e parte fica fora do repo:

| Peça | Onde está | Problema |
|---|---|---|
| Plugin ESBMC (skill `esbmc-verification`, comandos verify e audit) | `~/.claude/plugins/cache/esbmc-marketplace/esbmc-plugin/1.1.0` | fora do repo, só na máquina dela, só no Claude Code |
| Instrução da tarefa (`_PROMPT`, `_SIMPLIFY`) | string em `verify/agent_arm.py` | texto misturado com código |
| Instrução do agente via API (`_API_SYSTEM`) | string em `verify/agent_arm.py` | idem, e duplica parte do `_PROMPT` |
| O que o ESBMC-Python aceita | `verify/esbmc_python_notes.md` | solto, longe do resto |

Uma rodada do agente não é reproduzível por outra pessoa sem instalar o plugin na mesma versão.

## Proposta

1. **Uma pasta só:** `skills/esbmc-python-harness/`, no formato aberto Agent Skills (`SKILL.md` com
   frontmatter `name` e `description`), lido diretamente pelo Claude Code e por outras ferramentas
   que adotaram o formato; as que não leem recebem o mesmo texto no prompt.
   - `SKILL.md`: a tarefa (escrever `harness.py` com a função original intacta, entradas `nondet_*`,
     `__ESBMC_assume`, stubs dentro do arquivo, sem `assert` novo, sem proteger a expressão suspeita)
     e o ciclo (rodar o ESBMC, ler o erro, corrigir, parar num veredito).
   - `references/esbmc-python.md`: as notas de hoje (`esbmc_python_notes.md`), movidas para cá.
   - `examples/`: dois harnesses reais que confirmaram (nível 1 e agente), sem nada do gabarito.
2. **O código lê a skill:** `agent_arm.py` monta o prompt e a instrução do agente via API a partir da
   pasta, em vez das strings. Uma fonte de verdade para os dois tipos de agente.
3. **Agente trocável:** além de `claude` (Claude Code) e das APIs, backends de linha de comando para
   `codex exec` e Gemini CLI, todos pela mesma interface `run_agent(prompt, pasta, tempo)`. Cada um
   recebe a skill copiada para a pasta do caso. Antigravity entra só se tiver modo sem interface;
   senão, usa a skill manualmente.
4. **O plugin ESBMC vira opcional:** a rodada padrão usa só a skill do repo. O plugin continua
   disponível como variante (`--with-esbmc-plugin`) para comparar, sem ser copiado para o repo
   (é de outro autor, Paulo Matos/Igalia, `esbmc/agent-marketplace`; licença não verificada).
5. **Mesma desconfiança para todos:** ESBMC de novo, CPython e função preservada, como hoje.

## Como medir

Nos 20 casos difíceis, rota do orquestrador, um agente por vez:
- Claude Code com a skill do repo contra Claude Code com o plugin (a skill substitui o plugin?);
- Codex e Gemini CLI com a mesma skill, se estiverem instalados e autenticados (custo confirmado antes).
Métrica: bugs do gabarito confirmados na linha; tempo por caso.

## Fora do escopo

- Reescrever o conteúdo do plugin ESBMC; só a parte que a tarefa usa entra na skill.
- Mudar o nível 1 (harness pelo código).
