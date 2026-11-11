"""Tests never run the real ESBMC capability probes through main; test_verify_capabilities.py
calls them directly with a fake runner."""

import sys
import socket
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _offline_and_temporary_caches(monkeypatch, tmp_path_factory):
    """Accidental real providers fail; local tools and fakes remain usable."""
    from research_pipeline.verify import esbmc_knowledge

    cache = tmp_path_factory.mktemp("tool-caches")
    monkeypatch.setenv("RUFF_CACHE_DIR", str(cache / "ruff"))
    monkeypatch.setenv("MYPY_CACHE_DIR", str(cache / "mypy"))
    monkeypatch.setattr(esbmc_knowledge, "KNOWLEDGE_CACHE", cache / "knowledge")
    for name, module in tuple(sys.modules.items()):
        if name.startswith("research_pipeline.") and hasattr(module, "KNOWLEDGE_CACHE"):
            monkeypatch.setattr(module, "KNOWLEDGE_CACHE", cache / "knowledge")

    original_connect, original_popen = socket.socket.connect, subprocess.Popen

    def connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            pytest.fail("Network is disabled in the offline test suite")
        return original_connect(sock, address)

    def popen(command, *args, **kwargs):
        executable = command[0] if isinstance(command, (list, tuple)) and command else command
        if isinstance(executable, str) and Path(executable).name in {"codex", "claude", "gemini", "ollama"}:
            pytest.fail("Live LLM commands are disabled in the offline test suite")
        return original_popen(command, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(subprocess, "Popen", popen)


@pytest.fixture(autouse=True)
def _capability_probes_off(monkeypatch):
    module = sys.modules.get("main")
    if module is not None and hasattr(module, "resolve_rules"):
        from research_pipeline.verify.capabilities import all_rules_report

        monkeypatch.setattr(module, "resolve_rules", lambda *args, **kwargs: all_rules_report("testes"))


@pytest.fixture(autouse=True)
def _notebook_copy(monkeypatch, tmp_path_factory):
    """Automatic lessons write to a copy: no test may change the real repair notebook."""
    import shutil

    from research_pipeline.verify import lessons

    copy = tmp_path_factory.mktemp("caderno") / "SKILL.md"
    shutil.copy(lessons.NOTEBOOK, copy)
    monkeypatch.setattr(lessons, "NOTEBOOK", copy)
