# smell: LongParameterList
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/nltk/nltk/blob/3.0.2/nltk/chunk/regexp.py#L1171-L1180
# smelly line(s) in the original file: 1171
# smelly line(s) in this file: 8
# ids: pysmell_1864
# note: Python 2 era source, kept as found
def _add_stage(self, rules, lhs, root_label, trace):
    """
    Helper function for __init__: add a new stage to the parser.
    """
    if rules != []:
        if not lhs:
            raise ValueError('Expected stage marker (eg NP:)')
        parser = RegexpChunkParser(rules, chunk_label=lhs,
                                   root_label=root_label, trace=trace)
        self._stages.append(parser)
