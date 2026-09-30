# smell: LongLambdaFunction
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/nltk/nltk/blob/3.0.2/nltk/metrics/agreement.py#L111-L114
# smelly line(s) in the original file: 112
# smelly line(s) in this file: 9
# ids: pysmell_1030
# note: Python 2 era source, kept as found
def __str__(self):
    return "\r\n".join(map(lambda x:"%s\t%s\t%s" %
                           (x['coder'], x['item'].replace('_', "\t"),
                            ",".join(x['labels'])), self.data))
