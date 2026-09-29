import subprocess
from pathlib import Path

from research_pipeline.scan.replay import (
    ContainerReplayExecutor, ReplayCase, ReplayOutcome, compare_rewrite,
)


class _FakeExecutor:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)

    def run(self, source, function, case):
        return next(self.outcomes)


def test_equal_return_and_exception_match():
    result = compare_rewrite(
        "original", "rewrite", "f", (ReplayCase((1,), {}),),
        _FakeExecutor([
            ReplayOutcome("return", 1), ReplayOutcome("return", 1),
        ]),
    )
    assert result.status == "matched"
    assert result.compared == 1


def test_changed_exception_diverges():
    result = compare_rewrite(
        "original", "rewrite", "f", (ReplayCase((), {}),),
        _FakeExecutor([
            ReplayOutcome("exception", exception_type="ZeroDivisionError", exception_message="division by zero"),
            ReplayOutcome("exception", exception_type="ValueError", exception_message="bad"),
        ]),
    )
    assert result.status == "diverged"
    assert result.divergences


def test_runtime_missing_is_unavailable(tmp_path: Path):
    executor = ContainerReplayExecutor(runtime=str(tmp_path / "no-container"), image="python:3.12")
    outcome = executor.run("def f(): return 1", "f", ReplayCase((), {}))
    assert outcome.kind == "unavailable"


def test_import_side_effect_never_runs_on_host(tmp_path: Path):
    marker = tmp_path / "host-side-effect.txt"
    source = f"open({str(marker)!r}, 'w').write('ran')\ndef f(): return 1\n"
    executor = ContainerReplayExecutor(runtime=str(tmp_path / "missing"), image="python:3.12")
    outcome = executor.run(source, "f", ReplayCase((), {}))
    assert outcome.kind == "unavailable"
    assert not marker.exists()


def test_constructor_without_json_entry_is_unavailable(tmp_path: Path, monkeypatch):
    executor = ContainerReplayExecutor(runtime="docker", image="local-python")
    monkeypatch.setattr(executor, "_image_available", lambda: True)
    source = (
        "class Service:\n"
        "    def __init__(self, dependency):\n"
        "        self.dependency = dependency\n"
        "    def execute(self, value):\n"
        "        return value\n"
    )
    outcome = executor.run(source, "Service.execute", ReplayCase((1,), {}))
    assert outcome.kind == "unavailable"


def test_container_command_disables_network_and_mounts_source_read_only(tmp_path: Path):
    executor = ContainerReplayExecutor(runtime="docker", image="local-python")
    source = tmp_path / "source.py"
    worker = tmp_path / "worker.py"
    output = tmp_path / "result.json"
    command = executor._build_command(source, worker, output, "f", ReplayCase((), {}))
    assert "--network" in command and command[command.index("--network") + 1] == "none"
    mounts = [part for part in command if "type=bind" in part]
    assert any("readonly" in mount and str(source) in mount for mount in mounts)
    assert "--read-only" in command
    assert "--cap-drop" in command and "ALL" in command
    assert "--security-opt" in command and "no-new-privileges" in command


def test_timeout_is_not_match():
    report = compare_rewrite(
        "original", "rewrite", "f", (ReplayCase((), {}),),
        _FakeExecutor([
            ReplayOutcome("timeout"), ReplayOutcome("return", 1),
        ]),
    )
    assert report.status == "timeout"
    assert report.compared == 0


def test_boundary_cases_come_from_annotations_one_factor_at_a_time():
    from research_pipeline.scan.replay import boundary_cases
    cases = boundary_cases("def f(a: int, b: bool):\n    return a\n", "f")
    assert ReplayCase((0, False), {}) in cases
    assert ReplayCase((-1, False), {}) in cases
    assert ReplayCase((0, True), {}) in cases
    assert len({repr(case) for case in cases}) == len(cases)


def test_boundary_cases_skip_unannotated_or_unknown_types():
    from research_pipeline.scan.replay import boundary_cases
    assert boundary_cases("def f(a, b: int):\n    return a\n", "f") == ()
    assert boundary_cases("def f(a: Widget):\n    return a\n", "f") == ()


def test_boundary_cases_ignore_self_for_methods():
    from research_pipeline.scan.replay import boundary_cases
    source = "class C:\n    def f(self, items: list[int]):\n        return items\n"
    assert ReplayCase(([],), {}) in boundary_cases(source, "C.f")


def test_independent_boundary_cases_are_added_to_llm_cases():
    from research_pipeline.scan.replay import merge_cases
    merged = merge_cases(
        ({"args": [5], "kwargs": {}},),
        "def f(x: int):\n    return 10 // x\n", "f",
    )
    assert ReplayCase((5,), {}) in merged
    assert ReplayCase((0,), {}) in merged


def test_unavailable_executor_never_runs_code():
    from research_pipeline.scan.replay import UnavailableReplayExecutor
    outcome = UnavailableReplayExecutor("no image configured").run("def f(): 1/0", "f", ReplayCase((), {}))
    assert outcome.kind == "unavailable"
    assert "no image" in outcome.exception_message
