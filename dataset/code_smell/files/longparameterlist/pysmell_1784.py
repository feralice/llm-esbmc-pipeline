# smell: LongParameterList
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/boto/boto/blob/2.38.0/boto/cloudfront/identity.py#L88-L94
# smelly line(s) in the original file: 88
# smelly line(s) in this file: 8
# ids: pysmell_1784
# note: Python 2 era source, kept as found
def endElement(self, name, value, connection):
    if name == 'Comment':
        self.comment = value
    elif name == 'CallerReference':
        self.caller_reference = value
    else:
        setattr(self, name, value)
