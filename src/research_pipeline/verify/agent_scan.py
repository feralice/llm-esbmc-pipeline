"""The scan's verifier backed by the harness agent: each hypothesis the scan's detection produced goes to
run_agent_arm, with the same signature as verify.loop.run_verify so execute_scan can take either."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast

from ..llm.rate_limit import UsageLimitReached
from .agent_arm import AGENT_FAILED, RunAgent, run_agent_arm
from .doc_context import documentation_snapshot, relevant_documentation
from .hypothesis import BugHypothesis
from .lessons import round_repairs
from .outcome import PIPELINE_ERROR

# run_agent_arm's reason when the session did not finish; a TimeoutExpired is the case's own result.
_UNFINISHED = "agent did not finish: "


class AgentVerifier(Protocol):
    label: str

    def __call__(self, hypotheses: list[BugHypothesis], *, llm, output_dir: Path,
                 completed: dict[int, dict], on_result: Callable[[int, dict], None], **kwargs) -> list[dict]: ...


def learn_from_rounds(case_dir: Path, data: dict, run_dir: Path) -> int:
    """Queue refused rounds that a later attempt turned into a verdict."""
    from research_pipeline.maintenance.learning import queue_lesson

    return sum(queue_lesson(error=c["erro"], fix=c["diff"], program=c["program"],
                            case=c["caso"], run_dir=run_dir)
               for c in round_repairs(case_dir, data))


def agent_verifier(run_agent: RunAgent, *, esbmc_command: list[str] | None, bound: int, timeout_seconds: int,
                   agent_timeout: int, graph_tool: bool = False, retry: bool = True,
                   model: str | None = None, auto_lessons: bool = False, project_skills: bool = True,
                   skill: bool = True, backend: str = "claude",
                   documentation_root: Path | None = None) -> AgentVerifier:
    """``auto_lessons`` queues candidate repairs without changing the active notebook."""
    docs = documentation_snapshot(documentation_root) if documentation_root is not None else None
    def verify(hypotheses: list[BugHypothesis], *, llm, output_dir: Path, completed: dict[int, dict],
               on_result: Callable[[int, dict], None], **_ignored) -> list[dict]:
        results, cases_dir = [], Path(output_dir) / "agent_cases"
        for index, h in enumerate(hypotheses):
            if index in completed:
                results.append(completed[index])
                continue
            try:
                data = run_agent_arm(h, work_dir=cases_dir, run_agent=run_agent,
                                     esbmc_command=esbmc_command, bound=bound, timeout_seconds=timeout_seconds,
                                     agent_timeout=agent_timeout, project_skills=project_skills, skill=skill,
                                     log_rounds=project_skills,
                                     absolute_logger=backend == "codex", retry=retry, graph_tool=graph_tool,
                                     documentation=(relevant_documentation(docs, documentation_root, Path(h.file),
                                                                           h.function)
                                                    if docs is not None and documentation_root is not None else ""))
                if "skills" in data:
                    data["notebook_version"] = data["skills"].get("reparos-aprendidos", "")
            except UsageLimitReached:
                raise
            except Exception as exc:  # noqa: BLE001 - one broken case must not stop the scan
                data = {"hypothesis": h.to_dict(), "verdict": PIPELINE_ERROR, "reason": f"{type(exc).__name__}: {exc}"}
            reason = data.get("reason", "")
            if data["verdict"] == AGENT_FAILED and reason.startswith(_UNFINISHED) and "TimeoutExpired" not in reason:
                # A usage limit or a crashed session says nothing about the case: --resume runs it again.
                data = {**data, "verdict": PIPELINE_ERROR}
            if auto_lessons and data["verdict"] != PIPELINE_ERROR:
                try:
                    learn_from_rounds(cases_dir / h.hypothesis_id, data, Path(output_dir))
                except (OSError, ValueError) as exc:
                    data["learning_error"] = f"{type(exc).__name__}: {exc}"
            on_result(index, data)
            results.append(data)
        return results
    backend_label = "" if backend == "claude" else f"{backend}:"
    configured = cast(AgentVerifier, verify)  # Python functions carry attributes; the protocol describes that API.
    configured.label = f"agent:{backend_label}{model or 'default'}:graph_tool={graph_tool}:retry={retry}:timeout={agent_timeout}"
    if docs is not None:
        configured.label += f":docs-v1={docs.digest}"
    if auto_lessons:  # off keeps the label of runs made before 05/11, which read a fixed notebook
        configured.label += ":lesson-quarantine-v1:auto_lessons"
    return configured
