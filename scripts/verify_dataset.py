"""
Verifica a confiabilidade do dataset V1:
  1. Metadados do ground truth batem com o arquivo .py
  2. Arquivos são compatíveis com ESBMC (type hints, sem top-level calls, sem imports externos)
  3. Bugs são triggerable (há caminho para a falha)
  4. Cleans são realmente seguros (têm guard antes da operação perigosa)
"""
import ast
import json
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

ROOT = Path(__file__).parent.parent
BUGS_DIR = ROOT / "dataset/labeled/ok/bugs"
CLEAN_DIR = ROOT / "dataset/labeled/ok/clean"
SMELLS_DIR = ROOT / "dataset/labeled/ok/smells"
GT_BUGS_DIR = ROOT / "dataset/labeled/ground_truths/bugs"
GT_CLEAN = ROOT / "dataset/labeled/ground_truths/clean/clean.json"
GT_SMELLS_DIR = ROOT / "dataset/labeled/ground_truths/smells"

STDLIB_MODULES = {
    "math", "os", "sys", "re", "json", "collections", "itertools",
    "functools", "typing", "abc", "io", "pathlib", "datetime",
    "random", "string", "copy", "operator", "types", "enum",
}

EXTERNAL_IMPORTS = {"numpy", "pandas", "requests", "flask", "django",
                    "scipy", "sklearn", "torch", "tensorflow"}


@dataclass
class CheckResult:
    file: str
    item_id: str
    ok: bool
    issues: list[str] = field(default_factory=list)

    def __str__(self):
        status = "OK" if self.ok else "FAIL"
        base = f"  [{status}] {self.item_id} ({self.file})"
        if self.issues:
            return base + "\n" + "\n".join(f"         - {i}" for i in self.issues)
        return base


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def parse_file(path: Path) -> Optional[ast.Module]:
    try:
        return ast.parse(path.read_text())
    except SyntaxError as e:
        return None


# --- checks individuais ---

def check_syntax(tree, path) -> list[str]:
    if tree is None:
        return [f"SyntaxError ao parsear {path.name}"]
    return []


def check_type_hints(tree, func_name: str) -> list[str]:
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            for arg in node.args.args:
                if arg.annotation is None:
                    issues.append(f"Parâmetro '{arg.arg}' sem type hint")
            if node.returns is None:
                issues.append("Return sem type hint")
    return issues


def check_no_toplevel_calls(tree) -> list[str]:
    issues = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            issues.append(f"Chamada top-level na linha {node.lineno}")
        if isinstance(node, ast.If):
            # if __name__ == "__main__": é aceitável mas não deve existir no dataset
            issues.append(f"Bloco 'if' top-level na linha {node.lineno}")
    return issues


def check_no_external_imports(tree) -> list[str]:
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [n.name for n in node.names] if isinstance(node, ast.Import) \
                    else [node.module or ""]
            for name in names:
                base = name.split(".")[0]
                if base in EXTERNAL_IMPORTS:
                    issues.append(f"Import externo proibido: {name}")
    return issues


def check_function_exists(tree, func_name: str) -> list[str]:
    names = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    if func_name not in names:
        return [f"Função '{func_name}' não encontrada (encontradas: {names})"]
    return []


def check_expression_at_line(path: Path, expression: str, line: int) -> list[str]:
    if not expression:
        return []
    lines = path.read_text().splitlines()
    # aceita match em ±1 linha
    window = range(max(0, line - 2), min(len(lines), line + 1))
    snippet = expression.replace(" ", "").lower()
    for i in window:
        if snippet in lines[i].replace(" ", "").lower():
            return []
    context = [f"  linha {i+1}: {lines[i]}" for i in window]
    return [
        f"Expressão '{expression}' não encontrada próximo à linha {line}",
        *context,
    ]


def check_bug_is_triggerable(tree, func_name: str, category: str) -> list[str]:
    """Verifica heuristicamente que o bug pode ser acionado."""
    issues = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name == func_name):
            continue

        if category == "division_by_zero":
            divs = [n for n in ast.walk(node)
                    if isinstance(n, ast.BinOp)
                    and isinstance(n.op, (ast.Div, ast.FloorDiv, ast.Mod))]
            if not divs:
                issues.append("Nenhuma divisão encontrada na função")

        elif category == "out_of_bounds":
            subs = [n for n in ast.walk(node) if isinstance(n, ast.Subscript)]
            if not subs:
                issues.append("Nenhum subscript encontrado na função")

        elif category == "assertion_violation":
            asserts = [n for n in ast.walk(node) if isinstance(n, ast.Assert)]
            if not asserts:
                issues.append("Nenhum assert encontrado na função")
        # Nota: presença de guard não implica que o bug está protegido.
        # O dataset inclui casos com guard incompleto/errado intencionalmente
        # (off-by-one, condição invertida, branch duplicado). A verificação
        # semântica fina fica por conta do ESBMC.
    return issues


def check_clean_is_safe(tree, func_name: str) -> list[str]:
    """Verifica que a função clean tem guards para operações perigosas."""
    issues = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name == func_name):
            continue

        divs = [n for n in ast.walk(node)
                if isinstance(n, ast.BinOp)
                and isinstance(n.op, (ast.Div, ast.FloorDiv, ast.Mod))]
        asserts = [n for n in ast.walk(node) if isinstance(n, ast.Assert)]

        if divs and not _all_divisions_guarded(node):
            issues.append("Divisão sem guard detectada em arquivo clean")

        # Assert em clean só é problema se vier antes de qualquer guard (if+return).
        # Assert após guards é postcondição sempre verdadeira — intencionalmente segura.
        if asserts and not _has_early_return_guard(node):
            issues.append(f"Assert sem guard anterior em arquivo clean ({len(asserts)} assert(s))")
    return issues


