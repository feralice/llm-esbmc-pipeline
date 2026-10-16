import ast
from pathlib import Path

import pytest

from research_pipeline.models import ESBMCDirectResult
from research_pipeline.verify import capabilities
from research_pipeline.verify.capabilities import (
    ACEITA,
    INDETERMINADA,
    PROBES,
    RECUSA,
    Probe,
    active_rules,
    cache_key,
    catalog_digest,
    esbmc_identity,
    named_exceptions,
    probe_capabilities,
    resolve_rules,
    run_probe,
)
from research_pipeline.verify.compat import rewrite_compat
from research_pipeline.verify.rules import (
    ALL_RULES,
    BUILTIN_NAMED_METHODS,
    METHOD_ALIAS,
    NONE_ATTRIBUTE,
    NONE_GUARD_KINDS,
    PERCENT_FORMAT,
)


class _Infeasible(Exception):
    pass


def _cpython_run(probe: Probe) -> BaseException | None:
    """Runs the probe under CPython with its declared nondet values; returns what it raised."""
    values = {"nondet_bool": False, "nondet_int": 0, "nondet_str": "", **dict(probe.cpython)}

    def assume(condition):
        if not condition:
            raise _Infeasible(probe.name)

    namespace = {name: (lambda value=value: value) for name, value in values.items()}
    namespace.update({"__ESBMC_assume": assume, "__name__": "probe"})
    try:
        exec(compile(probe.source(), str(probe.path), "exec"), namespace)
    except _Infeasible:
        raise
    except Exception as exc:  # noqa: BLE001 - the raised exception is the result under test
        return exc
    return None


def test_every_rule_has_a_probe_and_every_probe_a_known_rule():
    assert {p.rule for p in PROBES} == ALL_RULES
    assert len({p.name for p in PROBES}) == len(PROBES)
    assert all(p.path.exists() for p in PROBES)


def test_every_none_probe_has_a_safe_twin_on_the_non_none_branch():
    by_name = {p.name: p for p in PROBES}
    detecting = [p for p in PROBES if p.rule in NONE_GUARD_KINDS and p.exception is not None]
    assert len(detecting) == 17
    for probe in detecting:
        twin = by_name.get(f"{probe.name}_seguro")
        assert twin is not None and twin.rule == probe.rule and twin.exception is None, probe.name
        assert "__ESBMC_assume(" in twin.source() and "is not None" in twin.source()


@pytest.mark.parametrize("probe", PROBES, ids=lambda p: p.name)
def test_cpython_does_what_the_probe_expects(probe):
    raised = _cpython_run(probe)
    if probe.exception is None:
        assert raised is None
    else:
        assert type(raised).__name__ == probe.exception


def test_catalog_digest_changes_with_any_probe():
    before = catalog_digest()
    last = PROBES[-1]
    changed = (*PROBES[:-1], Probe(last.name, last.rule, "ValueError", last.cpython))
    assert catalog_digest(changed) != before
    assert catalog_digest() == before


BY_NAME = {p.name: p for p in PROBES}
NULL = "dereference failure: NULL pointer"


def _fixed_runner(status, properties=(), error=None):
    calls = []

    def run(path, *, esbmc_command, bound, timeout_seconds, output_dir, bound_flags, extra_flags):
        calls.append(Path(path).stem)
        if error is not None:
            raise error
        return ESBMCDirectResult(source_file=str(path), status=status, command=list(esbmc_command), returncode=1,
                                 summary=status, details={"violated_properties": list(properties),
                                                          "violated_files": [Path(path).name] * len(properties)})
    run.calls = calls
    return run


def test_only_exceptions_esbmc_names_count():
    assert named_exceptions(["uncaught exception: AttributeError"]) == {"AttributeError"}
    assert named_exceptions(["TypeError: unsupported operand"]) == {"TypeError"}
    assert named_exceptions(["assertion s != 'ab 7'"]) == {"AssertionError"}
    assert named_exceptions(["division by zero"]) == {"ZeroDivisionError"}
    assert named_exceptions([NULL, "array bounds violated", "unwinding assertion loop 1"]) == frozenset()


def test_an_exception_from_a_frontend_limitation_message_does_not_count():
    assert named_exceptions(["TypeError: object of this type has no len()"]) == frozenset()
    assert named_exceptions(["TypeError: list indices must be integers"]) == frozenset()


@pytest.mark.parametrize(("name", "status", "properties", "expected"), [
    ("none_atributo_local", "violation_found", ["uncaught exception: AttributeError"], ACEITA),
    ("none_atributo_local", "violation_found", [NULL], RECUSA),
    ("none_atributo_local", "violation_found", ["uncaught exception: TypeError"], RECUSA),
    ("none_atributo_local", "no_violation_found", [], RECUSA),
    ("none_atributo_local", "tool_error", [], RECUSA),
    ("none_atributo_local", "timeout", [], INDETERMINADA),
    ("none_atributo_local", "skipped", [], INDETERMINADA),
    ("percent_valor", "no_violation_found", [], ACEITA),
    ("percent_valor", "violation_found", ["assertion s == 'ab 7'"], RECUSA),
    ("none_indice_campo", "violation_found", ["TypeError: object of this type has no len()"], RECUSA),
])
def test_probe_outcome(tmp_path, name, status, properties, expected):
    outcome = run_probe(BY_NAME[name], ["esbmc"], work_dir=tmp_path, runner=_fixed_runner(status, properties))
    assert outcome["outcome"] == expected


