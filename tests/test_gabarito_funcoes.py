import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from gabarito_funcoes import changed_old_lines, touched_functions  # noqa: E402

SOURCE = """class A:
    def f(self, x):
        return x[0]

    def g(self, y):
        return y / 2


def top(z):
    return z.a
"""

DIFF = """--- a/mod.py
+++ b/mod.py
@@ -2,3 +2,4 @@
     def f(self, x):
+        if not x:
+            return None
         return x[0]
@@ -9,2 +11,2 @@
 def top(z):
-    return z.a
+    return z.a if z else None
--- a/other.py
+++ b/other.py
@@ -1,1 +1,1 @@
-old
+new
"""


def test_changed_lines_only_for_the_named_file():
    assert changed_old_lines(DIFF, "mod.py") == [3, 3, 10]


def test_touched_functions_are_the_innermost_with_class_prefix():
    assert touched_functions(SOURCE, [3, 10]) == ["A.f", "top"]


def test_line_outside_any_function_is_module_level():
    assert touched_functions(SOURCE, [1]) == ["<módulo>"]
