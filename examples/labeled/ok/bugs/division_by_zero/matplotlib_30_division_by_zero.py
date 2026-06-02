# Extracted from lib/matplotlib/colors.py — Matplotlib visualization library
# Source: BugsInPy matplotlib #30
# Bug: division by zero when x_ind == x_ind_prev (two consecutive colormap control points coincide)
# Real fix: added deduplication of control points before computing distances
def matplotlib_colormap_distance(xind_i: float, x_ind: float, x_ind_prev: float) -> float:
    return (xind_i - x_ind_prev) / (x_ind - x_ind_prev)
