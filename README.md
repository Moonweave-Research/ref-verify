<div align="center">

<img src=".github/assets/ref-verify-mark-512.png" alt="ref-verify mark" width="96">

</div>

# ref-verify

**Stop citing papers that don't say what you think they say.**

You asked your AI agent to find papers. The DOIs look plausible. The author names sound right. The quotes feel accurate. But some of them are wrong — and you won't find out until a reviewer does.

`ref-verify` is an agent skill for citation verification. It gives Claude Code,
Cursor, Codex, and other skill-aware agents a repeatable workflow for checking
references before they land in a draft.

The current implementation is intentionally **skill/plugin-level**, not MCP. The
skill can optionally call the bundled Python CLI as a terminal execution engine
for DOI-backed checks. Anything the CLI cannot prove falls back to the manual
5-layer protocol in `SKILL.md`.

Current CLI coverage:

- CrossRef-backed DOI metadata checks: `ref-verify verify-doi`
- CrossRef-abstract claim checks: `ref-verify check-claim`
- JSON output for agent-readable routing
- Non-zero exit codes for `WARN`, `REJECT`, and `UNVERIFIABLE` results

Still handled by the skill protocol:

- Semantic Scholar, Unpaywall, arXiv, and PubMed fallback checks
- DOI landing-page confirmation
- Two-source existence checks
- Retraction checks

---

## What you install

```bash
# requires npx (comes with Node.js)
npx skills add Moonweave-Research/ref-verify -g
```

Works with **Claude Code, Cursor, Codex**, and any agent that supports the `npx skills` ecosystem.

After installation, use it like a normal agent skill: ask the agent to verify,
audit, or find citations. You do not start a server and you do not configure MCP
for this workflow.

Example prompts:

```text
verify these citations before I submit: [DOI list]
does this paper actually support the claim "actuation strain above 100%"?
find 3 papers supporting the claim that X, and verify each citation
check doi 10.1126/science.287.5454.836 against this title and year
```

### Optional executable engine

The skill is the agent workflow. The Python CLI is the skill-level execution engine that the installed skill can call from a terminal before falling back to the manual protocol.

No MCP server is required for this workflow. Current CLI scope is CrossRef-backed DOI metadata checks and CrossRef-abstract claim checks. If CrossRef does not expose an abstract, `check-claim` returns `UNVERIFIABLE`; the agent skill can still continue with the manual Semantic Scholar, Unpaywall, arXiv, and PubMed fallback protocol.

```bash
git clone https://github.com/Moonweave-Research/ref-verify.git
cd ref-verify
python3 -m pip install -e .
```

For local development before installation, run the test suite with the source
tree on `PYTHONPATH`:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Check whether the CLI is available:

```bash
ref-verify --help
```

When working from a source checkout before installation, use:

```bash
PYTHONPATH=src python3 -m ref_verify.cli --help
```

Then run focused checks directly:

```bash
ref-verify verify-doi 10.1126/science.287.5454.836 \
  --title "High-Speed Electrically Actuated Elastomers with Strain Greater Than 100%" \
  --first-author Pelrine \
  --year 2000 \
  --json

ref-verify check-claim 10.1126/science.287.5454.836 \
  --claim "actuation strain above 100%" \
  --json
```

From an uninstalled source checkout, run the same checks through the module
entrypoint:

```bash
PYTHONPATH=src python3 -m ref_verify.cli verify-doi 10.1126/science.287.5454.836 \
  --title "High-Speed Electrically Actuated Elastomers with Strain Greater Than 100%" \
  --first-author Pelrine \
  --year 2000 \
  --json

PYTHONPATH=src python3 -m ref_verify.cli check-claim 10.1126/science.287.5454.836 \
  --claim "actuation strain above 100%" \
  --json
```

---

## What gets caught

The full skill/manual workflow catches:

| Problem | What happens without ref-verify |
|---|---|
| **Wrong DOI** | Agent lists a plausible DOI that resolves to a completely different paper |
| **Wrong authors** | "Smith et al. (2020)" — but CrossRef shows only Smith as single author |
| **Wrong year** | Paper was published in 2008, AI confidently writes 2011 |
| **Made-up content** | Agent describes a paper as "showing 380% strain" — the abstract says no such thing |
| **Near-miss citation** | Paper mentions the number you need, but in a different context (e.g. a measurement condition, not a result) |
| **Retracted paper** | Valid DOI, but the paper was retracted — and you had no idea |

