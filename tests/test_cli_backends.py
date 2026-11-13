from __future__ import annotations

import pytest

from research_pipeline import cli


@pytest.mark.parametrize("backend", ["anthropic", "openai", "google", "ollama"])
def test_scan_accepts_every_backend_the_pipeline_supports(backend: str) -> None:
    args = cli.build_parser().parse_args(["scan", "pasta", "--backend", backend])
    argv = cli.scan_argv(args)
    assert argv[argv.index("--backend") + 1] == backend
    assert argv[argv.index("--agent-backend") + 1] == backend


def test_maintenance_directory_follows_the_environment_variable(monkeypatch, tmp_path) -> None:
    import main

    monkeypatch.setenv("LLM_ESBMC_MAINTENANCE_DIR", str(tmp_path))
    assert main.maintenance_dir() == tmp_path
    monkeypatch.delenv("LLM_ESBMC_MAINTENANCE_DIR")
    assert main.maintenance_dir().name == "manutencao_automatica"
