"""Tests never run the real ESBMC capability probes through main; test_verify_capabilities.py
calls them directly with a fake runner."""

import sys

import pytest


@pytest.fixture(autouse=True)
def _capability_probes_off(monkeypatch):
    module = sys.modules.get("main")
    if module is not None and hasattr(module, "resolve_rules"):
        from research_pipeline.verify.capabilities import all_rules_report

        monkeypatch.setattr(module, "resolve_rules", lambda *args, **kwargs: all_rules_report("testes"))
