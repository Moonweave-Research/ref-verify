from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from email.message import Message
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError

import js
from pyodide.ffi import JsException, JsProxy

from ref_verify import __version__, http
from ref_verify.crossref import CrossrefClient
from ref_verify.reference_parse import ReferenceInputError, parse_reference_file
from ref_verify.reference_resolve import check_reference, reference_payload
from ref_verify.report import render_report, rows_from_reference_results

INPUT_DIR = Path("/tmp/ref-verify-input")


class XhrBackend:
    # A Web Worker may use synchronous XMLHttpRequest, so the engine's blocking calls,
    # retries, and CrossRef pacing run unchanged. Headers are dropped: browsers refuse a
    # custom User-Agent, and any other header would add a CORS preflight request.
    def get(self, url: str, headers: dict[str, str], timeout: float) -> str:
        xhr = js.XMLHttpRequest.new()
        xhr.open("GET", url, False)
        xhr.timeout = int(timeout * 1000)
        try:
            xhr.send()
        except JsException as exc:
            if not js.navigator.onLine or "TimeoutError" in str(exc):
                raise URLError(str(exc)) from None
            # CrossRef sends its HTTP 429 without CORS headers, so the browser hides the
            # status and reports a network error. While online, treat it as the 429 it most
            # likely is, so the engine backs off and retries as the CLI does.
            raise HTTPError(url, 429, "Too Many Requests (hidden by the browser)", Message(), None) from None
        if 200 <= xhr.status < 300:
            return xhr.responseText
        # Retry-After is readable only when the server exposes it to pages; without it the
        # engine uses its own backoff.
        response_headers = Message()
        retry_after = xhr.getResponseHeader("Retry-After")
        if retry_after:
            response_headers["Retry-After"] = retry_after
        raise HTTPError(url, xhr.status, xhr.statusText or "HTTP error", response_headers, None)


def check(name: str, data: JsProxy, progress: Callable[[int, int], None]) -> str:
    http.set_backend(XhrBackend())
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Keep the file name: the engine reads the format from its extension.
    path = INPUT_DIR / Path(name).name
    path.write_bytes(data.to_bytes())
    try:
        entries = parse_reference_file(path, None)
    except ReferenceInputError as exc:
        return json.dumps({"error": str(exc)})
    finally:
        path.unlink(missing_ok=True)

    # No disk cache in the browser: the page keeps nothing after it is closed.
    client = CrossrefClient(cache=None)
    progress(0, len(entries))
    results = []
    for entry in entries:
        results.append(check_reference(entry, client))
        progress(len(results), len(entries))

    payload = reference_payload(results)
    rows = rows_from_reference_results(results)
    report = render_report(
        "html",
        command="check-bib",
        source_name=name,
        summary=payload["summary"],
        rows=rows,
        generated_at=datetime.now(timezone.utc),
    )
    return json.dumps(
        {
            "version": __version__,
            "payload": payload,
            "rows": [asdict(row) for row in rows],
            "report": report,
        }
    )