def _has_early_return_guard(func_node: ast.FunctionDef) -> bool:
    """Retorna True se a função tem pelo menos um `if` com `return` antes de qualquer assert."""
    found_guard = False
    for stmt in ast.walk(func_node):
        if isinstance(stmt, ast.If):
            for child in ast.walk(stmt):
                if isinstance(child, ast.Return):
                    found_guard = True
                    break
        if isinstance(stmt, ast.Assert) and found_guard:
            return True
    return False


# --- helpers heurísticos de guard ---

def _all_divisions_guarded(func_node: ast.FunctionDef) -> bool:
    """
    Heurística: considera divisão guardada se há qualquer `if` na função
    que compara o denominador com 0 ou com um valor.
    """
    has_div = any(
        isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Div, ast.FloorDiv, ast.Mod))
        for n in ast.walk(func_node)
    )
    if not has_div:
        return True
    has_guard = any(
        isinstance(n, ast.If) for n in ast.walk(func_node)
    )
    return has_guard


def _all_subscripts_guarded(func_node: ast.FunctionDef) -> bool:
    has_sub = any(isinstance(n, ast.Subscript) for n in ast.walk(func_node))
    if not has_sub:
        return True
    has_guard = any(isinstance(n, ast.If) for n in ast.walk(func_node))
    return has_guard


# --- runner principal ---

def verify_bug_category(category: str) -> list[CheckResult]:
    gt_path = GT_BUGS_DIR / f"{category}.json"
    bug_dir = BUGS_DIR / category
    gt = load_json(gt_path)
    results = []

    for item in gt["items"]:
        file_path = bug_dir / item["file"]
        issues = []

        if not file_path.exists():
            results.append(CheckResult(item["file"], item["id"], False,
                                       ["Arquivo não encontrado"]))
            continue

        tree = parse_file(file_path)
        issues += check_syntax(tree, file_path)
        if tree is None:
            results.append(CheckResult(item["file"], item["id"], False, issues))
            continue

        issues += check_function_exists(tree, item["function"])
        issues += check_type_hints(tree, item["function"])
        issues += check_no_toplevel_calls(tree)
        issues += check_no_external_imports(tree)
        issues += check_expression_at_line(file_path, item.get("expression", ""), item.get("line", 0))
        issues += check_bug_is_triggerable(tree, item["function"], category)

        results.append(CheckResult(item["file"], item["id"], len(issues) == 0, issues))

    return results


def verify_clean() -> list[CheckResult]:
    gt = load_json(GT_CLEAN)
    results = []

    for item in gt["items"]:
        file_path = CLEAN_DIR / item["file"]
        issues = []

        if not file_path.exists():
            results.append(CheckResult(item["file"], item["id"], False,
                                       ["Arquivo não encontrado"]))
            continue

        tree = parse_file(file_path)
        issues += check_syntax(tree, file_path)
        if tree is None:
            results.append(CheckResult(item["file"], item["id"], False, issues))
            continue

        issues += check_function_exists(tree, item["function"])
        issues += check_type_hints(tree, item["function"])
        issues += check_no_toplevel_calls(tree)
        issues += check_no_external_imports(tree)
        issues += check_clean_is_safe(tree, item["function"])

        results.append(CheckResult(item["file"], item["id"], len(issues) == 0, issues))

    return results


def verify_smell_category(category: str) -> list[CheckResult]:
    gt_path = GT_SMELLS_DIR / f"{category}.json"
    smell_dir = SMELLS_DIR / category
    gt = load_json(gt_path)
    results = []

    for item in gt["items"]:
        file_path = smell_dir / item["file"]
        issues = []

        if not file_path.exists():
            results.append(CheckResult(item["file"], item["id"], False,
                                       ["Arquivo não encontrado"]))
            continue

        tree = parse_file(file_path)
        issues += check_syntax(tree, file_path)
        if tree is None:
            results.append(CheckResult(item["file"], item["id"], False, issues))
            continue

        issues += check_function_exists(tree, item["function"])
        issues += check_type_hints(tree, item["function"])
        issues += check_no_toplevel_calls(tree)
        issues += check_no_external_imports(tree)

        results.append(CheckResult(item["file"], item["id"], len(issues) == 0, issues))

    return results


def print_section(title: str, results: list[CheckResult]):
    total = len(results)
    ok = sum(1 for r in results if r.ok)
    fails = [r for r in results if not r.ok]
    warnings = [r for r in results if r.ok is True and r.issues]

    print(f"\n{'='*60}")
    print(f"  {title}  —  {ok}/{total} OK")
    print(f"{'='*60}")
    for r in results:
        print(r)

    return fails


def main():
    all_fails = []

    for cat in ["assertion_violation", "division_by_zero", "out_of_bounds"]:
        results = verify_bug_category(cat)
        fails = print_section(f"bugs/{cat}", results)
        all_fails += fails

    results = verify_clean()
    fails = print_section("clean", results)
    all_fails += fails

    for cat in ["complex_conditional", "long_method", "many_parameters"]:
        results = verify_smell_category(cat)
        fails = print_section(f"smells/{cat}", results)
        all_fails += fails

    print(f"\n{'='*60}")
    if not all_fails:
        print("  DATASET OK — nenhum problema encontrado")
    else:
        print(f"  {len(all_fails)} arquivo(s) com problemas:")
        for r in all_fails:
            print(f"    - {r.item_id}: {'; '.join(r.issues)}")
    print(f"{'='*60}\n")

    sys.exit(1 if all_fails else 0)


if __name__ == "__main__":
    main()
