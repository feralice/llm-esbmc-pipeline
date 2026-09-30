import ast

from research_pipeline.verify.context import context_module

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


def test_pruned_top_level_write_to_kept_name_is_kept():
    source = "D = 0\nD += 4\n\n\ndef f(x: int):\n    return x // D\n"
    assert "D += 4" in context_module(source, "f")


def test_global_rebinding_function_called_at_top_level_is_kept_with_the_call():
    source = (
        "D = 0\n\n\ndef init():\n    global D\n    D = 5\n\n\ninit()\n\n\n"
        "def f(x: int):\n    return x // D\n"
    )
    module = context_module(source, "f")
    assert "def init():" in module and "\ninit()" in module


def test_global_rebinding_function_never_called_is_left_out():
    source = "D = 1\n\n\ndef reset():\n    global D\n    D = 0\n\n\ndef f(x: int):\n    return x // D\n"
    module = context_module(source, "f")
    assert "D = 1" in module and "reset" not in module


def test_top_level_mutation_of_kept_container_is_kept():
    source = "TABLE = {}\nTABLE.update(k=1)\nprint('noise')\n\n\ndef f(key):\n    return TABLE[key]\n"
    module = context_module(source, "f")
    assert "TABLE.update(k=1)" in module and "noise" not in module


def test_top_level_call_of_function_that_mutates_kept_data_is_kept():
    source = (
        "TABLE = {}\n\n\ndef fill():\n    TABLE['k'] = 1\n\n\nfill()\n\n\n"
        "def f(key):\n    return TABLE[key]\n"
    )
    module = context_module(source, "f")
    assert "def fill():" in module and "\nfill()" in module


def test_assignment_that_only_reads_kept_data_is_left_out():
    source = (
        "from collections import namedtuple\n\nRow = namedtuple('Row', 'a b')\n"
        "FORMATS = {'simple': Row(1, 2)}\n\n\ndef f(r):\n    return Row(r, r)\n"
    )
    module = context_module(source, "f")
    assert "Row = namedtuple" in module and "FORMATS" not in module


def test_main_guard_touching_kept_data_is_never_kept():
    source = "DATA = []\n\n\ndef f():\n    return DATA[0]\n\n\nif __name__ == '__main__':\n    DATA.append(1)\n"
    assert "__main__" not in context_module(source, "f")


def test_top_level_item_assignment_is_kept_verbatim():
    source = "TABLE = {}\nTABLE['k'] = 1\n\n\ndef f(key):\n    return TABLE[key]\n"
    assert "TABLE['k'] = 1" in context_module(source, "f")


def test_unrelated_side_effect_and_docstring_are_fine():
    source = '"""doc."""\nimport os\nLIMIT = 3\nprint(os.getcwd())\n\n\ndef f(x):\n    return x // LIMIT\n'
    assert "LIMIT = 3" in context_module(source, "f")


def test_dropped_statement_that_only_calls_a_kept_module_is_fine():
    source = "import re\n\nPATTERN = re.compile('x')\n\n\ndef f(s):\n    return re.match('a', s)\n"
    module = context_module(source, "f")
    assert "import re" in module and "PATTERN" not in module


def test_conditional_import_block_binding_a_kept_name_is_kept_whole():
    source = (
        "import sys\n\nif sys.version_info[0] == 3:\n    text = str\nelse:\n    text = unicode\n\n\n"
        "def f(x):\n    return text(x)\n"
    )
    module = context_module(source, "f")
    assert "if sys.version_info[0] == 3:" in module and "import sys" in module


def test_try_import_block_is_kept_whole():
    source = "try:\n    import json\nexcept ImportError:\n    json = None\n\n\ndef f(s):\n    return json.loads(s)\n"
    assert "except ImportError:" in context_module(source, "f")


def test_top_level_call_passing_kept_data_is_kept():
    source = "ITEMS = []\nregister(ITEMS)\n\n\ndef f(i):\n    return ITEMS[i]\n"
    assert "register(ITEMS)" in context_module(source, "f")


def test_class_method_rebinding_kept_global_is_kept_with_its_call():
    source = (
        "X = 0\n\n\nclass C:\n    @classmethod\n    def load(cls):\n        global X\n        X = 10\n\n\n"
        "C.load()\n\n\ndef f(a):\n    return a / X\n"
    )
    module = context_module(source, "f")
    assert "C.load()" in module and "global X" in module


def test_read_only_use_of_kept_data_is_not_kept():
    source = "CFG = {}\nprint(CFG)\n\n\ndef show():\n    print(CFG)\n\n\nshow()\n\n\ndef f(k):\n    return CFG[k]\n"
    module = context_module(source, "f")
    assert "print(CFG)" not in module and "show()" not in module
