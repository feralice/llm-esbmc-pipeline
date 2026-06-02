# Extracted from matplotlib/axes/_axes.py — Matplotlib visualization library
# Source: matplotlib project / Axes.plot() interface
# Smell: many parameters — plot() accepts data, format, color, linestyle, linewidth,
# marker, markersize, label, alpha, zorder, visible, animated, clip_on, in addition to **kwargs
def plot_line(x: list, y: list, fmt: str = "", color: str = None,
              linestyle: str = "-", linewidth: float = 1.5, marker: str = None,
              markersize: float = 6.0, label: str = None, alpha: float = 1.0,
              zorder: int = 2, visible: bool = True, animated: bool = False) -> dict:
    return {
        "x": x, "y": y, "fmt": fmt, "color": color, "linestyle": linestyle,
        "linewidth": linewidth, "marker": marker, "markersize": markersize,
        "label": label, "alpha": alpha, "zorder": zorder,
        "visible": visible, "animated": animated,
    }
