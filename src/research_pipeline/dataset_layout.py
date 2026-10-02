"""Folder names of the V2 dataset, current first and older ones after them.

dataset/bugs_reais/ holds the buggy code (funcao_com_bug/, arquivo_com_bug/, arquivo_corrigido/);
the hand-written harnesses of 2026-09-09 live beside it, in dataset/harness_bugs_reais/. Tests and
older runs build datasets with the earlier names (detection/, bugs/ inside the dataset), so those
still resolve.
"""

from __future__ import annotations

from pathlib import Path

BUGGY_FUNCTION = ("funcao_com_bug", "buggy_function", "detection")
MANUAL_HARNESS = ("harness_manual_0909", "manual_harness_0909", "bugs")
HARNESS_ROOT = "harness_bugs_reais"


def _resolve(candidates: list[Path]) -> Path:
    return next((path for path in candidates if path.is_dir()), candidates[0])


def buggy_function_dir(root: Path) -> Path:
    """Where the per-bug function excerpts the LLM reads live."""
    return _resolve([Path(root) / name for name in BUGGY_FUNCTION])


def manual_harness_dir(root: Path) -> Path:
    """Where the hand-written harnesses of the dataset at ``root`` live."""
    root = Path(root)
    return _resolve([root.parent / HARNESS_ROOT / MANUAL_HARNESS[0], *(root / name for name in MANUAL_HARNESS)])


def dataset_of_harness(harness: Path) -> Path:
    """The dataset folder a hand-written harness file belongs to."""
    folder = Path(harness).parent
    if folder.parent.name == HARNESS_ROOT:
        return folder.parent.parent / "bugs_reais"
    return folder.parent
