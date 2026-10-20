"""One bounded attempt loop per hypothesis: spec (LLM) -> program -> ESBMC -> replay -> verdict."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


from research_pipeline.models import ESBMCDirectResult

from ..scan.callgraph import CallGraph
from .astutil import undefined_globals
from .caller_facts import collect_facts, render_section, usage_problems
from .grounding import Grounded, GroundingFailure, ground
from .hypothesis import VALUE_ORACLE, BugHypothesis
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
    VALUE_VIOLATION,
    EsbmcReading,
    final_verdict,
)
from .render import DRIVER, Program, RenderError, render_program
from .rules import ALL_RULES
from .replay import ReplayVerdict, concrete_replay, counterexample_seeds
from .spec import InputSpec, ignored_keys, parse_spec, resolved_types, shape_unpacked, spec_problems
from .string_witness import string_witness
from .value_oracle import apply_control, check_fixed, esbmc_hits_property, value_verdict

SYSTEM_PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "input_spec_prompt.txt").read_text(encoding="utf-8")
VALUE_PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "value_property_prompt.txt").read_text(encoding="utf-8")
STRATEGIES = ("repair", "resample")
SPEC_CONTEXTS = ("none", "callers")
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
    spec_context: dict = field(default_factory=dict)
    control: dict = field(default_factory=dict)
    healing: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "hypothesis": self.hypothesis.to_dict(), "verdict": self.verdict, "reason": self.reason,
            "attempts": self.attempts, "llm_calls": sum(1 for a in self.attempts if "spec" in a),
            "transforms": list(self.transforms), "program_path": self.program_path, "replay": self.replay,
            "tokens": self.tokens, "seconds": round(self.seconds, 3),
            **({"pytest": self.pytest} if self.pytest else {}),
            **({"spec_context": self.spec_context} if self.spec_context else {}),
            **({"control": self.control} if self.control else {}),
            **({"healing": self.healing} if self.healing else {}),
        }


def _user_prompt(grounded: Grounded, previous: str, feedback: str, context: str = "") -> str:
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
    if h.oracle == VALUE_ORACLE:
        parts.insert(3, 'Kind: wrong result (nothing raises). Also give "returns" and "postcondition".')
    if context:
        parts.append(context)
    if previous:
        parts.append(f"Previous attempt:\n{previous}\nError:\n{feedback}")
    return "\n\n".join(parts)


def _placeholder_spec(grounded: Grounded) -> InputSpec:
    params, attrs = resolved_types(InputSpec({}, {}, ()), grounded)
    return shape_unpacked(InputSpec({n: "int" for n, t in params.items() if not t},
                                    {n: "int" for n, t in attrs.items() if not t},
                                    (), {key: "int" for key in grounded.stub_keys}), grounded)


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


def precheck(h: BugHypothesis, source: str, esbmc_command: list[str] | None = None,
             rules: frozenset[str] = ALL_RULES) -> tuple[Grounded | None, str, str]:
    """Everything decidable before spending an LLM call; returns (grounded, "", "") when ready.
    With ``esbmc_command``, library members ESBMC cannot convert are stubbed before the LLM sees the slice."""
    refused: frozenset[str] = frozenset()
    for _ in range(_ORACLE_ROUNDS):
        grounded = ground(h, source, refused, rules=rules)
        if isinstance(grounded, GroundingFailure):
            return None, UNSUPPORTED if grounded.unsupported else GROUNDING_FAILED, grounded.reason
        try:
            probe = render_program(grounded, _placeholder_spec(grounded), rules=rules)
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
    strategy: str = "repair", rules: frozenset[str] = ALL_RULES, spec_context: str = "none",
    graph: CallGraph | None = None, fixed_source: str | None = None,
) -> VerifyResult:
    """``strategy="resample"`` spends the same call budget on independent samples that never see
    the previous error: the baseline a guided repair has to beat (Olausson et al., ICLR 2024).
    ``spec_context="callers"`` shows the call sites and usage facts and rejects a spec they contradict;
    ``graph`` is the repository's call graph (scan mode), else the callers come from ``source`` alone.
    ``fixed_source`` (evaluation only) is the fixed version of the file: a wrong-result hypothesis is
    replayed on it, after the LLM is done, with the input that broke the original."""
    if strategy not in STRATEGIES:
        raise ValueError(f"strategy must be one of {STRATEGIES}")
    if spec_context not in SPEC_CONTEXTS:
        raise ValueError(f"spec_context must be one of {SPEC_CONTEXTS}")
    started = time.monotonic()
    result = VerifyResult(h, "")
    value = h.oracle == VALUE_ORACLE
    system = f"{SYSTEM_PROMPT}\n{VALUE_PROMPT}" if value else SYSTEM_PROMPT

    def finish(verdict: str, reason: str = "") -> VerifyResult:
        result.verdict, result.reason, result.seconds = verdict, reason, time.monotonic() - started
        return result

    grounded, verdict, reason = precheck(h, source, esbmc_command, rules)
    if grounded is None:
        return finish(verdict, reason)

    facts = collect_facts(h, grounded, source, graph=graph) if spec_context == "callers" else None
    context = render_section(facts, grounded) if facts is not None else ""
    if facts is not None:
        result.spec_context = {"call_sites": facts.site_count, "references": len(facts.references),
                               "chars": len(context)}
    work_dir.mkdir(parents=True, exist_ok=True)
    previous, feedback, last_problems = "", "", []
    for attempt in range(1 + max_repairs):
        shown_previous, shown_feedback = (previous, feedback) if strategy == "repair" else ("", "")
        reply = llm.complete(system, _user_prompt(grounded, shown_previous, shown_feedback, context),
                             json_mode=True)
        result.tokens += int((reply.telemetry or {}).get("total_tokens") or 0)
        record: dict = {"attempt": attempt, "spec": reply.harness, "feedback_given": feedback}
        result.attempts.append(record)
        previous = reply.harness
        try:
            spec = shape_unpacked(parse_spec(reply.harness), grounded)
            problems = spec_problems(spec, grounded, require_property=value)
            if not problems and facts is not None:
                problems = usage_problems(spec, grounded, facts)
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
        program = render_program(grounded, spec, rules=rules)
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
        if replay.status == "not_reproduced" and reading.kind == "violation" and esbmc_command \
                and "nondet_str()" in program.source:
            strings = string_witness(path, esbmc_command=esbmc_command,
                                     bound=how["unwind"] if isinstance(how["unwind"], int) and how["unwind"] else bound,
                                     timeout_seconds=timeout_seconds, work_dir=work_dir / path.stem)
            record["witness_strings"] = strings
            if strings:
                replay = _replay_if_checked(reading, program, grounded, replay_runs, esbmc_output(esbmc), strings)
        result.replay = replay.to_dict()
        if value:
            return finish(*_value_outcome(result, reading, esbmc, program, grounded, replay, fixed_source))
        verdict = final_verdict(reading, replay)
        if verdict == CONFIRMED and esbmc_command:
            result.pytest = _pytest_for(program, grounded, spec, replay, esbmc_command, bound, work_dir)
        return finish(verdict, reading.message)
    if last_problems and all("unsupported type" in p for p in last_problems):
        # The model kept naming a real type the harness cannot build: a method limit, not a model error.
        return finish(UNSUPPORTED, "input type outside the supported subset: " + "; ".join(last_problems))
    return finish(SPEC_FAILED, feedback)


def _value_outcome(result: VerifyResult, reading: EsbmcReading, esbmc: ESBMCDirectResult, program: Program,
                   grounded: Grounded, replay: ReplayVerdict, fixed_source: str | None) -> tuple[str, str]:
    verdict = value_verdict(reading, esbmc_hits_property(esbmc, program.property_line), replay)
    if verdict != VALUE_VIOLATION or fixed_source is None:
        return verdict, reading.message
    control = check_fixed(program, grounded.hypothesis.function, grounded.method_name, fixed_source,
                          replay.inputs)
    result.control = control.to_dict()
    verdict, why = apply_control(verdict, control)
    return verdict, why or reading.message


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
                       log: str = "", strings: list[str] | None = None) -> ReplayVerdict:
    """``strings``: the counterexample's nondet strings, which ESBMC's own trace does not print."""
    if reading.kind not in {"violation", "artifact", "safe"}:
        return ReplayVerdict("unavailable", reason="ESBMC produced no verdict to validate")
    seeds = counterexample_seeds(log, DRIVER)
    if strings:
        seeds["str"] = strings
    return concrete_replay(program, grounded.method_name, max_runs=runs, seeds=seeds)


def verification_source(h: BugHypothesis, verification_sources: Path | None) -> Path:
    """Detection may run on a slice; verification prefers the full file of the same name."""
    if verification_sources is not None:
        full = Path(verification_sources) / Path(h.file).name
        if full.exists():
            return full
    return Path(h.file)


def _fixed_source(h: BugHypothesis, fixed_sources: Path | None) -> str | None:
    """Only a wrong-result hypothesis gets the fixed file, and only for the control after the LLM."""
    if fixed_sources is None or h.oracle != VALUE_ORACLE:
        return None
    path = Path(fixed_sources) / Path(h.file).name
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else None


def run_verify(
    hypotheses: list[BugHypothesis], *, llm: SpecLLM, output_dir: Path, verification_sources: Path | None = None,
    completed: dict[int, dict] | None = None, on_result: Callable[[int, dict], None] | None = None,
    strict_sources: bool = False, fixed_sources: Path | None = None, healer=None, heal_rounds: int = 3,
    **kwargs,
) -> list[dict]:
    """``strict_sources`` skips a hypothesis with no file in ``verification_sources`` instead of
    falling back to its detection file (needed when those files are, e.g., the fixed versions).
    ``healer`` (verify/healing.py) repairs a hypothesis ESBMC never reached, up to ``heal_rounds`` times."""
    from .healing import verify_with_healing  # healing imports this module
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
            common = {"llm": llm, "work_dir": Path(output_dir) / "programs",
                      "fixed_source": _fixed_source(h, fixed_sources), **kwargs}
            data = (verify_with_healing(h, healer=healer, source=source, rounds=heal_rounds, **common)
                    if healer is not None else verify_hypothesis(h, source=source, **common)).to_dict()
        except Exception as exc:  # noqa: BLE001 - one broken case must not end the batch
            data = VerifyResult(h, PIPELINE_ERROR, f"{type(exc).__name__}: {exc}").to_dict()
        print(f"    -> {data['verdict']} {data['reason'][:120]}")
        results.append(data)
        if on_result is not None:
            on_result(index, data)
    return results
