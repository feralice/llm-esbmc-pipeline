"""Container entrypoint; this module is never run by the host pipeline."""

from __future__ import annotations

import contextlib
import inspect
import io
import json
import runpy
import sys
import traceback
from pathlib import Path


def _resolve(namespace: dict, qualified_name: str):
    parts = qualified_name.split(".")
    if len(parts) == 1:
        return namespace[parts[0]]
    if len(parts) == 2:
        cls = namespace[parts[0]]
        signature = inspect.signature(cls)
        signature.bind()
        return getattr(cls(), parts[1])
    raise ValueError("only module functions and one-level class methods are supported")


def _encode(value):
    """Type-tagged JSON form, so 1, 1.0, True and (1,)/[1] never compare equal."""
    if value is None or isinstance(value, (bool, int, str)):
        return [type(value).__name__, value]
    if isinstance(value, float):
        return ["float", repr(value)]
    if isinstance(value, (list, tuple)):
        return [type(value).__name__, [_encode(item) for item in value]]
    if isinstance(value, (set, frozenset)):
        items = [_encode(item) for item in value]
        return [type(value).__name__, sorted(items, key=lambda item: json.dumps(item, sort_keys=True))]
    if isinstance(value, dict):
        return ["dict", [[_encode(key), _encode(item)] for key, item in value.items()]]
    raise TypeError(f"unsupported replay value type: {type(value).__name__}")


def main(argv: list[str]) -> int:
    source_path, function, args_json, kwargs_json, output_path = argv[1:]
    args = json.loads(args_json)
    kwargs = json.loads(kwargs_json)
    stdout = io.StringIO()
    stderr = io.StringIO()
    result: dict[str, object]
    phase = "load"
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            namespace = runpy.run_path(source_path, run_name="<isolated-replay>")
            phase = "resolve"
            target = _resolve(namespace, function)
            inspect.signature(target).bind(*args, **kwargs)
            phase = "call"
            value = target(*args, **kwargs)
    except BaseException as exc:  # noqa: BLE001 -- record exits inside the isolated worker
        location = {}
        frames = traceback.extract_tb(exc.__traceback__)
        if frames:
            frame = frames[-1]
            trace = exc.__traceback__
            while trace.tb_next is not None:
                trace = trace.tb_next
            location = {
                "file": "<candidate>" if Path(frame.filename).resolve() == Path(source_path).resolve() else frame.filename,
                "function": trace.tb_frame.f_code.co_qualname,
                "line": frame.lineno,
                "column": frame.colno,
            }
        result = {
            "kind": "exception" if phase == "call" else "unavailable",
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "exception_location": location,
        }
    else:
        try:
            result = {"kind": "return", "value": _encode(value)}
        except TypeError as exc:
            result = {"kind": "unavailable", "exception_message": str(exc)}
    effects: dict[str, object] = {"stdout": stdout.getvalue(), "stderr": stderr.getvalue()}
    if phase == "call":
        try:
            effects["arguments"] = _encode([list(args), kwargs])
        except TypeError as exc:
            result = {"kind": "unavailable", "exception_message": f"mutated argument: {exc}"}
    result["phase"] = phase
    result["effects"] = effects
    Path(output_path).write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
