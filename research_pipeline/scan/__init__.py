"""V2 scan mode: point the pipeline at a real repository, let the LLM triage
functions, synthesize a self-contained ESBMC harness for each candidate, and
confirm formally.

This package is additive: the V1 flows (esbmc-only / llm-only / hybrid /
benchmark / ensemble) do not import from it.
"""
