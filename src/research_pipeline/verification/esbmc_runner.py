from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import time
from hashlib import sha256
from pathlib import Path

from ..models import ESBMCDirectResult, ESBMCResult


def _bounded_incremental_flags(bound: int) -> list[str]:
    """Return the ESBMC flags that make the configured incremental bound real."""
    if isinstance(bound, bool) or bound < 1:
        raise ValueError("bound deve ser um inteiro maior ou igual a 1")
    return ["--incremental-bmc", "--max-k-step", str(bound)]


def _artifact_stem(file_path: Path) -> str:
    """Return a readable stem with a path hash to avoid cross-directory clashes."""
    digest = sha256(str(file_path.resolve()).encode("utf-8")).hexdigest()[:10]
    return f"{file_path.stem}_{digest}"


def _esbmc_path(file_path: Path) -> Path:
    """Return path relative to cwd when possible — ESBMC behaves differently with absolute paths."""
    try:
        import os
        # relpath correctly handles absolute/relative mix and returns relative if possible
        rel = os.path.relpath(str(file_path), os.getcwd())
        if not rel.startswith(".."):
            return Path(rel)
        return file_path
    except Exception:
        return file_path


# ---------------------------------------------------------------------------
# Legacy helper — ESBMC on original file at module level
# ---------------------------------------------------------------------------

def run_esbmc_direct(
    file_path: str | Path,
    esbmc_command: list[str] | None = None,
    bound: int = 5,
    timeout_seconds: int = 30,
    output_dir: str | Path | None = None,
) -> ESBMCDirectResult:
    """Run ESBMC directly on the original Python file (no instrumentation)."""
    file_path = Path(file_path)
    base_command = list(esbmc_command or ["esbmc"])

    # --multi-property: without it, ESBMC's __ESBMC_cover (implemented internally
    # as an inverted assert) can shadow the harness's own marked assert when both
    # trip on the same input, so "Violated property" reports the cover's own text
    # instead of the marker. With it, both are reported separately (verified
    # empirically 2026-09-04; see docs/experiment_log.md EXP-01).
    command = [*base_command, *_bounded_incremental_flags(bound), "--multi-property", str(file_path)]

    executable = shutil.which(command[0])
    if executable is None:
        return ESBMCDirectResult(
            source_file=str(file_path),
            status="skipped",
            command=command,
            returncode=None,
            summary="ESBMC não encontrado no PATH. Verificação direta não executada.",
        )

    start = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        elapsed = time.monotonic() - start
    except subprocess.TimeoutExpired:
        return ESBMCDirectResult(
            source_file=str(file_path),
            status="timeout",
            command=command,
            returncode=None,
            summary=f"ESBMC direto excedeu o tempo limite de {timeout_seconds}s.",
            time_seconds=float(timeout_seconds),
        )

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    combined = f"{stdout}\n{stderr}"

    status = _classify_esbmc_direct_result(combined, completed.returncode)

    details = _extract_esbmc_details(combined, file_path)
    details["bound"] = bound
    details["generated_vcc_count"] = _extract_generated_vcc_count(combined)
    details["zero_vccs"] = details["generated_vcc_count"] == 0

    # ESBMC returned SUCCESSFUL but issued no verification conditions — not a proof of safety
    if status == "no_violation_found" and details["zero_vccs"]:
        status = "no_vcc_generated"

    raw_log_path = _write_direct_log(file_path, combined, output_dir)

    return ESBMCDirectResult(
        source_file=str(file_path),
        status=status,
        command=command,
        returncode=completed.returncode,
        summary=_summarize_direct(status, details, timeout_seconds),
        time_seconds=round(elapsed, 3),
        stdout=stdout,
        stderr=stderr,
        details=details,
        raw_log_path=str(raw_log_path),
    )


def _classify_esbmc_direct_result(output: str, returncode: int | None) -> str:
    """Classify ESBMC output into one of the five canonical statuses for Flow A."""
    if re.search(
        r"Undefined function .*replacing with assert\(false\)", output, re.IGNORECASE
    ):
        return "unsupported_case"
    if re.search(r"(?:ERROR:\s*)?TypeError:", output):
        return "tool_error"
    if "ERROR:" in output and "VERIFICATION" not in output:
        # Distinguish "unsupported" (missing module/feature) from generic crash
        if "Cannot open file" in output or "not supported" in output.lower():
            return "unsupported_case"
        return "tool_error"
    return _classify_esbmc_result(output, returncode)


def _extract_generated_vcc_count(output: str) -> int | None:
    match = re.search(r"Generated\s+(\d+)\s+VCC(?:\(s\)|s)?", output, re.IGNORECASE)
    if match is None:
        return None
    return int(match.group(1))


