# smell: ComplexContainerComprehension
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/nltk/nltk/blob/3.0.2/nltk/corpus/reader/timit.py#L292-L295
# smelly line(s) in the original file: 293
# smelly line(s) in this file: 9
# ids: pysmell_0127
# note: Python 2 era source, kept as found
def word_times(self, utterances=None):
    return [(line.split()[2], int(line.split()[0]), int(line.split()[1]))
            for fileid in self._utterance_fileids(utterances, '.wrd')
            for line in self.open(fileid) if line.strip()]
