---
name: reparos-aprendidos
description: Repairs learned from earlier harness attempts that ESBMC-Python rejected. Use together with regras-harness.
---

# Learned repairs

### Annotate attributes that start as None with their class
- Error: `ERROR: Cannot resolve nested attribute: <name>`
- What to do: where `__init__` sets `self.x = None` and code later reads `obj.x.y`, annotate it with the
  class it will hold, unquoted: `self.x: Node = None`. The value stays None, so behaviour is unchanged.
- Source case: 6e33562fdd8f (nm_real_12), rounds 4 and 7.
- Approval date: 2026-10-27.

## Format of an approved repair

Candidates come from `scripts/v2_repair_candidates.py` (candidatos.md) or the `/self-healing` command. A repair
enters only after the researcher approves it, through `scripts/add_repair.py`, which checks this format; never
edit this file by hand. Its version is the hash of this file, which each run records. Each rule:

### <short title>
- Error: the first `ERROR:` line ESBMC printed for the refused harness.
- What to do: the rewrite that made ESBMC reach a verdict without changing the function's behaviour.
- Source case: the hypothesis id and round the pair came from.
- Approval date: YYYY-MM-DD.