def test_a_broken_runner_gives_an_indeterminate_probe(tmp_path):
    runner = _fixed_runner("violation_found", error=RuntimeError("boom"))
    outcome = run_probe(BY_NAME["metodo_get"], ["esbmc"], work_dir=tmp_path, runner=runner)
    assert outcome == {"outcome": INDETERMINADA, "detail": "RuntimeError: boom"}


def test_a_rule_goes_off_only_when_all_its_probes_are_accepted():
    outcomes = {p.name: ACEITA for p in PROBES}
    assert active_rules(outcomes) == frozenset()
    outcomes["none_atributo_campo"] = RECUSA
    assert active_rules(outcomes) == {NONE_ATTRIBUTE}
    del outcomes["metodo_get"]
    assert active_rules(outcomes) == {NONE_ATTRIBUTE, BUILTIN_NAMED_METHODS}
    assert active_rules({}) == ALL_RULES


IDENTITY = {"command": ["esbmc"], "version": "ESBMC version 8.5.0", "files": {"/x/esbmc": "abc"}}


def _probe_runner(refuse=(), timeout=()):
    """Answers each probe as a correct ESBMC would, except the names in ``refuse`` and ``timeout``."""
    calls = []

    def run(path, *, esbmc_command, bound, timeout_seconds, output_dir, bound_flags, extra_flags):
        name = Path(path).stem
        calls.append(name)
        probe = BY_NAME[name]
        if name in timeout:
            status, properties = "timeout", []
        elif (probe.exception is None) != (name in refuse):
            status, properties = "no_violation_found", []
        else:
            status, properties = "violation_found", [f"uncaught exception: {probe.exception or 'AssertionError'}"]
        return ESBMCDirectResult(source_file=str(path), status=status, command=list(esbmc_command), returncode=1,
                                 summary=status, details={"violated_properties": properties,
                                                          "violated_files": [Path(path).name] * len(properties)})
    run.calls = calls
    return run


def test_accepted_probes_switch_every_rule_off_and_the_cache_spares_the_next_batch(tmp_path):
    runner = _probe_runner()
    first = probe_capabilities(["esbmc"], cache_dir=tmp_path, runner=runner, identity=IDENTITY)
    assert first["active_rules"] == [] and first["disabled_rules"] == sorted(ALL_RULES)
    assert sorted(runner.calls) == sorted(BY_NAME)
    again = _probe_runner()
    second = probe_capabilities(["esbmc"], cache_dir=tmp_path, runner=again, identity=IDENTITY)
    assert again.calls == [] and second["active_rules"] == []


def test_one_refused_probe_keeps_only_its_rule_on(tmp_path):
    report = probe_capabilities(["esbmc"], cache_dir=tmp_path, runner=_probe_runner(refuse={"none_atributo_campo"}),
                                identity=IDENTITY)
    assert report["active_rules"] == [NONE_ATTRIBUTE]
    assert report["results"]["none_atributo_campo"]["outcome"] == RECUSA


def test_an_indeterminate_probe_keeps_its_rule_on_and_runs_again_next_batch(tmp_path):
    report = probe_capabilities(["esbmc"], cache_dir=tmp_path, runner=_probe_runner(timeout={"metodo_get"}),
                                identity=IDENTITY)
    assert report["active_rules"] == [BUILTIN_NAMED_METHODS]
    assert report["results"]["metodo_get"]["outcome"] == INDETERMINADA
    again = _probe_runner()
    second = probe_capabilities(["esbmc"], cache_dir=tmp_path, runner=again, identity=IDENTITY)
    assert set(again.calls) == {"metodo_get"} and second["active_rules"] == []


def test_a_corrupt_cache_is_ignored(tmp_path):
    (tmp_path / f"{cache_key(IDENTITY)}.json").write_text("{not json", encoding="utf-8")
    runner = _probe_runner()
    assert probe_capabilities(["esbmc"], cache_dir=tmp_path, runner=runner, identity=IDENTITY)["active_rules"] == []
    assert len(runner.calls) == len(PROBES)


def test_cache_key_changes_with_binary_flags_and_catalog():
    keys = {
        cache_key(IDENTITY),
        cache_key({**IDENTITY, "files": {"/x/esbmc": "abd"}}),
        cache_key({**IDENTITY, "command": ["esbmc", "--no-pointer-check"]}),
        cache_key({**IDENTITY, "version": "ESBMC version 8.6.0"}),
        cache_key(IDENTITY, "outro catálogo"),
        cache_key(IDENTITY, bound=7),
        cache_key(IDENTITY, timeout_seconds=30),
    }
    assert len(keys) == 7


