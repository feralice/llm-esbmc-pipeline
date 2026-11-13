from __future__ import annotations

import sys
from datetime import date

sys.path.insert(0, "scripts")
import vetar_alvo


def _info(archived: bool = False, pushed: str = "2026-11-12") -> dict:
    return {"archived": archived, "pushed_at": pushed + "T00:00:00Z", "fork": False}


def test_an_active_repository_has_no_objection() -> None:
    assert vetar_alvo.objections(_info(), "A nice sample.", today=date(2026, 11, 13)) == []


def test_archived_repository_is_refused() -> None:
    assert any("arquivado" in o for o in vetar_alvo.objections(_info(archived=True), "", today=date(2026, 11, 13)))


def test_deprecated_notice_in_the_readme_is_refused() -> None:
    readme = "> **This project is deprecated.** Use the new service."
    assert any("deprecated" in o for o in vetar_alvo.objections(_info(), readme, today=date(2026, 11, 13)))


def test_repository_without_a_push_in_a_year_is_flagged() -> None:
    found = vetar_alvo.objections(_info(pushed="2024-12-16"), "", today=date(2026, 11, 13))
    assert any("último push" in o for o in found)


def test_a_word_like_deprecate_in_prose_about_a_feature_is_not_enough() -> None:
    assert vetar_alvo.objections(_info(), "We deprecate old flags in v2 only.", today=date(2026, 11, 13)) == []
