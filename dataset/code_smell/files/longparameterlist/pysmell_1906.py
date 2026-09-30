# smell: LongParameterList
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/matplotlib/matplotlib/blob/v1.4.3/lib/matplotlib/spines.py#L44-L85
# smelly line(s) in the original file: 44
# smelly line(s) in this file: 8
# ids: pysmell_1906
# note: Python 2 era source, kept as found
def __init__(self, axes, spine_type, path, **kwargs):
    """
    - *axes* : the Axes instance containing the spine
    - *spine_type* : a string specifying the spine type
    - *path* : the path instance used to draw the spine

    Valid kwargs are:
    %(Patch)s
    """
    super(Spine, self).__init__(**kwargs)
    self.axes = axes
    self.set_figure(self.axes.figure)
    self.spine_type = spine_type
    self.set_facecolor('none')
    self.set_edgecolor(rcParams['axes.edgecolor'])
    self.set_linewidth(rcParams['axes.linewidth'])
    self.set_capstyle('projecting')
    self.axis = None

    self.set_zorder(2.5)
    self.set_transform(self.axes.transData)  # default transform

    self._bounds = None  # default bounds
    self._smart_bounds = False

    # Defer initial position determination. (Not much support for
    # non-rectangular axes is currently implemented, and this lets
    # them pass through the spines machinery without errors.)
    self._position = None
    assert isinstance(path, matplotlib.path.Path)
    self._path = path

    # To support drawing both linear and circular spines, this
    # class implements Patch behavior two ways. If
    # self._patch_type == 'line', behave like a mpatches.PathPatch
    # instance. If self._patch_type == 'circle', behave like a
    # mpatches.Ellipse instance.
    self._patch_type = 'line'

    # Behavior copied from mpatches.Ellipse:
    # Note: This cannot be calculated until this is added to an Axes
    self._patch_transform = mtransforms.IdentityTransform()
