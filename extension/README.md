# llm-esbmc extension for Claude Code

Command `/verify-repo <folder> [focus]`: the call graph picks the repository's functions, the LLM points out
possible runtime bugs, the agent writes the harness and ESBMC-Python confirms them. The report separates the
confirmed bugs (each with the failing test) from the LLM's suspicions that were not confirmed.

Self-healing is part of the run: when ESBMC stops without a verdict, the agent rewrites the harness from the
ESBMC message, following the rules in the repair notebook (`verify/skills/reparos-aprendidos/SKILL.md`), and
each repair that works is added to the notebook for the next case.

## Install

```bash
export LLM_ESBMC_HOME=/path/to/llm_esbmc
claude --plugin-dir "$LLM_ESBMC_HOME/extension"
```

In Claude Code, the command appears as `/verify-repo` (or `/llm-esbmc:verify-repo`, with the plugin name).

Requirements: the pipeline environment (`$LLM_ESBMC_HOME/.venv`), ESBMC on the `PATH` (or `--esbmc-command`) and
Claude Code with a login (detection and the agent use the subscription, `claude_cli`).

## Backend

`/verify-repo <folder> [focus] backend=codex` runs the same flow with the Codex CLI (ChatGPT account) instead of
Claude. The default is `backend=claude`. Outputs go to `artifacts/extensao/<backend>/<folder>`, so the two
backends never overwrite each other. Gemini is not available yet: it has no command-running agent.

## Cost

The command always does a dry run first and only spends after you confirm. Detection makes one call per chosen
function; confirmation, one agent session per hypothesis.
