.PHONY: install format lint test build security demo demo-incident benchmark figures up down

PYTHON ?= python

install:
	$(PYTHON) -m pip install --require-hashes -r requirements-dev.lock
	$(PYTHON) -m pip install --no-deps -e .

format:
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --fix .

lint:
	$(PYTHON) -m ruff format --check .
	$(PYTHON) -m ruff check .
	$(PYTHON) -m mypy src

test:
	$(PYTHON) -m pytest --cov=incident_lens --cov-report=term-missing

build:
	$(PYTHON) -m build

security:
	$(PYTHON) -m pip_audit --disable-pip -r requirements-dev.lock --vulnerability-service osv
	$(PYTHON) -m bandit -c pyproject.toml -r src

up:
	docker compose up --build -d --wait

down:
	docker compose down --remove-orphans

demo:
	docker compose up --build

demo-incident:
	$(PYTHON) scripts/demo_incident.py

benchmark:
	$(PYTHON) benchmarks/run.py --output local

figures:
	$(PYTHON) benchmarks/plot.py --result local