def test_resolve_rules_probes_with_the_run_bound_and_timeout(tmp_path):
    seen = []

    def run(path, *, esbmc_command, bound, timeout_seconds, output_dir, bound_flags, extra_flags):
        seen.append((bound, timeout_seconds))
        return ESBMCDirectResult(source_file=str(path), status="no_violation_found", command=list(esbmc_command),
                                 returncode=0, summary="", details={})

    report = resolve_rules(["esbmc"], cache_dir=tmp_path, runner=run, identity=IDENTITY, bound=7, timeout_seconds=30)
    assert seen and set(seen) == {(7, 30)}
    assert report["key"] == cache_key(IDENTITY, bound=7, timeout_seconds=30)


def test_identity_follows_the_binary_a_wrapper_names(tmp_path):
    binary = tmp_path / "esbmc-real"
    binary.write_bytes(b"v1")
    wrapper = tmp_path / "esbmc.sh"
    wrapper.write_text(f'#!/bin/sh\nexec {binary} --no-pointer-check "$@"\n', encoding="utf-8")
    wrapper.chmod(0o755)
    before = esbmc_identity([str(wrapper)])
    assert str(binary.resolve()) in before["files"]
    binary.write_bytes(b"v2")
    assert cache_key(esbmc_identity([str(wrapper)])) != cache_key(before)


@pytest.mark.parametrize(("kwargs", "reason"), [
    ({"enabled": False}, "sondas desligadas"),
    ({"resumed": True}, "retomada"),
])
def test_resolve_rules_keeps_every_rule_without_probing(tmp_path, kwargs, reason):
    runner = _probe_runner()
    report = resolve_rules(["esbmc"], cache_dir=tmp_path, runner=runner, identity=IDENTITY, **kwargs)
    assert report["active_rules"] == sorted(ALL_RULES) and reason in report["reason"] and runner.calls == []


def test_resolve_rules_without_esbmc_or_on_a_failure_keeps_every_rule(tmp_path, monkeypatch):
    assert resolve_rules(None, cache_dir=tmp_path)["active_rules"] == sorted(ALL_RULES)

    def broken(esbmc_command, timeout_seconds=30):
        raise OSError("disk")

    monkeypatch.setattr(capabilities, "esbmc_identity", broken)
    report = resolve_rules(["esbmc"], cache_dir=tmp_path)
    assert report["active_rules"] == sorted(ALL_RULES) and "OSError" in report["reason"]


PERCENT_SHAPES = ("percent", "percent_float_s", "percent_d_float", "percent_d_bool", "percent_porcento",
                  "percent_operando_unico", "percent_r")


def _parameter_types(source: str) -> dict[str, dict[str, str]]:
    return {f.name: {a.arg: ast.unparse(a.annotation) for a in f.args.args if a.annotation}
            for f in ast.walk(ast.parse(source)) if isinstance(f, ast.FunctionDef)}


def test_every_percent_shape_the_rule_lowers_has_a_value_pair_the_rule_rewrites():
    percent = {p.name: p for p in PROBES if p.rule == PERCENT_FORMAT}
    assert set(percent) == {f"{shape}_{kind}" for shape in PERCENT_SHAPES for kind in ("valor", "violacao")}
    for shape in PERCENT_SHAPES:
        assert percent[f"{shape}_valor"].exception is None
        assert percent[f"{shape}_violacao"].exception == "AssertionError"
    for probe in percent.values():
        source = probe.source()
        assert rewrite_compat(source, parameter_types=_parameter_types(source))[1] == ["compat_percent_format:1"], \
            probe.name


def test_the_alias_probes_cover_repr_bound_to_str_and_the_rule_rewrites_them():
    alias = {p.name: p for p in PROBES if p.rule == METHOD_ALIAS}
    assert {"alias_repr_divisao", "alias_repr_valor"} <= set(alias)
    assert alias["alias_repr_divisao"].exception == "ZeroDivisionError" and alias["alias_repr_valor"].exception is None
    for name in ("alias_repr_divisao", "alias_repr_valor"):
        source = alias[name].source()
        assert "__repr__ = __str__" in source and "repr(" in source
        assert rewrite_compat(source)[1] == ["compat_method_alias:1"]


def test_the_cache_is_written_through_a_temp_file_of_its_own(tmp_path):
    (tmp_path / f"{cache_key(IDENTITY)}.tmp").mkdir()
    probe_capabilities(["esbmc"], cache_dir=tmp_path, runner=_probe_runner(), identity=IDENTITY)
    again = _probe_runner()
    probe_capabilities(["esbmc"], cache_dir=tmp_path, runner=again, identity=IDENTITY)
    assert again.calls == []
