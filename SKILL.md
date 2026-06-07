---
name: ref-verify
description: "Prevents citation hallucination in academic writing. Invoke when: finding papers to support a specific claim; verifying/checking/auditing existing citations or DOIs; confirming whether a paper actually says what the user claims it says ('is that what the paper says?', 'did they actually show X?'); adding a citation by describing a paper ('add a citation for the paper where X'); running a pre-submission reference sweep. Do NOT invoke for: formatting references in APA/IEEE style, general topic explanations, citation style questions, or prose editing. Selects Quick Screen (seconds per paper) or Full Audit (abstract fetch + claim check) automatically."
---

# ref-verify — Reference Hallucination Guard

The specific failure this skill prevents: LLMs describe paper content from recalled training data rather than from what the abstract actually says. A paper gets attributed findings it doesn't contain, or cited for claims that appear nowhere in the text. The fix is one rule applied consistently:

**Every content statement about a paper must come from a live-fetched abstract, quoted or paraphrased verbatim. If you cannot fetch the abstract, say so explicitly — never fill the gap with recalled description.**

---

## Mode Decision

Pick the mode before doing any work. The choice controls cost and depth.

```
User provides DOI(s) for sanity check?
  └─ ≤10 refs → Quick Screen all
  └─ >10 refs → Quick Screen all; Full Audit only MISMATCH/DEAD results

User says "find papers on X" or "cite papers supporting claim Y"?
  └─ Full Audit (searching from scratch requires content verification)

User says "verify/check my reference list" or pre-submission audit?
  └─ ≤5 refs  → Full Audit all
  └─ >5 refs  → Quick Screen all first; Full Audit MISMATCH/DEAD + any ref
                 cited for a specific factual claim

User is writing inline and adds a single citation from memory?
  └─ Quick Screen minimum; Full Audit if citing for a specific claim
```

The expensive part is Full Audit (5-layer, abstract fetch). Quick Screen costs ~5s per paper. Only escalate to Full Audit when the task genuinely requires content verification.

---

## Executable Engine

Use this as a skill-level workflow. Do not build or require MCP for this path.
The CLI is an execution engine the skill can call from the terminal; the manual
protocol remains the fallback and the source of truth for layers the CLI does
not yet cover.

### CLI Availability Check

Before a DOI-backed check, see whether the executable engine is available:

```bash
ref-verify --help
```

If the console script is unavailable but the repository source is present, use:

```bash
PYTHONPATH=src python3 -m ref_verify.cli --help
```

If both commands fail, follow the manual fallback protocol below. Do not pretend
the CLI ran, and do not invent a result from memory.

### CLI-first workflow

Use the CLI first when the user provides a DOI or asks whether a DOI-backed
abstract supports a specific factual claim. Current CLI scope is CrossRef-backed
DOI metadata and CrossRef-abstract claim checks.

CrossRef metadata screen:

```bash
ref-verify verify-doi <doi> \
  --title "<provided title>" \
  --first-author <provided-first-author-last-name> \
  --year <provided-year> \
  --json
```

Source-checkout fallback:

```bash
PYTHONPATH=src python3 -m ref_verify.cli verify-doi <doi> \
  --title "<provided title>" \
  --first-author <provided-first-author-last-name> \
  --year <provided-year> \
  --json
```

`verify-doi` exits `0` only for `PASS`; `WARN` and `REJECT` return non-zero.
Supplying only a DOI checks that CrossRef resolves but is not enough to pass
metadata verification.

Route the result:

- `PASS`: report the metadata match, then continue Layer 4 DOI landing-page
  resolution and Layer 5 retraction checks when the selected mode requires them.
- `WARN`: report the missing or weak metadata, then continue manual fallback for
  the missing layers instead of silently accepting the reference.
- `REJECT`: stop using that citation as verified; report the mismatch and ask
  for a corrected DOI or citation unless the user explicitly wants alternatives.

Single claim check against a DOI abstract:

```bash
ref-verify check-claim <doi> --claim "<specific factual claim>" --json
```

Source-checkout fallback:

```bash
PYTHONPATH=src python3 -m ref_verify.cli check-claim <doi> --claim "<specific factual claim>" --json
```

Route the result:

- `ACCEPT`: quote the CLI evidence and continue any required manual DOI
  resolution, second-source existence, and retraction layers.
- `WARN` or `PARTIAL`: report what the CrossRef abstract did and did not
  support, then continue manual fallback when more sources are required.
- `UNVERIFIABLE`: CrossRef did not expose enough abstract evidence. Continue the
  manual fallback chain below instead of treating the claim as rejected or
  supported.

The CLI does not replace Layer 4 DOI landing-page resolution, two-source
existence checks, or retraction checks. Continue the manual protocol for those
layers when the selected mode requires them.

---

### Quick Screen — metadata + DOI sanity check

Use when the user provides a DOI or full citation and wants a sanity check.

1. Hit CrossRef: `https://api.crossref.org/works/{DOI}`
2. Compare returned title + first-author last name against what user provided
3. Fetch `https://doi.org/{DOI}` — confirm it resolves and lands on the right paper
4. Report one line per reference:

```
Smith et al. (2021) 10.1234/example — PASS (title/author match, DOI resolves)
Jones (2019) 10.5678/other — MISMATCH (CrossRef: Jones & Lee 2019, not Jones alone)
Kim (2023) 10.9999/fake — DEAD DOI
```

Escalate to Full Audit if: DOI resolves to a different paper, any field mismatches, or user is citing for a specific factual claim.

---

### Full Audit — for literature search or pre-submission check

Use when: searching for papers to support a claim, or doing a final citation sweep.

Run all five layers per paper. The layers are ordered by what they catch — don't skip forward.

**Layer 1 — Existence**