def _summarize_direct(status: str, details: dict, timeout_seconds: int = 30) -> str:
    prop_kind = str(details.get("property_kind", "")).strip()
    location  = str(details.get("location", "")).strip()
    zero_vccs = details.get("zero_vccs", False)

    if status == "violation_found":
        base = f"ESBMC direto encontrou violação: {prop_kind}." if prop_kind else "ESBMC direto encontrou violação."
        return f"{base} Local: {location}." if location else base
    if status == "no_violation_found":
        if zero_vccs:
            return (
                "ESBMC direto: sem violação, mas 0 VCCs geradas — prova pode ser vazia "
                "(nenhuma computação relevante sobreviveu ao slicer)."
            )
        return "ESBMC direto: sem violação no bound analisado."
    if status == "no_vcc_generated":
        return "ESBMC direto: 0 VCCs geradas — arquivo sem chamadas verificáveis no nível de módulo."
    if status == "timeout":
        return f"ESBMC direto excedeu o tempo limite de {timeout_seconds}s."
    if status == "tool_error":
        return "ESBMC direto encontrou erro interno (tipo não suportado, annotation ausente, etc.)."
    if status == "unsupported_case":
        return "ESBMC direto: arquivo não suportado (módulo Python ausente ou feature não implementada)."
    return "ESBMC direto: resultado inconclusivo."


