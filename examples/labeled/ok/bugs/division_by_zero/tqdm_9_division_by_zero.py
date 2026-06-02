# Extracted from tqdm/_tqdm.py — tqdm project
# Source: BugsInPy tqdm #9 / tqdm rate calculation (pre-guard version)
# Bug: n / elapsed raises ZeroDivisionError when elapsed == 0.0 at start
# Real fix: rate = n / elapsed if elapsed else None
def format_rate(n: int, elapsed: float, unit: str = "it") -> str:
    rate = n / elapsed
    return f"{rate:.2f} {unit}/s"
