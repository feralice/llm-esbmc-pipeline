import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("collect_validated_bugs", ROOT / "scripts" / "collect_validated_bugs.py")
collect = importlib.util.module_from_spec(spec)
sys.modules["collect_validated_bugs"] = collect
spec.loader.exec_module(collect)

PATCH = """diff --git a/pkg/utils.py b/pkg/utils.py
index 1111111..2222222 100644
--- a/pkg/utils.py
+++ b/pkg/utils.py
@@ -12,7 +12,8 @@ def other():

 class Box:
     def ratio(self, total, count):
-        return total / count
+        if count == 0:
+            return 0
+        return total / count


diff --git a/tests/test_utils.py b/tests/test_utils.py
--- a/tests/test_utils.py
+++ b/tests/test_utils.py
@@ -1,2 +1,4 @@
 import pkg
+def test_zero():
+    assert pkg.Box().ratio(1, 0) == 0
"""

BUGGY = "\n" * 9 + "def other():\n    pass\n\nclass Box:\n    def ratio(self, total, count):\n        return total / count\n"


def test_parse_unified_diff_keeps_old_line_ranges_per_file():
    hunks = collect.parse_unified_diff(PATCH)
    assert set(hunks) == {"pkg/utils.py", "tests/test_utils.py"}
    first = hunks["pkg/utils.py"][0]
    assert (first.old_start, first.old_len) == (12, 7)
    assert first.removed == ["        return total / count"]
    assert first.changed_old_lines == [15]


def test_enclosing_function_is_qualified_by_class():
    assert collect.enclosing_function(BUGGY, [15]) == "Box.ratio"
    assert collect.enclosing_function(BUGGY, [11]) == "other"
    assert collect.enclosing_function(BUGGY, [1]) is None


def test_select_single_function_ignores_test_files():
    choice = collect.select_single_function(collect.parse_unified_diff(PATCH), {"pkg/utils.py": BUGGY})
    assert choice == ("pkg/utils.py", "Box.ratio", ["return total / count"])


def test_two_source_files_are_rejected():
    patch = PATCH.replace("tests/test_utils.py", "pkg/other.py")
    reason = collect.select_single_function(collect.parse_unified_diff(patch), {"pkg/utils.py": BUGGY, "pkg/other.py": ""})
    assert isinstance(reason, str) and "files" in reason


def test_pure_addition_hunk_maps_to_the_function_around_it():
    patch = PATCH.replace("-        return total / count\n", "")
    choice = collect.select_single_function(collect.parse_unified_diff(patch), {"pkg/utils.py": BUGGY})
    assert choice[1] == "Box.ratio" and choice[2] == []
