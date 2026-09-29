import json

import pytest

from research_pipeline.scan.rewrite import RewriteProposal, parse_rewrite_proposal


def _payload() -> dict:
    return {
        "rewritten_source": "def ratio(a: float, b: float) -> float:\n    return a / b\n",
        "driver_source": "def main():\n    ratio(nondet_float(), nondet_float())\nmain()\n",
        "changes": [{"before": "def ratio(a, b)", "after": "def ratio(a: float, b: float)", "reason": "ESBMC needs parameter types"}],
        "input_cases": [{"args": [1.0, 2.0], "kwargs": {}}],
        "assumptions": [],
        "oracle_ref": None,
    }


def test_valid_rewrite_json_parses() -> None:
    proposal = parse_rewrite_proposal(json.dumps(_payload()))
    assert isinstance(proposal, RewriteProposal)
    assert proposal.rewritten_source.startswith("def ratio")
    assert proposal.changes[0].reason == "ESBMC needs parameter types"
    assert proposal.input_cases[0]["args"] == [1.0, 2.0]


def test_missing_manifest_is_rejected() -> None:
    payload = _payload()
    del payload["changes"]
    with pytest.raises(ValueError, match="changes"):
        parse_rewrite_proposal(json.dumps(payload))


def test_malformed_or_non_json_response_is_rejected() -> None:
    with pytest.raises(ValueError, match="JSON"):
        parse_rewrite_proposal("def harness(): pass")


def test_invalid_input_case_shape_is_rejected() -> None:
    payload = _payload()
    payload["input_cases"] = [{"args": "not-a-list", "kwargs": {}}]
    with pytest.raises(ValueError, match="args"):
        parse_rewrite_proposal(json.dumps(payload))
