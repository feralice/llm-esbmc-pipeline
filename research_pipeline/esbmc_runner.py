from __future__ import annotations

import re
import shutil
import subprocess
import time
import os
from pathlib import Path

from .models import ESBMCDirectResult, ESBMCResult, InstrumentationResult


# ---------------------------------------------------------------------------
# Flow A — ESBMC direct on original file
# ---------------------------------------------------------------------------

def run_esbmc_direct(
    file_path: str | Path,
    esbmc_command: list[str] | None = None,
    bound: int = 5,
    timeout_seconds: int = 30,
    output_dir: str | Path | None = None,
) -> ESBMCDirectResult:
    """Run ESBMC directly on the original Python file (no instrumentation)."""
    file_path = Path(file_path).resolve()
    base_command = list(esbmc_command or ["esbmc", "--python", "python3"])

    # For direct mode use explicit bound (not incremental) for reproducibility
    command = [*base_command, "--unwind", str(bound), str(file_path)]

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
        logs_dir = Path(__file__).resolve().parents[1] / "artifacts" / "esbmc_outputs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    target = logs_dir / f"{file_path.stem}_direct.log"
    target.write_text(combined, encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# Flow B — ESBMC on instrumented file
# ---------------------------------------------------------------------------

def run_esbmc(
    instrumentation: InstrumentationResult,
    esbmc_command: list[str] | None = None,
    timeout_seconds: int = 30,
) -> ESBMCResult:
    command = _build_esbmc_command(
        esbmc_command=esbmc_command,
        esbmc_flags=instrumentation.esbmc_flags,
    )
    executable = shutil.which(command[0])
    if executable is None:
        return ESBMCResult(
            finding_id=instrumentation.finding_id,
            status="skipped",
            command=command + [str(instrumentation.output_path)],
            returncode=None,
            summary="ESBMC não encontrado no PATH. Verificação formal não executada.",
        )

    full_command = [*command, str(Path(instrumentation.output_path))]
    start = time.monotonic()
    try:
        env = os.environ.copy()
        site_packages = _find_local_site_packages()
        esbmc_python  = _find_esbmc_python_path()
        extra_paths = [
            str(p) for p in [esbmc_python, site_packages] if p is not None
        ]
        if extra_paths:
            existing = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = os.pathsep.join(extra_paths + ([existing] if existing else []))
        completed = subprocess.run(
            full_command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
        )
        elapsed = time.monotonic() - start
    except subprocess.TimeoutExpired:
        return ESBMCResult(
            finding_id=instrumentation.finding_id,
            status="inconclusive",
            command=full_command,
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

    raw_log_path = _write_raw_log(instrumentation, combined)
    details = _extract_esbmc_details(
        output=combined,
        instrumented_path=Path(instrumentation.output_path),
    )

    return ESBMCResult(
        finding_id=instrumentation.finding_id,
        status=status,
        command=full_command,
        returncode=completed.returncode,
        summary=_summarize(status, details),
        time_seconds=round(elapsed, 3),
        stdout=stdout,
        stderr=_prettify_output(status, details, raw_log_path),
        details=details,
        raw_log_path=str(raw_log_path),
    )


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


def _write_raw_log(instrumentation: InstrumentationResult, combined_output: str) -> Path:
    artifacts_dir = instrumentation.output_path.parent.parent
    logs_dir = artifacts_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    target = logs_dir / f"{instrumentation.output_path.stem}.log"
    target.write_text(combined_output, encoding="utf-8")
    return target


def _extract_esbmc_details(
    output: str,
    instrumented_path: Path | None = None,
) -> dict[str, object]:
    normalized_lines = output.splitlines()
    warnings: list[str] = []
    counterexample: list[str] = []
    property_kind = ""
    property_text = ""
    location = ""
    function_name = ""

    path_text = str(instrumented_path).replace("\\", "/") if instrumented_path else ""

    for raw_line in normalized_lines:
        line = raw_line.strip()

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

    property_block_match = re.search(
        r"Violated property:\s*\n(?P<body>.*?)(?:\n\s*\nVERIFICATION FAILED|\Z)",
        output,
        re.DOTALL,
    )
    if property_block_match:
        property_lines = [
            ln.strip()
            for ln in property_block_match.group("body").splitlines()
            if ln.strip()
        ]
        for ln in property_lines:
            if " function " in ln and " line " in ln:
                fm = re.search(r"function ([^ ]+)", ln)
                lm = re.search(r" line (\d+)", ln)
                if fm:
                    function_name = fm.group(1)
                if lm:
                    location = f"linha {lm.group(1)}"
                    if function_name:
                        location = f"{function_name}, {location}"
                continue
            if not property_kind:
                property_kind = ln
                continue
            if not property_text:
                property_text = ln
                break

    return {
        "warnings": warnings,
        "counterexample": counterexample[:6],
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
    warnings      = [str(item) for item in details.get("warnings", [])]
    counterexample = [str(item) for item in details.get("counterexample", [])]

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


def _find_local_site_packages() -> Path | None:
    # Look for .venv in the project root (2 levels up from this file)
    repo_root = Path(__file__).resolve().parents[1]
    venv_lib = repo_root / ".venv" / "lib"
    if not venv_lib.exists():
        return None
    candidates = sorted(venv_lib.glob("python*/site-packages"))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _find_esbmc_python_path() -> Path | None:
    """Return the directory containing esbmc.py (nondet_int, nondet_bool, etc.).

    Priority:
    1. ESBMC_PYTHON_PATH env var — use this to point to the full ESBMC models
       directory if you need the complete set of stubs (builtins, math, etc.).
    2. Bundled stubs at research_pipeline/esbmc_stubs/ — covers the common
       nondet_* and __ESBMC_* functions used by the instrumented files.
    """
    env_path = os.environ.get("ESBMC_PYTHON_PATH")
    if env_path:
        p = Path(env_path)
        if (p / "esbmc.py").exists():
            return p

    bundled = Path(__file__).resolve().parent / "esbmc_stubs"
    if (bundled / "esbmc.py").exists():
        return bundled

    return None


def _build_esbmc_command(
    esbmc_command: list[str] | None,
    esbmc_flags: list[str],
) -> list[str]:
    command = list(esbmc_command or ["esbmc", "--python", "python3", "--incremental-bmc"])
    for flag in esbmc_flags:
        if flag not in command:
            command.append(flag)
    return command
