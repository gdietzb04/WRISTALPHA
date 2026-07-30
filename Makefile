.PHONY: install lint typecheck test verify migrate compose-up compose-down

install:
	python -m pip install -e ".[dev]"

lint:
	python -m ruff check .
	python -m ruff format --check .

typecheck:
	python -m mypy

test:
	python -m pytest --cov=wristalpha --cov-report=term-missing

verify: lint typecheck test
	cd frontend && npm ci && npm run build

migrate:
	python -m alembic upgrade head

compose-up:
	docker compose up --build

compose-down:
	docker compose down
