"""V2 harness synthesis: reuse V1 detection, then abstract findings for ESBMC
functions, synthesize a self-contained ESBMC harness for each candidate, and
confirm formally.

This package is additive: the V1 flows (esbmc-only / llm-only / hybrid /
benchmark / ensemble) do not import from it.
"""
