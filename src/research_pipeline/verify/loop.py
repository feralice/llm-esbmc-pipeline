"""One bounded attempt loop per hypothesis: spec (LLM) -> program -> ESBMC -> replay -> verdict."""

from __future__ import annotations

import dataclasses
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


from research_pipeline.models import ESBMCDirectResult

from ..llm.rate_limit import UsageLimitReached
from ..scan.callgraph import CallGraph
from .astutil import undefined_globals
from .attempts import prepare_spec
from .caller_facts import collect_facts, render_section
from .grounding import Grounded, GroundingFailure, ground
from .external_origin import stubbed_response_origin
from .hypothesis import VALUE_ORACLE, BugHypothesis
from .llm_client import SynthResult, _bound_untrusted
from .esbmc_run import check, esbmc_output
from .oracle import convert, refusals
from .pytest_gen import pytest_reproducer
from .outcome import (
    CONFIRMED,
    DEPENDS_ON_LIBRARY,
    ESBMC_TIMEOUT,
    GROUNDING_FAILED,
    MISSING_DEPENDENCY,
    NO_SOURCE,
    OTHER_FAILURE,
    PIPELINE_ERROR,
    SPEC_FAILED,
    UNSUPPORTED,
    EsbmcReading,
    final_verdict,
)
from .render import DRIVER, Program, RenderError, render_program
from .rules import ALL_RULES
from .replay import ReplayVerdict, concrete_replay, counterexample_seeds
from .spec import InputSpec, ignored_keys, resolved_types, shape_unpacked
from .string_witness import string_witness
from .value_oracle import value_outcome

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
    notebook_version: str = ""
    harness_state: dict | None = None

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
            **({"notebook_version": self.notebook_version} if self.notebook_version else {}),
            **({"harness_state": self.harness_state} if self.harness_state is not None else {}),
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


def _with_exception_class_stubs(spec: InputSpec, grounded: Grounded) -> InputSpec:
    """The original body may name library exception classes (``except json.JSONDecodeError``) that the simplified
    copy dropped; they are never called, so the type given to them does not matter."""
    missing = {key: "int" for key in grounded.stub_keys
               if key not in spec.stubs and key.rsplit(".", 1)[-1].endswith(("Error", "Exception", "Warning"))}
    return dataclasses.replace(spec, stubs={**spec.stubs, **missing}) if missing else spec


