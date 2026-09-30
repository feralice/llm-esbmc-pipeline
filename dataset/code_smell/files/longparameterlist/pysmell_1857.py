# smell: LongParameterList
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/nltk/nltk/blob/3.0.2/nltk/featstruct.py#L1862-L1863
# smelly line(s) in the original file: 1862
# smelly line(s) in this file: 8
# ids: pysmell_1857
# note: Python 2 era source, kept as found
def read_value(self, s, position, reentrances, parser):
    return parser.read_value(s, position, reentrances)
