from __future__ import annotations

import json
import time
from email.message import Message
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ref_verify import __version__
from ref_verify.cache import ResponseCache

USER_AGENT = f"ref-verify/{__version__} (+https://github.com/Moonweave-Research/ref-verify)"
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
MAX_BACKOFF_SECONDS = 10.0


def fetch_json(
    url: str,
    *,
    headers: dict[str, str],
    timeout: float,
    cache: ResponseCache | None = None,
    max_retries: int = 3,
    sleep: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    body = fetch_text(
        url,
        headers=headers,
        timeout=timeout,
        cache=cache,
        max_retries=max_retries,
        sleep=sleep,
    )
    return json.loads(body)


def fetch_text(
    url: str,
    *,
    headers: dict[str, str],
    timeout: float,
    cache: ResponseCache | None = None,
    max_retries: int = 3,
    sleep: Callable[[float], None] | None = None,
) -> str:
    if cache is not None:
        cached = cache.get(url)
        if cached is not None:
            if cached.status == 404:
                raise HTTPError(url, 404, "Not Found (cached)", Message(), None)
            return cached.body

    attempt = 0
    while True:
        try:
            with urlopen(Request(url, headers=headers), timeout=timeout) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            if exc.code == 404 and cache is not None:
                cache.put(url, 404, "")
            if exc.code not in RETRY_STATUSES or attempt >= max_retries:
                raise
            delay = _retry_delay(exc, attempt)
            if delay is None:
                raise
            (sleep or time.sleep)(delay)
            attempt += 1
            continue
        if cache is not None:
            cache.put(url, 200, body)
        return body


def _retry_delay(exc: HTTPError, attempt: int) -> float | None:
    retry_after = _retry_after_seconds(exc)
    if retry_after is None:
        return min(2.0**attempt, MAX_BACKOFF_SECONDS)
    # Waiting less than the server asked only earns another 429, and waiting longer
    # would stall the CLI, so give up and let the caller report the rate limit.
    if retry_after > MAX_BACKOFF_SECONDS:
        return None
    return retry_after


def _retry_after_seconds(exc: HTTPError) -> float | None:
    headers = exc.headers
    if headers is None:
        return None
    value = headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None
