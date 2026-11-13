"""Cheap, deterministic checks that drop a detector hypothesis before it reaches the specification and ESBMC.

Two kinds of drop, both measured on scans where the drop was a false positive:
- the hypothesis claims a method or name does not exist, but the source defines it;
- the detector itself says its verdict depends on code it was not shown.

Fail open: anything that cannot be parsed or matched keeps the hypothesis.
"""

from __future__ import annotations

import ast
import builtins
import re

_MISSING_CONTEXT = re.compile(
    r"context_needed"
    r"|\bwhich (?:is|are) (?:not shown|missing|not visible|not in the (?:provided |shown )?context)"
    r"|\b(?:not|missing)\b[^.]{0,30}\b(?:in|from)\b[^.]{0,20}\b(?:the )?(?:provided |shown |visible )?context\b"
    r"|cannot be (?:confirmed|determined) from"
    r"|\b(?:class|module) (?:body|definition) is not",
    re.IGNORECASE)
_ATTRIBUTE_CLAIM = re.compile(
    r"(?:has|have) no\b|(?:does not|doesn't) (?:exist|define|have)|is not (?:an attribute|defined)"
    r"|not an attribute|no such|no method|is undefined|no \w+ (?:attribute|method)", re.IGNORECASE)
_NAME_CLAIM = re.compile(r"NameError|not defined|undefined|free name|not imported", re.IGNORECASE)
_ASSIGNMENT = re.compile(r"^\s*(?:self\.\w+|\w+)\s*(?:[-+*/|&]?=)(?!=)")
_SELF_ATTRIBUTE = re.compile(r"\bself\.(\w+)")
_BARE_NAME = re.compile(r"(?<![\w.])([A-Za-z_]\w*)")


def _class_members(tree: ast.Module, qualname: str) -> set[str]:
    owners = qualname.split(".")[:-1]
    node: ast.AST = tree
    for owner in owners:
        match = next((n for n in ast.walk(node) if isinstance(n, ast.ClassDef) and n.name == owner), None)
        if match is None:
            return set()
        node = match
    if node is tree:
        return set()
    # Only what always exists: methods, nested classes and class-level names. `self.x = ...` inside a method
    # may run after the use, so it proves nothing.
    members: set[str] = set()
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            members.add(item.name)
        members.update(_stored_names(item))
    return members


def _module_names(tree: ast.Module) -> set[str]:
    names = {n for node in ast.walk(tree) if isinstance(node, ast.Global) for n in node.names}
    pending = list(tree.body)
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((a.asname or a.name).split(".")[0] for a in node.names)
        elif isinstance(node, (ast.If, ast.Try, ast.With, ast.For, ast.While)):
            pending.extend(child for child in ast.iter_child_nodes(node) if isinstance(child, ast.stmt))
            pending.extend(h for h in getattr(node, "handlers", []) for h in h.body)
        for target in _stored_names(node):
            names.add(target)
    return names


def _stored_names(node: ast.AST) -> list[str]:
    if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        return [n.id for t in targets for n in ast.walk(t) if isinstance(n, ast.Name)]
    return []


def drop_reason(expression: str, note: str, module_source: str, qualname: str) -> str | None:
    """Why the hypothesis should not be verified, or None to keep it."""
    if _MISSING_CONTEXT.search(note):
        return "the detector says its verdict depends on code it was not shown (missing context)"
    attribute_claim, name_claim = _ATTRIBUTE_CLAIM.search(note), _NAME_CLAIM.search(note)
    if not (attribute_claim or name_claim) or _ASSIGNMENT.match(expression):
        return None
    try:
        tree = ast.parse(module_source)
    except (SyntaxError, ValueError, RecursionError):
        return None
    if attribute_claim:
        members = _class_members(tree, qualname)
        for attribute in _SELF_ATTRIBUTE.findall(expression):
            if attribute in members and re.search(rf"\b{re.escape(attribute)}\b", note):
                return f"self.{attribute} is defined in the class"
    if name_claim:
        names = _module_names(tree)
        for name in _BARE_NAME.findall(expression):
            if name in names and not hasattr(builtins, name) and re.search(rf"\b{re.escape(name)}\b", note):
                return f"{name} is defined in the module"
    return None
