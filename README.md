# ref-verify

**Stop citing papers that don't say what you think they say.**

You asked your AI agent to find papers. The DOIs look plausible. The author names sound right. The quotes feel accurate. But some of them are wrong — and you won't find out until a reviewer does.

`ref-verify` forces live verification against CrossRef, Semantic Scholar, and PubMed before anything lands in your draft. Every citation gets checked. Every content claim gets traced to a fetched abstract, not recalled from memory.

---

## Install

```bash
# requires npx (comes with Node.js)
npx skills add moonweave/ref-verify -g
```

Works with **Claude Code, Cursor, Codex**, and any agent that supports the `npx skills` ecosystem.

---

## What gets caught

| Problem | What happens without ref-verify |
|---|---|
| **Wrong DOI** | Agent lists a plausible DOI that resolves to a completely different paper |
| **Wrong authors** | "Smith et al. (2020)" — but CrossRef shows only Smith as single author |
| **Wrong year** | Paper was published in 2008, AI confidently writes 2011 |
| **Made-up content** | Agent describes a paper as "showing 380% strain" — the abstract says no such thing |
| **Near-miss citation** | Paper mentions the number you need, but in a different context (e.g. a measurement condition, not a result) |
| **Retracted paper** | Valid DOI, but the paper was retracted — and you had no idea |

---

## See it in action

**Finding a paper by description → gets verified before it reaches you:**

```
User: "find papers showing cancer cells are stiffer than healthy cells"

ref-verify Full Audit:

REFERENCE AUDIT
────────────────────────────────────────────────────────
Paper:   Biomechanical properties of cancer cells
DOI:     10.1088/0957-4484/18/18/185101 — ✓ Resolves (paywalled)
Authors: Bhanu Ponugoti, et al.  →  ✗ MISMATCH: CrossRef returns Cross, S.E. et al.
Year:    2007 — ✓ Consistent

VERDICT: WARN — author list does not match CrossRef record. Verify before citing.
────────────────────────────────────────────────────────
```

**Checking citations you already have — catches wrong DOI silently lurking in your reference list:**

```
User: "verify these 3 citations before I submit"

Shahinpoor & Kim (2001) 10.1088/0964-1726/10/4/327 — PASS
Bar-Cohen (2004)        10.1117/3.547465            — WARN  (listed as author; CrossRef: editor)
Carpi et al. (2011)     10.1016/B978-0-08-047488-5.00001-0 — REJECT (DOI resolves to different paper,
                                                               year is 2008 not 2011, different authors)
```

**Verifying a specific claim — checks if the abstract actually contains what you think it does:**

```
User: "does the Pelrine 2000 paper actually say DEAs reach over 100% strain?"

CONTENT: ✓ Supported
"Actuated strains up to 117% were demonstrated with silicone elastomers,
and up to 215% with acrylic elastomers."
[Source: CrossRef raw JSON, fetched 2026-06-01 — not recalled from memory]
```

---

## How to trigger it

Just talk naturally. `ref-verify` activates automatically on citation tasks:

```
"find 3 papers supporting the claim that X"
"verify these citations before I submit: [DOI list]"
"check doi 10.1002/adma.202108361 — I think I copied it wrong"
"is that actually what the paper says?"
"audit all my references before submission"
"add a citation for the paper where [author] showed [finding]"
```

Stays quiet for: general topic questions, prose editing, APA formatting, citation style questions.

---

## Two modes — picked automatically

**Quick Screen** — for DOIs you already have.
Hits CrossRef, confirms title + author match, verifies DOI resolves. Seconds per paper.

**Full Audit** — for searching from scratch or final pre-submission review.
Fetches the abstract live from CrossRef → Semantic Scholar → Unpaywall → arXiv → PubMed (in order). Checks whether the abstract actually contains the specific claim being cited. Explicitly marks any paper as `UNVERIFIABLE` if no abstract is accessible — never guesses.

> **The rule that cannot be relaxed:** Every content statement must come from a live-fetched abstract, quoted verbatim. If the abstract is inaccessible after all fallbacks, the output says so — it does not fill the gap with training data.

---

## Near-miss detection

Existence alone is not enough. The skill checks whether the abstract actually supports the *specific* claim being made.

A paper can mention a number that looks exactly right but refers to a different physical quantity, a measurement condition, or a baseline — not the result you're citing it for. Without claim checking, this passes unnoticed. With `ref-verify`, it's flagged as `WARN (PARTIAL)` with an explanation.

---

## 5-layer verification

1. **Existence** — two independent sources required (CrossRef + Semantic Scholar). Single-source results flagged.
2. **Metadata** — title, all authors, year, journal cross-checked. Any mismatch shown explicitly, never resolved silently.
3. **Content traceability** — abstract fetched from 5 sources in priority order. Verbatim quote in output. `UNVERIFIABLE` if inaccessible.
4. **DOI resolution** — `doi.org` fetch confirms landing page matches expected paper.
5. **Retraction** — web search + DOI landing page banner check.

---

## Related

- [anneal-skill](https://github.com/moonweave/anneal-skill) — measure-first decision discipline for AI agents
- [decide-skill](https://github.com/Moon-python/decide-skill) — decision automation for non-expert domains
