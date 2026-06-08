from __future__ import annotations

import ast
import warnings
from pathlib import Path

from .models import CodeUnit, OperationRecord


class _UnitCollector(ast.NodeVisitor):
    """Collect analyzable Python functions from a parsed source file.

    The collector walks the module AST, keeps track of class/function scope,
    skips test helpers, and creates one CodeUnit for each function that should
    be analyzed by the pipeline.
    """

    def __init__(self, source_lines: list[str], path: Path):
        self.source_lines = source_lines
        self.path = path
        self.units: list[CodeUnit] = []
        self.scope: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Enter a class scope so method qualnames include the class name."""
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Create a CodeUnit for a regular function, unless it is skipped."""
        if self._should_skip(node.name):
            return
        self.units.append(self._build_unit(node))
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Create a CodeUnit for an async function, unless it is skipped."""
        if self._should_skip(node.name):
            return
        self.units.append(self._build_unit(node))
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def _should_skip(self, name: str) -> bool:
        """Return True for helper functions that should not be analyzed."""
        if name.startswith("test_"):
            return True
        # Module-level main() is orchestration, not a useful formal target.
        if name == "main" and not self.scope:
            return True
        return False

    def _build_unit(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> CodeUnit:
        """Convert one AST function node into the pipeline's CodeUnit format."""
        extractor = _StructureExtractor(self.source_lines)
        extractor.visit(node)

        qualname = ".".join([*self.scope, node.name]) if self.scope else node.name
        source = "\n".join(self.source_lines[node.lineno - 1 : node.end_lineno])
        params = [arg.arg for arg in node.args.args]

        hints = {}
        for arg in node.args.args:
            if arg.annotation is not None:
                hints[arg.arg] = ast.unparse(arg.annotation)
        if node.returns is not None:
            hints["return"] = ast.unparse(node.returns)

        return CodeUnit(
            path=self.path,
            name=node.name,
            qualname=qualname,
            source=source,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            parameters=params,
            type_hints=hints,
            operations=extractor.operations,
            loops=extractor.loops,
            conditionals=extractor.conditionals,
            guards=extractor.guards,
            metrics={
                "line_count": (node.end_lineno or node.lineno) - node.lineno + 1,
                "parameter_count": len(params),
                "branch_count": extractor.branch_count,
                "loop_count": len(extractor.loops),
                "operation_count": len(extractor.operations),
            },
        )


class _StructureExtractor(ast.NodeVisitor):
    """Extract operations, guards and simple metrics from one function body."""

    def __init__(self, source_lines: list[str]):
        self.source_lines = source_lines
        self.operations: list[OperationRecord] = []
        self.loops: list[str] = []
        self.conditionals: list[str] = []
        self.guards: list[str] = []
        self.branch_count = 0
        self.source_text = "\n".join(source_lines)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit only the body of this function, not the FunctionDef wrapper."""
        for stmt in node.body:
            self.visit(stmt)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit only the body of this async function."""
        for stmt in node.body:
            self.visit(stmt)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Visit annotated assignment values, ignoring the annotation itself."""
        if node.value is not None:
            self.visit(node.value)

    def visit_For(self, node: ast.For) -> None:
        """Record a for-loop and keep walking inside it."""
        self.loops.append(ast.get_source_segment(self.source_text, node) or ast.unparse(node))
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        """Record a while-loop and keep walking inside it."""
        self.loops.append(ast.get_source_segment(self.source_text, node) or ast.unparse(node))
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        """Record if conditions as both branches and possible guards."""
        self.branch_count += 1
        test = ast.unparse(node.test)
        self.conditionals.append(test)
        self.guards.append(test)
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        """Record assert expressions as possible guards/properties."""
        test = ast.unparse(node.test)
        self.guards.append(test)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        """Record indexed access such as items[i]."""
        # Known limitation: only syntax like items[i] is recorded as subscript.
        # Methods such as items.pop(i) are calls, so they are recorded by
        # visit_Call instead of being treated as direct out_of_bounds evidence.
        self.operations.append(
            OperationRecord(
                kind="subscript",
                expression=ast.unparse(node),
                line=node.lineno,
                relative_line=node.lineno,
            )
        )
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        """Record division-like binary operations: /, // and %."""
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            self.operations.append(
                OperationRecord(
                    kind="division",
                    expression=ast.unparse(node),
                    line=node.lineno,
                    relative_line=node.lineno,
                )
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Record function/method calls as generic operations."""
        self.operations.append(
            OperationRecord(
                kind="call",
                expression=ast.unparse(node),
                line=node.lineno,
                relative_line=node.lineno,
            )
        )
        self.generic_visit(node)


def preprocess_file(path: str | Path) -> list[CodeUnit]:
    """Read a Python file and return one CodeUnit for each analyzable function."""
    file_path = Path(path)
    source = file_path.read_text(encoding="utf-8")
    source_lines = source.splitlines()

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        warnings.warn(f"Skipping invalid Python file {file_path}: {exc}", RuntimeWarning)
        return []

    collector = _UnitCollector(source_lines, file_path)
    collector.visit(tree)

    # Convert absolute operation lines into function-relative line numbers.
    for unit in collector.units:
        for operation in unit.operations:
            operation.relative_line = operation.line - unit.start_line + 1

    return collector.units
