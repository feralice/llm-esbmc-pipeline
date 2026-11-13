from research_pipeline.scan.prefilter import drop_reason

CLASS_SRC = '''
import re
cache = {}

class Cw:
    def __init__(self):
        self.client = None

    def pages(self, token=None):
        resp = self.client.get(token)
        if resp.get("next"):
            self.pages(resp.get("next"))

def top():
    global registry
    registry = {}

def reads():
    return registry["x"] + cache["y"]
'''


def test_drops_self_method_that_exists():
    note = "If the class has no pages attribute, self.pages raises AttributeError"
    assert drop_reason("self.pages(resp.get('next'))", note, CLASS_SRC, "Cw.pages")


def test_keeps_self_method_that_is_missing():
    note = "self.nope raises AttributeError"
    assert drop_reason("self.nope(1)", note, CLASS_SRC, "Cw.pages") is None


def test_drops_name_defined_at_module_level():
    note = "cache is a free name; NameError if not defined"
    assert drop_reason("if key in cache:", note, CLASS_SRC, "reads")


def test_drops_name_declared_global_in_a_function():
    note = "registry is not defined, so NameError"
    assert drop_reason("registry['x']", note, CLASS_SRC, "reads")


def test_keeps_name_error_for_undefined_name():
    note = "ghost is not defined, NameError"
    assert drop_reason("ghost + 1", note, CLASS_SRC, "reads") is None


def test_ignores_existing_name_when_claim_is_not_about_definition():
    note = "cache['y'] raises KeyError when y is absent"
    assert drop_reason("cache['y']", note, CLASS_SRC, "reads") is None


def test_drops_hypothesis_that_admits_missing_context():
    note = "Whether this raises depends on _convert_values, which is not shown"
    assert "context" in drop_reason("conv(x)", note, CLASS_SRC, "reads")
    note = "Reachability depends on the helper, which is missing from the context"
    assert drop_reason("h(x)", note, CLASS_SRC, "reads")
    note = "the finding is reported with context_needed rather than confirmed"
    assert drop_reason("h(x)", note, CLASS_SRC, "reads")


def test_keeps_plain_hypothesis():
    assert drop_reason("a[0]", "a is empty, so IndexError", CLASS_SRC, "reads") is None


def test_unparseable_source_keeps_hypothesis():
    assert drop_reason("self.x()", "AttributeError", "def (:", "A.b") is None


def test_assignment_expression_is_not_a_missing_attribute_claim():
    note = "self.size is set but content_length is unset, AttributeError later"
    assert drop_reason("self.size = init['ContentLength']", note, "class A:\n    def f(self):\n        self.size = 1\n", "A.f") is None


def test_attribute_error_from_a_call_does_not_drop_an_existing_module_name():
    src = "from distutils.util import strtobool\n"
    note = "a tuple reaches strtobool and raises AttributeError"
    assert drop_reason("verify = strtobool(verify)", note, src, "f") is None


def test_none_attribute_error_is_not_a_missing_method():
    src = "class P:\n    def deinit(self):\n        self.pin.stop()\n        self.pin = None\n"
    note = "A second call makes self.pin.stop() run on None and raises AttributeError"
    assert drop_reason("self.pin.stop()", note, src, "P.deinit") is None


def test_attribute_set_only_inside_a_method_is_not_proof_of_existence():
    src = "class P:\n    def run(self):\n        self.last = 1\n    def idle(self):\n        return self.last\n"
    note = "self.last may not exist yet if run was never called, AttributeError: no attribute last"
    assert drop_reason("return self.last", note, src, "P.idle") is None


def test_scan_detection_holds_the_dropped_hypothesis_with_its_reason(tmp_path):
    from types import SimpleNamespace

    from research_pipeline.scan.pipeline import _detect

    source = tmp_path / "m.py"
    source.write_text("class C:\n    def go(self, t=None):\n        self.go(t)\n    def other(self):\n        pass\n")
    finding = SimpleNamespace(verifiable=True, explanation="if the class has no go method, AttributeError",
                              metadata={"expression": "self.go(t)"})
    keep = SimpleNamespace(verifiable=True, explanation="t is None so IndexError", metadata={"expression": "t[0]"})
    analyzer = SimpleNamespace(analyze=lambda unit: [finding, keep])
    target = SimpleNamespace(file=str(source), qualname="C.go", unit=None)

    off = _detect(analyzer, target)
    on = _detect(analyzer, target, prefilter=True)

    assert len(off["candidates"]) == 2 and not off["held"]
    assert [c["expression"] for c in on["candidates"]] == ["t[0]"]
    assert on["held"][0]["expression"] == "self.go(t)" and "defined" in on["held"][0]["reason"]


def test_scan_skip_takes_the_next_batch(tmp_path):
    from research_pipeline.scan.pipeline import plan_scan

    repo = tmp_path / "repo"
    repo.mkdir()
    body = "\n".join(f"def f{i}(a):\n    return a[{i}]\n" for i in range(4))
    (repo / "m.py").write_text(body)

    first = plan_scan(repo, tmp_path / "o1", limit=2)
    second = plan_scan(repo, tmp_path / "o2", limit=2, skip=2)

    names = [t.qualname for t in first.targets] + [t.qualname for t in second.targets]
    assert sorted(names) == ["f0", "f1", "f2", "f3"]
