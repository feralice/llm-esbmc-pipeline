"""Pure model resolution shared by the CLI modes."""

from .llm.backends.factory import Backend, _DEFAULT_MODEL


def resolve_model(model: str | None, backend: Backend) -> str | None:
    """Expand existing detection aliases without changing explicit model identifiers."""
    if model is None:
        return None
    aliases = {"claude": "claude-opus-4-8", "gpt": "gpt-5.5",
               "gemini": "gemini-2.5-flash", "deepseek": "deepseek-r1:7b"}
    return aliases.get(model.lower(), model)


def resolve_models(backend: Backend, model: str | None, synth_backend: Backend | None = None,
                   synth_model: str | None = None) -> tuple[str | None, Backend, str]:
    detection = resolve_model(model, backend)
    if backend in {"codex", "claude_cli"} and not model:
        detection = ""
    synthesis = synth_backend or backend
    if synth_model:
        selected = synth_model
    elif synthesis in {"codex", "claude_cli"}:
        selected = ""
    elif synthesis == backend:
        selected = detection or _DEFAULT_MODEL[synthesis]
    else:
        selected = _DEFAULT_MODEL[synthesis]
    return detection, synthesis, selected
