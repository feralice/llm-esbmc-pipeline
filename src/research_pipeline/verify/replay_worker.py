"""Run a verification program under CPython, enumerating small values for every nondet call.

Standalone script (run with ``python -I -S``): argv = program, config JSON, output JSON.
"""

import __future__
import io
import json
import random
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
RANDOM_MAX_LIST = 5
RUN_SECONDS = 0.5


class _Discard(BaseException):
    """Not an Exception, so target code's ``except Exception`` cannot swallow or convert it."""


class _Inconsistent(BaseException):
    """A fixed input sequence that does not fit the program's nondet calls."""


class _Chooser:
    def __init__(self, vector):
        self.vector = vector
        self.sizes = []
        self.values = []

    def pick(self, domain):
        index = len(self.sizes)
        choice = self.vector[index] if index < len(self.vector) else 0
        self.sizes.append(len(domain))
        self.values.append(domain[choice])
        return domain[choice]

    def pick_length(self, limit):
        return self.pick(list(range(limit + 1)))


class _RandomChooser:
    def __init__(self, rng):
        self.rng = rng
        self.values = []

    def pick(self, domain):
        value = self.rng.choice(domain)
        self.values.append(value)
        return value

    def pick_length(self, limit):
        return self.pick(list(range(limit + 1)))


class _FixedChooser:
    """Returns ``inputs`` in call order; a value of another type, a list longer than the harness
    allows, or a sequence that ends early or late makes the replay unavailable, never a search."""

    def __init__(self, inputs):
        self.inputs = list(inputs)
        self.values = []

    def _next(self):
        if len(self.values) == len(self.inputs):
            raise _Inconsistent("the program asked for more values than the fixed input has")
        value = self.inputs[len(self.values)]
        self.values.append(value)
        return value

    def pick(self, domain):
        value = self._next()
        if type(value) is not type(domain[0]):  # bool is not int here
            raise _Inconsistent(f"value {value!r} does not fit a nondet {type(domain[0]).__name__}")
        return value

    def pick_length(self, limit):
        value = self._next()
        if type(value) is not int or not 0 <= value <= limit:
            raise _Inconsistent(f"list length {value!r} outside 0..{limit}")
        return value


def _random_domains(rng):
    """Wider values than DOMAINS: edges and sampled ints, strings with separators and non-ASCII."""
    edges = [0, 1, -1, 2, -2, 3, 7, 10, 100, 127, 128, 255, 256, 1000, -1000, 2**31 - 1, -2**31, 2**63 - 1]
    return {
        int: edges + [rng.randint(-10**6, 10**6) for _ in range(30)],
        float: [0.0, -0.0, 0.5, -1.5, 1.0, -1.0, 1e9, -1e-9, 3.14, float("inf"), float("-inf"), float("nan")],
        bool: [False, True],
        str: ["", "a", " ", "0", "-1", "1.5", "abc", "a b", "a.b", "a,b", "a/b", "a\\b", "\n", "\t", "\u00e9",
              "%s", "{}", "'", '"', " x ", "A" * 40, "None", "true"],
    }


def _next_vector(vector, sizes):
    used = [vector[i] if i < len(vector) else 0 for i in range(len(sizes))]
    for j in range(len(sizes) - 1, -1, -1):
        if used[j] + 1 < sizes[j]:
            return used[:j] + [used[j] + 1]
    return None


def _intrinsics(chooser, domains=None, max_list=MAX_LIST):
    domains = domains or DOMAINS

    def nondet_list(size=MAX_LIST, elem_type=0):
        kind = type(elem_type) if type(elem_type) in domains else int
        length = chooser.pick_length(min(size, max_list))
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


_DISCARDED = "discarded"


