"""Run a verification program under CPython, enumerating small values for every nondet call.

Standalone script (run with ``python -I -S``): argv = program, config JSON, output JSON.
"""

import __future__
import io
import json
import signal
import sys
import time
import traceback

DOMAINS = {
    int: [0, 1, -1, 2],
    float: [0.0, 1.0, -1.0],
    bool: [False, True],
    str: ["", "a"],
}
MAX_LIST = 2
RUN_SECONDS = 0.5


class _Discard(BaseException):
    """Not an Exception, so target code's ``except Exception`` cannot swallow or convert it."""


class _Chooser:
    def __init__(self, vector):
        self.vector = vector
        self.sizes = []

    def pick(self, domain):
        index = len(self.sizes)
        choice = self.vector[index] if index < len(self.vector) else 0
        self.sizes.append(len(domain))
        return domain[choice]


def _next_vector(vector, sizes):
    used = [vector[i] if i < len(vector) else 0 for i in range(len(sizes))]
    for j in range(len(sizes) - 1, -1, -1):
        if used[j] + 1 < sizes[j]:
            return used[:j] + [used[j] + 1]
    return None


def _intrinsics(chooser, domains=None):
    domains = domains or DOMAINS

    def nondet_list(size=MAX_LIST, elem_type=0):
        kind = type(elem_type) if type(elem_type) in domains else int
        length = chooser.pick(list(range(min(size, MAX_LIST) + 1)))
        return [chooser.pick(domains[kind]) for _ in range(length)]

    def assume(condition):
        if not condition:
            raise _Discard()

    return {
        "nondet_int": lambda: chooser.pick(domains[int]),
        "nondet_float": lambda: chooser.pick(domains[float]),
        "nondet_bool": lambda: chooser.pick(domains[bool]),
        "nondet_str": lambda: chooser.pick(domains[str]),
        "nondet_list": nondet_list,
        "__ESBMC_assume": assume,
        # Names an agent-written harness imports from ESBMC's Python module.
        "assume": assume,
        "esbmc_assert": _esbmc_assert,
        "__ESBMC_assert": _esbmc_assert,
    }


def _esbmc_assert(condition, message=""):
    if not condition:
        raise AssertionError(message)


def _timeout(_signum, _frame):
    raise _Discard()


SEED_RUNS = 100


def _seeded(seeds):
    """Domains made of ESBMC's counterexample values only (defaults where it gave none)."""
    domains = dict(DOMAINS)
    for kind, values in seeds.items():
        python_type = {"int": int, "float": float}[kind]
        unique = [v for i, v in enumerate(values) if v == v and v not in values[:i]]  # NaN never repeats
        if unique:
            domains[python_type] = unique
    return domains


def main(program_path, config_path, output_path):
    with open(program_path, encoding="utf-8") as handle:
        # Annotations stay unevaluated: ESBMC models types (e.g. uint64) CPython does not define.
        code = compile(handle.read(), "<program>", "exec", flags=__future__.annotations.compiler_flag)
    with open(config_path, encoding="utf-8") as handle:
        config = json.load(handle)
    function, spans, max_runs = config["function"], config["spans"], config["max_runs"]
    first, last = config.get("range") or (0, 0)
    deadline = time.monotonic() + config.get("deadline_seconds", 15)
    signal.signal(signal.SIGALRM, _timeout)
    real_stdout = sys.stdout
    other, result, runs = None, None, 0
    # The counterexample's values get a short pass of their own; the default search then runs whole.
    passes = ([(_seeded(config["seeds"]), SEED_RUNS)] if any(config.get("seeds", {}).values()) else [])
    if not config.get("seeds_only"):
        passes.append((DOMAINS, max_runs))
    for domains, budget in passes:
        vector, used = [], 0
        while vector is not None and used < budget and time.monotonic() < deadline:
            chooser = _Chooser(vector)
            runs, used = runs + 1, used + 1
            sys.stdout = io.StringIO()
            signal.setitimer(signal.ITIMER_REAL, RUN_SECONDS)
            try:
                exec(code, {"__name__": "__main__", **_intrinsics(chooser, domains)})  # noqa: S102 - the replay is the point; host_replay_problem gates it
            except _Discard:
                pass
            except Exception as exc:  # noqa: BLE001 - every crash is evidence
                frames = [f for f in traceback.extract_tb(exc.__traceback__) if f.filename == "<program>"]
                # Name and line range together: another class's method may share the name.
                in_target = [f for f in frames if f.name == function and (not last or first <= f.lineno <= last)]
                line = in_target[-1].lineno if in_target else (frames[-1].lineno if frames else None)
                record = {"exception_type": type(exc).__name__, "line": line, "inputs": vector}
                if in_target and any(start <= line <= end for start, end in spans):
                    result = {"status": "reproduced", **record}
                    break
                other = other or record
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
                sys.stdout = real_stdout
            vector = _next_vector(vector, chooser.sizes)
        if result:
            break
    if result is None:
        result = {"status": "other_failure", **other} if other else {"status": "not_reproduced"}
    result["runs"] = runs
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle)


if __name__ == "__main__":
    main(*sys.argv[1:4])
