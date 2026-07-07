VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: install test scan report clean

install:
	python3 -m venv $(VENV)
	$(PIP) install -q --upgrade pip
	$(PIP) install -q -e ".[dev]"

test:
	$(PY) -m pytest -q

# Ví dụ: make scan FROM=2026-06-01 TO=2026-06-30
scan:
	$(VENV)/bin/hdtool scan --from $(FROM) --to $(TO)

report:
	$(VENV)/bin/hdtool report --from $(FROM) --to $(TO)

clean:
	rm -rf $(VENV) .pytest_cache src/*.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
