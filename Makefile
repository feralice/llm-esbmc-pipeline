PYTHON ?= .venv/bin/python

.PHONY: check lint typecheck test

check: lint typecheck test

lint:
	$(PYTHON) -m ruff check src scripts tests

typecheck:
	$(PYTHON) -m mypy

test:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m pytest -q
