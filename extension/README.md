# Extensão llm-esbmc para o Claude Code

Comando `/verificar-repo <pasta> [foco]`: o grafo de chamadas escolhe as funções do repositório, o LLM aponta
possíveis bugs de execução, o agente escreve o harness e o ESBMC-Python confirma. O relatório separa os bugs
confirmados (cada um com o teste que falha) das suspeitas do LLM que não foram confirmadas.

## Instalar

```bash
export LLM_ESBMC_HOME=/caminho/para/llm_esbmc
claude --plugin-dir "$LLM_ESBMC_HOME/extension"
```

No Claude Code, o comando aparece como `/verificar-repo` (ou `/llm-esbmc:verificar-repo`, com o nome do plugin).

Requisitos: o ambiente do pipeline (`$LLM_ESBMC_HOME/.venv`), o ESBMC no `PATH` (ou `--esbmc-command`) e o
Claude Code com login (a detecção e o agente usam a assinatura, `claude_cli`).

## Custo

O comando sempre simula primeiro e só gasta depois de você confirmar. A detecção faz uma chamada por função
escolhida; a confirmação, uma sessão do agente por hipótese.
