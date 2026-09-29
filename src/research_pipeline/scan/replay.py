"""Differential replay using a locally available, network-isolated container."""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ReplayCase:
    args: tuple[object, ...]
    kwargs: dict[str, object]


@dataclass(frozen=True)
class ReplayOutcome:
    kind: str
    value: object | None = None
    exception_type: str = ""
    exception_message: str = ""
    effects: dict[str, object] = field(default_factory=dict)
    phase: str = ""
    # Locations may move under a rewrite; they are attribution, not observable output.
    exception_location: dict[str, object] = field(default_factory=dict, compare=False)


@dataclass(frozen=True)
class ReplayReport:
    status: str
    compared: int
    divergences: tuple[str, ...] = ()


_BOUNDARY_VALUES: dict[str, tuple[object, ...]] = {
    "int": (0, 1, -1),
    "float": (0.0, 1.0, -1.0),
    "bool": (False, True),
    "str": ("", "a"),
}
_MAX_CASES = 16


def _values_for(annotation: ast.expr | None) -> tuple[object, ...] | None:
    if isinstance(annotation, ast.Name):
        return _BOUNDARY_VALUES.get(annotation.id)
    if (isinstance(annotation, ast.Subscript) and isinstance(annotation.value, ast.Name)
            and annotation.value.id == "list"):
        element = _values_for(annotation.slice)
        return None if element is None else ([], [element[0]], list(element))
    return None


def _entry_signature(source: str, function: str) -> list[ast.arg] | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    parts = function.split(".")
    scope: list[ast.stmt] = tree.body
    if len(parts) == 2:
        classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == parts[0]]
        if len(classes) != 1:
            return None
        scope = classes[0].body
    elif len(parts) != 1:
        return None
    matches = [node for node in scope if isinstance(node, ast.FunctionDef) and node.name == parts[-1]]
    if len(matches) != 1:
        return None
    params = list(matches[0].args.posonlyargs) + list(matches[0].args.args)
    return params[1:] if len(parts) == 2 else params


def boundary_cases(source: str, function: str) -> tuple[ReplayCase, ...]:
    """Deterministic edge inputs from annotations, varying one parameter at a time.

    Independent of the LLM, so its own input suggestions cannot hide a divergence alone.
    """
    params = _entry_signature(source, function)
    if not params:
        return ()
    domains = [_values_for(param.annotation) for param in params]
    if any(domain is None for domain in domains):
        return ()
    base = [domain[0] for domain in domains]
    cases = [ReplayCase(tuple(base), {})]
    for index, domain in enumerate(domains):
        for value in domain[1:]:
            args = list(base)
            args[index] = value
            cases.append(ReplayCase(tuple(args), {}))
    return tuple(cases[:_MAX_CASES])


def merge_cases(llm_cases: tuple[dict, ...], annotated_source: str, function: str) -> tuple[ReplayCase, ...]:
    merged: list[ReplayCase] = []
    candidates = [ReplayCase(tuple(case["args"]), dict(case["kwargs"])) for case in llm_cases]
    for case in [*candidates, *boundary_cases(annotated_source, function)]:
        if case not in merged:
            merged.append(case)
    return tuple(merged[:_MAX_CASES * 2])


class UnavailableReplayExecutor:
    """Stand-in when no isolated runtime is configured: never executes anything."""

    def __init__(self, reason: str) -> None:
        self.reason = reason

    def run(self, source: str, function: str, case: ReplayCase) -> ReplayOutcome:
        return ReplayOutcome("unavailable", exception_message=self.reason)


