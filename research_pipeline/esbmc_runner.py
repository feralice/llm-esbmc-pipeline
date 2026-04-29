from __future__ import annotations

import re
import shutil
import subprocess
import os
from pathlib import Path

from .models import ESBMCResult, InstrumentationResult


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
            summary="ESBMC nao encontrado no PATH. Verificacao formal nao executada.",
        )

    full_command = [*command, str(Path(instrumentation.output_path))]
    try:
        env = os.environ.copy()
        site_packages = _find_local_site_packages()
        if site_packages is not None:
            existing = env.get("PYTHONPATH")
            env["PYTHONPATH"] = (
                f"{site_packages}:{existing}" if existing else str(site_packages)
            )
        completed = subprocess.run(
            full_command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return ESBMCResult(
            finding_id=instrumentation.finding_id,
            status="inconclusive",
            command=full_command,
            returncode=None,
            summary="ESBMC excedeu o tempo limite configurado.",
        )

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    combined = f"{stdout}\n{stderr}"
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
        stdout=stdout,
        stderr=_prettify_output(status, details, raw_log_path),
        details=details,
        raw_log_path=str(raw_log_path),
    )


def _classify_esbmc_result(output: str, returncode: int) -> str:
    normalized = output.lower()
    if "verification failed" in normalized or "violation" in normalized:
        return "violation_found"
    if "verification successful" in normalized:
        return "no_violation_found"
    if returncode == 0:
        return "no_violation_found"
    return "inconclusive"


def _summarize(status: str, details: dict[str, object]) -> str:
    property_kind = str(details.get("property_kind", "")).strip()
    property_text = str(details.get("property_text", "")).strip()
    location = str(details.get("location", "")).strip()

    if status == "violation_found":
        base = "ESBMC encontrou violacao da propriedade."
        if property_kind and property_text:
            base = f"ESBMC encontrou violacao: {property_kind} ({property_text})."
        elif property_kind:
            base = f"ESBMC encontrou violacao: {property_kind}."
        elif property_text:
            base = f"ESBMC encontrou violacao da propriedade {property_text}."
        if location:
            return f"{base} Local: {location}."
        return base
    if status == "no_violation_found":
        return "ESBMC nao encontrou violacao no escopo analisado."
    return "Resultado inconclusivo da verificacao formal."


def _write_raw_log(instrumentation: InstrumentationResult, combined_output: str) -> Path:
    artifacts_dir = instrumentation.output_path.parent.parent
    logs_dir = artifacts_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    target = logs_dir / f"{instrumentation.output_path.stem}.log"
    target.write_text(combined_output, encoding="utf-8")
    return target


def _extract_esbmc_details(output: str, instrumented_path: Path) -> dict[str, object]:
    normalized_lines = output.splitlines()
    warnings: list[str] = []
    counterexample: list[str] = []
    property_kind = ""
    property_text = ""
    location = ""
    function_name = ""

    instrumented_path_text = str(instrumented_path).replace("\\", "/")

    for raw_line in normalized_lines:
        line = raw_line.strip()
        if "SyntaxWarning:" in raw_line:
            warning_text = raw_line.split("SyntaxWarning:", 1)[1].strip()
            if warning_text and warning_text not in warnings:
                warnings.append(warning_text)

        if raw_line.startswith("State ") and instrumented_path_text in raw_line:
            function_match = re.search(r"function ([^ ]+) thread", raw_line)
            line_match = re.search(r" line (\d+) column ", raw_line)
            if function_match:
                function_name = function_match.group(1)
            if line_match:
                location = f"linha {line_match.group(1)}"
                if function_name:
                    location = f"{function_name}, {location}"

        assignment_match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^\(\n]+)", raw_line)
        if assignment_match:
            variable = assignment_match.group(1).strip()
            value = assignment_match.group(2).strip()
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
            line.strip()
            for line in property_block_match.group("body").splitlines()
            if line.strip()
        ]
        for line in property_lines:
            if " function " in line and " line " in line:
                function_match = re.search(r"function ([^ ]+)", line)
                line_match = re.search(r" line (\d+)", line)
                if function_match:
                    function_name = function_match.group(1)
                if line_match:
                    location = f"linha {line_match.group(1)}"
                    if function_name:
                        location = f"{function_name}, {location}"
                continue
            if not property_kind:
                property_kind = line
                continue
            if not property_text:
                property_text = line
                break

    filtered_counterexample = counterexample[:6]

    return {
        "warnings": warnings,
        "counterexample": filtered_counterexample,
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
    location = str(details.get("location", "")).strip()
    warnings = [str(item) for item in details.get("warnings", [])]
    counterexample = [str(item) for item in details.get("counterexample", [])]

    if status == "violation_found":
        lines.append("ESBMC confirmou violacao.")
    elif status == "no_violation_found":
        lines.append("ESBMC nao encontrou violacao no escopo analisado.")
    else:
        lines.append("ESBMC retornou resultado inconclusivo.")

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
    repo_root = Path(__file__).resolve().parents[3]
    venv_lib = repo_root / ".venv" / "lib"
    if not venv_lib.exists():
        return None

    candidates = sorted(venv_lib.glob("python*/site-packages"))
    for candidate in candidates:
        if candidate.exists():
            return candidate
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
