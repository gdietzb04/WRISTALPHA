"""Append-only raw HTTP response cache."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True)
class CacheEntry:
    source: str
    url: str
    fetched_at: datetime
    status: int
    content_type: str | None
    body_sha256: str
    body_path: str


class RawResponseCache:
    """Write content-addressed response bodies and immutable metadata sidecars."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def store(
        self,
        *,
        source: str,
        url: str,
        fetched_at: datetime,
        status: int,
        content_type: str | None,
        body: bytes,
    ) -> CacheEntry:
        if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
            raise ValueError("fetched_at must be timezone-aware")
        digest = hashlib.sha256(body).hexdigest()
        host = urlparse(url).hostname or "unknown-host"
        day = fetched_at.astimezone(UTC).strftime("%Y/%m/%d")
        directory = self._root / source / host / day
        directory.mkdir(parents=True, exist_ok=True)
        body_path = directory / f"{digest}.body"
        metadata_path = directory / f"{digest}.json"
        if not body_path.exists():
            self._atomic_create(body_path, body)
        entry = CacheEntry(
            source=source,
            url=url,
            fetched_at=fetched_at,
            status=status,
            content_type=content_type,
            body_sha256=digest,
            body_path=str(body_path),
        )
        if not metadata_path.exists():
            payload = json.dumps(
                {**asdict(entry), "fetched_at": fetched_at.isoformat()},
                sort_keys=True,
                indent=2,
            ).encode("utf-8")
            self._atomic_create(metadata_path, payload)
        return entry

    @staticmethod
    def _atomic_create(path: Path, payload: bytes) -> None:
        temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
        temporary.write_bytes(payload)
        try:
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
