from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

DEFAULT_TTL_DAYS = 7.0
NOT_FOUND_TTL_SECONDS = 86400.0


@dataclass(frozen=True)
class CachedResponse:
    status: int
    body: str


class ResponseCache:
    def __init__(
        self,
        directory: Path,
        ttl_seconds: float,
        *,
        not_found_ttl_seconds: float = NOT_FOUND_TTL_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.directory = directory
        self.ttl_seconds = ttl_seconds
        self.not_found_ttl_seconds = not_found_ttl_seconds
        self.clock = clock

    def get(self, url: str) -> CachedResponse | None:
        try:
            entry = json.loads(self._path(url).read_text(encoding="utf-8"))
            status = entry["status"]
            body = entry["body"]
            stored_at = float(entry["stored_at"])
            if entry["url"] != url or not isinstance(status, int) or not isinstance(body, str):
                return None
        except (OSError, ValueError, KeyError, TypeError):
            return None
        # A dead DOI gets a short TTL so a newly registered DOI is re-checked soon.
        ttl = self.not_found_ttl_seconds if status == 404 else self.ttl_seconds
        if self.clock() - stored_at >= ttl:
            return None
        return CachedResponse(status=status, body=body)

    def put(self, url: str, status: int, body: str) -> None:
        entry = {"url": url, "status": status, "stored_at": self.clock(), "body": body}
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            # Write-then-rename so a parallel reader never sees a half-written entry.
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.directory,
                suffix=".tmp",
                delete=False,
            ) as handle:
                json.dump(entry, handle)
            os.replace(handle.name, self._path(url))
        except OSError:
            return

    def _path(self, url: str) -> Path:
        return self.directory / f"{hashlib.sha256(url.encode('utf-8')).hexdigest()}.json"


def cache_directory() -> Path:
    explicit = os.environ.get("REF_VERIFY_CACHE_DIR")
    if explicit:
        return Path(explicit).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg).expanduser() / "ref-verify"
    return Path.home() / ".cache" / "ref-verify"


def default_cache() -> ResponseCache | None:
    if os.environ.get("REF_VERIFY_NO_CACHE", "").strip().lower() in ("1", "true", "yes"):
        return None
    try:
        ttl_days = float(os.environ.get("REF_VERIFY_CACHE_TTL_DAYS", DEFAULT_TTL_DAYS))
    except ValueError:
        ttl_days = DEFAULT_TTL_DAYS
    return ResponseCache(cache_directory(), ttl_seconds=ttl_days * 86400)
