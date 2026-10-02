"""One bounded attempt loop per hypothesis: spec (LLM) -> program -> ESBMC -> replay -> verdict."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


from .astutil import undefined_globals
from .grounding import Grounded, GroundingFailure, ground
from .hypothesis import BugHypothesis
from .llm_client import SynthResult, _bound_untrusted
from .esbmc_run import check, esbmc_output
from .oracle import convert, refusals
from .pytest_gen import pytest_reproducer
from .outcome import (
    CONFIRMED,
    GROUNDING_FAILED,
    MISSING_DEPENDENCY,
    NO_SOURCE,
    PIPELINE_ERROR,
    SPEC_FAILED,
    UNSUPPORTED,
    EsbmcReading,
    final_verdict,
)
from .render import DRIVER, Program, RenderError, render_program
from .replay import ReplayVerdict, concrete_replay, counterexample_seeds
from .spec import InputSpec, ignored_keys, parse_spec, resolved_types, spec_problems

SYSTEM_PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "input_spec_prompt.txt").read_text(encoding="utf-8")
STRATEGIES = ("repair", "resample")
_INTRINSICS = {"nondet_int", "nondet_float", "nondet_bool", "nondet_str", "nondet_list", "__ESBMC_assume"}


class SpecLLM(Protocol):
    model: str

    def complete(self, system_prompt: str, user_prompt: str, *, json_mode: bool = False) -> SynthResult: ...


@dataclass
class VerifyResult:
    hypothesis: BugHypothesis
    verdict: str
    reason: str = ""
    attempts: list[dict] = field(default_factory=list)
    transforms: tuple[str, ...] = ()
    program_path: str = ""
    replay: dict = field(default_factory=dict)
    tokens: int = 0
    seconds: float = 0.0
    pytest: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "hypothesis": self.hypothesis.to_dict(), "verdict": self.verdict, "reason": self.reason,
            "attempts": self.attempts, "llm_calls": sum(1 for a in self.attempts if "spec" in a),
            "transforms": list(self.transforms), "program_path": self.program_path, "replay": self.replay,
            "tokens": self.tokens, "seconds": round(self.seconds, 3),
            **({"pytest": self.pytest} if self.pytest else {}),
        }


def _user_prompt(grounded: Grounded, previous: str, feedback: str) -> str:
    h = grounded.hypothesis
    params = {p.name: p.annotation or "" for p in grounded.params}
    attrs = {a: grounded.attr_annotations.get(a, "") for a in grounded.receiver_attrs}
    needed_params, needed_attrs = resolved_types(InputSpec({}, {}, ()), grounded)
    parts = [
        f"Function: {h.function}",
        f"Suspect expression (line {h.line or 'unknown'}): {h.suspect_expression}",
        f"Hypothesis: {h.trigger_condition or 'not given'}",
        "Parameters needing a type: " + (", ".join(n for n, t in needed_params.items() if not t) or "none")
        + f"  (declared: {params})",
        "Receiver attributes needing a type: " + (", ".join(n for n, t in needed_attrs.items() if not t) or "none")
        + f"  (declared: {attrs})",
        "Library calls replaced by stubs, needing a return type: " + (", ".join(grounded.stub_keys) or "none"),
        "Members used on inputs (type them only if you choose object for that input): "
        + ("; ".join(f"{key}: " + ", ".join(f"{m}()" if call else m for m, call in sorted(members.items()))
                     for key, members in sorted(grounded.object_members.items())) or "none"),
        "Code (verbatim slice of the real module):\n```python\n" + _bound_untrusted(grounded.module) + "\n```",
    ]
    if previous:
        parts.append(f"Previous attempt:\n{previous}\nError:\n{feedback}")
    return "\n\n".join(parts)


def _placeholder_spec(grounded: Grounded) -> InputSpec:
    params, attrs = resolved_types(InputSpec({}, {}, ()), grounded)
    return InputSpec({n: "int" for n, t in params.items() if not t}, {n: "int" for n, t in attrs.items() if not t},
                     (), {key: "int" for key in grounded.stub_keys})


def _with_line_context(message: str, program: Program) -> str:
    match = re.search(r"line (\d+)", message)
    if not match:
        return message
    number = int(match.group(1))
    lines = program.source.splitlines()
    if not 1 <= number <= len(lines):
        return message
    region = "generated driver" if number >= program.driver_start else "original code"
    return f"{message}\n(program line {number}, {region}: {lines[number - 1].strip()})"


_ORACLE_ROUNDS = 5


def precheck(h: BugHypothesis, source: str,
             esbmc_command: list[str] | None = None) -> tuple[Grounded | None, str, str]:
    """Everything decidable before spending an LLM call; returns (grounded, "", "") when ready.
    With ``esbmc_command``, library members ESBMC cannot convert are stubbed before the LLM sees the slice."""
    refused: frozenset[str] = frozenset()
    for _ in range(_ORACLE_ROUNDS):
        grounded = ground(h, source, refused)
        if isinstance(grounded, GroundingFailure):
            return None, UNSUPPORTED if grounded.unsupported else GROUNDING_FAILED, grounded.reason
        try:
            probe = render_program(grounded, _placeholder_spec(grounded))
        except RenderError as exc:
            return None, UNSUPPORTED, str(exc)
        if not esbmc_command:
            break
        new = refusals(convert(probe.source, esbmc_command), probe.source) - refused
        if not new:
            break
        refused |= new
    undefined = undefined_globals(probe.source, "program.py") - _INTRINSICS
    if undefined:
        return None, MISSING_DEPENDENCY, "undefined name(s): " + ", ".join(sorted(undefined))
    return grounded, "", ""


def verify_hypothesis(
    h: BugHypothesis, *, llm: SpecLLM, source: str, esbmc_command: list[str] | None, bound: int,
    timeout_seconds: int, work_dir: Path, max_repairs: int = 2, replay_runs: int = 400,
    strategy: str = "repair",
) -> VerifyResult:
    """``strategy="resample"`` spends the same call budget on independent samples that never see
    the previous error: the baseline a guided repair has to beat (Olausson et al., ICLR 2024)."""
    if strategy not in STRATEGIES:
        raise ValueError(f"strategy must be one of {STRATEGIES}")
    started = time.monotonic()
    result = VerifyResult(h, "")

    def finish(verdict: str, reason: str = "") -> VerifyResult:
        result.verdict, result.reason, result.seconds = verdict, reason, time.monotonic() - started
        return result

    grounded, verdict, reason = precheck(h, source, esbmc_command)
    if grounded is None:
        return finish(verdict, reason)

    work_dir.mkdir(parents=True, exist_ok=True)
    previous, feedback, last_problems = "", "", []
    for attempt in range(1 + max_repairs):
        shown_previous, shown_feedback = (previous, feedback) if strategy == "repair" else ("", "")
        reply = llm.complete(SYSTEM_PROMPT, _user_prompt(grounded, shown_previous, shown_feedback), json_mode=True)
        result.tokens += int((reply.telemetry or {}).get("total_tokens") or 0)
        record: dict = {"attempt": attempt, "spec": reply.harness, "feedback_given": feedback}
        result.attempts.append(record)
        previous = reply.harness
        try:
            spec = parse_spec(reply.harness)
            problems = spec_problems(spec, grounded)
        except ValueError as exc:
            problems = [str(exc)]
        if problems:
            record["problems"] = problems
            feedback = "The JSON was rejected: " + "; ".join(problems)
            last_problems = problems
            continue
        last_problems = []
        ignored = ignored_keys(spec, grounded)
        if ignored:
            record["ignored"] = ignored
        program = render_program(grounded, spec)
        path = work_dir / f"{h.hypothesis_id}_a{attempt}.py"
        path.write_text(program.source, encoding="utf-8")
        replay_path = path.with_name(path.stem + "_replay.py")
        replay_path.write_text(program.replay_source, encoding="utf-8")
        record["replay_program_path"] = str(replay_path)
        result.program_path, result.transforms = str(path), program.transforms
        # An unwinding assertion alone says the bound was short, not that the code is safe: raise it.
        # Incremental BMC with --multi-property prints FAILED and UNKNOWN together (measured 2026-09-29).
        esbmc, reading, how = check(path, esbmc_command=esbmc_command, bound=bound,
                                    timeout_seconds=timeout_seconds, work_dir=work_dir / path.stem)
        record.update({"esbmc_status": esbmc.status, "reading": reading.kind, "message": reading.message, **how})
        if reading.kind == "repairable" and attempt < max_repairs:
            feedback = "ESBMC rejected the program: " + _with_line_context(reading.message, program)
            continue
        replay = _replay_if_checked(reading, program, grounded, replay_runs, esbmc_output(esbmc))
        result.replay = replay.to_dict()
        verdict = final_verdict(reading, replay)
        if verdict == CONFIRMED and esbmc_command:
            result.pytest = _pytest_for(program, grounded, spec, replay, esbmc_command, bound, work_dir)
        return finish(verdict, reading.message)
    if last_problems and all("unsupported type" in p for p in last_problems):
        # The model kept naming a real type the harness cannot build: a method limit, not a model error.
        return finish(UNSUPPORTED, "input type outside the supported subset: " + "; ".join(last_problems))
    return finish(SPEC_FAILED, feedback)


def _pytest_for(program: Program, grounded: Grounded, spec: InputSpec, replay: ReplayVerdict,
                esbmc_command: list[str], bound: int, work_dir: Path) -> dict:
    """ESBMC's pytest generator on the confirmed program, kept only if the test reproduces the bug."""
    if grounded.entry != "function" or any(p.keyword for p in grounded.params):
        return {"status": "unsupported_shape", "path": "", "reason": "ESBMC's generator handles free functions only"}
    params, _ = resolved_types(spec, grounded)
    name = f"bug_{grounded.hypothesis.hypothesis_id}"
    return pytest_reproducer(program, function=grounded.method_name, params=params, exception=replay.exception_type,
                             esbmc_command=esbmc_command, bound=bound, out_dir=work_dir / "pytest" / name, name=name)


