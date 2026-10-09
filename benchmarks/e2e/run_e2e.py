"""Run each e2e manuscript through an isolated `claude -p` session, with and without the skill.

Condition A copies the skill (SKILL.md + src/, as `npx skills add` lays it out) into
<scratch project>/.claude/skills/ref-verify/; condition B gets the same project without it.
Every run uses a fresh scratch project and a fresh engine cache, so runs do not share state.

Isolation of the child sessions (verified before the first real run):
  --setting-sources project      user settings (hooks, plugins, permissions) are not read
  --settings {"disableAllHooks": true, "autoMemoryEnabled": false}
                                 no hooks at all, no memory files under ~/.claude/projects
  --strict-mcp-config --mcp-config '{"mcpServers":{}}'   no MCP servers
  --no-session-persistence       no session transcript under ~/.claude
  CLAUDE_REFVERIFY_EVAL_CHILD=1  marks the process as an eval child
A run whose stream reports any hook event is stopped and the harness exits.

Usage: python3 run_e2e.py --scratch DIR [--only m1_dea_en:A:1 ...] [--parallel 2]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CLAUDE = os.environ.get("CLAUDE_BIN", str(Path.home() / ".local/bin/claude"))
SETTINGS = json.dumps({"disableAllHooks": True, "autoMemoryEnabled": False})
ALLOWED_TOOLS = "Bash Read Glob Grep WebFetch WebSearch Skill"
DISALLOWED_TOOLS = "Write Edit NotebookEdit"
TIMEOUT_SECONDS = 1800

PROMPTS = {
    "ko": "투고 전에 이 원고({files})의 참고문헌과 인용을 검사해줘. 문제 있는 것만 알려줘.",
    "en": "Before I submit, please check the references and citations in this manuscript ({files}). "
    "Only tell me about the problems.",
}


def command(prompt: str) -> list[str]:
    return [
        CLAUDE,
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--include-hook-events",
        "--setting-sources",
        "project",
        "--settings",
        SETTINGS,
        "--strict-mcp-config",
        "--mcp-config",
        '{"mcpServers":{}}',
        "--no-session-persistence",
        "--permission-mode",
        "dontAsk",
        "--allowedTools",
        ALLOWED_TOOLS,
        "--disallowedTools",
        DISALLOWED_TOOLS,
    ]


def prepare_project(root: Path, manuscript: dict, with_skill: bool) -> list[str]:
    if root.exists():
        raise SystemExit(f"{root} already exists; use a fresh --scratch directory")
    root.mkdir(parents=True)
    files = []
    for key in ("path", "bib"):
        if manuscript.get(key):
            source = HERE / manuscript[key]
            shutil.copy2(source, root / source.name)
            files.append(source.name)
    if with_skill:
        skill = root / ".claude" / "skills" / "ref-verify"
        skill.mkdir(parents=True)
        shutil.copy2(REPO / "SKILL.md", skill / "SKILL.md")
        shutil.copytree(REPO / "src", skill / "src", ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"))
    return files


def _events(transcript: Path) -> list[dict]:
    events = []
    for line in transcript.open(encoding="utf-8"):
        try:
            events.append(json.loads(line))
        except ValueError:
            continue
    return events


def run_one(scratch: Path, name: str, manuscript: dict, condition: str, repeat: int) -> dict:
    run_id = f"{name}__{condition}__{repeat}"
    project = scratch / "projects" / run_id
    files = prepare_project(project, manuscript, with_skill=condition == "A")
    prompt = PROMPTS[manuscript["language"]].format(files=", ".join(files))
    transcript = scratch / "transcripts" / f"{run_id}.jsonl"
    transcript.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, CLAUDE_REFVERIFY_EVAL_CHILD="1", REF_VERIFY_CACHE_DIR=str(project / ".rv-cache"))
    started = time.time()
    with transcript.open("w", encoding="utf-8") as out, open(os.devnull) as devnull:
        try:
            process = subprocess.run(
                command(prompt),
                cwd=project,
                env=env,
                stdin=devnull,
                stdout=out,
                stderr=subprocess.STDOUT,
                timeout=TIMEOUT_SECONDS,
            )
            exit_code = process.returncode
        except subprocess.TimeoutExpired:
            exit_code = "timeout"
    wall = time.time() - started
    hooks = sum(1 for event in _events(transcript) if event.get("type") == "system" and "hook" in str(event.get("subtype")))
    record = {
        "run_id": run_id,
        "manuscript": name,
        "condition": condition,
        "repeat": repeat,
        "prompt": prompt,
        "exit_code": exit_code,
        "wall_seconds": round(wall, 1),
        "hook_event_lines": hooks,
        "transcript": str(transcript),
    }
    print(json.dumps(record, ensure_ascii=False), flush=True)
    if hooks:
        raise SystemExit(f"{run_id}: hook events in the child stream; stopping")
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--only", nargs="*", help="run ids like m1_dea_en:A:1")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--parallel", type=int, default=1, choices=(1, 2))
    args = parser.parse_args()

    truth = json.loads((HERE / "truth.json").read_text(encoding="utf-8"))
    jobs = [
        (name, manuscript, condition, repeat)
        for repeat in range(1, args.repeats + 1)
        for name, manuscript in truth["manuscripts"].items()
        for condition in ("A", "B")
    ]
    if args.only:
        wanted = {tuple(item.split(":")) for item in args.only}
        jobs = [job for job in jobs if (job[0], job[2], str(job[3])) in wanted]
    print("command template:", json.dumps(command("<PROMPT>")), flush=True)
    log = args.scratch / "runs.jsonl"
    args.scratch.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.parallel) as executor:
        for record in executor.map(lambda job: run_one(args.scratch, *job), jobs):
            with log.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
