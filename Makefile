# Local helper commands. Run `make help` to list them.
VENV   ?= .venv
PYTHON ?= $(VENV)/bin/python

.PHONY: help install validate render check-readme test check clean

help:
	@echo "make install       create .venv and install dependencies"
	@echo "make validate      validate every file in data/"
	@echo "make render        regenerate README.md from data/"
	@echo "make test          run the test suite"
	@echo "make check         validate + test + render (run before opening a PR)"

$(PYTHON):
	python3 -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"

install: $(PYTHON)

validate: $(PYTHON)
	$(PYTHON) -m startup_jobs validate

render: $(PYTHON)
	$(PYTHON) -m startup_jobs render

check-readme: $(PYTHON)
	$(PYTHON) -m startup_jobs check-readme

test: $(PYTHON)
	$(PYTHON) -m pytest -q

check: validate test render

clean:
	rm -rf $(VENV) .pytest_cache src/*.egg-info
