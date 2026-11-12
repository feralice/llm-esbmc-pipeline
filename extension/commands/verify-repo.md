---
name: verify-repo
description: Scan a Python repository, confirm bugs with ESBMC and show the report (confirmed bugs with a test, suspicions apart)
arguments:
  - name: folder
    description: The repository folder to scan
    required: true
  - name: focus
    description: What to prioritise, in free text (optional)
    required: false
  - name: backend
    description: "backend=claude" (default) or "backend=codex", written anywhere in the arguments
    required: false
---

# Verify a repository

Arguments: $ARGUMENTS. The first word is the folder. A word `backend=claude` or `backend=codex` anywhere
picks the subscription (default `claude`); the rest, if any, is the focus.

Backend flags, used in steps 2 and 4:
- `claude`: `--backend claude_cli --agent-backend claude`
- `codex`: `--backend codex --agent-backend codex`

1. **Find the pipeline.** Use the `LLM_ESBMC_HOME` environment variable (the llm_esbmc repository folder). If
   it is not set, ask the user where the pipeline is and stop until you have the answer. From here on, `$HOME_P`
   is that folder and the output goes to `$HOME_P/artifacts/extensao/<backend>/<name of the scanned folder>`.

2. **Dry run, no spending.** Before any `cd`, keep the folder as an absolute path and the focus in a variable
   in single quotes (replace each `'` in the focus with `'\''`), so no character of the focus becomes a command:

   ```bash
   FOLDER=$(realpath "<folder>")
   FOCUS='<focus, or empty>'
   cd "$HOME_P" && .venv/bin/python src/main.py --mode scan --input "$FOLDER" --output-dir "<output>" \
     <backend flags> --scan-rank pagerank --scan-focus "$FOCUS"
   ```

   Read `<output>/scan_selection.json` and say, in a few lines: how many functions the graph chose, the first
   five, and the token estimate for detection. Remind the user that confirmation calls the agent once per
   hypothesis.

3. **Ask for confirmation.** Ask whether the scan may spend the subscription (name it: Claude or Codex), suggesting `--scan-limit 5` on a
   large repository. Without an explicit yes, stop here: the dry run is already saved.

4. **Run.** With the yes, repeat the command from step 2 adding `--yes --scan-verify agent` (and the agreed
   `--scan-limit`). With `codex`, the subscription is the ChatGPT account used by the Codex CLI: say so, and stop
   if the Codex CLI reports a usage limit. It can take a while: run it in the background and say when it finishes. Check the exit
   code: anything other than 0 means part of detection failed, and the report starts by listing those failures.
   When ESBMC stops without a verdict, the agent repairs the harness itself and records what it learned in the
   repair notebook; no separate step is needed.

5. **Show the result.** Read `<output>/relatorio.md` and present, with what the report contains, in this order:
   - detection failures, if any (functions that were not analysed);
   - bugs **confirmed by ESBMC**, each with the expression, the input that breaks it and the test, when there is one;
   - bugs confirmed only on simplified code and those stopped by the checks, as leads, not as bugs;
   - the **LLM's suspicions**, always labelled as suspicions, with the reason they were not confirmed.

   Never present a suspicion as a confirmed bug, and do not add detail the report does not have.
