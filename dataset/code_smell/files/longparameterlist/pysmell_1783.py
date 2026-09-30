# smell: LongParameterList
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/boto/boto/blob/2.38.0/boto/cloudformation/stack.py#L206-L207
# smelly line(s) in the original file: 206
# smelly line(s) in this file: 8
# ids: pysmell_1783
# note: Python 2 era source, kept as found
def startElement(self, name, attrs, connection):
    return None
