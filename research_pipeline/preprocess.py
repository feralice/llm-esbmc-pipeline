from __future__ import annotations

import ast
from pathlib import Path

from .models import CodeUnit, OperationRecord


class _UnitCollector(ast.NodeVisitor):
    def __init__(self, source_lines: list[str], path: Path):
        self.source_lines = source_lines
        self.path = path
        self.units: list[CodeUnit] = []
        self.scope: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if self._should_skip(node.name):
            return
        self.units.append(self._build_unit(node))
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if self._should_skip(node.name):
            return
        self.units.append(self._build_unit(node))
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def _should_skip(self, name: str) -> bool:
        if name.startswith("test_"):
            return True
        # main() de nível de módulo é apenas orquestração, sem propriedades formais úteis
        if name == "main" and not self.scope:
            return True
        return False

    def _build_unit(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> CodeUnit:
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
    def __init__(self, source_lines: list[str]):
        self.source_lines = source_lines
        self.operations: list[OperationRecord] = []
        self.loops: list[str] = []
        self.conditionals: list[str] = []
        self.guards: list[str] = []
        self.branch_count = 0
        self.source_text = "\n".join(source_lines)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        for stmt in node.body:
            self.visit(stmt)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        for stmt in node.body:
            self.visit(stmt)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self.visit(node.value)

    def visit_For(self, node: ast.For) -> None:
        self.loops.append(ast.get_source_segment(self.source_text, node) or ast.unparse(node))
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.loops.append(ast.get_source_segment(self.source_text, node) or ast.unparse(node))
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        self.branch_count += 1
        test = ast.unparse(node.test)
        self.conditionals.append(test)
        self.guards.append(test)
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        test = ast.unparse(node.test)
        self.guards.append(test)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        # LIMITAÇÃO CONHECIDA: apenas acessos da forma lst[i] são detectados aqui.
        # Métodos como .pop(i), .insert(i, v), .remove(x) que também podem causar
        # IndexError são registrados como ast.Call, não ast.Subscript, e portanto
        # não são capturados. Achados da LLM sobre esses padrões serão classificados
        # como llm_false_positive pelo _normalize_findings. Não corrigir neste momento.
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
    file_path = Path(path)
    source = file_path.read_text(encoding="utf-8")
    source_lines = source.splitlines()
    tree = ast.parse(source)
    collector = _UnitCollector(source_lines, file_path)
    collector.visit(tree)
    for unit in collector.units:
        for operation in unit.operations:
            operation.relative_line = operation.line - unit.start_line + 1
    return collector.units
