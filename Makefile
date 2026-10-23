# Local development commands. Run from the repo root; see README.md.

ifeq ($(OS),Windows_NT)
PYTHON ?= py -3
VENV_BIN := backend/.venv/Scripts
else
PYTHON ?= python3
VENV_BIN := backend/.venv/bin
endif

PY := $(VENV_BIN)/python
MANAGE := $(PY) backend/manage.py

.PHONY: help install up down migrate run worker beat test lint format

help:
	@echo "make install  create backend/.venv and install dev requirements"
	@echo "make up       start PostgreSQL and Redis (docker compose)"
	@echo "make down     stop them"
	@echo "make migrate  apply database migrations"
	@echo "make run      start the Django dev server on http://localhost:8000"
	@echo "make worker   run the Celery worker (runs the timed checkpoints)"
	@echo "make beat     run Celery Beat (starts them on schedule; run only one)"
	@echo "make test     run the backend tests"
	@echo "make lint     ruff lint and format check"
	@echo "make format   apply ruff fixes and formatting"

install:
	$(PYTHON) -m venv backend/.venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r backend/requirements/dev.txt

up:
	docker compose up -d --wait

down:
	docker compose down

migrate:
	$(MANAGE) migrate

run:
	$(MANAGE) runserver

# Threads, not Celery's default process pool: on macOS with Python 3.14 the pool starts its
# children by spawning and every task fails ("not enough values to unpack"). Production on
# Linux can use the default pool.
worker:
	cd backend && DJANGO_SETTINGS_MODULE=config.settings.local $(CURDIR)/$(VENV_BIN)/celery -A config worker --loglevel=INFO --pool=threads --concurrency=4

beat:
	cd backend && DJANGO_SETTINGS_MODULE=config.settings.local $(CURDIR)/$(VENV_BIN)/celery -A config beat --loglevel=INFO --schedule=$(CURDIR)/backend/celerybeat-schedule

test:
	$(PY) -m pytest backend

lint:
	$(PY) -m ruff check backend
	$(PY) -m ruff format --check backend

format:
	$(PY) -m ruff check --fix backend
	$(PY) -m ruff format backend
