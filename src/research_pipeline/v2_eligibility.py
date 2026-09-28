"""Build the optional ESBMC reference-baseline subset for the V2 corpus.

Inputs, all under dataset/v2_real_world/:
  ground_truths.json, manifest.json  full corpus (never modified here)
  eligibility.json                   human decision per item
  esbmc_audit.json                   ESBMC verdicts from scripts/audit_v2_buggy_fixed.py
  patches/<id>.diff                  real fix hunks (provenance evidence)
Output: dataset/v2_real_world_eligible/ with copies of items whose manual
reference harnesses pass every baseline gate. The full V2 corpus is the
dataset/v2_real_world directory and is not gated by this module.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from .llm.categories import FORMAL_CATEGORIES

STATUSES = frozenset({"eligible", "needs_review", "unsupported_by_esbmc", "rejected"})


class EligibilityError(ValueError):
    """A manually selected baseline item fails one of the reference gates."""


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _norm(line: str) -> str:
    return re.sub(r"\s+", "", line)


def _code_lines(lines: list[str]) -> list[str]:
    normalized = (_norm(line) for line in lines)
    return [line for line in normalized if line and not line.startswith("#")]


def patch_lines(diff_text: str) -> tuple[list[str], list[str]]:
    """Return substantive removed and added lines from a unified diff."""
    removed = [
        _norm(line[1:])
        for line in diff_text.splitlines()
        if line.startswith("-") and not line.startswith("---")
    ]
    added = [
        _norm(line[1:])
        for line in diff_text.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    return removed, added


def change_blocks(diff_text: str) -> list[tuple[list[str], list[str] | None]]:
    """Split a diff into (pre-fix, post-fix) blocks of normalized code lines.

    Each block is one run of -/+ lines plus the context line on each side, so
    a pure insertion is still anchored to the code around it. The post-fix
    block is None for a pure deletion: context alone cannot tell the two
    versions apart.
    """
    blocks: list[tuple[list[str], list[str] | None]] = []
    for hunk in re.split(r"^@@[^\n]*\n", diff_text, flags=re.MULTILINE)[1:]:
        lines = [l for l in hunk.splitlines() if l[:1] in (" ", "-", "+") and not l.startswith(("---", "+++"))]
        i = 0
        while i < len(lines):
            if lines[i][0] == " ":
                i += 1
                continue
            start = i
            while i < len(lines) and lines[i][0] != " ":
                i += 1
            before = [lines[start - 1][1:]] if start > 0 else []
            after = [lines[i][1:]] if i < len(lines) else []
            run = lines[start:i]
            pre = _code_lines(before + [l[1:] for l in run if l[0] == "-"] + after)
            post = _code_lines(before + [l[1:] for l in run if l[0] == "+"] + after)
            if pre != post:
                added = _code_lines([l[1:] for l in run if l[0] == "+"])
                blocks.append((pre, post if added else None))
    return blocks


def _contains_block(source: list[str], block: list[str]) -> bool:
    size = len(block)
    return size > 0 and any(source[i:i + size] == block for i in range(len(source) - size + 1))


def detection_shows_buggy_code(detection_text: str, diff_text: str) -> bool:
    """True when some fix hunk appears in its pre-fix form and none in its fixed form."""
    source = _code_lines(detection_text.splitlines())
    blocks = change_blocks(diff_text)
    if any(post and _contains_block(source, post) for _, post in blocks):
        return False
    if any(_contains_block(source, pre) for pre, _ in blocks):
        return True

    # Detection files are often focused snippets rather than a verbatim copy
    # of the whole source file. In that case the diff's surrounding context
    # cannot be expected to be contiguous, but every substantive removed line
    # must still be present and no added line may be present.
    removed, added = patch_lines(diff_text)
    if removed and all(line in source for line in removed) and not any(line in source for line in added):
        return True

    # Preserve whitespace inside quoted literals (for example ``' '`` in a
    # tab/space branch); `_norm` intentionally removes formatting whitespace.
    raw_source = [line.strip() for line in detection_text.splitlines()]
    raw_removed = [
        line[1:].strip()
        for line in diff_text.splitlines()
        if line.startswith("-") and not line.startswith("---") and line[1:].strip()
    ]
    raw_added = [
        line[1:].strip()
        for line in diff_text.splitlines()
        if line.startswith("+") and not line.startswith("+++") and line[1:].strip()
    ]
    return bool(raw_removed) and all(line in raw_source for line in raw_removed) and not any(
        line in raw_source for line in raw_added
    )


def gate_failures(item: dict, decision: dict, audit: dict | None, dataset: Path,
                  symptoms: dict[str, list[str]]) -> list[str]:
    """List every gate an item marked eligible does not pass."""
    failures: list[str] = []
    categories = decision.get("categories") or []
    if not categories:
        failures.append("no categories")
    for category in categories:
        if category not in FORMAL_CATEGORIES:
            failures.append(f"non-formal category {category}")
        if category not in item.get("categories", []):
            failures.append(f"category {category} not in the original labels")

    provenance = item.get("provenance", {})
    if not provenance.get("repo_url"):
        failures.append("missing repo_url")
    if not (provenance.get("fixed_commit") or provenance.get("commit_hash")):
        failures.append("missing fix commit")
    diff = dataset / "patches" / f"{item['id']}.diff"
    if not diff.is_file():
        failures.append("missing patches/<id>.diff")
    else:
        detection = dataset / "detection" / f"{item['id']}.py"
        if not detection_shows_buggy_code(detection.read_text(encoding="utf-8"), diff.read_text(encoding="utf-8")):
            failures.append("detection does not show the pre-fix code")

    harness = dataset / "bugs" / item["harness_file"]
    fixed = harness.with_name(harness.stem + "_fixed.py")
    if not fixed.is_file():
        failures.append("missing fixed harness")
    if audit is None or audit.get("fixed") is None:
        failures.append("no ESBMC audit for the buggy/fixed pair")
        return failures
    expected = decision.get("esbmc_property")
    buggy = audit["buggy"]
    if buggy["verdict"] != "failed" or buggy["esbmc_property"] != expected:
        failures.append(f"buggy harness: {buggy['verdict']} {buggy['esbmc_property']!r}, expected failed {expected!r}")
    if audit["fixed"]["verdict"] != "successful":
        failures.append(f"fixed harness: {audit['fixed']['verdict']}, expected successful")
    for category in categories:
        if expected not in symptoms.get(category, []):
            failures.append(f"symptom {expected} incompatible with {category}")
    return failures


def build_eligible(dataset: Path, output: Path) -> dict:
    """Validate every eligible decision and write the eligible subset."""
    ground_truth = _load(dataset / "ground_truths.json")
    manifest = _load(dataset / "manifest.json")
    decisions = _load(dataset / "eligibility.json")
    audit = _load(dataset / "esbmc_audit.json")["results"]

    items = {item["id"]: item for item in ground_truth["items"]}
    unknown = set(decisions["items"]) ^ set(items)
    if unknown:
        raise EligibilityError(f"eligibility.json and ground_truths.json differ on {sorted(unknown)}")
    bad_status = {k: d["status"] for k, d in decisions["items"].items() if d["status"] not in STATUSES}
    if bad_status:
        raise EligibilityError(f"invalid status: {bad_status}")

    eligible = [k for k, d in decisions["items"].items() if d["status"] == "eligible"]
    errors = {
        k: failures for k in eligible
        if (failures := gate_failures(items[k], decisions["items"][k], audit.get(k), dataset,
                                      decisions["symptoms_for_category"]))
    }
    if errors:
        raise EligibilityError(json.dumps(errors, indent=2, ensure_ascii=False))

    selected = set(eligible)
    gt_items = []
    for item in ground_truth["items"]:
        if item["id"] not in selected:
            continue
        decision = decisions["items"][item["id"]]
        gt_items.append({**item, "categories": decision["categories"],
                         "esbmc_property": decision["esbmc_property"],
                         "eligibility_reason": decision["reason"]})
    manifest_items = [
        {**item, "categories": decisions["items"][item["id"]]["categories"],
         "esbmc_property": decisions["items"][item["id"]]["esbmc_property"]}
        for item in manifest["items"] if item["id"] in selected
    ]
    policy = {**ground_truth.get("evaluation_policy", {})}
    policy["patch_context_items"] = [k for k in policy.get("patch_context_items", []) if k in selected]
    description = (f"ESBMC-verifiable subset of v2_real_world ({len(gt_items)} of {len(items)} items). "
                   "Built by scripts/build_v2_eligible.py from eligibility.json; do not edit by hand.")

    if output.exists():
        shutil.rmtree(output)
    (output / "bugs").mkdir(parents=True)
    (output / "detection").mkdir()
    for key in sorted(selected):
        harness = items[key]["harness_file"]
        for name in (harness, harness.replace(".py", "_fixed.py")):
            shutil.copyfile(dataset / "bugs" / name, output / "bugs" / name)
        shutil.copyfile(dataset / "detection" / f"{key}.py", output / "detection" / f"{key}.py")
    _write(output / "ground_truths.json", {"evaluation_policy": policy, "description": description, "items": gt_items})
    _write(output / "manifest.json", {"evaluation_policy": policy, "description": description, "items": manifest_items})
    return {"eligible": sorted(selected), "total": len(items)}


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
