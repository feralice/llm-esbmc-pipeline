import json
import re
from pathlib import Path

from main import build_parser

EXTENSION = Path(__file__).resolve().parents[1] / "extension"
COMMAND = EXTENSION / "commands" / "verificar-repo.md"


def test_plugin_manifest_names_the_extension():
    manifest = json.loads((EXTENSION / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "llm-esbmc" and manifest["description"]


def test_command_flags_exist_and_it_asks_before_spending():
    text = COMMAND.read_text(encoding="utf-8")
    known = {option for action in build_parser()._actions for option in action.option_strings}
    used = set(re.findall(r"(?<![\w-])--[a-z][a-z0-9-]*", text))
    assert used and used <= known, used - known
    dry, paid = text.index("--mode scan"), text.index("--yes")
    assert dry < paid and "confirm" in text[dry:paid].lower()
    assert "—" not in text


def test_command_resolves_the_folder_before_cd_and_quotes_the_focus():
    text = COMMAND.read_text(encoding="utf-8")
    assert text.index("realpath") < text.index('cd "$HOME_P"')
    assert '--scan-focus "$FOCO"' in text and "FOCO='" in text
    assert "código de saída" in " ".join(text.split())
