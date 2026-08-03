from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import make_url

from wristalpha.operations.entrypoint import build_database_url, read_database_password


def test_database_url_uses_secret_file_and_escapes_password(tmp_path: Path) -> None:
    secret = tmp_path / "postgres_password"
    password = "safe/@password:" + ("x" * 32)
    secret.write_text(password, encoding="utf-8")

    result = make_url(
        build_database_url(
            {
                "WRISTALPHA_DATABASE_PASSWORD_FILE": str(secret),
                "WRISTALPHA_DATABASE_USER": "watch user",
                "WRISTALPHA_DATABASE_HOST": "db",
                "WRISTALPHA_DATABASE_PORT": "5433",
                "WRISTALPHA_DATABASE_NAME": "watch alpha",
            }
        )
    )

    assert result.username == "watch user"
    assert result.password == password
    assert result.host == "db"
    assert result.port == 5433
    assert result.database == "watch alpha"


def test_database_secret_fails_closed_when_missing_or_weak(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    with pytest.raises(RuntimeError, match="unavailable"):
        read_database_password(missing)

    weak = tmp_path / "weak"
    weak.write_text("short", encoding="utf-8")
    with pytest.raises(RuntimeError, match="at least 32"):
        read_database_password(weak)


@pytest.mark.parametrize("port", ["not-a-port", "0", "65536"])
def test_database_url_rejects_invalid_ports(tmp_path: Path, port: str) -> None:
    secret = tmp_path / "postgres_password"
    secret.write_text("x" * 64, encoding="utf-8")
    with pytest.raises(RuntimeError, match="PORT"):
        build_database_url(
            {
                "WRISTALPHA_DATABASE_PASSWORD_FILE": str(secret),
                "WRISTALPHA_DATABASE_PORT": port,
            }
        )
