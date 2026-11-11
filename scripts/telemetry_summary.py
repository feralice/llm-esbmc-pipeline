"""Totals over every llm_telemetry.json under the given roots, with the row count per root.

    python scripts/telemetry_summary.py artifacts docs/experimentos
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from research_pipeline.llm.usage_summary import load_rows, summarize

HEADER = ("provider", "model", "stage", "calls", "ok", "limit", "timeout", "legacy",
          "prompt_tok", "compl_tok", "cache_read", "cache_write", "cost_usd", "costed", "billed_usd", "no_prompt")


def main(roots: list[str]) -> None:
    rows: list[dict] = []
    for root in roots:
        files = sorted(Path(root).glob("**/llm_telemetry.json"))
        root_rows = [row for path in files for row in load_rows(path)]
        print(f"{root}: {len(files)} arquivos, {len(root_rows)} chamadas")
        rows.extend(root_rows)
    print(f"total: {len(rows)} chamadas\n")
    print(" | ".join(HEADER))
    for group in summarize(rows):
        values = [group["provider"], group["model"], group["stage"], int(group["calls"]), int(group["success"]),
                  int(group["usage_limit"]), int(group["timeout"]), int(group["legacy"]),
                  int(group["prompt_tokens"]), int(group["completion_tokens"]), int(group["cached_tokens"]),
                  int(group["cache_creation_tokens"]), round(group["cost_usd"], 4), int(group["costed"]),
                  round(group["billed_usd"], 4), int(group["unknown_prompt"])]
        print(" | ".join("-" if v is None else str(v) for v in values))


if __name__ == "__main__":
    main(sys.argv[1:] or ["artifacts", "docs/experimentos"])
