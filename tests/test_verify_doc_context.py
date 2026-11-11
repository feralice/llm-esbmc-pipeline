from research_pipeline.verify.doc_context import (
    documentation_snapshot,
    relevant_documentation,
)


def test_finds_related_docs_with_path_and_line_but_not_unrelated(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "api.rst").write_text("API\n\nDecodePDU.add_sub_pdu accepts a class.\n", encoding="utf-8")
    (docs / "other.md").write_text("Unrelated documentation.\n", encoding="utf-8")
    source = tmp_path / "pymodbus" / "pdu" / "decoders.py"
    source.parent.mkdir(parents=True)
    source.write_text("", encoding="utf-8")
    snapshot = documentation_snapshot(tmp_path)
    text = relevant_documentation(snapshot, tmp_path, source, "DecodePDU.add_sub_pdu")
    assert "docs/api.rst:3" in text and "accepts a class" in text
    assert "other.md" not in text


def test_snapshot_hash_changes_with_content_and_ignores_symlinks(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    target = docs / "api.md"
    target.write_text("first", encoding="utf-8")
    (docs / "link.md").symlink_to(target)
    first = documentation_snapshot(tmp_path)
    assert "docs/link.md" not in first.files
    target.write_text("second", encoding="utf-8")
    assert first.digest != documentation_snapshot(tmp_path).digest
