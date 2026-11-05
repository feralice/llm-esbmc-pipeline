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


@pytest.fixture(autouse=True)
def _notebook_copy(monkeypatch, tmp_path_factory):
    """Automatic lessons write to a copy: no test may change the real repair notebook."""
    import shutil

    from research_pipeline.verify import lessons

    copy = tmp_path_factory.mktemp("caderno") / "SKILL.md"
    shutil.copy(lessons.NOTEBOOK, copy)
    monkeypatch.setattr(lessons, "NOTEBOOK", copy)
