# smell: LargeClass
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/matplotlib/matplotlib/blob/v1.4.3/lib/matplotlib/artist.py#L79-L110
# smelly line(s) in the original file: 79
# smelly line(s) in this file: 8
# ids: pysmell_0463
# note: Python 2 era source, kept as found
def __init__(self):
    self.figure = None

    self._transform = None
    self._transformSet = False
    self._visible = True
    self._animated = False
    self._alpha = None
    self.clipbox = None
    self._clippath = None
    self._clipon = True
    self._lod = False
    self._label = ''
    self._picker = None
    self._contains = None
    self._rasterized = None
    self._agg_filter = None

    self.eventson = False  # fire events only if eventson
    self._oid = 0  # an observer id
    self._propobservers = {}  # a dict from oids to funcs
    try:
        self.axes = None
    except AttributeError:
        # Handle self.axes as a read-only property, as in Figure.
        pass
    self._remove_method = None
    self._url = None
    self._gid = None
    self._snap = None
    self._sketch = rcParams['path.sketch']
    self._path_effects = rcParams['path.effects']
