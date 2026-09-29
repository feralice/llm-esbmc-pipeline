import ast

from research_pipeline.scan.context import context_module

SOURCE = '''import math
import os

LIMIT = 10
print("side effect")


def helper(x):
    return math.sqrt(x)


def unrelated():
    return os.getcwd()


@staticmethod
def decorated(y):
    return y


def target(a, b):
    return helper(a) / b + LIMIT


class Service:
    rate = 2

    def run(self, x):
        return decorated(x) // self.rate


if __name__ == "__main__":
    target(1, 0)
'''


def _names(module: str) -> set[str]:
    tree = ast.parse(module)
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Import):
            names.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return names


def test_keeps_transitive_dependencies_only():
    assert _names(context_module(SOURCE, "target")) == {"target", "helper", "math", "LIMIT"}


def test_drops_module_side_effects_and_main_guard():
    module = context_module(SOURCE, "target")
    assert "print(" not in module
    assert "__main__" not in module


def test_method_keeps_whole_class_and_its_dependencies():
    module = context_module(SOURCE, "Service.run")
    assert _names(module) == {"Service", "decorated"}
    assert "@staticmethod" in module


def test_statements_are_verbatim_and_in_source_order():
    module = context_module(SOURCE, "target")
    assert module.index("import math") < module.index("LIMIT = 10") < module.index("def helper")
    assert "def helper(x):\n    return math.sqrt(x)\n" in module


def test_missing_target_returns_empty():
    assert context_module(SOURCE, "absent") == ""


def test_pruned_top_level_write_to_kept_name_refuses_context():
    source = "D = 0\nD += 4\n\n\ndef f(x: int):\n    return x // D\n"
    assert context_module(source, "f") == ""


def test_global_rebinding_of_kept_name_refuses_context():
    source = (
        "D = 0\n\n\ndef init():\n    global D\n    D = 5\n\n\ninit()\n\n\n"
        "def f(x: int):\n    return x // D\n"
    )
    assert context_module(source, "f") == ""


def test_top_level_mutation_of_kept_container_refuses_context():
    source = "TABLE = {}\nTABLE.update(k=1)\n\n\ndef f(key):\n    return TABLE[key]\n"
    assert context_module(source, "f") == ""


def test_top_level_item_assignment_is_kept_verbatim():
    source = "TABLE = {}\nTABLE['k'] = 1\n\n\ndef f(key):\n    return TABLE[key]\n"
    assert "TABLE['k'] = 1" in context_module(source, "f")


def test_unrelated_side_effect_and_docstring_are_fine():
    source = '"""doc."""\nimport os\nLIMIT = 3\nprint(os.getcwd())\n\n\ndef f(x):\n    return x // LIMIT\n'
    assert "LIMIT = 3" in context_module(source, "f")