---

## Real hallucinations caught during testing

These are not hypothetical examples. These failures were found while evaluating this skill against a real AI agent.

**Case 1 — Content hallucination (not in the abstract)**

We asked an AI agent (without the skill) to find papers on IPMC actuator strain performance. It described Nemat-Nasser (2002) as follows:

> *"Develops the first physics-based micromechanical model explicitly predicting strain distribution and tip displacement... provides the quantitative strain-voltage relationship."*

That description is not in the abstract. We fetched the actual CrossRef raw JSON. The abstract discusses stiffness modeling and ion effects — it does not mention strain distribution predictions or strain-voltage relationships. The agent filled the gap from training memory and presented it as fact.

With `ref-verify`, the same paper gets:

```
CONTENT: ⚠ Partial
Abstract (CrossRef verbatim): "A systematic experimental evaluation of the mechanical
response of both metal-plated and bare Nafion and Flemion in various cation forms and
various water saturation levels has been performed..."
→ Abstract does not contain a specific strain value. Verify full text before citing
  for a quantitative strain claim.
```

---

**Case 2 — DOI resolves to a completely different paper**

A citation appeared in a reference list as:

> *Carpi, F. et al. (2011). Dielectric elastomers as electromechanical transducers. Elsevier. DOI: 10.1016/B978-0-08-047488-5.00001-0*

We fetched that DOI. It resolves to **Chapter 1** of the edited book — authored by **Ronald Pelrine and Roy Kornbluh**, published in **2008**, not 2011. Carpi et al. are the book editors, not the chapter authors.

The skill verdict:

```
VERDICT: REJECT
DOI resolves to different paper. Year: 2011 (provided) vs 2008 (CrossRef).
Authors: Carpi et al. are editors; chapter authors are Pelrine & Kornbluh.
Corrected book-level DOI: 10.1016/b978-0-08-047488-5.x0001-9
```

---

**Case 3 — Right number, wrong meaning (near-miss)**

Searching for papers supporting ">100% actuation strain in dielectric elastomers," the skill found a candidate whose abstract contained "500% strain." That looks strong.

Fetching and reading the abstract: the 500% value is the mechanical **pre-strain level** at which the electric breakdown field was measured — not an actuation output. Citing this paper for "500% actuation strain" would be wrong.

```
CONTENT: ⚠ Partial
Abstract contains "500% strain" but this refers to the pre-strain condition
at which breakdown field (218 MV/m) was measured — not an actuation strain output.
Abstract does not explicitly report an actuation strain result.
VERDICT: WARN — does not meet the ACCEPT threshold for this specific claim.
```

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

For the CrossRef metadata portion, use:

```bash
ref-verify verify-doi <doi> --title "<title>" --first-author <last-name> --year <year> --json
```

`verify-doi` exits `0` only for `PASS`; `WARN` and `REJECT` return a non-zero exit code so missing or mismatched comparison metadata cannot silently pass automation gates.

**Full Audit** — for searching from scratch or final pre-submission review.
Fetches the abstract live from CrossRef → Semantic Scholar → Unpaywall → arXiv → PubMed (in order). Checks whether the abstract actually contains the specific claim being cited. Explicitly marks any paper as `UNVERIFIABLE` if no abstract is accessible — never guesses.

For a single DOI-backed claim, use:

```bash
ref-verify check-claim <doi> --claim "<specific claim>" --json
```

This command is intentionally conservative. It accepts only what the fetched CrossRef abstract supports and marks missing abstracts as `UNVERIFIABLE`.

`check-claim` exits `0` only for `ACCEPT`; `WARN`, `PARTIAL`, and `UNVERIFIABLE` return a non-zero exit code for automation gates.

The CLI does not yet replace the full manual Quick Screen: still follow the skill protocol for DOI landing-page resolution, second-source confirmation, and retraction checks when those layers are required.

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

- [anneal-skill](https://github.com/Moonweave-Systems/anneal-skill) — measure-first decision discipline for AI agents
- [decide-skill](https://github.com/Moonweave-Systems/decide-skill) — decision automation for non-expert domains
