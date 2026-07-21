PYTHON ?= python

.PHONY: install install-dev run lint format-check compile test coverage security check docker-build clean

install:
	$(PYTHON) -m pip install -r backend/requirements.txt

install-dev:
	$(PYTHON) -m pip install -r backend/requirements-dev.txt

run:
	cd backend && $(PYTHON) -m uvicorn main:app --host 127.0.0.1 --port 8765 --reload

lint:
	ruff check backend

format-check:
	ruff format --check backend

compile:
	$(PYTHON) -m compileall -q backend
	node --check frontend/app.js

test:
	pytest -q

coverage:
	pytest --cov=backend --cov-report=term-missing --cov-report=xml --cov-fail-under=68

security:
	bandit -q -r backend -c pyproject.toml
	pip-audit -r backend/requirements.txt

check: lint format-check compile test

docker-build:
	docker build -t 00swift:local .

clean:
	rm -rf .pytest_cache .ruff_cache .coverage coverage.xml htmlcov backend/.pytest_cache backend/.coverage
	find backend -type d -name __pycache__ -prune -exec rm -rf {} +
