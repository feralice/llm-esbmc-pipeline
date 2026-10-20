import json
from dataclasses import dataclass, field

from research_pipeline.scan.callgraph import build_callgraph
from research_pipeline.verify.esbmc_knowledge import KnowledgeIndex, Snippet
from research_pipeline.verify.healing import Healer, graph_definitions
from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.llm_client import SynthResult
from research_pipeline.verify.outcome import (
    GROUNDING_FAILED,
    MISSING_DEPENDENCY,
    UNSUPPORTED,
)

SOURCE = '''from .util import scale


class Reader:
    def parse(self, line):
        parts = line.split(",")
        return int(parts[1]) / scale(parts[0])
'''


@dataclass
class FakeLLM:
    replies: list
    prompts: list = field(default_factory=list)

    def complete(self, system_prompt, user_prompt, *, json_mode=False):
        self.prompts.append(user_prompt)
        reply = self.replies.pop(0) if self.replies else "{}"
        return SynthResult(harness=reply if isinstance(reply, str) else json.dumps(reply), raw_response="",
                           model="fake", telemetry={})


def _h(function="Reader.parse", expression="int(parts[1]) / scale(parts[0])"):
    return BugHypothesis(file="reader.py", function=function, suspect_expression=expression,
                         trigger_condition="scale returns 0")


def _repo(tmp_path, util="def scale(tag):\n    return len(tag) - 2\n"):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg/__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg/reader.py").write_text(SOURCE, encoding="utf-8")
    (tmp_path / "pkg/util.py").write_text(util, encoding="utf-8")
    return build_callgraph(tmp_path)


def test_grounding_patch_keeps_literal_expression():
    llm = FakeLLM([{"function": "Reader.parse", "expression": "int(parts[1]) / scale(parts[0])"}])
    patch = Healer(llm, None).propose(_h("parse", "parts[1] / scale"), SOURCE, GROUNDING_FAILED,
                                      "function 'parse' not found (or ambiguous)", [])
    assert (patch.hypothesis_function, patch.hypothesis_expression) == ("Reader.parse", "int(parts[1]) / scale(parts[0])")
    assert "Reader.parse" in llm.prompts[0]


def test_grounding_patch_with_invented_expression_is_dropped():
    llm = FakeLLM([{"function": "Reader.parse", "expression": "x / y"}])
    assert Healer(llm, None).propose(_h("parse"), SOURCE, GROUNDING_FAILED, "not found", []) is None


def test_missing_dependency_uses_graph_before_llm(tmp_path):
    llm = FakeLLM([])
    patch = Healer(llm, None, _repo(tmp_path)).propose(_h(), SOURCE, MISSING_DEPENDENCY,
                                                      "undefined name(s): scale", [])
    assert "return len(tag) - 2" in patch.real_code
    assert patch.definitions == "" and llm.prompts == []


def test_graph_definitions_follow_calls_two_levels(tmp_path):
    graph = _repo(tmp_path, "def scale(tag):\n    return width(tag)\n\n\ndef width(t):\n    return deep(t)\n\n\n"
                            "def deep(t):\n    return 1\n")
    code = graph_definitions({"scale"}, graph, depth=2)
    assert "def scale" in code and "def width" in code and "def deep" not in code


def test_ambiguous_graph_name_falls_back_to_llm(tmp_path):
    graph = _repo(tmp_path)
    (tmp_path / "pkg/other.py").write_text("def scale(x):\n    return 3\n", encoding="utf-8")
    graph = build_callgraph(tmp_path)
    stub = "def scale(a0=None) -> int:\n    return nondet_int()\n"
    llm = FakeLLM([{"definitions": stub}])
    patch = Healer(llm, None, graph).propose(_h(), SOURCE, MISSING_DEPENDENCY, "undefined name(s): scale", [])
    assert patch.real_code == "" and patch.definitions == stub
    assert "parts[0]" in llm.prompts[0]


def test_unsupported_prompt_carries_knowledge():
    index = KnowledgeIndex("c" * 40, [Snippet("README", "Type Annotations", "Annotate every receiver parameter.")], [])
    llm = FakeLLM([{"edits": [{"old": "def parse(self, line):", "new": "def parse(self, line: str):"}]}])
    patch = Healer(llm, index).propose(_h(), SOURCE, UNSUPPORTED,
                                       "ERROR: Could not resolve type of receiver. Add a type annotation", [])
    assert "Annotate every receiver parameter." in llm.prompts[0]
    assert patch.edits == (("def parse(self, line):", "def parse(self, line: str):"),)


def test_previous_rounds_are_shown():
    llm = FakeLLM([{"edits": []}])
    Healer(llm, None).propose(_h(), SOURCE, UNSUPPORTED, "ERROR: x", [{"problems": ["the body changed"]}])
    assert "the body changed" in llm.prompts[0]


def test_unparseable_reply_returns_none():
    llm = FakeLLM(["not json at all"])
    assert Healer(llm, None).propose(_h(), SOURCE, UNSUPPORTED, "ERROR: x", []) is None


def test_empty_reply_returns_none():
    assert Healer(FakeLLM([{}]), None).propose(_h(), SOURCE, UNSUPPORTED, "ERROR: x", []) is None
