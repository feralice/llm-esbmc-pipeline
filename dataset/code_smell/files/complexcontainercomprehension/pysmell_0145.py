# smell: ComplexContainerComprehension
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/nltk/nltk/blob/3.0.2/nltk/sem/glue.py#L411-L426
# smelly line(s) in the original file: 416
# smelly line(s) in this file: 13
# ids: pysmell_0145
# note: Python 2 era source, kept as found
def lookup_unique(self, rel, node, depgraph):
    """
    Lookup 'key'. There should be exactly one item in the associated relation.
    """
    deps = [
        depgraph.nodes[dep]
        for dep in sum(list(node['deps'].values()), [])
        if depgraph.nodes[dep]['rel'].lower() == rel.lower()
    ]

    if len(deps) == 0:
        raise KeyError("'%s' doesn't contain a feature '%s'" % (node['word'], rel))
    elif len(deps) > 1:
        raise KeyError("'%s' should only have one feature '%s'" % (node['word'], rel))
    else:
        return deps[0]
