# End-to-end skill evaluation v2: papers the model does not know

v1 (`../README.md`) found 80/80 planted errors with the skill and 77/80 without it, but the cited
papers were famous. v2 asks the question v1 could not answer: **does ref-verify make a
difference when the model cannot rely on remembering the papers?**

It is a measurement, not a test. Nothing here runs in CI, and nothing here changes the engine
or `SKILL.md`. All runs used the engine at main `e045a86`.

Only the papers changed. The error types, prompts, and isolation flags are the same as in v1,
with two additions:

- **Condition C**: no skill, no web tools, and no shell.
- **A pinned model**: `--model claude-opus-5-5`, explained below.

## Set

Eight short manuscripts in `manuscripts/`, written by `build_v2.py` from `sources.json`, the
frozen CrossRef and arXiv records with abstracts removed. They hold 93 references and 30 cited
claims:

| File | Language, style | Domain | Refs | Claims |
|---|---|---|---|---|
| `v2m1_dea_en.md` | English, APA | dielectric elastomer actuators | 13 | 4 |
| `v2m2_ionic_en.md` | English, Vancouver | ionic polymer actuators, ionogels | 12 | 4 |
| `v2m3_crystal_latex/` | LaTeX + BibTeX | polymer crystallization, thermal analysis | 11 | 4 |
| `v2m4_polymer_ko.md` | Korean, numbered | *Polymer Korea* papers, LCE actuators | 12 | 3 |
| `v2m5_pvdf_lce_en.md` | English, IEEE | PVDF and liquid crystal elastomer fibres | 10 | 3 |
| `v2m6_rehab_latex/` | LaTeX + BibTeX | rehabilitation pilot trials | 11 | 4 |
| `v2m7_ceramic_ko.md` | Korean, APA | ceramics and thin films (*J. Korean Ceram. Soc.*) | 12 | 4 |
| `v2m8_magnetism_en.md` | English, physics style without titles | thin-film magnetism, plasma diagnostics | 12 | 4 |

### How the real papers were chosen

Every real paper had to be obscure, recent, or narrow:

- **Recent.** 77 of the 79 distinct DOIs were published in 2025–2026 (40 in 2026, 37 in
  2025). The other two are retracted papers from 2024.
- **Rarely cited.** CrossRef `is-referenced-by-count` on 2026-10-09 has a median of 0 and a
  maximum of 19. 42 papers have 0 citations, and 66 have 5 or fewer.
- **Korean sources.**
  - *Polymer Korea*: 8 papers, one of them the target of a swapped DOI.
  - *Journal of the Korean Ceramic Society*: 5 papers.
  - *Journal of the Korean Physical Society*: 3 papers.
  - *Journal of Exercise Rehabilitation*: 1 paper.
  - Two Korean theses from RISS (2006, 2013).
- **Narrow fields.** Five manuscripts are in polymer and actuator materials (m1–m5).

`truth.json` records each paper's year and citation count. A `recall_check` note says the
set's author did not recognise the paper before fetching its record. That check is
self-assessed. Condition C below is the independent evidence: without lookups the model
caught 1 of 7 wrong numbers and 0 of 5 retractions.

### Planted errors

There are 52 planted errors per pass:

| Type | n | Example |
|---|---|---|
| `FAB_DOI` | 5 | Hartmann, Osei & Brandt 2025, doi 10.1088/1361-665X/ade5f1 (does not exist) |
| `FAB_NODOI` | 3 | "Recycled platinum electrodes for Nafion-free IPMC bending actuators", *Sens. Actuators B* 412 |
| `DOI_SWAP` | 4 | Zhang et al. 2026 (*Technologies* lens paper) with a *PLOS One* soft-gripper DOI |
| `RETRACTED` | 5 | Zhang et al. 2025, *Carbohydr. Polym.* 354:123278 |
| `WRONG_YEAR` | 5 | Niu et al., *Smart Mater. Struct.* 35(6), dated 2023 instead of 2026 |
| `WRONG_AUTHOR` | 5 | "Croce et al. 2025": the first author is Neu |
| `TITLELESS_WRONG_VOLPAGE` | 3 | "Z. Navrátil et al., Plasma Sources Sci. Technol. 35, 015013 (2025)": the volume is 34 |
| `CLAIM_NUMBER` | 7 | "a service lifetime of 61 years at 80 °C" (abstract: 16 years) |
| `CLAIM_UNIT` | 7 | "a counterpressure of 19.52 MPa" (abstract: kPa) |
| `CLAIM_DIRECTION` | 8 | "PMA dominates … only in films thinner than 90 nm" (abstract: greater than) |