def with_original_replay(program: Program, h: BugHypothesis, original: str, spec: InputSpec,
                         rules: frozenset[str] = ALL_RULES) -> Program | str:
    """``program`` with its replay copy rebuilt from ``original``, the source before self-healing simplified the
    target's body: ESBMC checks the simplified copy, CPython replays the real one. A string says why it cannot."""
    grounded = ground(h, original, rules=rules)
    if isinstance(grounded, GroundingFailure):
        return f"original body cannot be grounded for the replay: {grounded.reason}"
    spec = _with_exception_class_stubs(spec, grounded)
    try:
        twin = render_program(grounded, spec, rules=rules)
    except RenderError as exc:
        return f"original body cannot be rendered for the replay: {exc}"
    return dataclasses.replace(
        program, replay_source=twin.replay_source or twin.source,
        replay_target_spans=twin.replay_target_spans or twin.target_spans,
        replay_target_range=twin.replay_target_range or twin.target_range,
        replay_property_line=twin.replay_property_line if twin.replay_source else twin.property_line)


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
    graph: CallGraph | None = None, fixed_source: str | None = None, replay_source: str | None = None,
    repository_context: str = "",
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
                               "caller_guards": [f"{p}: {form}" for p, form in facts.guards],
                               "chars": len(context)}
    if repository_context:
        context = f"{context}\n\n{repository_context}" if context else repository_context
        result.spec_context["repository_evidence_chars"] = len(repository_context)
    work_dir.mkdir(parents=True, exist_ok=True)
    previous, feedback, last_problems = "", "", []
    refinements, limit, held, reached = 0, 1 + max_repairs, None, ""
    attempt = -1
    while (attempt := attempt + 1) < limit:
        shown_previous, shown_feedback = (previous, feedback) if strategy == "repair" else ("", "")
        reply = llm.complete(system, _user_prompt(grounded, shown_previous, shown_feedback, context),
                             json_mode=True)
        result.tokens += int((reply.telemetry or {}).get("total_tokens") or 0)
        record: dict = {"attempt": attempt, "spec": reply.harness, "feedback_given": feedback}
        result.attempts.append(record)
        previous = reply.harness
        spec, problems, assumed = prepare_spec(reply.harness, grounded, facts, require_property=value)
        if problems:
            record["problems"] = problems
            feedback = "The JSON was rejected: " + "; ".join(problems)
            last_problems = problems
            continue
        last_problems = []
        if spec is None:
            raise RuntimeError("prepare_spec returned no specification without problems")
        if assumed:
            # The callers' guards on the arguments, as the harness's assumptions (caller_facts.caller_guards).
            spec = dataclasses.replace(spec, assumptions=(*spec.assumptions, *assumed))
            record["caller_assumptions"] = list(assumed)
        ignored = ignored_keys(spec, grounded)
        if ignored:
            record["ignored"] = ignored
        program = render_program(grounded, spec, rules=rules)
        _, attributes = resolved_types(spec, grounded)
        result.harness_state = {"generated_attributes": {
            name: kind for name, kind in attributes.items()
            if grounded.has_receiver and name not in grounded.called_attrs
        }, "dict_assignments": list(grounded.dict_assignments),
            "assumed_dict_keys": {name: list(keys) for name, keys in grounded.required_dict_keys}}
        no_replay = ""
        if replay_source is not None:
            rebuilt = with_original_replay(program, h, replay_source, spec, rules)
            program, no_replay = (program, rebuilt) if isinstance(rebuilt, str) else (rebuilt, "")
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
        if reading.kind == "repairable" and attempt - refinements < max_repairs:
            feedback = "ESBMC rejected the program: " + _with_line_context(reading.message, program)
            reached = reading.message
            continue
        replay = (ReplayVerdict("unavailable", reason=no_replay) if no_replay
                  else _replay_if_checked(reading, program, grounded, replay_runs, esbmc_output(esbmc)))
        if replay.status in {"not_reproduced", "other_failure"} and reading.kind == "violation" and esbmc_command \
                and "nondet_str()" in program.source:
            witness_bound = how["unwind"] if isinstance(how["unwind"], int) and how["unwind"] else bound
            witness_timeout = min(timeout_seconds, 30) if how.get("partial_timeout") else timeout_seconds
            for multi, seconds in ((False, witness_timeout), (True, timeout_seconds)):
                strings = string_witness(path, esbmc_command=esbmc_command, bound=witness_bound,
                                         timeout_seconds=seconds, work_dir=work_dir / path.stem, multi_property=multi)
                record["witness_strings_multi" if multi else "witness_strings"] = strings
                if not strings:
                    continue
                retried = _replay_if_checked(reading, program, grounded, replay_runs, esbmc_output(esbmc), strings)
                # Only a reproduction replaces an other_failure: a miss would turn OTHER_FAILURE into UNVALIDATED.
                if retried.status == "reproduced" or replay.status == "not_reproduced":
                    replay = retried
                if replay.status == "reproduced":
                    break
        result.replay = replay.to_dict()
        if how.get("partial_timeout"):
            if replay.status == "reproduced" and replay.exception_type in reading.exceptions:
                if grounded.entry == "function" and esbmc_command:
                    result.pytest = _pytest_for(program, grounded, spec, replay, esbmc_command,
                                                how["unwind"] if isinstance(how["unwind"], int) else bound,
                                                work_dir)
                return finish(CONFIRMED, "timeout após contraexemplo parcial; exceção reproduzida no CPython: "
                                          + replay.exception_type)
            return finish(ESBMC_TIMEOUT, "ESBMC excedeu o tempo limite; contraexemplo parcial não reproduzido "
                                         "no CPython.")
        if value:
            return finish(*_value_outcome(result, reading, esbmc, program, grounded, replay, fixed_source,
                                           source if replay_source is None else replay_source))
        verdict = final_verdict(reading, replay)
        if verdict == OTHER_FAILURE and held is None and strategy == "repair" and refinements < MAX_REFINEMENTS \
                and _failed_before_target(replay):
            held = (replay.to_dict(), reading.message, result.harness_state)
        if held is not None and verdict != CONFIRMED:
            if verdict == OTHER_FAILURE and refinements < MAX_REFINEMENTS and _failed_before_target(replay):
                refinements, limit = refinements + 1, limit + 1
                record["refinement"] = _refinement_feedback(replay)
                feedback = record["refinement"]
                continue
            result.replay = held[0]
            result.harness_state = held[2]
            return finish(OTHER_FAILURE, held[1])
        if verdict == CONFIRMED:
            origin = stubbed_response_origin(source, grounded, replay.exception_type)
            if origin:
                return finish(DEPENDS_ON_LIBRARY, f"{reading.message}; the dict read comes from the stubbed call "
                                                  f"{origin}(), whose real response the harness does not know")
        if verdict == CONFIRMED and esbmc_command:
            result.pytest = _pytest_for(program, grounded, spec, replay, esbmc_command, bound, work_dir)
        return finish(verdict, reading.message)
    if held is not None:
        result.replay = held[0]
        result.harness_state = held[2]
        return finish(OTHER_FAILURE, held[1])
    if reached and last_problems:
        # An earlier attempt reached ESBMC and was refused; a later spec the checks reject does not undo that.
        return finish(UNSUPPORTED, reached)
    if last_problems and all("unsupported type" in p for p in last_problems):
        # The model kept naming a real type the harness cannot build: a method limit, not a model error.
        return finish(UNSUPPORTED, "input type outside the supported subset: " + "; ".join(last_problems))
    return finish(SPEC_FAILED, feedback)


