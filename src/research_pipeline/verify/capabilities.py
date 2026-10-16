"""Capability probes: which harness rules (rules.py) the installed ESBMC still needs.

Each rule has small programs under probes/. A probe is "aceita" when ESBMC reports what CPython does
(the named exception, or no violation for a safe program). A rule is switched off only when every
probe of it is aceita; a refusal, a timeout or a crash keeps it on."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from research_pipeline.models import ESBMCDirectResult

from .diagnose import limitation
from .esbmc_run import Runner, check
from .outcome import EsbmcReading
from .rules import (
    ALL_RULES,
    BUILTIN_NAMED_METHODS,
    CONDITIONAL_ASSIGNMENTS,
    METHOD_ALIAS,
    NONE_ARITHMETIC,
    NONE_ATTRIBUTE,
    NONE_CALL,
    NONE_MEMBERSHIP,
    NONE_ORDERING,
    NONE_SUBSCRIPT,
    PERCENT_FORMAT,
    PROJECT_DECORATORS,
    PROPERTIES_AS_ATTRIBUTES,
)

PROBE_DIR = Path(__file__).resolve().parent / "probes"
ACEITA, RECUSA, INDETERMINADA = "aceita", "recusa", "indeterminada"


@dataclass(frozen=True)
class Probe:
    name: str
    rule: str
    # What CPython raises and a correct ESBMC reports; None: the program is safe.
    exception: str | None
    # Values the CPython check gives each nondet_* call (default False, 0, "").
    cpython: tuple[tuple[str, object], ...] = ()

    @property
    def path(self) -> Path:
        return PROBE_DIR / f"{self.name}.py"

    def source(self) -> str:
        return self.path.read_text(encoding="utf-8")


PROBES = (
    Probe("percent_valor", PERCENT_FORMAT, None, (("nondet_int", 7),)),
    Probe("percent_violacao", PERCENT_FORMAT, "AssertionError", (("nondet_int", 7),)),
    Probe("percent_float_s_valor", PERCENT_FORMAT, None, (('nondet_float', 1.5),)),
    Probe("percent_float_s_violacao", PERCENT_FORMAT, "AssertionError", (('nondet_float', 1.5),)),
    Probe("percent_d_float_valor", PERCENT_FORMAT, None, (('nondet_float', 2.75),)),
    Probe("percent_d_float_violacao", PERCENT_FORMAT, "AssertionError", (('nondet_float', 2.75),)),
    Probe("percent_d_bool_valor", PERCENT_FORMAT, None, (('nondet_bool', True),)),
    Probe("percent_d_bool_violacao", PERCENT_FORMAT, "AssertionError", (('nondet_bool', True),)),
    Probe("percent_porcento_valor", PERCENT_FORMAT, None, (('nondet_int', 5),)),
    Probe("percent_porcento_violacao", PERCENT_FORMAT, "AssertionError", (('nondet_int', 5),)),
    Probe("percent_operando_unico_valor", PERCENT_FORMAT, None, (('nondet_int', 7),)),
    Probe("percent_operando_unico_violacao", PERCENT_FORMAT, "AssertionError", (('nondet_int', 7),)),
    Probe("percent_r_valor", PERCENT_FORMAT, None, (('nondet_int', 7),)),
    Probe("percent_r_violacao", PERCENT_FORMAT, "AssertionError", (('nondet_int', 7),)),
    Probe("alias_de_metodo", METHOD_ALIAS, "ZeroDivisionError"),
    Probe("alias_repr_divisao", METHOD_ALIAS, "ZeroDivisionError"),
    Probe("alias_repr_valor", METHOD_ALIAS, None),
    Probe("metodo_append", BUILTIN_NAMED_METHODS, "ZeroDivisionError"),
    Probe("metodo_get", BUILTIN_NAMED_METHODS, "ZeroDivisionError"),
    Probe("property_decorador", PROPERTIES_AS_ATTRIBUTES, "ZeroDivisionError"),
    Probe("property_funcao", PROPERTIES_AS_ATTRIBUTES, "ZeroDivisionError"),
    Probe("decorador_do_projeto", PROJECT_DECORATORS, "ZeroDivisionError"),
    Probe("condicional_de_funcoes", CONDITIONAL_ASSIGNMENTS, "ZeroDivisionError"),
    Probe("none_atributo_local", NONE_ATTRIBUTE, "AttributeError"),
    Probe("none_atributo_local_seguro", NONE_ATTRIBUTE, None, (("nondet_bool", True),)),
    Probe("none_atributo_campo", NONE_ATTRIBUTE, "AttributeError"),
    Probe("none_atributo_campo_seguro", NONE_ATTRIBUTE, None, (("nondet_bool", True),)),
    Probe("none_indice_local", NONE_SUBSCRIPT, "TypeError"),
    Probe("none_indice_local_seguro", NONE_SUBSCRIPT, None, (("nondet_bool", True),)),
    Probe("none_indice_campo", NONE_SUBSCRIPT, "TypeError"),
    Probe("none_indice_campo_seguro", NONE_SUBSCRIPT, None, (("nondet_bool", True),)),
    Probe("none_len_local", NONE_CALL, "TypeError"),
    Probe("none_len_local_seguro", NONE_CALL, None, (("nondet_bool", True),)),
    Probe("none_int_local", NONE_CALL, "TypeError"),
    Probe("none_int_local_seguro", NONE_CALL, None, (("nondet_bool", True),)),
    Probe("none_float_local", NONE_CALL, "TypeError"),
    Probe("none_float_local_seguro", NONE_CALL, None, (("nondet_bool", True),)),
    Probe("none_int_campo", NONE_CALL, "TypeError"),
    Probe("none_int_campo_seguro", NONE_CALL, None, (("nondet_bool", True),)),
    Probe("none_in_dict_local", NONE_MEMBERSHIP, "TypeError"),
    Probe("none_in_dict_local_seguro", NONE_MEMBERSHIP, None, (("nondet_bool", True),)),
    Probe("none_in_lista_local", NONE_MEMBERSHIP, "TypeError"),
    Probe("none_in_lista_local_seguro", NONE_MEMBERSHIP, None, (("nondet_bool", True),)),
    Probe("none_in_str_local", NONE_MEMBERSHIP, "TypeError"),
    Probe("none_in_str_local_seguro", NONE_MEMBERSHIP, None, (("nondet_bool", True),)),
    Probe("none_in_str_campo", NONE_MEMBERSHIP, "TypeError"),
    Probe("none_in_str_campo_seguro", NONE_MEMBERSHIP, None, (("nondet_bool", True),)),
    Probe("none_ordem_local", NONE_ORDERING, "TypeError"),
    Probe("none_ordem_local_seguro", NONE_ORDERING, None, (("nondet_bool", True),)),
    Probe("none_ordem_campo", NONE_ORDERING, "TypeError"),
    Probe("none_ordem_campo_seguro", NONE_ORDERING, None, (("nondet_bool", True),)),
    Probe("none_soma_local", NONE_ARITHMETIC, "TypeError"),
    Probe("none_soma_local_seguro", NONE_ARITHMETIC, None, (("nondet_bool", True),)),
    Probe("none_produto_local", NONE_ARITHMETIC, "TypeError"),
    Probe("none_produto_local_seguro", NONE_ARITHMETIC, None, (("nondet_bool", True),)),
    Probe("none_soma_campo", NONE_ARITHMETIC, "TypeError"),
    Probe("none_soma_campo_seguro", NONE_ARITHMETIC, None, (("nondet_bool", True),)),
)


def catalog_digest(probes: tuple[Probe, ...] = PROBES) -> str:
    """Changes whenever a probe, its rule, its expectation or its program changes."""
    digest = hashlib.sha256()
    for probe in sorted(probes, key=lambda p: p.name):
        digest.update(repr((probe.name, probe.rule, probe.exception, probe.cpython)).encode("utf-8"))
        digest.update(probe.source().encode("utf-8"))
    return digest.hexdigest()


_UNCAUGHT = re.compile(r"uncaught exception: ([A-Za-z_]\w*)")
_LEADING = re.compile(r"([A-Z]\w*(?:Error|Exception))\b")


def named_exceptions(properties: list[object]) -> frozenset[str]:
    """Exceptions ESBMC names itself. Memory-model messages do not count: without --no-pointer-check a
    None dereference reads as "NULL pointer", which outcome.py maps to AttributeError for the verdict.
    Nor do frontend limitations diagnose.py lists ("TypeError: object of this type has no len()")."""
    names: set[str] = set()
    for text in map(str, properties):
        if limitation(text):
            continue
        match = _UNCAUGHT.search(text) or _LEADING.match(text)
        if match:
            names.add(match.group(1))
        lowered = text.lower()
        if lowered.startswith("assertion "):
            names.add("AssertionError")
        if "division by zero" in lowered:
            names.add("ZeroDivisionError")
    return frozenset(names)


def classify_probe(probe: Probe, result: ESBMCDirectResult, reading: EsbmcReading) -> dict[str, str]:
    detail = f"{reading.kind}: {reading.message}"[:300]
    if reading.kind in {"timeout", "error"}:
        return {"outcome": INDETERMINADA, "detail": detail}
    if probe.exception is None:
        accepted = reading.kind == "safe"
    else:
        accepted = reading.kind == "violation" and probe.exception in named_exceptions(
            list(result.details.get("violated_properties") or []))
    return {"outcome": ACEITA if accepted else RECUSA, "detail": detail}


def run_probe(probe: Probe, esbmc_command: list[str], *, work_dir: Path, runner: Runner | None = None,
              bound: int = 5, timeout_seconds: int = 60) -> dict[str, str]:
    """The probe through the engine's own check(): same bounds, retries and solver fallbacks."""
    try:
        path = Path(work_dir) / f"{probe.name}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(probe.source(), encoding="utf-8")
        result, reading, _ = check(path, esbmc_command=esbmc_command, bound=bound, timeout_seconds=timeout_seconds,
                                   work_dir=Path(work_dir) / probe.name, runner=runner)
    except Exception as exc:  # noqa: BLE001 - a broken probe keeps its rule on and never ends the batch
        return {"outcome": INDETERMINADA, "detail": f"{type(exc).__name__}: {exc}"[:300]}
    return classify_probe(probe, result, reading)


