# smell: LongParameterList
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/nltk/nltk/blob/3.0.2/nltk/collocations.py#L178-L185
# smelly line(s) in the original file: 178
# smelly line(s) in this file: 8
# ids: pysmell_1856
# note: Python 2 era source, kept as found
def __init__(self, word_fd, bigram_fd, wildcard_fd, trigram_fd):
    """Construct a TrigramCollocationFinder, given FreqDists for
    appearances of words, bigrams, two words with any word between them,
    and trigrams.
    """
    AbstractCollocationFinder.__init__(self, word_fd, trigram_fd)
    self.wildcard_fd = wildcard_fd
    self.bigram_fd = bigram_fd
