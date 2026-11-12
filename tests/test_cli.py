import pytest

from research_pipeline.cli import build_parser, scan_argv
from research_pipeline.cli_args import REPO_ROOT


def _argv(*args):
    return scan_argv(build_parser().parse_args(["scan", "/tmp/repo", *args]))


def test_claude_is_the_default_and_uses_the_subscription_flags():
    argv = _argv()
    assert argv[argv.index("--backend") + 1] == "claude_cli"
    assert argv[argv.index("--agent-backend") + 1] == "claude"


def test_codex_backend_maps_to_codex_flags():
    argv = _argv("--backend", "codex")
    assert argv[argv.index("--backend") + 1] == "codex"
    assert argv[argv.index("--agent-backend") + 1] == "codex"


def test_without_yes_nothing_is_spent_and_no_agent_verification_is_asked():
    argv = _argv()
    assert "--yes" not in argv and "--scan-verify" not in argv


def test_yes_enables_the_agent_verification():
    argv = _argv("--yes")
    assert argv[argv.index("--scan-verify") + 1] == "agent"
    assert "--yes" in argv


def test_default_output_is_per_backend_and_per_folder():
    argv = _argv("--backend", "codex")
    assert argv[argv.index("--output-dir") + 1] == str(REPO_ROOT / "artifacts" / "cli" / "codex" / "repo")


def test_limit_and_focus_are_passed_through():
    argv = _argv("--limit", "5", "--focus", "parsing")
    assert argv[argv.index("--scan-limit") + 1] == "5"
    assert argv[argv.index("--scan-focus") + 1] == "parsing"


def test_unknown_backend_is_rejected():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["scan", "/tmp/repo", "--backend", "gemini"])
