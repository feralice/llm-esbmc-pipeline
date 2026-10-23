import importlib.util
import json
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "v2_repair_candidates", Path(__file__).resolve().parents[1] / "scripts/v2_repair_candidates.py")
v2_repair_candidates = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v2_repair_candidates)

REFUSED = "Parsing...\nERROR: Unsupported construct\nmore detail\n"
VERDICT = "VERIFICATION FAILED\n"


def _case(tmp_path: Path, rounds: list[tuple[str, str, int]], preservation: str | None = None) -> Path:
    case = tmp_path / "cases" / "h1"
    for number, (source, output, code) in enumerate(rounds, 1):
        folder = case / "rounds" / f"{number:03d}"
        folder.mkdir(parents=True)
        (folder / "input.py").write_text(source, encoding="utf-8")
        (folder / "output.txt").write_text(output, encoding="utf-8")
        (folder / "exit_code").write_text(str(code), encoding="utf-8")
    entry = {"hypothesis": {"hypothesis_id": "h1"}}
    if preservation:
        entry["differential"] = {"preservation": preservation}
    (tmp_path / "agent_results.json").write_text(json.dumps([entry]), encoding="utf-8")
    return case


def test_refused_then_verdict_is_a_candidate(tmp_path) -> None:
    case = _case(tmp_path, [("x = a[0]\n", REFUSED, 1), ("x = a[0] if a else 0\n", VERDICT, 1)], "preservada")

    [candidate] = v2_repair_candidates.repair_candidates(case)

    assert candidate["caso"] == "h1" and candidate["rodada"] == 1
    assert candidate["erro"] == "ERROR: Unsupported construct"
    assert "-x = a[0]" in candidate["diff"] and "+x = a[0] if a else 0" in candidate["diff"]


def test_changed_behaviour_is_never_a_candidate(tmp_path) -> None:
    case = _case(tmp_path, [("a\n", REFUSED, 1), ("b\n", VERDICT, 1)], "alterada")

    assert v2_repair_candidates.repair_candidates(case) == []


def test_crash_is_never_a_candidate(tmp_path) -> None:
    case = _case(tmp_path, [("a\n", REFUSED, 1), ("b\n", "Couldn't convert expression\n", 134),
                            ("c\n", VERDICT, 1)])

    assert v2_repair_candidates.repair_candidates(case) == []


def test_write_candidates_lists_each_pair_in_portuguese(tmp_path) -> None:
    case = _case(tmp_path, [("a\n", REFUSED, 1), ("b\n", VERDICT, 1)])
    out = tmp_path / "candidatos.md"

    v2_repair_candidates.write_candidates(tmp_path, out)

    text = out.read_text(encoding="utf-8")
    assert "# Candidatos" in text and "ERROR: Unsupported construct" in text and "h1" in text
    assert chr(0x2014) not in text
    assert case.exists()
