def pipe_call_order_ok(args_swapped: bool) -> None:
    # Real code (spacy/language.py:Language.pipe, BugsInPy spacy bug #5):
    # docs = _pipe(pipe, docs, kwargs) swaps the two positional arguments of
    # _pipe(docs, proc, kwargs), which does `for doc in docs: proc(doc, **kwargs)`.
    # Called with the arguments swapped, the (non-iterable) pipe component is
    # iterated and the actual docs iterable is called as a function --
    # TypeError either way. ESBMC-Python's frontend requires static type
    # consistency between the two positions, so the real precondition
    # (arguments passed in the order the callee's signature expects) is
    # asserted directly.
    assert not args_swapped


def main() -> None:
    args_swapped: bool = nondet_bool()
    pipe_call_order_ok(args_swapped)


main()
