# smell: LongLambdaFunction
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/scipy/scipy/blob/v0.16.0b2/scipy/stats/_continuous_distns.py#L1336-L1364
# smelly line(s) in the original file: 1353
# smelly line(s) in this file: 25
# ids: pysmell_0950
# note: Python 2 era source, kept as found
def _stats(self, dfn, dfd):
    v1, v2 = 1. * dfn, 1. * dfd
    v2_2, v2_4, v2_6, v2_8 = v2 - 2., v2 - 4., v2 - 6., v2 - 8.

    mu = _lazywhere(
        v2 > 2, (v2, v2_2),
        lambda v2, v2_2: v2 / v2_2,
        np.inf)

    mu2 = _lazywhere(
        v2 > 4, (v1, v2, v2_2, v2_4),
        lambda v1, v2, v2_2, v2_4:
        2 * v2 * v2 * (v1 + v2_2) / (v1 * v2_2**2 * v2_4),
        np.inf)

    g1 = _lazywhere(
        v2 > 6, (v1, v2_2, v2_4, v2_6),
        lambda v1, v2_2, v2_4, v2_6:
        (2 * v1 + v2_2) / v2_6 * sqrt(v2_4 / (v1 * (v1 + v2_2))),
        np.nan)
    g1 *= np.sqrt(8.)

    g2 = _lazywhere(
        v2 > 8, (g1, v2_6, v2_8),
        lambda g1, v2_6, v2_8: (8 + g1 * g1 * v2_6) / v2_8,
        np.nan)
    g2 *= 3. / 2.

    return mu, mu2, g1, g2