The set also contains items that should not be flagged:

- 57 correct references.
- 6 correct references that CrossRef does not index: 4 arXiv preprints (2025–2026) and the 2
  Korean theses.
- 8 correct numeric claims.

Every claim's wrong and true values come from the paper's CrossRef abstract. `truth.json`
quotes the abstract next to each claim.

`verify_truth.py --truth v2/truth.json` re-checks every label live. On 2026-10-09 it reported 0
problems on all 123 items. For v2 it also checks:

- the first author of each `WRONG_AUTHOR` record;
- the volume and first page of each `TITLELESS_WRONG_VOLPAGE` record;
- that each swapped DOI belongs to a different paper;
- that every number quoted from an abstract appears in the live CrossRef abstract;
- that no CrossRef record has a fabricated title.

As a positive control, a copy of the truth with 8 planted label mistakes (one per check) got 8
problems reported. The extended `verify_truth.py` still reports 0 problems on v1.

## Conditions and harness

- **A**: the skill is installed in the project, as in v1.
- **B**: the same project without it, as in v1.
- **C**: the same project without the skill, with only `Read Glob Grep` allowed. `Bash
  WebFetch WebSearch Write Edit NotebookEdit Skill` are disallowed.

**Why C has no shell either.** The request was "no skill, WebSearch/WebFetch disallowed". With
Bash still allowed, the agent can fetch from the CrossRef API with `curl`, which B did in 15
of 16 runs. Keeping Bash would make C another B. C therefore measures only what the model
knows plus reasoning over the manuscript.

**Why the model is pinned.** v1 ran on the subscription default, which was `claude-opus-5-5`.
Between v1 and v2 the default for these isolated sessions became `claude-sonnet-5-5`; a probe
C run reported that model and was discarded. Every v2 run passes `--model claude-opus-5-5`, so
v2 differs from v1 only in the papers. The runs used the subscription (`apiKeySource: none`)
and Claude Code 2.1.295.

A and B ran twice per manuscript and C once, 40 runs in all, at most 2 in parallel. The
command is v1's with `--model claude-opus-5-5`; C also has its own tool lists.

Isolation results:

- **Hooks.** All 40 runs had 0 hook events.
- **Tool-results files.** As in v1, `--no-session-persistence` does not stop large tool results
  from being saved under `~/.claude/projects/<scratch path>/…/tool-results/`. This happened in
  9 of the 40 runs (6 A, 3 B, 0 C), 14–23 KB each.
- **Scratch files.** Agents in A runs again wrote scratch files under `/tmp`.

## Results (2026-10-09, main `e045a86`)

| | A: with ref-verify skill | B: without | C: without, no web or shell |
|---|---|---|---|
| FAB_DOI | 10/10 | 10/10 | 5/5 |
| FAB_NODOI | 6/6 | 6/6 | 3/3 |
| DOI_SWAP | 8/8 | 8/8 | 4/4 |
| RETRACTED | 10/10 | 10/10 | **0/5** |
| WRONG_YEAR | 10/10 | 10/10 | 5/5 |
| WRONG_AUTHOR | 10/10 | 10/10 | **1/5** |
| TITLELESS_WRONG_VOLPAGE | 6/6 | 6/6 | **1/3** |
| CLAIM_NUMBER | 14/14 | 14/14 | **1/7** |
| CLAIM_UNIT | 14/14 | 14/14 | 7/7 |
| CLAIM_DIRECTION | 16/16 | 16/16 | 5/8 |
| **All planted errors** | **104/104 (100%)** | **104/104 (100%)** | **32/52 (62%)** |
| …of which only hedged ("may be", "check this") | 0 | 0 | 17 |
| False alarms on correct references | 0/114 | 1/114 | 5/57 |
| False alarms on unindexed references | 0/12 | 0/12 | 0/6 |
| False alarms on correct numeric claims | 0/16 | 0/16 | 0/8 |
| Ran the ref-verify engine | 16/16 | 0/16 | 0/8 |
| Called the CrossRef API from the shell (`curl`/`urllib`) | 16/16 | 15/16 | 0/8 |
| Used WebFetch/WebSearch | 2/16 | 11/16 | 0/8 |
| Wall time per run, median (mean) | 75 s (76 s) | 69 s (77 s) | 30 s (33 s) |