def _entry_is_constructible(source: str, function: str) -> bool:
    parts = function.split(".")
    if len(parts) == 1:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return False
        return any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == parts[0]
                   for node in tree.body)
    if len(parts) != 2:
        return False
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == parts[0]]
    if len(classes) != 1:
        return False
    cls = classes[0]
    methods = [node for node in cls.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if not any(method.name == parts[1] for method in methods):
        return False
    constructors = [method for method in methods if method.name == "__init__"]
    if not constructors:
        return True
    init = constructors[0]
    defaults_start = len(init.args.args) - len(init.args.defaults)
    required_positional = [
        index for index, arg in enumerate(init.args.args)
        if index and arg.arg not in {"self", "cls"} and index < defaults_start
    ]
    required_keyword_only = [
        arg for arg, default in zip(init.args.kwonlyargs, init.args.kw_defaults)
        if default is None
    ]
    return not required_positional and not required_keyword_only


class ContainerReplayExecutor:
    """Execute a module only inside an already installed local container image."""

    def __init__(
        self,
        *,
        runtime: str | None = None,
        image: str,
        timeout_seconds: int = 10,
        memory_limit: str = "256m",
        cpu_limit: str = "1",
        pids_limit: int = 64,
    ) -> None:
        if not image.strip():
            raise ValueError("a locally installed replay image must be configured")
        self.runtime = runtime or shutil.which("podman") or shutil.which("docker") or ""
        self.image = image
        self.timeout_seconds = timeout_seconds
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self.pids_limit = pids_limit

    def _runtime_available(self) -> bool:
        return bool(self.runtime and shutil.which(self.runtime))

    def _image_available(self) -> bool:
        if not self._runtime_available():
            return False
        try:
            result = subprocess.run(
                [self.runtime, "image", "inspect", self.image],
                capture_output=True, text=True, timeout=10, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0

    def _build_command(
        self,
        source: Path,
        worker: Path,
        output: Path,
        function: str,
        case: ReplayCase,
    ) -> list[str]:
        return [
            self.runtime, "run", "--rm",
            "--network", "none",
            "--read-only",
            "--user", "65534:65534",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--pids-limit", str(self.pids_limit),
            "--memory", self.memory_limit,
            "--cpus", self.cpu_limit,
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
            "--mount", f"type=bind,src={source},dst=/sandbox/candidate.py,readonly",
            "--mount", f"type=bind,src={worker},dst=/sandbox/replay_worker.py,readonly",
            "--mount", f"type=bind,src={output},dst=/sandbox/result.json,rw",
            self.image, "python", "-I", "/sandbox/replay_worker.py",
            "/sandbox/candidate.py", function,
            json.dumps(case.args, separators=(",", ":")),
            json.dumps(case.kwargs, separators=(",", ":")),
            "/sandbox/result.json",
        ]

    def run(self, source: str, function: str, case: ReplayCase) -> ReplayOutcome:
        if not _entry_is_constructible(source, function):
            return ReplayOutcome("unavailable", exception_message="entry point is missing or cannot be constructed")
        if not self._image_available():
            return ReplayOutcome("unavailable", exception_message="local container runtime/image unavailable")
        worker = Path(__file__).with_name("replay_worker.py")
        try:
            with tempfile.TemporaryDirectory(prefix="llm-esbmc-replay-") as temp_dir:
                directory = Path(temp_dir)
                directory.chmod(0o755)
                source_path = directory / "candidate.py"
                output_path = directory / "result.json"
                source_path.write_text(source, encoding="utf-8")
                source_path.chmod(0o644)
                output_path.touch()
                output_path.chmod(0o666)
                command = self._build_command(source_path, worker, output_path, function, case)
                completed = subprocess.run(
                    command, capture_output=True, text=True,
                    timeout=self.timeout_seconds, check=False,
                )
                if not output_path.stat().st_size:
                    return ReplayOutcome(
                        "unavailable", exception_message=(completed.stderr or "container produced no result")[:1000]
                    )
                payload = json.loads(output_path.read_text(encoding="utf-8"))
                return ReplayOutcome(
                    kind=str(payload.get("kind", "unavailable")),
                    value=payload.get("value"),
                    exception_type=str(payload.get("exception_type", "")),
                    exception_message=str(payload.get("exception_message", "")),
                    effects=dict(payload.get("effects", {})),
                    phase=str(payload.get("phase", "")),
                    exception_location=dict(payload.get("exception_location", {})),
                )
        except subprocess.TimeoutExpired:
            return ReplayOutcome("timeout", exception_message="isolated replay timed out")
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            return ReplayOutcome("unavailable", exception_message=str(exc)[:1000])


def compare_rewrite(
    original: str,
    rewritten: str,
    function: str,
    cases: tuple[ReplayCase, ...],
    executor,
) -> ReplayReport:
    if not cases:
        return ReplayReport("unavailable", 0, ("no differential replay cases",))
    compared = 0
    divergences: list[str] = []
    for index, case in enumerate(cases):
        original_result = executor.run(original, function, case)
        rewritten_result = executor.run(rewritten, function, case)
        if "timeout" in {original_result.kind, rewritten_result.kind}:
            return ReplayReport("timeout", compared, tuple(divergences))
        if "unavailable" in {original_result.kind, rewritten_result.kind}:
            return ReplayReport("unavailable", compared, tuple(divergences))
        compared += 1
        if original_result != rewritten_result:
            divergences.append(f"case {index}: original and rewrite outcomes differ")
    return ReplayReport("diverged" if divergences else "matched", compared, tuple(divergences))
