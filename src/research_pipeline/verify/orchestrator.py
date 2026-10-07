"""Try the arms ``route`` picks for each result, in order; a formal verdict ends the sequence."""

from __future__ import annotations

from typing import Callable

from .routing import route as default_route

ARM_FAILED = "ARM_FAILED"
_FORMAL = {"CONFIRMED", "NOT_CONFIRMED", "ESBMC_MISSED"}


def _finished(row: dict) -> bool:
    return row.get("complete", False) and all(s["verdict"] != ARM_FAILED for s in row["steps"])


def orchestrate(results: list[dict], *, arms: dict[str, Callable[[dict], dict]], state: dict,
                save: Callable[[], None], route=default_route) -> list[dict]:
    """``state`` is saved after every arm, so a resume reruns only the arms that did not finish or
    failed; arms missing from ``arms`` are skipped."""
    done = state.setdefault("orchestrated", {})
    for result in results:
        key = result["hypothesis"]["hypothesis_id"]
        if key in done and _finished(done[key]):
            continue
        planned = route(result)
        kept = {s["arm"]: s for s in done.get(key, {}).get("steps", []) if s["verdict"] != ARM_FAILED}
        row = {"hypothesis_id": key, "engine_verdict": result["verdict"], "route": list(planned), "steps": [],
               "final": result["verdict"], "complete": False}
        done[key] = row
        for arm in planned:
            if arm not in arms:
                continue
            if arm in kept:
                outcome = {k: v for k, v in kept[arm].items() if k != "arm"}
            else:
                try:
                    outcome = arms[arm](result)
                except Exception as exc:  # noqa: BLE001 - one broken arm must not end the run
                    outcome = {"verdict": ARM_FAILED, "reason": f"{type(exc).__name__}: {exc}"}
            row["steps"].append({"arm": arm, **outcome})
            if outcome["verdict"] != ARM_FAILED:
                row["final"] = outcome["verdict"]
            save()
            if outcome["verdict"] in _FORMAL:
                break
        row["complete"] = True
        save()
    wanted = {r["hypothesis"]["hypothesis_id"] for r in results}
    return [row for key, row in done.items() if key in wanted]