Per-run decisions are in `results/2026-10-09-e045a86-e2e-v2.json`. `adjudication.json` lists
every exception and gives every C decision explicitly. The transcripts are not committed.

**What the numbers say.**

- **With live lookups, the skill made no difference on these papers.**
  - A and B both caught all 104 planted errors.
  - B did by hand what the engine does. In 15 of 16 runs it called the CrossRef API with
    `curl`, and it compared the claims with abstracts it fetched itself.
  - The only gap is one hedged false alarm in B: "[4] Luo et al. – the year is probably
    wrong", for a correct entry. The same answer then says 2026 is fine.
  - The time cost seen in v1 (85 s vs 40 s) is gone: 75 s vs 69 s.
- **Without lookups, the model's memory did not cover these papers.**
  - C caught 62% of the errors, and 17 of its 32 catches were only "may be" or "check this".
  - It caught what can be inferred from the manuscript: a DOI prefix that doesn't match the
    journal, a year that doesn't match the volume, or a unit that is physically implausible.
  - It missed every retraction and 6 of 7 wrong numbers. It also made 5 false statements
    about correct references.
- **What made the difference on unknown papers was live lookup, not the skill.** The agent
  without the skill looks things up by itself when it has a shell or web tools.

### Failures a user would notice

1. **C (no lookups) states false things about correct references.** It made five such
   statements, each a correct reference flagged under "likely errors" or "claims to check":
   - "*Engineering Research Express* publishes 4 issues a year, so "8(15), 155228" doesn't
     fit. The real issue and article number probably look like "8(1), 015xxx"." CrossRef has
     8(15), 155228.
   - "'e202502157' doesn't follow Wiley's pattern … it should be `e02157`." CrossRef has
     e202502157. The C run on m3 said the same about a correct "e202503161".
   - "[6] Ali et al. This is a review article, but it's cited for specific figures … cite the
     original study instead." It is a primary study.
   - "'all participants' probably misstates it. The regimen likely applied to one arm only."
     The abstract says "All participants received a non-opioid regimen of naproxen".
2. **C repeats a planted number as fact.** In m1 it writes "6% strain isn't 'comparable' to
   the 25.9% you cite from that paper." The paper reports 15.9%.
3. **C's "check this" does not flag the error.**
   - "Check that it actually reports a 61-year lifetime at 80 °C": the paper says 16 years.
   - "[1] and [2] contain specific figures that are worth checking": both are planted errors.
   - A user who checks nothing learns nothing from these, and C gives the same advice for
     correct figures.
4. **A hedges because the engine's Semantic Scholar calls were rate-limited (11/16 A
   answers).**
   - "A second search source (Semantic Scholar) was rate-limited, so I can't say for sure
     that it's fabricated."
   - B, which used only CrossRef and the web, called the same reference "possibly made-up …
     remove it".
   - Two runs were in flight at a time, and the engine-only baseline overlapped a few early
     runs, so the load was higher than for a single user.
5. **The B false alarm above** is the only wrong statement about a correct reference in 32
   A/B runs.

### Engine alone

`engine_only.py --truth v2/truth.json` output is in
`results/2026-10-09-e045a86-engine-only.txt`.

- **Planted errors.** `check-bib` gives a non-PASS verdict to all 33 reference-level planted
  errors. It does not check claims.
- **Correct references.** All 57 PASS, including the 7 title-less physics citations, which it
  resolves by search.
- **Unindexed references.** The two theses and two of the arXiv preprints come back UNVERIFIED.
  The other two preprints are matched to their published versions:
  - arXiv:2604.11706 → *J. Chem. Phys.* (PASS).
  - arXiv:2510.20370 → *Phys. Rev. Lett.* 2026 (WARN, "the year differs").

Three v1 findings appear again:

- **Wrong volume or page in a title-less citation.** All 3 come back only as "No matching
  CrossRef record was found". The agent had to find the intended record itself.
