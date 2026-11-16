

def test_stub_may_not_define_or_annotate_a_refused_builtin():
    from research_pipeline.verify.healing import stub_problems

    redefined = stub_problems("class bytearray:\n    def append(self, value: int = None) -> None:\n        pass\n")
    annotated = stub_problems("class Message:\n    def __init__(self, data: bytearray = None) -> None:\n        pass\n")
    assert any("bytearray" in p for p in redefined)
    assert any("bytearray" in p for p in annotated)
    assert stub_problems("class Message:\n    def __init__(self, data: bytes = None) -> None:\n        pass\n") == []
