# smell: LongParameterList
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/scipy/scipy/blob/v0.16.0b2/scipy/integrate/tests/test_integrate.py#L510-L513
# smelly line(s) in the original file: 510
# smelly line(s) in this file: 8
# ids: pysmell_1716
# note: Python 2 era source, kept as found
def jac2(t, x, omega1, omega2):
    j = array([[0.0, omega1],
               [-omega2, 0.0]])
    return j