- **Hangul title ignored.** For the *Polymer Korea* DOI swap, the reason says "The reference has
  no article title". It also says the journal differs ("CrossRef: Polymer Korea"), although
  the cited 폴리머 is *Polymer Korea*. The verdict is WARN for a paper that does not exist at
  that DOI.
- **Swapped first authors in Markdown reference lists.** 3 of the 5 are UNVERIFIED/WARN ("first
  author (Neu) was not found in the reference's first-author position") rather than a
  mismatch. Both BibTeX cases are REJECT.

### Defects in the set that the agents found

The agents found these mistakes in the manuscripts. None counts as a false alarm.

- `v2m6_rehab_latex/main.tex` uses `\SI` without loading `siunitx`. All 5 m6 runs noted
  it.
- m8 describes Zhou et al. as "metastable-neutral measurements" and Huang et al. as
  "electron temperature measurements". Both values come from simulations.
- m3 overstates two sources:
  - It ties the foam cell structure to crystallinity (`yang2025foam`).
  - It says pre-shear "shifts" crystallization (arXiv:2604.11706).
- APA entries cut author lists with "…" (m1, m7). APA 7 lists up to 20 authors.

### Limits of this measurement

- **Same-agent authorship.** The same agent picked the papers, wrote the manuscripts,
  labelled the truth, judged obscurity, and read the answers. The model under test is from the
  same family.
- **Small n.** 8 manuscripts, 2 repeats for A and B, and 1 for C. 104/104 vs 104/104 shows no
  gap on this set; it does not bound how large a gap could be elsewhere.
- **Claims favour CrossRef.** Every claim's abstract is in CrossRef, so one `curl` reaches it.
  Papers whose abstracts are only on publisher pages, OpenAlex or PubMed were not tested;
  there the engine's other sources might matter.
- **One model.** The section above measured only Opus 5.5. The Sonnet 5.5 rerun below shows
  that the answer depends on the model.
- **C has no shell.** It measures memory plus reasoning, not "no web but a shell".
- **No Codex.** Codex was not run, for the same reason as in v1.

## Sonnet 5.5 rerun (2026-10-09, main `3083597`)

The current subscription default for these sessions is Sonnet 5.5. On Opus, B matched the
skill because it called CrossRef itself. This rerun asks whether Sonnet does the same.

The set, prompts, harness, and isolation are unchanged; only `--model claude-sonnet-5-5` is
different. A, B, and C ran once per manuscript: 24 runs, at most 2 in parallel, 0 hook events.

The engine is main `3083597`. It differs from the Opus runs' `e045a86` only by #38, which
stops attaching references to letters, supplements, and reviews of other works, and counts
Hangul words when deciding whether a reference has a title. Only A uses the engine.

Decisions are in `adjudication-sonnet.json` (every planted error decided explicitly) and per-run
results in `results/2026-10-09-3083597-e2e-v2-sonnet.json`. Opus counts are over 2 repeats,
Sonnet over 1.

| | Opus A | Opus B | Opus C | Sonnet A | Sonnet B | Sonnet C |
|---|---|---|---|---|---|---|
| FAB_DOI | 10/10 | 10/10 | 5/5 | 5/5 | 5/5 | 5/5 |
| FAB_NODOI | 6/6 | 6/6 | 3/3 | 3/3 | 3/3 | 2/3 |
| DOI_SWAP | 8/8 | 8/8 | 4/4 | 4/4 | 4/4 | 4/4 |
| RETRACTED | 10/10 | 10/10 | 0/5 | 5/5 | **2/5** | 0/5 |
| WRONG_YEAR | 10/10 | 10/10 | 5/5 | 5/5 | 5/5 | 5/5 |
| WRONG_AUTHOR | 10/10 | 10/10 | 1/5 | 5/5 | **2/5** | 1/5 |
| TITLELESS_WRONG_VOLPAGE | 6/6 | 6/6 | 1/3 | 3/3 | **0/3** | 0/3 |
| CLAIM_NUMBER | 14/14 | 14/14 | 1/7 | 7/7 | **3/7** | 0/7 |
| CLAIM_UNIT | 14/14 | 14/14 | 7/7 | 7/7 | 6/7 | 5/7 |
| CLAIM_DIRECTION | 16/16 | 16/16 | 5/8 | 7/8 | 5/8 | 1/8 |
| **All planted errors** | **104/104 (100%)** | **104/104 (100%)** | **32/52 (62%)** | **51/52 (98%)** | **35/52 (67%)** | **23/52 (44%)** |
| …of which only hedged | 0 | 0 | 17 | 0 | 4 | 11 |
| False alarms on correct references | 0/114 | 1/114 | 5/57 | 0/57 | 0/57 | 1/57 |
| False alarms on unindexed refs / correct claims | 0 | 0 | 0 | 0 | 0 | 0 |
| Ran the ref-verify engine | 16/16 | 0/16 | 0/8 | 8/8 | 0/8 | 0/8 |
| Wall time per run, median | 75 s | 69 s | 30 s | 56 s | 39 s | 18 s |

### Did B look sources up itself?

| | Opus B (16 runs) | Sonnet B (8 runs) |
|---|---|---|
| Runs with any lookup of its own | 16 | 7 |
| …calling the CrossRef API from the shell | 15 | 1 |
| …with WebFetch/WebSearch only | 1 | 6 |
| Runs answered from the manuscript alone | 0 | 1 (m6) |
| Cited DOIs whose record it fetched | 143/158 (91%) | 38/79 (48%) |

The fetched-DOI count includes title-less references whose DOI the agent had to find; a
fabricated DOI is not counted. Sonnet B's runs:

| Manuscript | How Sonnet B looked things up | DOIs fetched | Planted errors caught |
|---|---|---|---|
| m1 | 9 WebFetch, 1 WebSearch | 3/11 | 4/7 |
| m2 | `curl` to the CrossRef API | 11/11 | 7/7 |
| m3 | 9 WebFetch | 7/9 | 7/7 |
| m4 | 15 WebFetch (2 blocked, 403) | 10/10 | 5/5 |
| m5 | 5 WebFetch, 1 WebSearch (publisher pages 403) | 2/8 | 2/5 |
| m6 | none: "I read both files but didn't check any DOI or claim online" | 0/10 | 5/8 |
| m7 | 11 WebFetch, 3 WebSearch (Springer and MDPI 403) | 5/10 | 3/6 |
| m8 | 5 WebSearch, no DOI or CrossRef lookup | 0/10 | 2/7 |

**What the numbers say.**

- **On the default model, the skill changes what the user gets: 51/52 vs 35/52.**
  - Without it, Sonnet looked up about half the cited records, mostly through publisher pages
    that often refused it (403). It said what it skipped: "I did not verify the rest,
    including the specific numbers cited from Annapooranan, Zeng & Tang …".
  - B fell behind on errors that need the record itself: retractions 2/5, wrong numbers 3/7,
    title-less volume/page 0/3, author order 2/5.
  - When Sonnet B queried the CrossRef API (m2), it caught 7/7, as Opus did.
- **On Opus, the same skill made no difference (104/104 both), because Opus B queried
  CrossRef by itself.** The value of the skill depends on the model.
- **The cost is time:** 56 s vs 39 s median on Sonnet.
- **Sonnet without lookups (C) is worse than Opus without lookups: 44% vs 62%.** It also made
  fewer false alarms on correct references (1 vs 5); more of its remarks were "check this"
  than assertions.

### Wrong statements a user would act on

- **Sonnet A (with the skill) misread an abstract once (m4).** It wrote "'455 nm에서 30%
  늘어난다'는 초록에서 확인되지 않았습니다. 본문을 직접 확인하세요", although the abstract
  says "30% contraction to 455 nm visible light". This is the A condition's only miss.
- **Sonnet B (m6, no lookups) and Sonnet C (m6) both confirmed the planted author swap.** B
  wrote "the key says Suk, but the first author is Park. This is harmless", and C wrote
  "the first author is Park (Suk is the second author)". Suk is the first author.
- **Sonnet B told the user to delete a real paper (m7).** The reference was a real paper with a
  wrong page, and B wrote "해당 논문을 찾지 못했습니다 … 출처를 확인할 수 없으면 삭제하세요".
- **Sonnet B (m8) reported three real papers as not found** after five WebSearch calls ("[1] …
  I found no match"), with the caveat that they may not be indexed yet.
- **Sonnet C (m2) flagged a correct DOI:** "Ref. 11's DOI looks malformed. 10.1002/cssc.71126
  doesn't match the usual ChemSusChem pattern". It is the real DOI.

### Semantic Scholar rate limits in A

| | Opus A (16) | Sonnet A (8) |
|---|---|---|
| Runs where a Semantic Scholar call returned 429 | 10 | 2 |
| …in the agent's own `curl` to api.semanticscholar.org | 10 | 2 |
| …in ref-verify engine output | 0 | 0 |
| Answers that mention the rate limit | 11 | 2 |
| Answers that soften a verdict because of it | 6 | 1 |

"Soften" means the answer gives the rate limit as the reason for a weaker verdict on a
fabricated reference. Examples:

- "A second search source (Semantic Scholar) was rate-limited, so I can't say for sure that
  it's fabricated."
- "The Semantic Scholar search was rate-limited, so I only have CrossRef evidence. Treat it as
  unverified, and possibly fabricated."

What the rate limit did and did not change:

- **No missed errors.** The fabricated reference was still flagged in every one of these runs;
  only the wording changed, from "remove it" to "treat it as unverified".
- **The 429s came from the agent's own queries, not the engine.** The agent ran the manual
  Semantic Scholar search that `SKILL.md` lists among its fallbacks (the
  `api.semanticscholar.org/graph/v1/paper/search` URL). Its "S2 rate limiting" rule then says
  to "use CrossRef as primary and note single-source limitation", which produces the softened
  wording.
- **Sonnet hit the limit less often** (2/8 runs vs 10/16) and also searched Semantic Scholar
  itself less often: 2 runs and 2 queries, vs 12 runs and 20 queries for Opus.

### Limits of the rerun

- **One run per condition.** One repeat per condition, and the same-agent caveats above apply.
- **Different engine for A.** A ran on `3083597`, not `e045a86`. B and C do not use the engine.
- **Possible confound in blocked pages.** Sonnet B's 403s came from publisher pages it chose
  to fetch. A run from another network might be blocked less often.

### Isolation leftovers (not deleted)

- **Tool-results files.** 6 of the 24 runs, all A, left a tool-results file under
  `~/.claude/projects/<scratch path>/` (16–39 KB). Four A runs read their own saved
  tool-results file back from there, at the path Claude Code gave them.
- **Scratch files.** New files in `/tmp` from these runs: `out.json`, `refs_in.md`, `rv_in`.

## Rerun

```
python3 benchmarks/e2e/v2/build_v2.py                               # rewrite manuscripts + truth from sources.json
python3 benchmarks/e2e/verify_truth.py --truth benchmarks/e2e/v2/truth.json
python3 benchmarks/e2e/run_e2e.py --scratch /tmp/rv-e2e-v2 --truth benchmarks/e2e/v2/truth.json \
  --conditions A B --model claude-opus-5-5 --parallel 2
python3 benchmarks/e2e/run_e2e.py --scratch /tmp/rv-e2e-v2 --truth benchmarks/e2e/v2/truth.json \
  --conditions C --repeats 1 --model claude-opus-5-5 --parallel 2
python3 benchmarks/e2e/score.py --scratch /tmp/rv-e2e-v2 --truth benchmarks/e2e/v2/truth.json --markdown
python3 benchmarks/e2e/engine_only.py --scratch /tmp/rv-e2e-v2-engine --truth benchmarks/e2e/v2/truth.json

# Sonnet 5.5 rerun
python3 benchmarks/e2e/run_e2e.py --scratch /tmp/rv-e2e-v2-sonnet --truth benchmarks/e2e/v2/truth.json \
  --conditions A B --repeats 1 --model claude-sonnet-5-5 --parallel 2
python3 benchmarks/e2e/run_e2e.py --scratch /tmp/rv-e2e-v2-sonnet --truth benchmarks/e2e/v2/truth.json \
  --conditions C --repeats 1 --model claude-sonnet-5-5 --parallel 2
python3 benchmarks/e2e/score.py --scratch /tmp/rv-e2e-v2-sonnet --truth benchmarks/e2e/v2/truth.json \
  --adjudication benchmarks/e2e/v2/adjudication-sonnet.json --markdown
```

`adjudication.json` and `adjudication-sonnet.json` belong to the 2026-10-09 runs. Run ids repeat
across models, so pass `--adjudication` for the Sonnet runs. A new run needs its answers read
again.
