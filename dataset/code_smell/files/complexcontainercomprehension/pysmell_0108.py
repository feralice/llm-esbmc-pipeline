# smell: ComplexContainerComprehension
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/nltk/nltk/blob/3.0.2/nltk/corpus/reader/framenet.py#L1201-L1230
# smelly line(s) in the original file: 1230
# smelly line(s) in this file: 37
# ids: pysmell_0108
# note: Python 2 era source, kept as found
def fes(self, name=None):
    '''
    Lists frame element objects. If 'name' is provided, this is treated as 
    a case-insensitive regular expression to filter by frame name. 
    (Case-insensitivity is because casing of frame element names is not always 
    consistent across frames.)

    >>> from nltk.corpus import framenet as fn
    >>> fn.fes('Noise_maker')
    [<fe ID=6043 name=Noise_maker>]
    >>> sorted([(fe.frame.name,fe.name) for fe in fn.fes('sound')])
    [('Cause_to_make_noise', 'Sound_maker'), ('Make_noise', 'Sound'), 
     ('Make_noise', 'Sound_source'), ('Sound_movement', 'Location_of_sound_source'), 
     ('Sound_movement', 'Sound'), ('Sound_movement', 'Sound_source'), 
     ('Sounds', 'Component_sound'), ('Sounds', 'Location_of_sound_source'), 
     ('Sounds', 'Sound_source'), ('Vocalizations', 'Location_of_sound_source'), 
     ('Vocalizations', 'Sound_source')]
    >>> sorted(set(fe.name for fe in fn.fes('^sound')))
    ['Sound', 'Sound_maker', 'Sound_source']
    >>> len(fn.fes('^sound$'))
    2

    :param name: A regular expression pattern used to match against
        frame element names. If 'name' is None, then a list of all
        frame elements will be returned.
    :type name: str
    :return: A list of matching frame elements
    :rtype: list(AttrDict)
    '''
    return PrettyList(fe for f in self.frames() for fename,fe in f.FE.items() if name is None or re.search(name, fename, re.I))
