"""Re-check truth.json against live CrossRef and doi.org (needs the network; not run in CI).

OK and claim items: the DOI resolves in CrossRef and is not retracted. RETRACTED: CrossRef
lists a retraction. FAB_DOI: CrossRef 404 and doi.org "DOI does not exist". FAB_NODOI: no
CrossRef search hit with the same title. DOI_SWAP / TITLELESS / WRONG_*: the true record
exists, and for WRONG_YEAR its years exclude the cited year.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
HEADERS = {"User-Agent": "ref-verify-e2e-benchmark (mailto:benchmark@example.org)"}


def fetch(url: str) -> dict | list | None:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    finally:
        time.sleep(0.8)


def crossref(doi: str) -> dict | None:
    data = fetch("https://api.crossref.org/works/" + urllib.parse.quote(doi, safe=""))
    return data["message"] if isinstance(data, dict) else None


def years(message: dict) -> set[int]:
    found = set()
    for key in ("published-print", "published-online", "issued"):
        parts = (message.get(key) or {}).get("date-parts")
        if parts and parts[0] and parts[0][0]:
            found.add(int(parts[0][0]))
    return found


def retracted(message: dict) -> bool:
    return any("retract" in str(update.get("type")) for update in message.get("updated-by") or [])


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.casefold())


def title_of(item: dict, manuscript_text: str) -> str:
    # The fabricated title is the item's identifying phrase in the manuscript.
    for line in manuscript_text.splitlines():
        if any(marker in line for marker in item["match"][1:]) and len(line) > 60:
            return line
    return ""


def check(item: dict, manuscript_text: str) -> str | None:
    kind = item["type"]
    doi = item.get("truth_doi")
    if kind in ("OK", "CLAIM_OK", "CLAIM_NUMBER", "CLAIM_UNIT", "CLAIM_DIRECTION", "DOI_SWAP",
                "TITLELESS_WRONG_VOLPAGE", "WRONG_AUTHOR", "WRONG_YEAR", "RETRACTED"):
        message = crossref(doi)
        if message is None:
            return f"{doi} not in CrossRef"
        if kind == "RETRACTED":
            return None if retracted(message) else f"{doi} has no retraction notice"
        if retracted(message):
            return f"{doi} is retracted but labelled {kind}"
        if kind == "WRONG_YEAR":
            if item["true_year"] not in years(message) or item["cited_year"] in years(message):
                return f"{doi} years {sorted(years(message))} vs cited {item['cited_year']}"
        return None
    if kind == "FAB_DOI":
        candidates = re.findall(r"10\.\d{4,9}/\S+", manuscript_text)
        target = next((c.rstrip(".,}") for c in candidates for m in item["match"] if m in c), None)
        if not target:
            return "fabricated DOI not found in manuscript"
        if crossref(target) is not None:
            return f"{target} exists in CrossRef"
        agency = fetch("https://doi.org/ra/" + target)
        status = agency[0].get("status", "") if isinstance(agency, list) and agency else ""
        return None if "does not exist" in status else f"{target} doi.org says {agency}"
    if kind == "FAB_NODOI":
        line = title_of(item, manuscript_text)
        data = fetch("https://api.crossref.org/works?" + urllib.parse.urlencode({"query.bibliographic": line, "rows": "5"}))
        cited = " ".join(words(line))
        for record in (data or {}).get("message", {}).get("items", []):
            title = " ".join(words((record.get("title") or [""])[0]))
            if title and len(title) > 20 and title in cited:
                return f"CrossRef has a record with this title: {record['DOI']}"
        return None
    if kind == "UNINDEXED_OK":
        return None
    return f"unknown type {kind}"


def main() -> int:
    truth = json.loads((HERE / "truth.json").read_text(encoding="utf-8"))
    problems = 0
    for name, manuscript in truth["manuscripts"].items():
        text = (HERE / manuscript["path"]).read_text(encoding="utf-8")
        if manuscript.get("bib"):
            text += "\n" + (HERE / manuscript["bib"]).read_text(encoding="utf-8")
        for item in manuscript["items"]:
            problem = check(item, text)
            status = "ok" if problem is None else f"PROBLEM: {problem}"
            problems += problem is not None
            print(f"{item['id']:22} {item['type']:24} {status}")
    print(f"{problems} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
