def _pipe(docs, proc, kwargs):
    kwargs = dict(kwargs)
    for arg in ["n_threads", "batch_size"]:
        if arg in kwargs:
            kwargs.pop(arg)
    for doc in docs:
        doc = proc(doc, **kwargs)
        yield doc


class Language:
    def pipe(self, texts, as_tuples=False, n_threads=-1, batch_size=1000, disable=[], component_cfg=None):
        for name, pipe in self.pipeline:
            if name in disable:
                continue
            kwargs = component_cfg.get(name, {})
            kwargs.setdefault("batch_size", batch_size)
            if not hasattr(pipe, "pipe"):
                docs = _pipe(pipe, docs, kwargs)
            else:
                docs = pipe.pipe(docs, **kwargs)
        for doc in docs:
            yield doc
