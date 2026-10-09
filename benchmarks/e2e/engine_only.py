"""Run check-bib alone on each manuscript's reference list, as a baseline for the agent runs.

The Markdown manuscripts' reference sections are written to a scratch .txt file; the LaTeX
manuscripts' .bib files are used as they are. Prints one line per truth reference item with
the engine's verdict, so "what the engine alone would flag" can be compared with what the
agent reported. Needs the network.

Usage: python3 engine_only.py --scratch DIR [--truth v2/truth.json]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def reference_section(text: str) -> str:
    match = re.search(r"^## (?:References|참고문헌)\s*$", text, flags=re.M)
    return text[match.end():] if match else text


def pair_results(items: list[dict], results: list[dict]) -> list[tuple[dict, dict | None]]:
    # v1 lists items in reference order; v2 does not. Pair by the DOI the reference cites first,
    # then by the most identifying strings found in the result's key or raw text.
    unused = list(results)
    paired: dict[str, dict] = {}
    for item in items:
        cited = (item.get("cited_doi") or item.get("truth_doi") or "").casefold()
        match = next((r for r in unused if cited and (r.get("doi") or "").casefold() == cited), None)
        if match is not None:
            unused.remove(match)
            paired[item["id"]] = match
    for item in items:
        if item["id"] in paired:
            continue

        def hits(result: dict) -> int:
            text = f"{result.get('key') or ''} {result['reference']['raw']}"
            return sum(token in text for token in item["match"])

        best = max(unused, key=hits, default=None)
        if best is not None and hits(best):
            unused.remove(best)
            paired[item["id"]] = best
    return [(item, paired.get(item["id"])) for item in items]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--truth", type=Path, default=HERE / "truth.json")
    args = parser.parse_args()
    args.scratch.mkdir(parents=True, exist_ok=True)
    truth = json.loads(args.truth.read_text(encoding="utf-8"))
    base = args.truth.resolve().parent
    env = dict(os.environ, PYTHONPATH=str(REPO / "src"), REF_VERIFY_CACHE_DIR=str(args.scratch / "cache"))
    out = {}
    for name, manuscript in truth["manuscripts"].items():
        if manuscript.get("bib"):
            source = base / manuscript["bib"]
        else:
            source = args.scratch / f"{name}.txt"
            source.write_text(reference_section((base / manuscript["path"]).read_text(encoding="utf-8")), encoding="utf-8")
        process = subprocess.run(
            [sys.executable, "-m", "ref_verify.cli", "check-bib", str(source), "--json"],
            env=env, capture_output=True, text=True, check=False,
        )
        results = json.loads(process.stdout)["results"]
        out[name] = results
        reference_items = [item for item in manuscript["items"] if not item["type"].startswith("CLAIM_")]
        for item, result in pair_results(reference_items, results):
            if result is None:
                print(f"{item['id']:22} {item['type']:24} {'NO MATCH':10}")
                continue
            label = "UNVERIFIED" if result["status"] == "UNVERIFIED" else result["verdict"]
            print(f"{item['id']:22} {item['type']:24} {label:10} {result['error_code'] or '':22} {result['reason'][:90]}")
    (args.scratch / "engine_only.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