Search two sources independently:
- CrossRef: `https://api.crossref.org/works?query.bibliographic={title+author}&rows=5`
- Semantic Scholar: `https://api.semanticscholar.org/graph/v1/paper/search?query={title+author}&fields=title,authors,year,externalIds,abstract&limit=5`
- arXiv for preprints: `https://export.arxiv.org/api/query?search_query=ti:{title}&max_results=3`

A paper is confirmed only if titles essentially match and first-author last name agrees across two sources.

- Two-source hit → `CONFIRMED`
- One-source → `SINGLE-SOURCE ⚠` — proceed with caution, note in output
- Zero → `NOT FOUND ✗` — stop; report clearly; do not invent a substitute

**Layer 2 — Metadata**

Extract from confirmed sources and compare: title, all authors (last names), year, journal full name, DOI, volume/pages (mark `[NOT IN SOURCE]` if absent). If any field differs between sources, show both — do not silently pick one.

**Layer 3 — Content Traceability** ← most important layer

This is where the skill's core value lies. The goal is not just "does this paper exist" but "does this paper actually contain the claim being attributed to it."

Fetch the abstract using this priority order:
1. CrossRef raw JSON: `https://api.crossref.org/works/{DOI}` — check the `abstract` field
2. Semantic Scholar: append `&fields=abstract` to your S2 DOI lookup
3. Open-access fallback: `https://api.unpaywall.org/v2/{DOI}?email=verify@ref-verify.local` — check `is_oa` and `oa_locations`
4. arXiv fallback for preprints: `https://export.arxiv.org/api/query?id_list={arxiv_id}`
5. PubMed Central for life/bio papers: `https://www.ncbi.nlm.nih.gov/pmc/articles/{PMCID}/`

After fetching, check: does the abstract contain the specific claim being cited?

- Abstract explicitly contains the claim (quote it verbatim) → `CONTENT: SUPPORTED`
- Abstract is about the topic but doesn't make the specific claim → `CONTENT: PARTIAL — quote what it actually says`
- Abstract contradicts the claim → `CONTENT: CONTRADICTED — do not use this citation`
- Abstract not accessible after trying all 5 sources → `CONTENT: UNVERIFIABLE — user must check full text`

**The rule that cannot be relaxed**: if you describe what a paper "shows" or "demonstrates" or "reports," you must quote or directly paraphrase the fetched abstract text. Summarizing from memory is not permitted even if you feel confident.

**Layer 4 — DOI Resolution**

Fetch `https://doi.org/{DOI}`. Confirm the landing page matches the expected paper. A 403 (bot-blocked) from a URL slug containing the title and volume is not a dead link — note it as paywalled. A redirect to an unrelated page is a critical failure.

**Layer 5 — Retraction**

Search `"{first author last name}" "{journal name}" retraction` and check the DOI landing page for retraction banners. A retracted paper must not be used as a primary source.

---

## Output Format

**Quick Screen**: one line per reference (see above).

**Full Audit**: one card per paper, then a summary table.

```
REFERENCE AUDIT
────────────────────────────────────────────────
Paper:   [Title from live source — not from memory]
DOI:     [DOI] — [✓ Resolves | ✗ Dead | ✗ Wrong paper | ⚠ Paywalled-403]
Authors: [Full list from CrossRef/S2]
Year:    [Year] — Source: CrossRef | S2 | arXiv
Journal: [Full name]

EXISTENCE:  ✓ Confirmed (sources) | ⚠ Single-source | ✗ Not found
METADATA:   ✓ Consistent | ⚠ Discrepancy: [field: value-A vs value-B]
CONTENT:    ✓ Supported — "[verbatim abstract excerpt]"
            ⚠ Partial — abstract says: "[what it actually says]"
            ✗ Contradicted | — Unverifiable (tried CrossRef/S2/Unpaywall/arXiv)
RETRACTION: ✓ None found | ✗ Retracted

VERDICT: ACCEPT | WARN | REJECT
Reason: [one sentence — what's missing or wrong]
────────────────────────────────────────────────
```

CONTENT field must show either a verbatim excerpt or an explicit "Unverifiable" — never a summary written from memory.

**ACCEPT**: two-source confirmed, DOI resolves to right paper, content supported by fetched abstract, no retraction.
**WARN**: solvable issue — single source, partial content match, or abstract inaccessible after trying all fallbacks. Safe to use if user verifies the flagged item.
**REJECT**: DOI dead or resolves to wrong paper, paper not found anywhere, content contradicted, or retraction confirmed.

Summary table after all cards:

```
SUMMARY
────────────────────────────────────────────────
1. Smith et al. (2021)  — ACCEPT
2. Kim & Park (2019)    — WARN (abstract unverifiable; try PMC or institutional access)
3. Zhang (2023)         — REJECT (DOI resolves to different paper)
────────────────────────────────────────────────
X / Y verified.  Z need attention.
```

---

## Anti-Hallucination Rules

- Never recall a DOI from memory — fetch from CrossRef or S2.
- Never describe paper content without a fetched abstract to quote from.
- Never fill in missing metadata by guessing or pattern-matching.
- If two sources disagree, show both — do not choose silently.
- If the abstract is inaccessible after all five fallback sources, mark UNVERIFIABLE and stop — do not substitute a description from memory.

---

## Edge Cases

**Preprint vs. published**: record both DOIs; prefer published for citation; note if title changed between versions.

**Author name variants**: "J. Smith" vs "John Smith" — flag but do not merge; let user confirm.

**Conference proceedings**: volume/pages often absent from CrossRef; mark `[NOT IN SOURCE]`, not guessed.

**S2 rate limiting**: wait 2s and retry once; if still failing, use CrossRef as primary and note single-source limitation.
