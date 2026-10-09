# End-to-end skill evaluation: "check my references before I submit"

This folder measures what an agent actually reports when a researcher hands it a manuscript and
asks it to check the references, with and without the ref-verify skill. It is a measurement,
not a test: nothing here runs in CI, and nothing here changes the engine or `SKILL.md`.

`v2/` repeats it with obscure 2025–2026 papers the model does not know, and adds a condition
without web tools or a shell.

## Set

Eight short manuscripts in `manuscripts/`, 11–12 references each (92 references, 21 cited
claims):

| File | Language, style | Domain |
|---|---|---|
| `m1_dea_en.md` | English, APA (author–date) | dielectric elastomers |
| `m2_vaccine_en.md` | English, Vancouver | biomedicine |
| `m3_ml_en.md` | English, IEEE | machine learning |
| `m4_physics_en.md` | English, physics style without article titles | physics |
| `m5_dea_latex/` | LaTeX + BibTeX | dielectric elastomers |
| `m6_biomed_latex/` | LaTeX + BibTeX | biomedicine |
| `m7_polymer_ko.md` | Korean, mixed Korean/English references | polymers |
| `m8_ml_ko.md` | Korean, APA list | machine learning / physics |

`truth.json` (written by `build_truth.py`) lists every reference and every cited number, with the
planted error or `OK`. There are 40 planted errors:

| Type | n | Example |
|---|---|---|
| `FAB_DOI` fabricated, invented DOI | 5 | Pei & Brochu 2014, doi 10.1002/adma.201305412 (does not exist) |
| `FAB_NODOI` fabricated, no DOI | 4 | "Quantum-inspired graph neural networks…", JCIM 61(8) |
| `DOI_SWAP` real DOI of another paper | 4 | Kingma & Welling (VAE) with the LSTM paper's DOI |
| `RETRACTED` | 4 | Mehra 2020 (Lancet), Wakefield 1998 (no DOI), Snider 2020, Dasenbrock-Gammon 2023 |
| `WRONG_YEAR` | 4 | Mnih et al., Nature 518 dated 2013 |
| `WRONG_AUTHOR` (first author) | 3 | "Hinton, LeCun, Bengio (2015). Deep learning." |
| `TITLELESS_WRONG_VOLPAGE` | 3 | "A. K. Geim and K. S. Novoselov, Nat. Mater. 7, 183 (2007)" (volume 6) |
| `CLAIM_NUMBER` | 5 | "BNT162b2 … was 85% effective" (abstract: 95%) |
| `CLAIM_UNIT` | 4 | "luminosity distance of 410 kpc" (abstract: Mpc) |
| `CLAIM_DIRECTION` | 4 | "keeps the operation voltage above 300 V" (abstract: below 300 V) |

There are also 60 correct references, 8 correct numeric claims, and 5 correct references that
CrossRef does not index: a Korean PhD thesis, a 2007 *Polymer Korea* paper without a DOI,
NeurIPS 2017, JMLR 2014, and an arXiv preprint. These should not be called wrong.

Every correct reference was checked against its CrossRef record, every invented DOI returns 404
at CrossRef and "DOI does not exist" at doi.org, and no fabricated title has a CrossRef match.
`verify_truth.py` re-checks all of this live; it reported 0 problems on 2026-10-09, and it does
catch a planted counter-example. The unindexed items reuse sources verified for
`references-v1.jsonl`.

## Conditions and harness

- **A**: Claude Code with the skill. `SKILL.md` and `src/` are copied, as `npx skills add` lays
  them out, into `<scratch project>/.claude/skills/ref-verify/`.
- **B**: the same scratch project without it.

Each manuscript was run twice per condition, giving 32 runs, at most 2 in parallel. Every run
used a fresh scratch project and a fresh engine cache. The model was the logged-in
subscription default (`claude-opus-5-5`, Claude Code 2.1.295; `apiKeySource: none`).

