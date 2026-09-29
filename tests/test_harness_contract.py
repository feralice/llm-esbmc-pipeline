from __future__ import annotations

import pytest

from research_pipeline.scan.contract import (
    HarnessContract,
    OperandSpec,
    contract_from_dict,
    inspect_expression,
    render_scalar_harness,
)
from research_pipeline.scan.compat import check_harness


DZ02 = {
    "strategy": "scalar",
    "category": "division_by_zero",
    "expression": "float(not_parsed) / float(num_substrings)",
    "operands": {
        "not_parsed": {"type": "int", "source": "local counter"},
        "num_substrings": {
            "type": "int",
            "source": "len(possible_substrings_splits[i])",
        },
    },
    "preserve": ["/", "float"],
    "assumptions": ["not_parsed >= 0", "not_parsed <= num_substrings"],
}


def test_contract_from_dict_preserves_the_semantic_witness() -> None:
    contract = contract_from_dict(DZ02)

    assert contract.strategy == "scalar"
    assert contract.category == "division_by_zero"
    assert contract.expression == DZ02["expression"]
    assert contract.operands["num_substrings"].source.startswith("len(")
    assert contract.preserve == ("/", "float")


def test_contract_rejects_unknown_operand_type() -> None:
    data = {**DZ02, "operands": {"x": {"type": "object", "source": "x"}}}

    with pytest.raises(ValueError, match="unsupported operand type"):
        contract_from_dict(data)


def test_expression_inspection_exposes_names_calls_and_division() -> None:
    shape = inspect_expression(DZ02["expression"])

    assert shape.names == ("not_parsed", "num_substrings")
    assert shape.calls == ("float", "float")
    assert shape.operators == ("/",)


def test_rendered_scalar_harness_keeps_expression_and_binds_operands() -> None:
    source = render_scalar_harness(contract_from_dict(DZ02))

    assert "float(not_parsed) / float(num_substrings)" in source
    assert "not_parsed: int = nondet_int()" in source
    assert "num_substrings: int = nondet_int()" in source
    assert "assert num_substrings != 0" in source
    assert "nondet_bool()" not in source
    assert check_harness(source, category="division_by_zero").ok


def test_rendered_dz02_harness_has_no_unconnected_assertion_variable() -> None:
    source = render_scalar_harness(contract_from_dict(DZ02))
    result = check_harness(source, category="division_by_zero")

    assert result.reasons == []