def _run_once(code, chooser, domains, max_list, target):
    """One execution: None when it ended normally, _DISCARDED when an assume or the per-run timer
    cut it, else the crash record."""
    function, spans, first, last = target
    real_stdout = sys.stdout
    sys.stdout = io.StringIO()
    signal.setitimer(signal.ITIMER_REAL, RUN_SECONDS)
    try:
        exec(code, {"__name__": "__main__", **_intrinsics(chooser, domains, max_list)})  # noqa: S102 - the replay is the point; host_replay_problem gates it
    except _Discard:
        return _DISCARDED
    except Exception as exc:  # noqa: BLE001 - every crash is evidence
        frames = [f for f in traceback.extract_tb(exc.__traceback__) if f.filename == "<program>"]
        # Name and line range together: another class's method may share the name.
        in_target = [f for f in frames if f.name == function and (not last or first <= f.lineno <= last)]
        line = in_target[-1].lineno if in_target else (frames[-1].lineno if frames else None)
        reproduced = bool(in_target) and any(start <= line <= end for start, end in spans)
        return {"status": "reproduced" if reproduced else "other_failure",
                "exception_type": type(exc).__name__, "line": line, "inputs": chooser.values}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        sys.stdout = real_stdout
    return None


def _fixed(code, inputs, target):
    """Exactly one run with ``inputs``: no search fills in what the sequence does not say."""
    chooser = _FixedChooser(inputs)
    try:
        outcome = _run_once(code, chooser, DOMAINS, 10**6, target)
    except _Inconsistent as exc:
        return {"status": "unavailable", "reason": str(exc), "inputs": inputs}
    if outcome != _DISCARDED and len(chooser.values) < len(inputs):
        return {"status": "unavailable", "reason": "the fixed input has more values than the program used",
                "inputs": inputs}
    return outcome if isinstance(outcome, dict) else {"status": "not_reproduced", "inputs": chooser.values}


def main(program_path, config_path, output_path):
    with open(program_path, encoding="utf-8") as handle:
        # Annotations stay unevaluated: ESBMC models types (e.g. uint64) CPython does not define.
        code = compile(handle.read(), "<program>", "exec", flags=__future__.annotations.compiler_flag)
    with open(config_path, encoding="utf-8") as handle:
        config = json.load(handle)
    first, last = config.get("range") or (0, 0)
    target = (config["function"], config["spans"], first, last)
    signal.signal(signal.SIGALRM, _timeout)
    if config.get("inputs") is not None:
        result = {**_fixed(code, config["inputs"], target), "runs": 1}
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(result, handle)
        return
    deadline = time.monotonic() + config.get("deadline_seconds", 15)
    other, result, runs = None, None, 0
    # The counterexample's values get a short pass of their own; the default search then runs whole.
    passes = ([(_seeded(config["seeds"]), SEED_RUNS)] if any(config.get("seeds", {}).values()) else [])
    if not config.get("seeds_only"):
        passes.append((DOMAINS, config["max_runs"]))
    if config.get("random_runs") and not config.get("seeds_only"):
        rng = random.Random(config.get("seed", 0))
        passes.append((_random_domains(rng), config["random_runs"], rng))
    for index, (domains, budget, *random_pass) in enumerate(passes):
        # Each pass gets its share of the time left, so a slow exhaustive pass cannot starve the random one.
        pass_deadline = time.monotonic() + (deadline - time.monotonic()) / (len(passes) - index)
        vector, used = [], 0
        while vector is not None and used < budget and time.monotonic() < pass_deadline:
            chooser = _RandomChooser(random_pass[0]) if random_pass else _Chooser(vector)
            runs, used = runs + 1, used + 1
            outcome = _run_once(code, chooser, domains, RANDOM_MAX_LIST if random_pass else MAX_LIST, target)
            if isinstance(outcome, dict):
                if outcome["status"] == "reproduced":
                    result = outcome
                    break
                other = other or outcome
            vector = [] if random_pass else _next_vector(vector, chooser.sizes)
        if result:
            break
    if result is None:
        result = other if other else {"status": "not_reproduced"}
    result["runs"] = runs
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle)


if __name__ == "__main__":
    main(*sys.argv[1:4])