MAX_REFINEMENTS = 2


def _failed_before_target(replay: ReplayVerdict) -> bool:
    """The replay raised inside the target function but not at the suspect expression."""
    line, span = replay.line, replay.target_range
    return replay.status == "other_failure" and isinstance(line, int) and bool(span) and span[0] <= line <= span[1]


def _refinement_feedback(replay: ReplayVerdict) -> str:
    return (f"ESBMC found a failure, but running the inputs it chose raised {replay.exception_type} "
            f"({replay.message}) at line {replay.line}, not at the suspect expression. Keep the same types and add "
            "an assumption (a condition on parameters or attributes) that excludes the input making that line "
            "fail, so the only failure left is at the suspect expression.")


def _value_outcome(result: VerifyResult, reading: EsbmcReading, esbmc: ESBMCDirectResult, program: Program,
                   grounded: Grounded, replay: ReplayVerdict, fixed_source: str | None,
                   source: str) -> tuple[str, str]:
    verdict, reason, control = value_outcome(reading, esbmc, program, grounded.hypothesis.function,
                                             grounded.method_name, replay, fixed_source, source)
    if control is not None:
        result.control = control.to_dict()
    return verdict, reason


def _pytest_for(program: Program, grounded: Grounded, spec: InputSpec, replay: ReplayVerdict,
                esbmc_command: list[str], bound: int, work_dir: Path) -> dict:
    """ESBMC's pytest generator on the confirmed program, kept only if the test reproduces the bug."""
    if grounded.entry != "function" or any(p.keyword for p in grounded.params):
        return {"status": "unsupported_shape", "path": "", "reason": "ESBMC's generator handles free functions only"}
    params, _ = resolved_types(spec, grounded)
    name = f"bug_{grounded.hypothesis.hypothesis_id}"
    return pytest_reproducer(program, function=grounded.method_name, params=params, exception=replay.exception_type,
                             esbmc_command=esbmc_command, bound=bound, out_dir=work_dir / "pytest" / name, name=name,
                             coroutine=grounded.coroutine)


def _replay_if_checked(reading: EsbmcReading, program: Program, grounded: Grounded, runs: int,
                       log: str = "", strings: list[str] | None = None) -> ReplayVerdict:
    """``strings``: the counterexample's nondet strings, which ESBMC's own trace does not print."""
    if reading.kind not in {"violation", "artifact", "safe"}:
        return ReplayVerdict("unavailable", reason="ESBMC produced no verdict to validate")
    seeds = counterexample_seeds(log, DRIVER)
    if strings:
        seeds["str"] = strings
    return _without_missing_member(concrete_replay(program, grounded.method_name, max_runs=runs, seeds=seeds),
                                   grounded)


_NO_ATTRIBUTE = re.compile(r"has no attribute '(\w+)'")


def _without_missing_member(replay: ReplayVerdict, grounded: Grounded) -> ReplayVerdict:
    """An AttributeError for a member the suspect expression calls on ``self``, which the module never defines
    (inherited from a base class the harness does not have), says nothing about the code: no replay."""
    found = _NO_ATTRIBUTE.search(replay.message or "")
    name = found.group(1) if found else ""
    if (replay.status in {"reproduced", "other_failure"} and replay.exception_type == "AttributeError" and name
            and f"self.{name}(" in grounded.hypothesis.suspect_expression
            and not re.search(rf"\bdef {name}\b|\b{name}\s*=", grounded.module)):
        return ReplayVerdict("unavailable", reason=f"member {name!r} comes from a base class the harness does not model")
    return replay


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
    repository_context=None,
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
            if repository_context is not None:
                common["repository_context"] = repository_context(h)
            data = (verify_with_healing(h, healer=healer, source=source, rounds=heal_rounds, **common)
                    if healer is not None else verify_hypothesis(h, source=source, **common)).to_dict()
        except UsageLimitReached:
            raise
        except Exception as exc:  # noqa: BLE001 - one broken case must not end the batch
            data = VerifyResult(h, PIPELINE_ERROR, f"{type(exc).__name__}: {exc}").to_dict()
        print(f"    -> {data['verdict']} {data['reason'][:120]}")
        results.append(data)
        if on_result is not None:
            on_result(index, data)
    return results
