from research_pipeline.verify.dead_guards import fold_dead_guards
from research_pipeline.verify.grounding import Grounded, ground
from research_pipeline.verify.hypothesis import BugHypothesis


def _folded(source):
    out, transforms = fold_dead_guards(source)
    assert len(out.splitlines()) == len(source.splitlines())
    compile(out, "folded.py", "exec")
    return out, transforms


def test_a_type_checking_block_becomes_pass():
    source = "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from pandas import DataFrame\n    import numpy\nx = 1\n"
    out, transforms = _folded(source)
    assert out == "from typing import TYPE_CHECKING\nif False:\n    pass\n\nx = 1\n"
    assert transforms == ["dead_guards_folded:1"]


def test_a_python_2_test_decides_the_whole_and():
    # bip_keras_33: `unicode` only lives in the Python 2 branch.
    source = ("import sys\n\ndef f(text):\n    if sys.version_info < (3,) and isinstance(text, unicode):\n"
              "        text = text.encode('utf-8')\n    return text.split()\n")
    out, _ = _folded(source)
    assert "unicode" not in out
    assert "    if False:\n        pass\n    return text.split()\n" in out


def test_a_python_3_test_becomes_true_and_keeps_its_body():
    source = "import sys\nif sys.version_info[0] >= 3:\n    y = 1\nelse:\n    y = 2\n"
    out, _ = _folded(source)
    assert out.startswith("import sys\nif True:\n    y = 1\n")


def test_an_elif_on_the_major_version_is_folded():
    source = "import sys\nif x:\n    a = 1\nelif sys.version_info.major == 2:\n    a = long(1)\n"
    out, _ = _folded(source)
    assert "long" not in out and "elif False:" in out


def test_a_call_before_the_decided_operand_keeps_the_test():
    source = "import sys\nif f() and sys.version_info < (3,):\n    g()\n"
    assert fold_dead_guards(source) == (source, [])


def test_a_program_without_guards_is_left_alone():
    source = "def f(x):\n    if x > 0:\n        return 1\n    return 0\n"
    assert fold_dead_guards(source) == (source, [])


def test_grounding_no_longer_needs_the_python_2_name():
    source = ("import sys\n\n\ndef words(text):\n    if sys.version_info < (3,) and isinstance(text, unicode):\n"
              "        text = text.encode('utf-8')\n    return text.split()[0]\n")
    grounded = ground(BugHypothesis("w.py", "words", "text.split()[0]"), source)
    assert isinstance(grounded, Grounded)
    assert "unicode" not in grounded.module
    assert "dead_guards_folded:1" in grounded.transforms


def test_a_decorated_dead_body_still_parses():
    # Review C1: blanking from the def line left the decorator alone.
    source = "from typing import TYPE_CHECKING, overload\nif TYPE_CHECKING:\n    @overload\n    def f(): ...\nx = 1\n"
    out, _ = _folded(source)
    assert "@overload" not in out


def test_non_ascii_text_in_a_folded_test_keeps_the_line_intact():
    # Review C2: AST offsets count UTF-8 bytes.
    source = 'from typing import TYPE_CHECKING\nif TYPE_CHECKING and name == "é":\n    import x\n'
    out, _ = _folded(source)
    assert "if False:" in out


def test_a_version_field_beyond_the_third_is_left_alone():
    # Review I1: sys.version_info[3] crashed grounding.
    source = 'import sys\nif sys.version_info[3] == "final":\n    y = 1\n'
    out, _ = _folded(source)


def test_a_three_field_tuple_compares_like_the_five_field_version_info():
    # Review I2: on 3.12.3, version_info == (3, 12, 3) is False and > (3, 12, 3) is True.
    import sys
    v = tuple(sys.version_info[:3])
    source = f"import sys\nif sys.version_info == {v}:\n    a = 1\nif sys.version_info > {v}:\n    b = 1\n"
    out, _ = _folded(source)
    assert "if False:" in out and "if True:" in out


def test_a_local_named_type_checking_is_not_the_typing_constant():
    # Review I3: the bug line vanished from the target.
    source = "def f(a):\n    TYPE_CHECKING = a > 0\n    if TYPE_CHECKING:\n        return 10 // a\n    return 0\n"
    assert fold_dead_guards(source) == (source, [])


def test_an_attribute_named_type_checking_is_not_folded():
    source = "from typing import TYPE_CHECKING\ndef f(self):\n    if self.TYPE_CHECKING:\n        return 1\n"
    assert fold_dead_guards(source) == (source, [])


def test_the_dead_else_of_a_true_test_becomes_pass():
    # Review I9: the most common Python 2/3 shape kept its Python 2 branch.
    source = "import sys\nif sys.version_info >= (3,):\n    y = str(x)\nelse:\n    y = unicode(x)\n"
    out, _ = _folded(source)
    assert "unicode" not in out and "else:\n    pass" in out


def test_an_attribute_before_the_decided_operand_keeps_the_test():
    # A property or __getattr__ would run in CPython.
    source = "import sys\nif obj.flag and sys.version_info < (3,):\n    g()\n"
    assert fold_dead_guards(source) == (source, [])
