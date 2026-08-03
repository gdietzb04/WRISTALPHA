from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import NoReturn

import pytest

from wristalpha.operations.entrypoint import run_role


class ExecutedRole(RuntimeError):
    pass


def _environment(secret: Path) -> dict[str, str]:
    secret.write_text("x" * 64, encoding="utf-8")
    return {"WRISTALPHA_DATABASE_PASSWORD_FILE": str(secret)}


def test_api_role_migrates_then_executes_with_secret_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    migration: dict[str, object] = {}
    executed: dict[str, object] = {}

    def fake_run(
        command: Sequence[str], *, check: bool, env: Mapping[str, str]
    ) -> subprocess.CompletedProcess[str]:
        migration.update(
            command=list(command), check=check, database_url=env["WRISTALPHA_DATABASE_URL"]
        )
        return subprocess.CompletedProcess(command, 0)

    def fake_exec(file: str, arguments: Sequence[str], env: Mapping[str, str]) -> NoReturn:
        executed.update(
            file=file, arguments=list(arguments), database_url=env["WRISTALPHA_DATABASE_URL"]
        )
        raise ExecutedRole

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(os, "execvpe", fake_exec)

    with pytest.raises(ExecutedRole):
        run_role("api", _environment(tmp_path / "password"))

    assert migration["command"] == ["alembic", "upgrade", "head"]
    assert migration["check"] is True
    assert executed["file"] == "uvicorn"
    assert "postgresql+psycopg://" in str(executed["database_url"])


def test_scheduler_role_executes_without_running_migrations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executed: dict[str, object] = {}

    def unexpected_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        del args, kwargs
        raise AssertionError("scheduler must not run migrations")

    def fake_exec(file: str, arguments: Sequence[str], env: Mapping[str, str]) -> NoReturn:
        executed.update(
            file=file, arguments=list(arguments), database_url=env["WRISTALPHA_DATABASE_URL"]
        )
        raise ExecutedRole

    monkeypatch.setattr(subprocess, "run", unexpected_run)
    monkeypatch.setattr(os, "execvpe", fake_exec)

    with pytest.raises(ExecutedRole):
        run_role("scheduler", _environment(tmp_path / "password"))

    assert executed["arguments"] == ["python", "-m", "wristalpha.operations.scheduler"]


def test_unknown_container_role_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="unsupported container role"):
        run_role("unknown", _environment(tmp_path / "password"))