def active_rules(outcomes: dict[str, str], probes: tuple[Probe, ...] = PROBES) -> frozenset[str]:
    """Rules still needed: a rule goes off only when it has probes and every one of them is aceita."""
    off = {rule for rule in ALL_RULES
           if any(p.rule == rule for p in probes)
           and all(outcomes.get(p.name) == ACEITA for p in probes if p.rule == rule)}
    return ALL_RULES - off


_SCRIPT_LIMIT = 64 * 1024
_ABSOLUTE_PATH = re.compile(r"(/[\w.@+-]+(?:/[\w.@+-]+)+)")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def esbmc_identity(esbmc_command: list[str], timeout_seconds: int = 30) -> dict:
    """What decides ESBMC's answers: the command with its flags, ``--version``, and the hash of the
    executable; for a wrapper script, also of every existing file it names (the real binary)."""
    files: dict[str, str] = {}
    executable = shutil.which(esbmc_command[0])
    if executable:
        path = Path(executable).resolve()
        files[str(path)] = _sha256(path)
        head = path.read_bytes() if path.stat().st_size <= _SCRIPT_LIMIT else b""
        if head.startswith(b"#!"):
            for named in _ABSOLUTE_PATH.findall(head.decode("utf-8", errors="replace")):
                target = Path(named)
                if target.is_file():
                    files[str(target.resolve())] = _sha256(target)
    try:
        done = subprocess.run([*esbmc_command, "--version"], capture_output=True, text=True,
                              timeout=timeout_seconds, check=False)
        version = (done.stdout or done.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        version = f"unavailable: {type(exc).__name__}"
    return {"command": list(esbmc_command), "version": version, "files": files}


def cache_key(identity: dict, digest: str | None = None, *, bound: int = 5, timeout_seconds: int = 60) -> str:
    payload = json.dumps({"identity": identity, "probes": digest or catalog_digest(), "bound": bound,
                          "timeout": timeout_seconds}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _load_cache(path: Path) -> dict[str, dict[str, str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, dict):
        return {}
    known = {p.name for p in PROBES}
    return {name: entry for name, entry in results.items()
            if name in known and isinstance(entry, dict) and entry.get("outcome") in {ACEITA, RECUSA}}


def _store_cache(path: Path, key: str, identity: dict, results: dict[str, dict[str, str]]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"key": key, "identity": identity, "created_at": datetime.now(timezone.utc).isoformat(),
                              "results": results}, indent=2, sort_keys=True)
        # A temp file per writer: two batches sharing the cache never write into the same file.
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=f"{key}.",
                                         suffix=".part", delete=False) as handle:
            handle.write(payload)
        Path(handle.name).replace(path)
    except OSError:
        pass  # without a cache the next batch probes again; this batch keeps what it measured


def _report(reason: str, active: frozenset[str], key: str = "", identity: dict | None = None,
            results: dict[str, dict[str, str]] | None = None) -> dict:
    return {"reason": reason, "key": key, "identity": identity or {}, "active_rules": sorted(active),
            "disabled_rules": sorted(ALL_RULES - active), "results": results or {}}


def all_rules_report(reason: str) -> dict:
    return _report(reason, ALL_RULES)


def probe_capabilities(esbmc_command: list[str], *, cache_dir: Path, runner: Runner | None = None,
                       identity: dict | None = None, bound: int = 5, timeout_seconds: int = 60) -> dict:
    """Runs the probes the cache lacks; only aceita and recusa are cached, so an indeterminate probe
    (timeout, crash) is tried again by the next batch."""
    identity = esbmc_identity(esbmc_command) if identity is None else identity
    key = cache_key(identity, bound=bound, timeout_seconds=timeout_seconds)
    path = Path(cache_dir) / f"{key}.json"
    cached = _load_cache(path)
    results = dict(cached)
    pending = [p for p in PROBES if p.name not in results]
    if pending:
        with tempfile.TemporaryDirectory(prefix="esbmc_probes_") as tmp:
            for probe in pending:
                results[probe.name] = run_probe(probe, esbmc_command, work_dir=Path(tmp), runner=runner,
                                                bound=bound, timeout_seconds=timeout_seconds)
    determinate = {name: entry for name, entry in results.items() if entry["outcome"] != INDETERMINADA}
    if determinate != cached:
        _store_cache(path, key, identity, determinate)
    active = active_rules({name: entry["outcome"] for name, entry in results.items()})
    return _report("sondas", active, key, identity, results)


def resolve_rules(esbmc_command: list[str] | None, *, cache_dir: Path, enabled: bool = True,
                  resumed: bool = False, runner: Runner | None = None, identity: dict | None = None,
                  bound: int = 5, timeout_seconds: int = 60) -> dict:
    """The rule set for one batch. Every rule stays on with the probes switched off, on a resume of a
    batch begun before the probes existed, without an ESBMC command, or on any failure of the probes."""
    if not enabled:
        return all_rules_report("sondas desligadas (--no-capability-probes)")
    if resumed:
        return all_rules_report("retomada de lote iniciado sem sondas")
    if not esbmc_command:
        return all_rules_report("sem comando ESBMC")
    try:
        return probe_capabilities(esbmc_command, cache_dir=cache_dir, runner=runner, identity=identity,
                                  bound=bound, timeout_seconds=timeout_seconds)
    except Exception as exc:  # noqa: BLE001 - the probes may switch rules off, never stop a batch
        return all_rules_report(f"falha nas sondas: {type(exc).__name__}: {exc}")
