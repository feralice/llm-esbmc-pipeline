import subprocess
import sys

from research_pipeline.verify.graph_tool import write_graph

ORIGINAL = '''class Parser:
    def parse(self, line):
        return line.split(",")


class Other:
    def parse(self, text):
        return text


def load(path):
    p = Parser()
    return p.parse(path)


def main():
    return load("a,b")
'''


def _ask(tmp_path, *args):
    write_graph(tmp_path, ORIGINAL)
    done = subprocess.run([sys.executable, "graph.py", *args], cwd=tmp_path, capture_output=True, text=True,
                          check=False)
    assert done.returncode == 0, done.stderr
    return done.stdout


def test_callers_prints_each_call_site_with_context(tmp_path):
    out = _ask(tmp_path, "callers", "load")
    assert "main" in out and 'return load("a,b")' in out


def test_class_prints_its_source(tmp_path):
    assert "return line.split" in _ask(tmp_path, "class", "Parser")


def test_unknown_name_says_not_found(tmp_path):
    assert "not found" in _ask(tmp_path, "callers", "nothing")


def test_ambiguous_name_lists_the_options(tmp_path):
    out = _ask(tmp_path, "where", "parse")
    assert "Parser.parse" in out and "Other.parse" in out
