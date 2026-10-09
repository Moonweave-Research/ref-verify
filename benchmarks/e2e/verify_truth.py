"""Re-check truth.json against live CrossRef and doi.org (needs the network; not run in CI).

OK and claim items: the DOI resolves in CrossRef and is not retracted. RETRACTED: CrossRef
lists a retraction. FAB_DOI: CrossRef 404 and doi.org "DOI does not exist". FAB_NODOI: no
CrossRef search hit with the same title. DOI_SWAP / TITLELESS / WRONG_*: the true record
exists, and for WRONG_YEAR its years exclude the cited year.

Items that carry more detail (the v2 set) are checked further: WRONG_AUTHOR against the record's
first author, TITLELESS_WRONG_VOLPAGE against its volume and first page, DOI_SWAP's cited DOI
against a different record, every number quoted in `abstract_says` against the live CrossRef
abstract (items with `abstract_source: crossref`), and FAB_NODOI against the item's `cited_title`.

Usage: python3 verify_truth.py [--truth v2/truth.json]
"""

from __future__ import annotations

import argparse
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


def numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:\.\d+)?", text))


def detail(item: dict, message: dict) -> str | None:
    kind = item["type"]
    doi = item["truth_doi"]
    if kind == "WRONG_AUTHOR" and item.get("true_first_author"):
        first = ((message.get("author") or [{}])[0].get("family") or "").casefold()
        if first != item["true_first_author"].casefold() or first == item["cited_first_author"].casefold():
            return f"{doi} first author {first!r} vs truth {item['true_first_author']!r} / cited {item['cited_first_author']!r}"
    if kind == "TITLELESS_WRONG_VOLPAGE" and item.get("true_volume"):
        first_page = re.split(r"[-–]", str(message.get("page") or message.get("article-number") or ""))[0]
        if message.get("volume") != item["true_volume"] or first_page != item["true_page"]:
            return f"{doi} is {message.get('volume')}, {first_page}; truth says {item['true_volume']}, {item['true_page']}"
        if (item["cited_volume"], item["cited_page"]) == (item["true_volume"], item["true_page"]):
            return "cited volume/page equal the true ones"
    if kind == "DOI_SWAP" and item.get("cited_doi"):
        other = crossref(item["cited_doi"])
        if other is None:
            return f"cited DOI {item['cited_doi']} not in CrossRef"
        if (other.get("title") or [""])[0].casefold() == (message.get("title") or [""])[0].casefold():
            return f"cited DOI {item['cited_doi']} has the same title as {doi}"
    if item.get("abstract_source") == "crossref":
        abstract = numbers(re.sub(r"<[^>]+>", " ", message.get("abstract") or ""))
        missing = numbers(item["abstract_says"]) - abstract
        if missing:
            return f"{doi} abstract lacks {sorted(missing)} quoted in abstract_says"
        if kind == "CLAIM_NUMBER" and numbers(" ".join(item["value"])) & abstract:
            return f"{doi} abstract contains the planted number {item['value']}"
    return None


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
        return detail(item, message)
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
        line = item.get("cited_title") or title_of(item, manuscript_text)
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--truth", type=Path, default=HERE / "truth.json")
    args = parser.parse_args()
    truth = json.loads(args.truth.read_text(encoding="utf-8"))
    base = args.truth.resolve().parent
    problems = 0
    for name, manuscript in truth["manuscripts"].items():
        text = (base / manuscript["path"]).read_text(encoding="utf-8")
        if manuscript.get("bib"):
            text += "\n" + (base / manuscript["bib"]).read_text(encoding="utf-8")
        for item in manuscript["items"]:
            problem = check(item, text)
            status = "ok" if problem is None else f"PROBLEM: {problem}"
            problems += problem is not None
            print(f"{item['id']:22} {item['type']:24} {status}")
    print(f"{problems} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
