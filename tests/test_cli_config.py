import pytest


@pytest.mark.parametrize("backend,model,synth_backend,synth_model,expected", [
    ("google", "gemini", "openai", None, ("gemini-2.5-flash", "openai", "gpt-5.5")),
    ("openai", "gpt", None, None, ("gpt-5.5", "openai", "gpt-5.5")),
    ("google", None, "openai", None, (None, "openai", "gpt-5.5")),
    ("codex", None, None, None, ("", "codex", "")),
    ("openai", "gpt", "claude_cli", None, ("gpt-5.5", "claude_cli", "")),
    ("google", "gemini", "openai", "explicit-model", ("gemini-2.5-flash", "openai", "explicit-model")),
])
def test_model_resolution_preserves_explicit_choices_and_backend_namespaces(
    backend, model, synth_backend, synth_model, expected,
):
    from research_pipeline.cli_config import resolve_models

    assert resolve_models(backend, model, synth_backend, synth_model) == expected