def _replay_if_checked(reading: EsbmcReading, program: Program, grounded: Grounded, runs: int,
                       log: str = "") -> ReplayVerdict:
    if reading.kind not in {"violation", "artifact", "safe"}:
        return ReplayVerdict("unavailable", reason="ESBMC produced no verdict to validate")
    return concrete_replay(program, grounded.method_name, max_runs=runs,
                           seeds=counterexample_seeds(log, DRIVER))


def verification_source(h: BugHypothesis, verification_sources: Path | None) -> Path:
    """Detection may run on a slice; verification prefers the full file of the same name."""
    if verification_sources is not None:
        full = Path(verification_sources) / Path(h.file).name
        if full.exists():
            return full
    return Path(h.file)


def run_verify(
    hypotheses: list[BugHypothesis], *, llm: SpecLLM, output_dir: Path, verification_sources: Path | None = None,
    completed: dict[int, dict] | None = None, on_result: Callable[[int, dict], None] | None = None,
    strict_sources: bool = False, **kwargs,
) -> list[dict]:
    """``strict_sources`` skips a hypothesis with no file in ``verification_sources`` instead of
    falling back to its detection file (needed when those files are, e.g., the fixed versions)."""
    results: list[dict] = []
    for index, h in enumerate(hypotheses):
        if completed and index in completed:
            results.append(completed[index])
            continue
        path = verification_source(h, verification_sources)
        if strict_sources and path == Path(h.file):
            data = VerifyResult(h, NO_SOURCE, "no file in the verification sources").to_dict()
            results.append(data)
            if on_result is not None:
                on_result(index, data)
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        print(f"[{index + 1}/{len(hypotheses)}] {Path(h.file).name}::{h.function}")
        try:
            data = verify_hypothesis(h, llm=llm, source=source, work_dir=Path(output_dir) / "programs",
                                     **kwargs).to_dict()
        except Exception as exc:  # noqa: BLE001 - one broken case must not end the batch
            data = VerifyResult(h, PIPELINE_ERROR, f"{type(exc).__name__}: {exc}").to_dict()
        print(f"    -> {data['verdict']} {data['reason'][:120]}")
        results.append(data)
        if on_result is not None:
            on_result(index, data)
    return results
