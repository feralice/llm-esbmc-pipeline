"""Smoke test for scan step 3: synthesize harnesses for a few V2 detection cases
with gpt-4o-mini, compat-check, run ESBMC, compare verdict to the hand-made bugs/<id>.py.
"""
import json, subprocess, sys, tempfile, os
from pathlib import Path

sys.path.insert(0, "/mnt/c/Users/ferna/Documents/mestrado/llm_esbmc")
os.chdir("/mnt/c/Users/ferna/Documents/mestrado/llm_esbmc")
from dotenv import load_dotenv
load_dotenv(".env")

from research_pipeline.preprocess import preprocess_file
from research_pipeline.models import Finding
from research_pipeline.scan.synth import HarnessSynthesizer
from research_pipeline.scan.compat import check_harness

V2 = Path("dataset/v2_real_world")
gts = {i["id"]: i for i in json.load(open(V2 / "ground_truths.json"))["items"]}

CASES = ["dz_real_01", "dz_real_02", "dz_real_04", "ip_real_01"]

def esbmc_verdict(path):
    try:
        p = subprocess.run(["esbmc", str(path), "--z3", "--timeout", "45s"],
                           capture_output=True, text=True, timeout=90)
        out = p.stdout + p.stderr
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    if "VERIFICATION FAILED" in out: return "FAILED"
    if "VERIFICATION SUCCESSFUL" in out: return "SUCCESSFUL"
    tail = " | ".join(l for l in out.splitlines()[-4:] if l.strip())
    return f"OTHER({tail[:160]})"

import argparse
MODEL = (sys.argv[1] if len(sys.argv) > 1 else "gpt-4o-mini")
synth = HarnessSynthesizer(model=MODEL)
print(f"### model = {MODEL}")
for cid in CASES:
    item = gts[cid]
    det = V2 / "detection" / f"{cid}.py"
    ref = V2 / "bugs" / f"{cid}.py"
    units = preprocess_file(det)
    # pick the unit whose name matches the ground-truth function (last dotted part)
    want = item["function"].split(".")[-1]
    unit = next((u for u in units if u.name == want), units[0])
    finding = Finding(id=cid, stage="llm_analysis", finding_type="suspected_bug",
                      category=item["categories"][0], title="", explanation="", evidence=[],
                      verifiable=True, confidence="medium",
                      metadata={"expression": item.get("expression", "")})
    print(f"\n===== {cid}  ({item['categories']})  fn={unit.name} =====")
    res = synth.synthesize(unit, finding)
    tmp = Path(tempfile.mkdtemp()) / f"{cid}_synth.py"
    tmp.write_text(res.harness, encoding="utf-8")
    compat = check_harness(res.harness)
    print(f"  tokens={res.telemetry.get('total_tokens')}  compat={compat.verdict} {compat.reasons}")
    print("  --- harness sintetizado ---")
    print("  " + res.harness.replace("\n", "\n  "))
    if compat.ok:
        v_synth = esbmc_verdict(tmp)
        v_ref = esbmc_verdict(ref)
        match = "OK" if v_synth == v_ref else "MISMATCH"
        print(f"  ESBMC sintetizado={v_synth}  |  referência(bugs/{cid}.py)={v_ref}  ->  {match}")
