"""Call the true original function with the arguments the harness's driver passes to its target.

Standalone script (run with ``python -I -S``): argv = harness program, config JSON, output JSON.
For each input sequence it runs the harness until the driver calls the target, then calls the harness's
target and the original module's function with those arguments.
"""

import __future__
import importlib.util
import io
import json
import os
import signal
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from replay_worker import RUN_SECONDS, _Discard, _FixedChooser, _intrinsics, _timeout

SCALARS = (int, float, bool, str)


class _Captured(BaseException):
    pass


def _arguments(code, function, first, last, inputs):
    """The harness's target and the scalar arguments of the driver's first call to it, or None."""
    captured = {}

    def tracer(frame, event, _arg):
        info = frame.f_code
        if (event == "call" and info.co_filename == "<program>" and info.co_name == function
                and first <= frame.f_lineno <= last):
            captured["code"] = info
            captured["args"] = [frame.f_locals[name] for name in info.co_varnames[:info.co_argcount]]
            raise _Captured()

    namespace = {"__name__": "__main__", **_intrinsics(_FixedChooser(inputs), None, 10**6)}
    sys.settrace(tracer)
    signal.setitimer(signal.ITIMER_REAL, RUN_SECONDS)
    try:
        exec(code, namespace)  # noqa: S102 - the harness already passed host_replay_problem
    except _Captured:
        pass
    except BaseException:  # noqa: BLE001 - a run that never reaches the target is skipped
        return None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        sys.settrace(None)
    target = namespace.get(function)
    args = captured.get("args")
    if args is None or getattr(target, "__code__", None) is not captured["code"]:
        return None
    if not all(type(a) in SCALARS for a in args):
        return None
    return target, args


def _call(function, args):
    """Status, exception type and the line of ``function`` the exception crosses."""
    signal.setitimer(signal.ITIMER_REAL, RUN_SECONDS)
    try:
        function(*args)
    except _Discard:
        return {"status": "timeout"}
    except BaseException as exc:  # noqa: BLE001 - every exception is the behaviour being compared
        line, tb = None, exc.__traceback__
        while tb is not None:
            if tb.tb_frame.f_code is function.__code__:
                line = tb.tb_lineno
            tb = tb.tb_next
        return {"status": "raised", "exception_type": type(exc).__name__, "line": line}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    return {"status": "ok"}


def _load(path, function):
    sys.path.append(os.path.dirname(path))
    spec = importlib.util.spec_from_file_location("_original_module", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    found = getattr(module, function, None)
    if not callable(found) or not hasattr(found, "__code__"):
        raise LookupError(f"{function} is not a plain function of the module")
    return found


def main(program_path, config_path, output_path):
    with open(program_path, encoding="utf-8") as handle:
        code = compile(handle.read(), "<program>", "exec", flags=__future__.annotations.compiler_flag)
    with open(config_path, encoding="utf-8") as handle:
        config = json.load(handle)
    signal.signal(signal.SIGALRM, _timeout)
    real_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        real = _load(config["module"], config["function"])
    except BaseException as exc:  # noqa: BLE001 - an original that does not import falls back to the stubs
        sys.stdout = real_stdout
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump({"import_error": f"{type(exc).__name__}: {exc}"[:300]}, handle)
        return
    first, last = config["range"]
    results = []
    for inputs in config["sequences"]:
        found = _arguments(code, config["function"], first, last, inputs)
        if found is None:
            results.append(None)
            continue
        target, args = found
        results.append({"inputs": inputs, "args": args, "harness": _call(target, args), "real": _call(real, args)})
    sys.stdout = real_stdout
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump({"results": results}, handle)


if __name__ == "__main__":
    main(*sys.argv[1:4])