def _write_direct_log(file_path: Path, combined: str, output_dir: str | Path | None = None) -> Path:
    if output_dir is not None:
        logs_dir = Path(output_dir) / "esbmc_outputs"
    else:
        # Resolve relative to project root, not CWD
        logs_dir = Path(tempfile.gettempdir()) / "llm-esbmc" / "esbmc_outputs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    target = logs_dir / f"{_artifact_stem(file_path)}_direct.log"
    target.write_text(combined, encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# Flow B — ESBMC with --function (symbolic entry point, no instrumentation)
# ---------------------------------------------------------------------------

# Both Flow A and Flow B use identical flags: symbolic parameters only.
# No cross-property suppression flags — both flows get the same verification conditions.
_FLOW_B_CATEGORY_FLAGS: dict[str, list[str]] = {
    "division_by_zero":    ["--assign-param-nondet"],
    "out_of_bounds":       ["--assign-param-nondet"],
    "assertion_violation": ["--assign-param-nondet"],
    "none_misuse":         ["--assign-param-nondet"],
    "type_mismatch":       ["--assign-param-nondet"],
    "invalid_precondition": ["--assign-param-nondet"],
    "variable_misuse":     ["--assign-param-nondet"],
    "integer_overflow":    ["--assign-param-nondet", "--overflow-check"],
}

_FLOW_A_BASE_FLAGS: list[str] = ["--assign-param-nondet"]


def run_esbmc_on_function(
    file_path: str | Path,
    function_name: str,
    finding_id: str,
    category: str,
    extra_flags: list[str] | None = None,
    esbmc_command: list[str] | None = None,
    bound: int = 5,
    timeout_seconds: int = 30,
    output_dir: str | Path | None = None,
) -> ESBMCResult:
    """Flow B: run ESBMC with --function so parameters become symbolic automatically."""
    file_path = Path(file_path)
    base = list(esbmc_command or ["esbmc"])
    flags = list(_FLOW_B_CATEGORY_FLAGS.get(category, []))
    if extra_flags:
        flags.extend(extra_flags)
    command = [
        *base,
        "--function",
        function_name,
        *_bounded_incremental_flags(bound),
        *flags,
        str(file_path),
    ]

    executable = shutil.which(command[0])
    if executable is None:
        return ESBMCResult(
            finding_id=finding_id,
            status="skipped",
            command=command,
            returncode=None,
            summary="ESBMC não encontrado no PATH. Verificação formal não executada.",
        )

    start = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        elapsed = time.monotonic() - start
    except subprocess.TimeoutExpired:
        return ESBMCResult(
            finding_id=finding_id,
            status="inconclusive",
            command=command,
            returncode=None,
            summary="ESBMC excedeu o tempo limite configurado.",
            time_seconds=float(timeout_seconds),
        )

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    combined = f"{stdout}\n{stderr}"

    if "ERROR:" in combined and "VERIFICATION" not in combined:
        status = "tool_error"
    else:
        status = _classify_esbmc_result(combined, completed.returncode)

    details = _extract_esbmc_details(combined, file_path)
    details["bound"] = bound

    logs_dir = (
        Path(output_dir)
        if output_dir
        else Path(tempfile.gettempdir()) / "llm-esbmc" / "esbmc_function_logs"
    )
    logs_dir.mkdir(parents=True, exist_ok=True)
    raw_log_path = logs_dir / f"{_artifact_stem(file_path)}_{finding_id}.log"
    raw_log_path.write_text(combined, encoding="utf-8")

    return ESBMCResult(
        finding_id=finding_id,
        status=status,
        command=command,
        returncode=completed.returncode,
        summary=_summarize(status, details),
        time_seconds=round(elapsed, 3),
        stdout=stdout,
        stderr=_prettify_output(status, details, raw_log_path),
        details=details,
        raw_log_path=str(raw_log_path),
    )


def run_esbmc_function_baseline(
    file_path: str | Path,
    function_names: list[str],
    esbmc_command: list[str] | None = None,
    bound: int = 5,
    timeout_seconds: int = 30,
    output_dir: str | Path | None = None,
) -> ESBMCDirectResult:
    """Flow A: run ESBMC with --function for each function, without LLM guidance."""
    file_path = Path(file_path)
    unique_names = list(dict.fromkeys(function_names))
    command = [
        *(esbmc_command or ["esbmc"]),
        "--function",
        "<each-function>",
        *_bounded_incremental_flags(bound),
        str(file_path),
    ]

    if not unique_names:
        return ESBMCDirectResult(
            source_file=str(file_path),
            status="skipped",
            command=command,
            returncode=None,
            summary="ESBMC Flow A: nenhuma função candidata encontrada.",
            details={
                "mode": "function_baseline",
                "bound": bound,
                "function_count": 0,
                "functions": [],
            },
        )

    start = time.monotonic()
    results = [
        run_esbmc_on_function(
            file_path=file_path,
            function_name=function_name,
            finding_id=f"flow_a_{function_name}",
            category="",
            extra_flags=_FLOW_A_BASE_FLAGS,
            esbmc_command=esbmc_command,
            bound=bound,
            timeout_seconds=timeout_seconds,
            output_dir=output_dir,
        )
        for function_name in unique_names
    ]
    elapsed = time.monotonic() - start

    statuses = [r.status for r in results]
    if any(status == "violation_found" for status in statuses):
        status = "violation_found"
    elif all(status == "skipped" for status in statuses):
        status = "skipped"
    elif any(status == "no_violation_found" for status in statuses):
        status = "no_violation_found"
    elif all(status == "tool_error" for status in statuses):
        status = "tool_error"
    else:
        status = "inconclusive"

    violating = [
        name for name, result in zip(unique_names, results)
        if result.status == "violation_found"
    ]
    details = {
        "mode": "function_baseline",
        "bound": bound,
        "function_count": len(unique_names),
        "functions": [
            {
                "name": name,
                "status": result.status,
                "summary": result.summary,
                "command": result.command,
                "raw_log_path": result.raw_log_path,
                "property_kind": result.details.get("property_kind", ""),
                "property_text": result.details.get("property_text", ""),
                "location": result.details.get("location", ""),
            }
            for name, result in zip(unique_names, results)
        ],
        "violating_functions": violating,
    }

    return ESBMCDirectResult(
        source_file=str(file_path),
        status=status,
        command=command,
        returncode=None,
        summary=_summarize_function_baseline(status, unique_names, violating),
        time_seconds=round(elapsed, 3),
        details=details,
    )


def _summarize_function_baseline(
    status: str,
    function_names: list[str],
    violating_functions: list[str],
) -> str:
    if status == "violation_found":
        names = ", ".join(violating_functions)
        return f"ESBMC Flow A encontrou violação em função candidata: {names}."
    if status == "no_violation_found":
        return f"ESBMC Flow A verificou {len(function_names)} função(ões) com --function sem violação no bound."
    if status == "skipped":
        return "ESBMC Flow A não executou: ESBMC não encontrado ou nenhuma função candidata."
    if status == "tool_error":
        return "ESBMC Flow A encontrou erro de ferramenta em todas as funções candidatas."
    return "ESBMC Flow A retornou resultado inconclusivo nas funções candidatas."


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _classify_esbmc_result(output: str, returncode: int | None) -> str:
    normalized = output.lower()
    # Use only "verification failed" — "violation" alone is too broad and matches
    # file paths containing the word (e.g. "black_23_assertion_violation.py").
    if "verification failed" in normalized:
        return "violation_found"
    if "verification successful" in normalized:
        return "no_violation_found"
    if returncode == 0:
        return "no_violation_found"
    return "inconclusive"


def _summarize(status: str, details: dict[str, object]) -> str:
    property_kind = str(details.get("property_kind", "")).strip()
    property_text = str(details.get("property_text", "")).strip()
    location      = str(details.get("location", "")).strip()

    if status == "violation_found":
        base = "ESBMC encontrou violação da propriedade."
        if property_kind and property_text:
            base = f"ESBMC encontrou violação: {property_kind} ({property_text})."
        elif property_kind:
            base = f"ESBMC encontrou violação: {property_kind}."
        elif property_text:
            base = f"ESBMC encontrou violação da propriedade {property_text}."
        return f"{base} Local: {location}." if location else base
    if status == "no_violation_found":
        return "ESBMC não encontrou violação no escopo analisado."
    if status == "tool_error":
        return "ESBMC retornou erro interno (recurso não suportado ou código incompatível)."
    return "Resultado inconclusivo da verificação formal."


def _extract_esbmc_details(
    output: str,
    source_path: Path | None = None,
) -> dict[str, object]:
    normalized_lines = output.splitlines()
    warnings: list[str] = []
    counterexample: list[str] = []
    property_kind = ""
    property_text = ""
    location = ""
    function_name = ""

    path_text = str(source_path).replace("\\", "/") if source_path else ""

    for raw_line in normalized_lines:
        if "SyntaxWarning:" in raw_line:
            warning_text = raw_line.split("SyntaxWarning:", 1)[1].strip()
            if warning_text and warning_text not in warnings:
                warnings.append(warning_text)

        if raw_line.startswith("State ") and (not path_text or path_text in raw_line):
            function_match = re.search(r"function ([^ ]+) thread", raw_line)
            line_match     = re.search(r" line (\d+) column ", raw_line)
            if function_match:
                function_name = function_match.group(1)
            if line_match:
                location = f"linha {line_match.group(1)}"
                if function_name:
                    location = f"{function_name}, {location}"

        assignment_match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^\(\n]+)", raw_line)
        if assignment_match:
            variable = assignment_match.group(1).strip()
            value    = assignment_match.group(2).strip()
            if variable not in {"l", "item"}:
                rendered = f"{variable} = {value}"
                if rendered not in counterexample:
                    counterexample.append(rendered)

    # --multi-property makes ESBMC print one "Violated property:" block per
    # failed property (e.g. one for a __ESBMC_cover reachability goal, another
    # for the harness's own marked assert) instead of stopping at the first.
    # Each block is "Violated property:\n" followed by consecutive indented
    # lines, ending at the next blank line.
    violated_properties: list[dict[str, str]] = []
    for block_match in re.finditer(r"Violated property:\n((?:[ \t]+.*\n)+)", output):
        block_lines = [ln.strip() for ln in block_match.group(1).splitlines() if ln.strip()]
        block_kind = ""
        block_text = ""
        block_location = ""
        block_function = ""
        for ln in block_lines:
            if " function " in ln and " line " in ln:
                fm = re.search(r"function ([^ ]+)", ln)
                lm = re.search(r" line (\d+)", ln)
                if fm:
                    block_function = fm.group(1)
                if lm:
                    block_location = f"linha {lm.group(1)}"
                    if block_function:
                        block_location = f"{block_function}, {block_location}"
                continue
            if not block_kind:
                block_kind = ln
                continue
            if not block_text:
                block_text = ln
                break
        if block_kind and block_kind not in {v["kind"] for v in violated_properties}:
            violated_properties.append({"kind": block_kind, "text": block_text, "location": block_location})

    if violated_properties:
        property_kind = violated_properties[0]["kind"]
        property_text = violated_properties[0]["text"]
        location = violated_properties[0]["location"] or location
        function_name = function_name or (location.split(",")[0] if location else "")

    return {
        "warnings": warnings,
        "counterexample": counterexample[:6],
        "violated_properties": [v["kind"] for v in violated_properties],
        "property_kind": property_kind,
        "property_text": property_text,
        "location": location,
        "function": function_name,
    }


