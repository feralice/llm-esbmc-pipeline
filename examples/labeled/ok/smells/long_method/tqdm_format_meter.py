# Extracted from tqdm/_tqdm.py — tqdm progress bar library
# Source: BugsInPy tqdm project / tqdm.format_meter() static method
# Smell: long method — format_meter handles ETA, rate, units, bar rendering,
# custom format strings, and ASCII/unicode fallback all in one function
def format_meter(n: int, total: int, elapsed: float, ncols: int = 80,
                 prefix: str = "", ascii: bool = False, unit: str = "it",
                 unit_scale: bool = False, rate=None, bar_format: str = "") -> str:
    if total and n > total:
        total = None

    elapsed_str = format_interval(elapsed)

    if rate is None and elapsed:
        rate = n / elapsed if elapsed else None
    inv_rate = 1 / rate if (rate and rate < 1) else None

    rate_noinv_fmt = (
        ((f"{rate * unit_scale:.2f}" if unit_scale else f"{rate:.2f}") + " " + unit + "/s")
        if rate else "?"
    )
    rate_inv_fmt = (
        ((f"{inv_rate * unit_scale:.2f}" if unit_scale else f"{inv_rate:.2f}") + " s/" + unit)
        if inv_rate else "?"
    )
    rate_fmt = rate_inv_fmt if inv_rate and inv_rate > 1 else rate_noinv_fmt

    if unit_scale:
        n_fmt = format_sizeof(n)
        total_fmt = format_sizeof(total) if total else None
    else:
        n_fmt = str(n)
        total_fmt = str(total)

    if total:
        frac = n / total
        percentage = frac * 100
        remaining = (total - n) / rate if rate else 0
        remaining_str = format_interval(remaining) if rate else "?"

        if bar_format:
            bar_args = {
                "n": n, "n_fmt": n_fmt, "total": total, "total_fmt": total_fmt,
                "percentage": percentage, "rate": rate or 0, "rate_fmt": rate_fmt,
                "elapsed": elapsed_str, "remaining": remaining_str,
                "l_bar": f"{percentage:3.0f}%|", "r_bar": f"| {n_fmt}/{total_fmt}",
            }
            return bar_format.format(**bar_args)

        ncols_offset = len(prefix) + len(n_fmt) + len(total_fmt) + 6
        bar_length = max(1, ncols - ncols_offset) if ncols else 10
        bar = "#" * int(frac * bar_length) if ascii else "█" * int(frac * bar_length)
        bar = bar.ljust(bar_length)
        return f"{prefix}{percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed_str}<{remaining_str}, {rate_fmt}]"

    if bar_format:
        return bar_format.format(n=n, n_fmt=n_fmt, rate=rate or 0, rate_fmt=rate_fmt, elapsed=elapsed_str)

    return f"{prefix}{n_fmt} [{elapsed_str}, {rate_fmt}]"

def format_interval(t: float) -> str:
    mins, s = divmod(int(t), 60)
    h, m = divmod(mins, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

def format_sizeof(num: float, suffix: str = "") -> str:
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if abs(num) < 999.95:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1000.0
    return f"{num:.1f}Y{suffix}"
