from research_pipeline.scan.callgraph import build_source_callgraph
from research_pipeline.scan.graph_metrics import pagerank

HUB = "def h(x):\n    return x\n\ndef a(x):\n    return h(x)\n\ndef b(x):\n    return h(x) + 1\n"


def test_pagerank_ranks_the_most_called_helper_first():
    scores = pagerank(build_source_callgraph(HUB, "m.py"))
    assert max(scores, key=scores.get) == "m:h"
    assert abs(sum(scores.values()) - 1) < 1e-9


def test_pagerank_handles_recursion_and_empty_graphs():
    recursive = pagerank(build_source_callgraph("def f(n):\n    return f(n - 1)\n", "m.py"))
    assert set(recursive) == {"m:f"}
    isolated = pagerank(build_source_callgraph("def f():\n    pass\n\ndef g():\n    pass\n", "m.py"))
    assert isolated["m:f"] == isolated["m:g"]
    assert pagerank(build_source_callgraph("x = 1\n", "m.py")) == {}


SLICE = '''def f(xs, k):
    return xs[k]


def caller(xs, flag):
    n = len(xs)
    log("x")
    k = n - 1
    if flag:
        k = k - 1
    for item in xs:
        total = item
    return f(xs, k)


def log(msg):
    return msg
'''


def _slice(source=SLICE, key="m:f"):
    from research_pipeline.scan.graph_metrics import caller_slices
    return caller_slices(build_source_callgraph(source, "m.py"), key, rename=False)


def test_slice_keeps_only_the_lines_the_arguments_depend_on():
    text = _slice()
    assert "n = len(xs)" in text and "k = n - 1" in text and "return f(xs, k)" in text
    assert 'log("x")' not in text and "total = item" not in text


def test_slice_follows_reassignment_and_stops_at_parameters():
    text = _slice()
    assert "k = k - 1" in text
    assert "# parameter: xs" in text and "# parameter: flag" not in text


def test_slice_of_function_without_callers_is_empty():
    assert _slice(key="m:caller") == ""


def test_slice_survives_loops_in_the_caller():
    source = "def f(x):\n    return x\n\ndef g(xs):\n    for x in xs:\n        x = x + 1\n        f(x)\n"
    assert "for x in xs:" in _slice(source) and "x = x + 1" in _slice(source)


def _repo_graph(tmp_path, files):
    from research_pipeline.scan.callgraph import build_callgraph
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    return build_callgraph(tmp_path)


def test_cycle_between_two_modules_is_reported(tmp_path):
    from research_pipeline.scan.graph_metrics import architecture_smells
    graph = _repo_graph(tmp_path, {
        "a.py": "from b import g\n\ndef f(x):\n    return g(x)\n",
        "b.py": "def g(x):\n    from a import f\n    return f(x) if x else 0\n"})
    smells = architecture_smells(graph)
    assert [s["smell"] for s in smells] == ["cyclic_dependency"] and set(smells[0]["modules"]) == {"a", "b"}


def test_hub_like_needs_both_high_fan_in_and_fan_out(tmp_path):
    from research_pipeline.scan.graph_metrics import architecture_smells
    files = {"hub.py": "from l1 import x1\nfrom l2 import x2\nfrom l3 import x3\n\n"
                       "def h():\n    return x1() + x2() + x3()\n",
             "sink.py": "def s():\n    return 1\n"}
    for i in (1, 2, 3):
        files[f"l{i}.py"] = f"def x{i}():\n    return 1\n"
        files[f"u{i}.py"] = f"from hub import h\nfrom sink import s\n\ndef use{i}():\n    return h() + s()\n"
    smells = architecture_smells(_repo_graph(tmp_path, files))
    hubs = [s["modules"] for s in smells if s["smell"] == "hub_like_dependency"]
    assert hubs == [["hub"]]


def test_no_smells_on_an_acyclic_project(tmp_path):
    from research_pipeline.scan.graph_metrics import architecture_smells
    graph = _repo_graph(tmp_path, {"a.py": "from b import g\n\ndef f():\n    return g()\n",
                                   "b.py": "def g():\n    return 1\n"})
    assert architecture_smells(graph) == []


ENVY = '''class Pedido:
    def __init__(self, itens):
        self.itens = itens

    def total(self, cliente):
        return len(self.itens) + len(cliente.nome) + len(cliente.cpf)

    def vazio(self):
        return not self.itens

    def eco(self, x):
        return x
'''


def test_metrics_count_self_and_foreign_accesses():
    from research_pipeline.scan.graph_metrics import feature_envy_metrics
    metrics = feature_envy_metrics(build_source_callgraph(ENVY, "m.py"), "m:Pedido.total")
    assert metrics["own_accesses"] == 1 and metrics["foreign_accesses"] == {"cliente": 2}


def test_envy_candidates_need_more_foreign_than_own():
    from research_pipeline.scan.graph_metrics import envy_candidates
    assert envy_candidates(build_source_callgraph(ENVY, "m.py")) == ["m:Pedido.total"]


def test_method_without_self_access_has_zero_own_and_is_not_crashed():
    from research_pipeline.scan.graph_metrics import feature_envy_metrics
    metrics = feature_envy_metrics(build_source_callgraph(ENVY, "m.py"), "m:Pedido.eco")
    assert metrics["own_accesses"] == 0 and metrics["foreign_accesses"] == {}


def test_slice_keeps_the_guard_around_the_call():
    source = "def f(x, d):\n    return x / d\n\ndef g(x, d):\n    if d != 0:\n        return f(x, d)\n    return 0\n"
    assert "if d != 0:" in _slice(source)


def test_slice_follows_the_call_to_the_target_when_a_line_has_several_calls():
    source = ("def f(k):\n    return k\n\ndef log(m):\n    return m\n\n"
              "def g(a, b):\n    m = a + 1\n    k = b - 1\n    return log(m) or f(k)\n")
    text = _slice(source)
    assert "k = b - 1" in text and "m = a + 1" not in text and text.count("# call in") == 1


def test_slice_of_a_method_with_a_column_zero_docstring():
    source = ('def f(x):\n    return x\n\nclass C:\n    def m(self, x):\n        """doc\nstill doc\n"""\n'
              '        y = x + 1\n        return f(y)\n')
    assert "y = x + 1" in _slice(source)


def test_envy_counts_only_parameters_not_modules_or_locals():
    from research_pipeline.scan.graph_metrics import feature_envy_metrics
    source = ("import math\n\nclass C:\n    def t(self, o):\n        out = []\n        out.append(1)\n"
              "        out.append(2)\n        return math.floor(o.a) + self.x\n")
    metrics = feature_envy_metrics(build_source_callgraph(source, "m.py"), "m:C.t")
    assert metrics["foreign_accesses"] == {"o": 1} and metrics["own_accesses"] == 1


def test_staticmethod_has_no_receiver():
    from research_pipeline.scan.graph_metrics import feature_envy_metrics
    source = "class C:\n    @staticmethod\n    def t(o):\n        return o.a + o.b\n"
    metrics = feature_envy_metrics(build_source_callgraph(source, "m.py"), "m:C.t")
    assert metrics["own_accesses"] == 0 and metrics["foreign_accesses"] == {"o": 2}


def test_envy_metrics_of_a_method_with_a_column_zero_docstring():
    from research_pipeline.scan.graph_metrics import feature_envy_metrics
    source = 'class C:\n    def t(self, o):\n        """doc\nmore\n"""\n        return o.a + o.b\n'
    assert feature_envy_metrics(build_source_callgraph(source, "m.py"), "m:C.t")["foreign_accesses"] == {"o": 2}
