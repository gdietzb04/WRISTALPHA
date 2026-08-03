"""Fail-closed container entry points that keep database secrets out of Compose metadata."""

from __future__ import annotations

import argparse
import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import NoReturn

from sqlalchemy import URL

MINIMUM_PASSWORD_LENGTH = 32
DEFAULT_SECRET_PATH = Path("/run/secrets/postgres_password")


def read_database_password(path: Path) -> str:
    """Read and validate the mounted database password without logging it."""
    try:
        password = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"database password secret is unavailable at {path}") from exc
    if len(password) < MINIMUM_PASSWORD_LENGTH:
        raise RuntimeError(
            f"database password secret must contain at least {MINIMUM_PASSWORD_LENGTH} characters"
        )
    if "\n" in password or "\r" in password or "\x00" in password:
        raise RuntimeError("database password secret contains unsupported control characters")
    return password


def build_database_url(environ: Mapping[str, str]) -> str:
    """Build a safely escaped SQLAlchemy URL from non-secret settings and a secret file."""
    secret_path = Path(environ.get("WRISTALPHA_DATABASE_PASSWORD_FILE", str(DEFAULT_SECRET_PATH)))
    password = read_database_password(secret_path)
    raw_port = environ.get("WRISTALPHA_DATABASE_PORT", "5432")
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise RuntimeError("WRISTALPHA_DATABASE_PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise RuntimeError("WRISTALPHA_DATABASE_PORT must be between 1 and 65535")

    url = URL.create(
        drivername="postgresql+psycopg",
        username=environ.get("WRISTALPHA_DATABASE_USER", "wristalpha"),
        password=password,
        host=environ.get("WRISTALPHA_DATABASE_HOST", "db"),
        port=port,
        database=environ.get("WRISTALPHA_DATABASE_NAME", "wristalpha"),
    )
    return url.render_as_string(hide_password=False)


def run_role(role: str, environ: Mapping[str, str] | None = None) -> NoReturn:
    """Run one static container role after injecting the secret-backed database URL."""
    child_environment = dict(os.environ if environ is None else environ)
    child_environment["WRISTALPHA_DATABASE_URL"] = build_database_url(child_environment)

    if role == "api":
        subprocess.run(
            ["alembic", "upgrade", "head"],
            check=True,
            env=child_environment,
        )
        command = [
            "uvicorn",
            "wristalpha.api:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ]
    elif role == "scheduler":
        command = ["python", "-m", "wristalpha.operations.scheduler"]
    else:
        raise RuntimeError(f"unsupported container role: {role}")

    os.execvpe(command[0], command, child_environment)


def main(argv: Sequence[str] | None = None) -> NoReturn:
    parser = argparse.ArgumentParser(description="Start a WRISTALPHA container role")
    parser.add_argument("role", choices=("api", "scheduler"))
    arguments = parser.parse_args(argv)
    run_role(arguments.role)


if __name__ == "__main__":
    main()
