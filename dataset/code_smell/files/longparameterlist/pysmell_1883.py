# smell: LongParameterList
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/nltk/nltk/blob/3.0.2/nltk/tag/brill_trainer_orig.py#L399-L408
# smelly line(s) in the original file: 399
# smelly line(s) in this file: 8
# ids: pysmell_1883
# note: Python 2 era source, kept as found
def _trace_rule(self, rule, score, fixscore, numchanges):
    rulestr = rule.format(self._ruleformat)

    if self._trace > 2:
        print(('%4d%4d%4d%4d ' % (score, fixscore, fixscore-score,
                                  numchanges-fixscore*2+score)), '|', end=' ')
        print(textwrap.fill(rulestr, initial_indent=' '*20, width=79,
                            subsequent_indent=' '*18+'|   ').strip())
    else:
        print(rulestr)
