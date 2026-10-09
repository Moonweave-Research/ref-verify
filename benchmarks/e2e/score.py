"""Score e2e runs against truth.json (standard library only).

For every run it reads the final answer of the transcript and decides, per truth item:
  caught / missed           planted errors (expected FLAG)
  clean / false_alarm       correct references and correct claims (expected NOT_FLAG)
  review                    the automatic rule cannot tell; a person decides
Decisions in adjudication.json (written by a person who read the answers) override the
automatic ones. It also records whether the run invoked the ref-verify engine, used the web,
and how long it took.

Usage: python3 score.py --scratch DIR [--truth v2/truth.json] [--adjudication FILE] [--review] [--markdown]
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONDITION_LABELS = {"A": "A: with ref-verify skill", "B": "B: without", "C": "C: without, no web or shell"}

# Words that show which problem the answer names, per error type (English and Korean).
PROBLEM_WORDS = {
    "FAB_DOI": ("not exist", "not to exist", "doesn't exist", "no such", "does not resolve", "doesn't resolve", "no record", "404", "fabricat", "invented",
                "could not find", "couldn't find", "not found", "존재하지", "찾을 수 없", "없는 doi", "확인되지"),
    "FAB_NODOI": ("not exist", "not to exist", "doesn't exist", "no such", "nothing match", "no record", "fabricat", "invented", "could not find", "couldn't find", "not found",
                  "no match", "존재하지", "찾을 수 없", "확인되지", "없는 논문"),
    "DOI_SWAP": ("different paper", "another paper", "points to", "resolves to", "belongs to", "다른 논문", "가리", "DOI"),
    "RETRACTED": ("retract", "철회"),
    "WRONG_YEAR": (),
    "WRONG_AUTHOR": (),
    "TITLELESS_WRONG_VOLPAGE": (),
}


def load_events(path: Path) -> list[dict]:
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            continue
    return events


def final_answer(events: list[dict]) -> str:
    results = [event for event in events if event.get("type") == "result"]
    return str(results[-1].get("result") or "") if results else ""


def tool_uses(events: list[dict]) -> list[dict]:
    uses = []
    for event in events:
        if event.get("type") != "assistant":
            continue
        for block in event.get("message", {}).get("content", []):
            if block.get("type") == "tool_use":
                uses.append(block)
    return uses


def engine_usage(events: list[dict]) -> dict:
    uses = tool_uses(events)
    commands = [str(use.get("input", {}).get("command", "")) for use in uses if use.get("name") == "Bash"]
    skill_loaded = any(use.get("name") == "Skill" and "ref-verify" in json.dumps(use.get("input")) for use in uses)
    engine = [c for c in commands if "ref_verify" in c or re.search(r"\bref-verify\s+(check|verify)", c)]
    subcommands = sorted({m for c in engine for m in re.findall(r"(check-bib|check-file|check-claim|verify-doi)", c)})
    web = sum(use.get("name") in ("WebFetch", "WebSearch") for use in uses)
    curl = sum("curl " in c or "urllib" in c for c in commands)
    if engine:
        mode = "engine"
    elif skill_loaded:
        mode = "skill_without_engine"
    else:
        mode = "no_skill"
    return {
        "mode": mode,
        "skill_loaded": skill_loaded,
        "engine_calls": len(engine),
        "engine_subcommands": subcommands,
        "web_tool_calls": web,
        "shell_http_calls": curl,
        "tool_calls": len(uses),
    }


def mentions(answer: str, needles: list[str]) -> bool:
    lowered = answer.casefold()
    for needle in needles:
        if needle.startswith("[") and needle.endswith("]"):
            # "[1]" must not match "[10]"; also accept "[1," "[1–" and "1]" inside ranges.
            number = needle[1:-1]
            if re.search(rf"\[{number}\]|\[{number}[,–-]|[,–-]\s*{number}\]|(?<![\d.]){re.escape(number)}\)(?!\d)"
                         rf"|reference {number}\b|ref\.? {number}\b|참고문헌 {number}\b|\b{number}번", answer, re.I):
                return True
        elif needle.casefold() in lowered:
            return True
    return False


def automatic_decision(item: dict, answer: str) -> str:
    named = mentions(answer, item["match"])
    kind = item["type"]
    if item["expected"] == "NOT_FLAG":
        if kind == "CLAIM_OK":
            return "review" if mentions(answer, item["value"]) else "clean"
        return "review" if named else "clean"
    if not named:
        return "missed"
    if kind.startswith("CLAIM_"):
        return "caught" if mentions(answer, item["value"]) else "review"
    words = PROBLEM_WORDS.get(kind, ())
    if kind == "WRONG_YEAR":
        words = (str(item["true_year"]),)
    elif kind in ("WRONG_AUTHOR", "TITLELESS_WRONG_VOLPAGE"):
        return "review"
    lowered = answer.casefold()
    return "caught" if any(word.casefold() in lowered for word in words) else "review"


def score(scratch: Path, truth_path: Path, adjudication_path: Path | None = None) -> dict:
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    adjudication_path = adjudication_path or truth_path.parent / "adjudication.json"
    adjudication = json.loads(adjudication_path.read_text(encoding="utf-8")) if adjudication_path.exists() else {}
    runs = [json.loads(line) for line in (scratch / "runs.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    scored = []
    for run in runs:
        transcript = scratch / "transcripts" / f"{run['run_id']}.jsonl"
        events = load_events(transcript)
        answer = final_answer(events)
        manual = adjudication.get("runs", {}).get(run["run_id"], {})
        decisions = {}
        for item in truth["manuscripts"][run["manuscript"]]["items"]:
            automatic = automatic_decision(item, answer)
            final = manual.get("items", {}).get(item["id"], automatic)
            if final == "review" and manual.get("reviewed"):
                # A person read this answer: an item the answer names (and that is not listed as an
                # exception) is a catch for a planted error and benign context for a correct one.
                final = "caught" if item["expected"] == "FLAG" else "clean"
            decisions[item["id"]] = {"auto": automatic, "final": final}
        scored.append(
            {
                **run,
                "answer_chars": len(answer),
                "usage": engine_usage(events),
                "usable": manual.get("usable"),
                "note": manual.get("note"),
                "decisions": decisions,
            }
        )
    return {"truth": truth, "runs": scored}


def summarize(result: dict) -> dict:
    truth = result["truth"]
    items = {item["id"]: item for m in truth["manuscripts"].values() for item in m["items"]}
    summary = {}
    for condition in sorted({run["condition"] for run in result["runs"]}):
        runs = [run for run in result["runs"] if run["condition"] == condition]
        recall: dict[str, list[int]] = {}
        false_alarms = {"correct_reference": [0, 0], "unindexed_reference": [0, 0], "correct_claim": [0, 0]}
        pending = 0
        for run in runs:
            for item_id, decision in run["decisions"].items():
                item = items[item_id]
                final = decision["final"]
                pending += final == "review"
                if item["expected"] == "FLAG":
                    hits = recall.setdefault(item["type"], [0, 0])
                    hits[0] += final == "caught"
                    hits[1] += 1
                else:
                    bucket = {"OK": "correct_reference", "UNINDEXED_OK": "unindexed_reference", "CLAIM_OK": "correct_claim"}[item["type"]]
                    false_alarms[bucket][0] += final == "false_alarm"
                    false_alarms[bucket][1] += 1
        caught = sum(v[0] for v in recall.values())
        total = sum(v[1] for v in recall.values())
        walls = [run["wall_seconds"] for run in runs]
        summary[condition] = {
            "runs": len(runs),
            "recall_by_type": recall,
            "recall_overall": [caught, total],
            "false_alarms": false_alarms,
            "engine_invoked": sum(run["usage"]["mode"] == "engine" for run in runs),
            "skill_loaded": sum(run["usage"]["skill_loaded"] for run in runs),
            "web_tool_runs": sum(run["usage"]["web_tool_calls"] > 0 for run in runs),
            "lookup_runs": sum(run["usage"]["web_tool_calls"] + run["usage"]["shell_http_calls"] > 0 for run in runs),
            "wall_seconds_median": round(statistics.median(walls), 1) if walls else None,
            "wall_seconds_mean": round(statistics.mean(walls), 1) if walls else None,
            "usable": sum(run.get("usable") is True for run in runs),
            "pending_review": pending,
        }
    return summary


def markdown(summary: dict, truth: dict) -> str:
    def pct(pair: list[int]) -> str:
        return f"{pair[0]}/{pair[1]} ({100 * pair[0] / pair[1]:.0f}%)" if pair[1] else "-"

    conditions = sorted(summary)
    lines = ["| | " + " | ".join(CONDITION_LABELS[c] for c in conditions) + " |", "|---" * (len(conditions) + 1) + "|"]

    def row(label: str, cells: list[str]) -> None:
        lines.append(f"| {label} | " + " | ".join(cells) + " |")

    for kind in truth["error_types"]:
        row(kind, [pct(summary[c]["recall_by_type"].get(kind, [0, 0])) for c in conditions])
    row("**All planted errors**", [f"**{pct(summary[c]['recall_overall'])}**" for c in conditions])
    for bucket, label in (("correct_reference", "False alarms: correct references"),
                          ("unindexed_reference", "False alarms: unindexed thesis/KCI/arXiv/JMLR"),
                          ("correct_claim", "False alarms: correct numeric claims")):
        row(label, [pct(summary[c]["false_alarms"][bucket]) for c in conditions])
    for key, label in (("engine_invoked", "Runs that ran the ref-verify engine"),
                       ("skill_loaded", "Runs that loaded the skill"),
                       ("web_tool_runs", "Runs that used WebFetch/WebSearch"),
                       ("lookup_runs", "Runs that looked sources up (shell HTTP or web tools)"),
                       ("usable", "Final answer usable (names reference, problem, fix)")):
        row(label, [f"{summary[c][key]}/{summary[c]['runs']}" for c in conditions])
    row("Wall time per run, median (mean)",
        [f"{summary[c]['wall_seconds_median']} s ({summary[c]['wall_seconds_mean']} s)" for c in conditions])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--truth", type=Path, default=HERE / "truth.json")
    parser.add_argument("--adjudication", type=Path, help="default: adjudication.json next to the truth file")
    parser.add_argument("--review", action="store_true", help="list the decisions a person still has to make")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--out", type=Path, help="write per-run results JSON here")
    args = parser.parse_args()
    result = score(args.scratch, args.truth, args.adjudication)
    summary = summarize(result)
    if args.review:
        items = {item["id"]: item for m in result["truth"]["manuscripts"].values() for item in m["items"]}
        for run in result["runs"]:
            for item_id, decision in run["decisions"].items():
                if decision["final"] == "review":
                    item = items[item_id]
                    print(f"{run['run_id']:28} {item_id:22} {item['type']:24} {item['ref']}")
    if args.out:
        args.out.write_text(json.dumps({"summary": summary, "runs": result["runs"]}, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    if args.markdown:
        print(markdown(summary, result["truth"]))
    else:
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