def _prettify_output(
    status: str,
    details: dict[str, object],
    raw_log_path: Path,
) -> str:
    lines: list[str] = []
    property_kind = str(details.get("property_kind", "")).strip()
    property_text = str(details.get("property_text", "")).strip()
    location      = str(details.get("location", "")).strip()
    warnings_raw = details.get("warnings", [])
    counterexample_raw = details.get("counterexample", [])
    warnings = [str(item) for item in warnings_raw] if isinstance(warnings_raw, list) else []
    counterexample = (
        [str(item) for item in counterexample_raw]
        if isinstance(counterexample_raw, list)
        else []
    )

    if status == "violation_found":
        lines.append("ESBMC confirmou violação.")
    elif status == "no_violation_found":
        lines.append("ESBMC não encontrou violação no escopo analisado.")
    else:
        lines.append("ESBMC retornou resultado inconclusivo ou erro.")

    if location:
        lines.append(f"Local: {location}")
    if property_kind:
        lines.append(f"Tipo de propriedade: {property_kind}")
    if property_text:
        lines.append(f"Propriedade: {property_text}")
    if counterexample:
        lines.append("Contraexemplo relevante:")
        for item in counterexample:
            lines.append(f"- {item}")
    if warnings:
        lines.append("Avisos:")
        for item in warnings:
            lines.append(f"- {item}")

    lines.append(f"Log bruto completo: {raw_log_path}")
    return "\n".join(lines)
