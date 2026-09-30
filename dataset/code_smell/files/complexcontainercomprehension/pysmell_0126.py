# smell: ComplexContainerComprehension
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/nltk/nltk/blob/3.0.2/nltk/corpus/reader/timit.py#L279-L285
# smelly line(s) in the original file: 283
# smelly line(s) in this file: 12
# ids: pysmell_0126
# note: Python 2 era source, kept as found
def phone_times(self, utterances=None):
    """
    offset is represented as a number of 16kHz samples!
    """
    return [(line.split()[2], int(line.split()[0]), int(line.split()[1]))
            for fileid in self._utterance_fileids(utterances, '.phn')
            for line in self.open(fileid) if line.strip()]