The prompt is in the user's words (`{files}` is the manuscript file name, or `main.tex,
references.bib`):

- English: *"Before I submit, please check the references and citations in this manuscript
  ({files}). Only tell me about the problems."*
- Korean: *"투고 전에 이 원고({files})의 참고문헌과 인용을 검사해줘. 문제 있는 것만 알려줘."*

Isolation command, run with the scratch project as the working directory, stdin from
`/dev/null`, and `CLAUDE_REFVERIFY_EVAL_CHILD=1` and `REF_VERIFY_CACHE_DIR=<project>/.rv-cache`
in the environment:

```
claude -p "<prompt>" --output-format stream-json --verbose --include-hook-events \
  --setting-sources project \
  --settings '{"disableAllHooks": true, "autoMemoryEnabled": false}' \
  --strict-mcp-config --mcp-config '{"mcpServers":{}}' \
  --no-session-persistence --permission-mode dontAsk \
  --allowedTools "Bash Read Glob Grep WebFetch WebSearch Skill" \
  --disallowedTools "Write Edit NotebookEdit"
```

What each part does:

- `--setting-sources project` keeps the user's settings out: hooks, plugins, and permissions.
- `disableAllHooks` turns off every hook.
- `--strict-mcp-config` with an empty config loads no MCP servers.
- Only built-in skills plus the project skill load. The init event of every A run lists
  `ref-verify`, and no B run does.

Two positive controls were run before any real run:

- A project-level hook planted in a probe project ran and was reported in the stream when hooks
  were enabled. With `disableAllHooks` it neither ran nor appeared.
- The harness stops at the first hook event in any child stream. All 32 runs had 0 hook events.

The flags do not keep everything out of the user's directories:

- When a tool result was too large, Claude Code still saved it under
  `~/.claude/projects/<scratch path>/…/tool-results/`. This happened in 5 runs, about 20 KB
  each.
- Agents in 9 of the 16 A runs wrote scratch files under `/tmp` (for example `/tmp/rv_work`).

`run_e2e.py` is the harness, `score.py` the scorer, `engine_only.py` runs `check-bib` alone on
each reference list for comparison, and `adjudication.json` holds the decisions of the person
who read every final answer.

## Scoring

`score.py` (standard library only) reads the final answer of each transcript.

- **Planted error**: counted as caught when the answer names the reference and the problem
  (for a claim, the wrong value).
- **Correct reference or claim**: counted as a false alarm only if the answer calls it wrong
  (nonexistent, wrong DOI/year/author, retracted, or misquoted). Remarks such as "only loosely
  relevant", "couldn't confirm, check the full text", or "please verify by hand" are not false
  alarms.

Everything the rules cannot decide is marked `review`. After reading all 32 answers, the person
cleared every `review`; `adjudication.json` records the three overrides. "Usable" means the
answer names the reference, the problem, and a fix.

## Results (2026-10-09, main `6a13a86`)

| | A: with ref-verify skill | B: without |
|---|---|---|
| FAB_DOI | 10/10 | 10/10 |
| FAB_NODOI | 8/8 | 8/8 |
| DOI_SWAP | 8/8 | 8/8 |
| RETRACTED | 8/8 | 8/8 |
| WRONG_YEAR | 8/8 | 8/8 |
| WRONG_AUTHOR | 6/6 | 6/6 |
| TITLELESS_WRONG_VOLPAGE | 6/6 | 6/6 |
| CLAIM_NUMBER | **10/10** | **7/10** |
| CLAIM_UNIT | 8/8 | 8/8 |
| CLAIM_DIRECTION | 8/8 | 8/8 |
| **All planted errors** | **80/80 (100%)** | **77/80 (96%)** |
| False alarms on correct references | 0/120 | 0/120 |
| False alarms on unindexed references | 0/10 (3 marked "please verify") | 0/10 (4 marked "please verify") |
| False alarms on correct numeric claims | 0/16 | 0/16 |
| Ran the ref-verify engine | 16/16 | 0/16 |
| Used WebFetch/WebSearch | 2/16 | 13/16 |
| Usable final answer | 16/16 | 16/16 |
| Wall time per run, median (mean) | 85 s (84.5 s) | 40 s (44.7 s) |

Per-run decisions are in `results/2026-10-09-6a13a86-e2e.json`. The full transcripts
(stream-json, 32 files) are not committed; they were kept in the scratch directory of the
session that ran them.

**What the numbers say.**

- On this set, the agent without the skill already catches almost everything at the reference
  level, from model knowledge plus one or two web searches, and it raises no false alarms.
- B's three misses are all numbers it did not check against a source:
  - In both runs of m1 it accepted "up to 380% with acrylic elastomers" for Pelrine 2000 (the
    abstract says 215%), listing Pelrine among the correct entries.
  - In one run of m8 it affirmed the planted number outright: "1,200만 장, 1000개 범주라는
    부분은 맞습니다" (the abstract says 1.2 million images).
- With the skill, every number was compared with a fetched abstract, quoted in the answer, and
  all 80 errors were caught in both repeats.
- The cost is time: about twice as long per run (85 s vs 40 s median).

**Engine alone** (`engine_only.py`, `results/2026-10-09-6a13a86-engine-only.txt`):

- `check-bib` gives a non-PASS verdict to all 27 reference-level planted errors and to 1 of the
  60 correct references.
- It does not check claims.

**Limits of this measurement.**

- Most planted papers are well known, and the base model knows them. A set built from obscure
  or recent papers would likely widen the A–B gap at the reference level too.
- The manuscripts, the truth labels, and the adjudication were all made by the same agent.
  Adjudication is done by reading the answers, and the rules it followed are written down
  above.
- Two repeats per condition show consistency, not variance.
- Codex was not run. User-level skills in `~/.agents/skills/` (where ref-verify is installed
  globally) would leak into a "without the skill" condition, and isolating them means changing
  `CODEX_HOME`, which breaks the logged-in session.

## Findings on the skill and engine

No skill or engine problem caused a missed error in the 16 A runs: the agent compensated each
time. They are ranked by how many A runs they affected, as cost or as a miss waiting to happen
if the engine's verdict were trusted alone.

1. **Claims are checked by hand, not with the engine (16/16 runs).**
   - `check-file` was never used.
   - `check-claim` was used in 7 runs.
   - Every A run made its own `curl` calls to CrossRef or OpenAlex, and 12 of them fetched
     abstracts from OpenAlex that way.
   - `SKILL.md` and `AGENT_USAGE.md` describe `check-file` for many claims, but the agent did not
     reach for it. This is most of the extra time.
2. **`check-bib --json` output is too large for one tool result (5/16 runs).** The output was
   cut off ("My `head` cut the output short, so I'm running it again"), and the agent re-ran or
   re-parsed it. A compact output, such as a non-PASS-only filter, would save a step.
3. **Two wrong matches in the search path, each in 2 runs.**
   - The retracted Wakefield 1998 paper, cited without a DOI, was matched to a 1998 *Lancet*
     letter with the same title (Sabra et al., 10.1016/s0140-6736(05)77837-5). The result was
     WARN "first author differs" instead of `PAPER_RETRACTED`.
   - A fabricated JCIM reference was matched to a supplementary-information component
     (`type: component`, 10.1021/acs.jcim.5c01019.s003) at 80% title-word overlap.
   - Both runs caught both, but only because the agent checked further.
4. **Title-less citations with a wrong volume or page come back only as "No matching CrossRef
   record was found" (4 runs).** The agent had to find the intended record itself. The same
   path also leaves the correct LIGO citation `B. P. Abbott et al. (LIGO Scientific
   Collaboration and Virgo Collaboration), Phys. Rev. Lett. 116, 061102 (2016)` as UNVERIFIED:
   the collaboration words push it over the title-less word limit.
5. **A Korean reference with a title gets a reason that says it has none (2 runs).** For the
   DOI swap in m7, the reason reads "The reference has no article title, and CrossRef's record
   for this DOI differs in journal …". Hangul words are ignored when deciding whether a
   reference has a title.
6. **Semantic Scholar rate limits show up in the answers** ("Semantic Scholar was
   rate-limited, so I couldn't check it there") in several A runs. They did not change any
   verdict.

## Rerun

```
python3 benchmarks/e2e/verify_truth.py                     # network: re-verify the labels
python3 benchmarks/e2e/run_e2e.py --scratch /tmp/rv-e2e --parallel 2
python3 benchmarks/e2e/score.py --scratch /tmp/rv-e2e --review     # what a person must read
python3 benchmarks/e2e/score.py --scratch /tmp/rv-e2e --markdown
python3 benchmarks/e2e/engine_only.py --scratch /tmp/rv-e2e-engine
```

`adjudication.json` belongs to the 2026-10-09 run. A new run needs its answers read again.
