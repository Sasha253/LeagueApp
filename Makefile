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

.PHONY: help install up down migrate run test lint format

help:
	@echo "make install  create backend/.venv and install dev requirements"
	@echo "make up       start PostgreSQL (docker compose)"
	@echo "make down     stop it"
	@echo "make migrate  apply database migrations"
	@echo "make run      start the Django dev server on http://localhost:8000"
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

test:
	$(PY) -m pytest backend

lint:
	$(PY) -m ruff check backend
	$(PY) -m ruff format --check backend

format:
	$(PY) -m ruff check --fix backend
	$(PY) -m ruff format backend
