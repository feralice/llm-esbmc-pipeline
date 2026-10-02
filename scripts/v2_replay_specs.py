"""Re-run a finished verify report with the specs its LLM already gave, without any LLM call.

Measures a harness change at no API cost: same hypotheses, same specs, current harness and ESBMC.
A spec missing a name the current harness asks for gets ``int`` there (counted in ``filled``), so a
version that needs more stubs is not rejected for a reason no LLM was ever asked about.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.llm_client import SynthResult
from research_pipeline.verify.loop import verification_source, verify_hypothesis

_NEEDED = {
    "params": re.compile(r"^Parameters needing a type: (.*?)  \(declared", re.M),
    "attributes": re.compile(r"^Receiver attributes needing a type: (.*?)  \(declared", re.M),
    "stubs": re.compile(r"^Library calls replaced by stubs, needing a return type: (.*)$", re.M),
}


class RecordedSpecs:
    model = "recorded"

    def __init__(self, specs: list[str]):
        self.specs, self.calls, self.filled = specs, 0, 0

    def complete(self, system_prompt, user_prompt, *, json_mode=False):
        text = self.specs[min(self.calls, len(self.specs) - 1)] if self.specs else "{}"
        self.calls += 1
        try:
            spec = json.loads(text)
        except json.JSONDecodeError:
            return SynthResult(harness=text, raw_response="", model=self.model, telemetry={})
        if not isinstance(spec, dict):
            return SynthResult(harness=text, raw_response="", model=self.model, telemetry={})
        for key, pattern in _NEEDED.items():
            match = pattern.search(user_prompt)
            names = [n.strip() for n in match.group(1).split(",")] if match and match.group(1) != "none" else []
            if not isinstance(spec.get(key, {}), dict):
                continue
            section = spec.setdefault(key, {})
            for name in names:
                if name and name not in section:
                    section[name] = "int"
                    self.filled += 1
        return SynthResult(harness=json.dumps(spec), raw_response="", model=self.model, telemetry={})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", help="v2_verify_report.json of a finished run")
    parser.add_argument("--esbmc", default="esbmc")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--sources", default="dataset/bugs_reais/arquivo_com_bug")
    parser.add_argument("--out", required=True)
    parser.add_argument("--strict-sources", action="store_true",
                        help="skip a hypothesis with no file in --sources instead of using its detection file")
    parser.add_argument("--only", default="", help="comma-separated hypothesis ids")
    parser.add_argument("--shard", default="0/1", help="i/n: run every n-th hypothesis starting at i")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    index, count = (int(part) for part in args.shard.split("/"))
    rows, results = [], []
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    bound = int(report.get("config", {}).get("bound", 5))
    only = set(filter(None, args.only.split(",")))
    for item in [i for i in report["results"] if not only or i["hypothesis"]["hypothesis_id"] in only][index::count]:
        h = BugHypothesis(**{k: v for k, v in item["hypothesis"].items() if k != "hypothesis_id"})
        h = BugHypothesis(**{**h.__dict__, "file": str(ROOT / h.file)}) if not Path(h.file).is_absolute() else h
        path = verification_source(h, ROOT / args.sources)
        if args.strict_sources and path == Path(h.file):
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        llm = RecordedSpecs([a["spec"] for a in item["attempts"] if "spec" in a])
        try:
            data = verify_hypothesis(h, llm=llm, source=source, esbmc_command=[args.esbmc], bound=bound,
                                     timeout_seconds=args.timeout, work_dir=out / "programs").to_dict()
        except Exception as exc:  # noqa: BLE001 - one broken case must not end the batch
            data = {"verdict": "PIPELINE_ERROR", "reason": f"{type(exc).__name__}: {exc}", "transforms": []}
        row = {"id": item["hypothesis"]["hypothesis_id"], "file": Path(h.file).name, "function": h.function,
               "before": item["verdict"], "after": data["verdict"], "reason": data["reason"][:300],
               "recorded_specs": len(llm.specs), "filled": llm.filled, "transforms": data.get("transforms", [])}
        rows.append(row)
        results.append({"hypothesis": item["hypothesis"], **{k: v for k, v in data.items() if k != "hypothesis"}})
        print(f"{row['file']:16s} {row['before']:18s} -> {row['after']:18s} {row['reason'][:80]}", flush=True)
    # A confirmation that needed a type no LLM gave is not counted as one.
    counts = Counter("CONFIRMED_WITH_FILLED_TYPES" if r["after"] == "CONFIRMED" and r["filled"] else r["after"]
                     for r in rows)
    print("\n", dict(counts.most_common()))
    (out / f"report_{index}of{count}.json").write_text(json.dumps({"results": results}, indent=2), encoding="utf-8")
    (out / f"replay_specs_{index}of{count}.json").write_text(json.dumps({"counts": counts, "rows": rows}, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
