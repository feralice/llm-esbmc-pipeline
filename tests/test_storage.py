import json
from pathlib import Path

import pytest


def test_atomic_json_preserves_existing_serialization_and_creates_parent(tmp_path):
    from research_pipeline.storage import write_json_atomic

    path = tmp_path / "nested/checkpoint.json"
    write_json_atomic(path, {"ação": [1, None], "done": False})
    assert path.read_bytes() == b'{\n  "a\xc3\xa7\xc3\xa3o": [\n    1,\n    null\n  ],\n  "done": false\n}'


def test_failed_replace_keeps_the_previous_checkpoint(tmp_path, monkeypatch):
    from research_pipeline.storage import write_json_atomic

    path = tmp_path / "checkpoint.json"
    path.write_text('{"old": true}')

    def refused(self, destination):
        raise OSError("replace unavailable")

    monkeypatch.setattr(Path, "replace", refused)
    with pytest.raises(OSError):
        write_json_atomic(path, {"new": True})
    assert json.loads(path.read_text()) == {"old": True}
