# smell: LongParameterList
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/ipython/ipython/blob/rel-3.1.0/IPython/core/debugger.py#L78-L79
# smelly line(s) in the original file: 78
# smelly line(s) in this file: 8
# ids: pysmell_1834
# note: Python 2 era source, kept as found
def BdbQuit_IPython_excepthook(self,et,ev,tb,tb_offset=None):
    print('Exiting Debugger.')
