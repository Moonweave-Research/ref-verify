---
name: ref-verify
description: "Prevents citation hallucination in academic writing. Invoke when: finding papers to support a specific claim; verifying/checking/auditing existing citations or DOIs; confirming whether a paper actually says what the user claims it says ('is that what the paper says?', 'did they actually show X?'); adding a citation by describing a paper ('add a citation for the paper where X'); running a pre-submission reference sweep. Do NOT invoke for: formatting references in APA/IEEE style, general topic explanations, citation style questions, or prose editing. Selects Quick Screen (seconds per paper) or Full Audit (abstract/full-text claim check) automatically."
---

# ref-verify — Reference Hallucination Guard

The specific failure this skill prevents: LLMs describe paper content from recalled training data rather than from what live-fetched source text actually says. A paper gets attributed findings it doesn't contain, or cited for claims that appear nowhere in the text. The fix is one rule applied consistently:

**Every content statement about a paper must come from live-fetched source text, quoted or paraphrased verbatim. Abstracts are enough only for existence/topic-level claims. Mechanism or implementation claims require full text. If you cannot fetch the needed source text, say so explicitly — never fill the gap with recalled description.**

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

The expensive part is Full Audit (5-layer, abstract/full-text fetch when needed). Quick Screen costs ~5s per paper. Only escalate to Full Audit when the task genuinely requires content verification. In Full Audit, classify claim depth before Layer 3: mechanism-level claims make full-text fetch mandatory, not optional.

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

Before checking content, classify the claim depth:

- **Tier-1 existence/topic-level**: "Does this paper discuss X?", "Is this the paper about Y?", DOI/title/author/year sanity. Abstract verification is sufficient.
- **Tier-2 mechanism/implementation-level**: "How, where, or via what does X happen?" This includes heat-source location, current path, electrode/device configuration, material bulk vs surface mechanism, actuator/sensor role separation, and measurement conditions behind specific quantitative values. Abstract verification is not sufficient; full text is mandatory.

Fetch the abstract using this priority order:
1. CrossRef raw JSON: `https://api.crossref.org/works/{DOI}` — check the `abstract` field
2. Semantic Scholar: append `&fields=abstract` to your S2 DOI lookup
3. Open-access fallback: `https://api.unpaywall.org/v2/{DOI}?email=verify@ref-verify.local` — check `is_oa` and `oa_locations`
4. arXiv fallback for preprints: `https://export.arxiv.org/api/query?id_list={arxiv_id}`
5. PubMed Central for life/bio papers: `https://www.ncbi.nlm.nih.gov/pmc/articles/{PMCID}/`

For Tier-2 claims, also fetch full text before assigning support:
1. PubMed Central article HTML/XML when a PMCID exists
2. NCBI ID Converter / PMC OA package when DOI maps to a PMCID but the article page is hard to scrape
3. Unpaywall OA locations, preferring `url_for_pdf` or `url_for_landing_page`
4. Publisher HTML or PDF from the DOI landing page
5. arXiv full text for preprints

When local source text is available, run the deterministic gate before writing the CONTENT verdict:

```
python3 checker.py --claim "[claim]" --abstract-file abstract.txt --full-text-file fulltext.txt
```

Use the checker output as the floor, not a suggestion. You may make a verdict stricter after manual reading, but never upgrade `ABSTRACT-LEVEL ONLY`, `UNSUPPORTED`, or `CONTRADICTED` to supported without a stronger verbatim full-text quote.

After fetching, check: does the right source contain the specific claim being cited?

- Tier-1: abstract explicitly contains the claim (quote it verbatim) → `CONTENT: SUPPORTED (abstract-level)`
- Tier-2: full text explicitly contains the mechanism claim (quote it verbatim) → `CONTENT: SUPPORTED (full-text confirmed)`
- Tier-2: abstract is topic-related but full text cannot be fetched or searched → `CONTENT: ABSTRACT-LEVEL ONLY — mechanism claim needs full text`
- Tier-2: full text is fetched but only contains adjacent keywords, not the claimed mechanism relation → `CONTENT: PARTIAL — quote what it actually says`
- Tier-2: full text is fetched and does not contain support for the mechanism claim → `CONTENT: UNSUPPORTED — no full-text support found`
- Abstract is about the topic but doesn't make the specific Tier-1 claim → `CONTENT: PARTIAL — quote what it actually says`
- Abstract or full text contradicts the claim → `CONTENT: CONTRADICTED — do not use this citation`
- Abstract not accessible after trying all 5 sources → `CONTENT: UNVERIFIABLE — user must check full text`

**The rule that cannot be relaxed**: if you describe what a paper "shows" or "demonstrates" or "reports," you must quote or directly paraphrase the fetched source text at the required depth. Summarizing from memory is not permitted even if you feel confident. Abstracts prove topic direction, not implementation details.

For Tier-2, keyword co-occurrence is not support. The quoted sentence(s) must bind the mechanism actors and relation: what component does the action, where it is located, what path/current/stimulus is used, and what role the material plays. If the quote says "LM layer served as a flexible Joule heater" and the claim says "the LCE bulk served as the Joule heater," that is `CONTRADICTED`, not partial support.

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
CONTENT:    ✓ Supported (full-text confirmed) — "[verbatim full-text excerpt]"
            ✓ Supported (abstract-level) — "[verbatim abstract excerpt]"
            ⚠ Abstract-level only — mechanism claim needs full text
            ⚠ Partial — source says: "[what it actually says]"
            ✗ Unsupported | ✗ Contradicted | — Unverifiable (tried required sources)
RETRACTION: ✓ None found | ✗ Retracted

VERDICT: ACCEPT | WARN | REJECT
Reason: [one sentence — what's missing or wrong]
────────────────────────────────────────────────
```

CONTENT field must show either a verbatim excerpt or an explicit warning/unverifiable state — never a summary written from memory.

**ACCEPT**: two-source confirmed, DOI resolves to right paper, content supported at the required depth (`SUPPORTED (abstract-level)` for Tier-1, `SUPPORTED (full-text confirmed)` for Tier-2), no retraction.
**WARN**: solvable issue — single source, partial content match, abstract inaccessible after trying all fallbacks, or Tier-2 claim stuck at `ABSTRACT-LEVEL ONLY`. Safe to use only if user verifies the flagged item.
**REJECT**: DOI dead or resolves to wrong paper, paper not found anywhere, content unsupported after full-text search, content contradicted, or retraction confirmed.

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
- Never describe paper content without fetched source text at the required claim depth to quote from.
- Never verify mechanism/implementation claims from the abstract alone. Heat source, electrode/device configuration, current path, quantitative measurement conditions, and similar how/where/via-what claims require full text; if full text is unavailable, mark `ABSTRACT-LEVEL ONLY`, not supported.
- Never treat adjacent keywords as content support. For mechanism claims, the quote must bind the claimed actors and causal relation, not merely mention the same material, stimulus, or property.
- Never fill in missing metadata by guessing or pattern-matching.
- If two sources disagree, show both — do not choose silently.
- If the source text required for the claim depth is inaccessible after all fallbacks, use `UNVERIFIABLE` or `ABSTRACT-LEVEL ONLY` as specified above — do not substitute a description from memory.

---

## Edge Cases

**Preprint vs. published**: record both DOIs; prefer published for citation; note if title changed between versions.

**Author name variants**: "J. Smith" vs "John Smith" — flag but do not merge; let user confirm.

**Conference proceedings**: volume/pages often absent from CrossRef; mark `[NOT IN SOURCE]`, not guessed.

**S2 rate limiting**: wait 2s and retry once; if still failing, use CrossRef as primary and note single-source limitation.
