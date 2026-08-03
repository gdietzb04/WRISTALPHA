.PHONY: install lint typecheck test verify migrate start update rebuild status logs stop compose-up compose-down

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

start:
	powershell.exe -NoLogo -NoProfile -File ./wristalpha.ps1 start

update:
	powershell.exe -NoLogo -NoProfile -File ./wristalpha.ps1 update

rebuild:
	powershell.exe -NoLogo -NoProfile -File ./wristalpha.ps1 rebuild

status:
	powershell.exe -NoLogo -NoProfile -File ./wristalpha.ps1 status

logs:
	powershell.exe -NoLogo -NoProfile -File ./wristalpha.ps1 logs

stop:
	powershell.exe -NoLogo -NoProfile -File ./wristalpha.ps1 stop

compose-up: rebuild

compose-down: stop
