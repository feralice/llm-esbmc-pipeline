---
name: reparos-aprendidos
description: Repairs learned from earlier harness attempts that ESBMC-Python rejected. Use together with regras-harness.
---

# Learned repairs

Version: 0

No repairs recorded yet.

## Format of an approved repair

Candidates come from `scripts/v2_repair_candidates.py` (candidatos.md). A repair is approved only when the
researcher copies it here by hand; its version is the hash of this file that each run records. Each rule:

### <short title>
- Error: the first `ERROR:` line ESBMC printed for the refused harness.
- What to do: the rewrite that made ESBMC reach a verdict without changing the function's behaviour.
- Source case: the hypothesis id and round the pair came from.
- Approval date: YYYY-MM-DD.
