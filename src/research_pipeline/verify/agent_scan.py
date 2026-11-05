"""The scan's verifier backed by the harness agent: each hypothesis the scan's detection produced goes to
run_agent_arm, with the same signature as verify.loop.run_verify so execute_scan can take either."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ..llm.rate_limit import UsageLimitReached
from .agent_arm import AGENT_FAILED, RunAgent, run_agent_arm
from .hypothesis import BugHypothesis
from .outcome import PIPELINE_ERROR

# run_agent_arm's reason when the session did not finish; a TimeoutExpired is the case's own result.
_UNFINISHED = "agent did not finish: "


def agent_verifier(run_agent: RunAgent, *, esbmc_command: list[str] | None, bound: int, timeout_seconds: int,
                   agent_timeout: int, graph_tool: bool = False, retry: bool = True,
                   model: str | None = None) -> Callable[..., list[dict]]:
    def verify(hypotheses: list[BugHypothesis], *, llm, output_dir: Path, completed: dict[int, dict],
               on_result: Callable[[int, dict], None], **_ignored) -> list[dict]:
        results = []
        for index, h in enumerate(hypotheses):
            if index in completed:
                results.append(completed[index])
                continue
            try:
                data = run_agent_arm(h, work_dir=Path(output_dir) / "agent_cases", run_agent=run_agent,
                                     esbmc_command=esbmc_command, bound=bound, timeout_seconds=timeout_seconds,
                                     agent_timeout=agent_timeout, project_skills=True, log_rounds=True,
                                     retry=retry, graph_tool=graph_tool)
            except UsageLimitReached:
                raise
            except Exception as exc:  # noqa: BLE001 - one broken case must not stop the scan
                data = {"hypothesis": h.to_dict(), "verdict": PIPELINE_ERROR, "reason": f"{type(exc).__name__}: {exc}"}
            reason = data.get("reason", "")
            if data["verdict"] == AGENT_FAILED and reason.startswith(_UNFINISHED) and "TimeoutExpired" not in reason:
                # A usage limit or a crashed session says nothing about the case: --resume runs it again.
                data = {**data, "verdict": PIPELINE_ERROR}
            on_result(index, data)
            results.append(data)
        return results
    verify.label = f"agent:{model or 'default'}:graph_tool={graph_tool}:retry={retry}:timeout={agent_timeout}"
    return verify
