<div align="center">

<img src="https://raw.githubusercontent.com/Moonweave-Research/ref-verify/main/.github/assets/ref-verify-mark-512.png" alt="ref-verify mark" width="96">

</div>

# ref-verify

[English](https://github.com/Moonweave-Research/ref-verify/blob/main/README.md) | [한국어](https://github.com/Moonweave-Research/ref-verify/blob/main/README.ko.md)

**Stop citing papers that do not say what you think they say.**

`ref-verify` is an agent skill for citation verification. It helps Claude Code,
Cursor, Codex, and other skill-aware agents check references before they land in
your draft.

Use it when you want an agent to find papers, verify a DOI, check whether a paper
supports a specific claim, or audit references before submission. No server setup is required.

---

## Scorecard

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Moonweave-Research/ref-verify/main/.github/assets/scorecard-dark.svg">
  <img src="https://raw.githubusercontent.com/Moonweave-Research/ref-verify/main/.github/assets/scorecard-light.svg" alt="Bar chart of check-bib verdicts on 86 held-out references: real 80% passed cleanly, fabricated 96% flagged, retracted 100% caught, 0 of 10 unindexed references rejected." width="830">
</picture>

Held-out set: 86 references written and committed before the tool was run on them, with no paper
shared with the development set.

| What was measured (held-out set) | Result | n | 95% CI |
|---|---|---|---|
| Real papers passed cleanly | **80%** | 40 | 65–90% |
| Real papers sent for a manual check (WARN) | 20% | 40 | 10–35% |
| Real papers wrongly rejected | 0% | 40 | 0–9% |
| Fabricated references flagged (WARN or REJECT) | **96%** | 26 | 81–99% |
| Retracted papers caught as `PAPER_RETRACTED` | **100%** | 10 | 72–100% |
| Legitimate references missing from CrossRef that were rejected | 0 of 10 | 10 | 0–28% |

- Fabricated, by type: invented DOI 5/5 · no DOI 5/5 · DOI swap 4/4 · wrong author/year 4/5 · publicly reported cases 7/7.
- 7 of the 8 real papers that did not pass are cited in the physics/chemistry style that omits the
  article title, which leaves nothing to compare against CrossRef.
- Time for all 86 references: 79 s on a cold cache (1.1 s median per reference), 0.1 s cached.

Development set (142 references, used while fixing the tool in
[#27](https://github.com/Moonweave-Research/ref-verify/pull/27), so these are in-sample scores): real
66/66 passed (94–100%), fabricated 43/43 flagged, retracted 16/16 caught, 1 of
17 unindexed references rejected.

Measured 2026-10-08 with ref-verify 1.2.2 (commit `01c7a37`) against live CrossRef, checking each set with
`check-bib` as BibTeX, RIS, and plain-text lists. Not measured: whether a paper supports a claim
(beyond a small numeric fixture), non-English literature beyond a few Korean items, and full text.
Every miss is listed per item in the results files ([held-out](https://github.com/Moonweave-Research/ref-verify/blob/main/benchmarks/results/2026-10-08-01c7a37-holdout-v1.json),
[development](https://github.com/Moonweave-Research/ref-verify/blob/main/benchmarks/results/2026-10-08-01c7a37-v1.json)); dataset, method, and how to rerun:
[benchmarks/README.md](https://github.com/Moonweave-Research/ref-verify/blob/main/benchmarks/README.md).

---

## Install the skill

```bash
# requires npx (comes with Node.js)
npx skills add Moonweave-Research/ref-verify -g \
  --skill ref-verify \
  --agent claude-code cursor codex \
  -y
```

Works with **Claude Code, Cursor, Codex**, and any agent that supports the
`npx skills` ecosystem.

After installation, use it like a normal agent skill. You do not start a server and you do not configure MCP for this workflow. No MCP server is required for this workflow.

The skill includes its own copy of the CLI engine, and the agent runs it from the skill folder, so nothing else needs to be installed. Python 3.10 or newer must be available as `python3`.

For explicit agent tool-calling rules, see [AGENT_USAGE.md](https://github.com/Moonweave-Research/ref-verify/blob/main/AGENT_USAGE.md).

---

## Use it

Ask naturally:

```text
verify these citations before I submit: [DOI list]
does this paper actually support the claim "actuation strain above 100%"?
find 3 papers supporting the claim that X, and verify each citation
check doi 10.1126/science.287.5454.836 against this title and year
audit all my references before submission
```

`ref-verify` stays quiet for general topic questions, prose editing, APA/IEEE
formatting, and citation style questions.

---

## Check a whole reference list

Find references in a paper or thesis that do not exist (for example ones a
chatbot made up), whose DOI points to a different paper, or that were
retracted, in one run.

**With the agent:** after installing the skill, ask "check every reference in
references.bib with ref-verify".

**From a terminal:**

1. Put the list in a file.
   - Zotero: right-click the collection → Export Collection → BibTeX →
     `references.bib` (EndNote and Mendeley export BibTeX or RIS).
   - A Word or other manuscript: copy the reference list into a plain-text
     editor and save it as `references.txt`. `[1]` or `1.` numbering and
     wrapped lines are fine. `.docx` and `.pdf` files are not read directly.
2. Install (Python 3.10 or newer):

   ```bash
   pipx install ref-verify
   ```

   With `uv`, skip the install:
   `uvx ref-verify check-bib references.bib`.

3. Run:

   ```bash
   ref-verify check-bib references.bib
   ```

   A first run takes about a second per reference (a little over two minutes
   for 150, with a `Checking references: 37/150` counter). Running the same
   list again takes seconds thanks to the cache. Prefixing
   `REF_VERIFY_MAILTO=you@university.edu` uses CrossRef's polite pool and is
   about three times faster.

   Add `--report check.html` for a file to send to an advisor or co-author;
   it opens in a browser with the items that need a look at the top.

**Reading the result**

| Result | Meaning | What to do |
|---|---|---|
| `PASS` | Title, first author, and year match the CrossRef record for the DOI (or the record found by search) | Nothing |
| `WARN` | Found, but something differs; the line below says what (year, author, the title of the paper the DOI really points to) | Compare that one with the source |
| `REJECT` | The DOI exists nowhere, points to a different paper, or the paper is retracted | Fix or drop the citation |
| `UNVERIFIED` | Could not be confirmed automatically; theses, local conference abstracts, some books, and DOIs registered outside CrossRef (arXiv, KISTI) often land here. It does not mean the reference is wrong | Check it yourself |

A made-up reference without a DOI can only show as `UNVERIFIED`, not `REJECT`,
so look each `UNVERIFIED` item up once (for example in Google Scholar).

---

## Optional CLI engine

The skill is the agent workflow. The Python CLI is the skill-level execution engine that the installed skill can call from a terminal.

The Python package is CLI-only. It does not install `SKILL.md`; install the agent skill from GitHub with `npx skills add` as shown above.

This is a skill/plugin-level workflow, not an MCP server. The CLI covers the
checks that are currently safe to automate directly:

- CrossRef metadata check: `ref-verify verify-doi`
- DOI-bound abstract claim check: `ref-verify check-claim`
- Batch DOI-bound claim checks: `ref-verify check-file`
  - literal text claims
  - subject-matched percentage claims such as efficiency, response rate, or actuation strain
  - simple unit/count claims such as cycles, patients, voltage, temperature, and concentration
  - CrossRef first, then DOI-bound OpenAlex, Semantic Scholar, and PubMed fallback when CrossRef has no abstract
- Reference-list check (BibTeX, RIS, plain text, Markdown): `ref-verify check-bib`
- JSON output for agent-readable routing
- Non-zero exit codes for `WARN`, `REJECT`, and `UNVERIFIABLE` results

Statistical metrics such as p-values, AUC/AUROC, F1 score, hazard ratio, odds ratio, and confidence intervals still use the manual skill protocol. DOI landing-page checks still use the skill protocol. The CLI rejects a DOI that CrossRef records as retracted (via its retraction notice); retraction banners CrossRef does not know about, Unpaywall, arXiv, and two-source existence checks remain in the `SKILL.md` protocol.

The CLI has zero third-party Python runtime dependencies, but it is not an
offline verifier. Functional checks require outbound HTTPS access to public
academic APIs such as CrossRef, OpenAlex, Semantic Scholar, and PubMed.

### Cache

The CLI keeps API responses on disk for 7 days, so re-running a check does not
query CrossRef and the abstract sources again. A DOI that returned HTTP 404 is
kept for 1 day only, so a newly registered DOI is re-checked soon. Rate limits
(429) and server errors (5xx) are retried up to 3 times with backoff, honouring
`Retry-After` up to 10 s, and are never cached.

- Location: `$REF_VERIFY_CACHE_DIR`, else `$XDG_CACHE_HOME/ref-verify`, else `~/.cache/ref-verify`.
- Lifetime: `REF_VERIFY_CACHE_TTL_DAYS` (default `7`).
- Disable: `--no-cache` on any command, or `REF_VERIFY_NO_CACHE=1`. Delete the directory to clear it.

To run the CLI yourself, install it from PyPI:

```bash
uvx ref-verify --help            # run without installing (uv)
pipx install ref-verify          # or install the `ref-verify` command
```

Or install it from a local checkout:

```bash
git clone https://github.com/Moonweave-Research/ref-verify.git
cd ref-verify
python3 -m pip install -e .
```

Check whether the CLI is available:

```bash
ref-verify --help
```

If you are working from an uninstalled source checkout, use the module
entrypoint:

```bash
PYTHONPATH=src python3 -m ref_verify.cli --help
```

Run a DOI metadata check:

```bash
ref-verify verify-doi 10.1126/science.287.5454.836 \
  --title "High-Speed Electrically Actuated Elastomers with Strain Greater Than 100%" \
  --first-author Pelrine \
  --year 2000 \
  --json
```

Run a DOI-bound abstract claim check:

```bash
ref-verify check-claim 10.1126/science.287.5454.836 \
  --claim "actuation strain above 100%" \
  --json
```

By default, `check-claim` uses CrossRef first. If CrossRef has no abstract, it tries DOI-bound OpenAlex, Semantic Scholar, and PubMed fallback sources. Use `--source crossref`, `--source openalex`, `--source semantic-scholar`, or `--source pubmed` for source-specific debugging; explicit non-CrossRef source selection bypasses CrossRef.

Source-checkout equivalents:

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

For local development, run:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Release safety checks also build the Python package, validate metadata, and
install the built wheel in a fresh virtualenv before publishing. Live checks
against public academic APIs are kept in a manual GitHub Actions workflow so
normal CI does not fail because an upstream API is temporarily unavailable.

---

## What it catches

| Problem | What happens without ref-verify |
|---|---|
| **Wrong DOI** | An agent lists a plausible DOI that resolves to a different paper |
| **Wrong authors** | A citation says "Smith et al. (2020)", but CrossRef shows one author |
| **Wrong year** | The paper was published in 2008, but the draft says 2011 |
| **Made-up content** | The draft says a paper shows a result that is not in the abstract |
| **Near-miss citation** | The right number appears, but in the wrong context |
| **Retracted paper** | The DOI is valid, but the paper was retracted |

---

## Scope — optional CLI versus manual audit

`ref-verify` is a conservative guard, not an oracle. It errs toward flagging: an
`ACCEPT` is high-confidence, and **anything else means "not auto-verifiable —
check it yourself", not "the citation is wrong."**

**The optional CLI verifies**

- DOI metadata: title, first-author surname, and year against CrossRef.
- Whether a DOI-bound **abstract** explicitly supports a specific numeric or
  literal claim, quoted verbatim. If no abstract is reachable, it returns
  `UNVERIFIABLE` rather than guessing.

**The optional CLI does not verify** (out of scope by design, not bugs)

- **Full-text, figure, table, or supplementary values** — abstract-only. A number
  that appears only in the body stays `UNVERIFIABLE`.
- **Relational or qualitative claims** — proportionalities, mechanisms,
  "broader/stronger than". Only value+unit and literal claims are checked.
- **Papers whose publisher withholds the abstract** — some titles expose no
  abstract to CrossRef or OpenAlex. No abstract → `UNVERIFIABLE`, which reflects
  reachability, not the claim.
- **Statistical metrics** (p-value, AUC/AUROC, F1, hazard/odds ratio, confidence
  intervals) — handled by the manual skill protocol, not the CLI.
- **Paper quality, novelty, field consensus**, or whether the *full* paper
  supports a broader statement.

The agent skill's manual Full Audit protocol goes beyond the optional CLI for
mechanism, implementation, and procedural claims. It requires a fetched
full-text passage at that source depth; when full text is unavailable, it
returns `WARN (ABSTRACT-ONLY)` instead of upgrading an abstract topic match to
`ACCEPT`.

**Reading a CLI verdict**

| Verdict | Meaning |
|---|---|
| `ACCEPT` | The fetched abstract explicitly supports the claim. High-confidence pass. |
| `WARN` / `PARTIAL` | An abstract was read but does not explicitly support the exact claim. Check the source. |
| `UNVERIFIABLE` | No abstract was reachable to check against. Not a judgment on the claim. |
| `REJECT` | DOI is dead, resolves to a different paper, contradicted, or retracted. |

---

## Modes

**Quick Screen** is for DOIs you already have. It uses CrossRef to compare the
provided DOI, title, first-author surname, and year.

```bash
ref-verify verify-doi <doi> --title "<title>" --first-author <last-name> --year <year> --json
```

`verify-doi` exits `0` only for `PASS`. `WARN` and `REJECT` return a non-zero
exit code, so weak or mismatched metadata cannot silently pass automation gates.

**Full Audit** is for literature search and final pre-submission review. The
skill fetches abstracts through CrossRef, OpenAlex, Semantic Scholar, Unpaywall,
arXiv, and PubMed where needed. For a topline claim, it checks the abstract; for
a mechanism, implementation, or procedural claim, it continues to a fetched
full-text passage before assigning support.

For a single DOI-backed claim, the CLI can run the abstract check:

```bash
ref-verify check-claim <doi> --claim "<specific claim>" --json
```

`check-claim` exits `0` only for `ACCEPT`. `WARN`, `PARTIAL`, and
`UNVERIFIABLE` return a non-zero exit code. JSON output includes
`abstract_source`, `source_attempts`, and `error_code` so agents can distinguish
missing abstracts, source failures, DOI mismatches, and ambiguous evidence.

Use `check-file` when a draft, literature note, or AI-agent output has many
DOI/claim pairs.

JSONL:

```bash
ref-verify check-file claims.jsonl
ref-verify check-file claims.jsonl --json
```

CSV:

```bash
ref-verify check-file claims.csv
```

Each row must include `doi` and `claim`. Optional fields are `id`, `source`,
and `note`. Rows are checked 4 at a time by default (`--workers N`); output keeps
the input order, and CrossRef and Semantic Scholar requests go one at a time
because their public APIs reject parallel requests. In a terminal, a
`Checking claims: N/M` counter on stderr shows progress (never with `--json`).
Ctrl-C stops the run; finished lookups stay cached, so rerunning resumes quickly. Batch mode reuses the same conservative `check-claim` engine:
`ACCEPT` means the abstract explicitly supports the numeric claim. `WARN`,
`PARTIAL`, `REJECT`, or `UNVERIFIABLE` means the claim should not be treated as
verified.

Current `check-claim` error codes:

- `CLAIM_SUPPORTED`: explicit abstract support found.
- `CLAIM_NOT_EXPLICIT`: an abstract was available, but the claim was not explicitly supported.
- `CLAIM_AMBIGUOUS`: numeric evidence or context exists, but binding is ambiguous.
- `NO_ABSTRACT`: attempted DOI-bound sources did not provide abstract text.
- `DOI_NOT_FOUND`: neither CrossRef nor doi.org knows the DOI, or the selected source did not find a DOI-bound record. The JSON still carries a `verdict` of `REJECT`.
- `DOI_NOT_IN_CROSSREF`: CrossRef has no record, but doi.org lists the DOI with another agency (DataCite for arXiv and Zenodo, KISTI, JaLC, ...). `verify-doi` returns `verdict: WARN`, `status: UNVERIFIED` without comparing metadata; `check-claim` tries OpenAlex, Semantic Scholar (arXiv DOIs by arXiv identifier), and PubMed for the abstract and judges the claim if one has it, otherwise returns `status: UNVERIFIABLE`, `verdict: WARN` with this code. Not a dead DOI.
- `PAPER_RETRACTED`: CrossRef lists a retraction notice for the DOI; the claim is rejected before any abstract is read.
- `DOI_MISMATCH`: the primary or explicitly selected DOI-bound record did not match the requested DOI.
- `SOURCE_API_ERROR`, `SOURCE_TIMEOUT`, `SOURCE_RATE_LIMITED`, `SOURCE_UNSUPPORTED`: source lookup failed, timed out, was rate-limited, or could not be used.

Use `check-bib` when you have a reference list rather than DOI/claim pairs:

```bash
ref-verify check-bib references.bib
ref-verify check-bib references.ris --json
ref-verify check-bib references.md --format txt
```

It reads BibTeX, RIS, and plain-text or Markdown lists (one reference per
paragraph, per line, or per `[1]`/`1.`/`1)` item). A reference with a DOI is
compared with its CrossRef record like `verify-doi`; a plain-text reference
passes only when its text shows the CrossRef title and first author. A
reference without a DOI is looked up with CrossRef bibliographic search and
accepted only when the title matches and the year is within one. Matching
accepts the print or the online-first year, a title with or without its
subtitle or edition note, TeX math in BibTeX titles (`$\beta$` reads as β),
CrossRef's original-language title (for example the Korean title of
a *Polymer Korea* paper), and Hangul author names against CrossRef's
romanized ones (윤 → Yoon/Yun). When a DOI is unknown to CrossRef, doi.org is
asked which agency registered it, so arXiv, Zenodo, or KISTI DOIs are not
reported as dead. Search results that are about the paper rather than the
paper itself (peer-review reports, Faculty Opinions recommendations,
addenda and corrections) are skipped. A citation in a style that omits the
article title (`J. Bardeen, L. N. Cooper, and J. R. Schrieffer, Phys. Rev. 108,
1175 (1957)`) is compared on journal (full name or abbreviation), volume, first
page or article number, year, and first author; it passes when all of them
agree, and otherwise the reason names each field that differs. Without a DOI,
when the plain search finds nothing and the citation looks title-less, a second
CrossRef search by first author,
the rest of the citation, and the cited year finds short citations such as
`A. G. Riess et al., Astron. J. 116, 1009 (1998).`; the same full agreement is
required. The first author
is read only from the first name in the list, so a reference that puts a
co-author first does not pass. The terminal output starts with a count line
(`19 references: 11 PASS, 2 WARN, 5 REJECT, 1 UNVERIFIED`), lists one row per
reference (citation key, or the start of the reference for a pasted list), puts
the reason under every row that is not `PASS`, and ends with a one-paragraph
legend. With `--json` it is an object with `summary` (`total`, `pass`, `warn`,
`reject`, `unverified`, `failed`; `warn` includes the `UNVERIFIED` rows) and
`results`. `check-bib` exits `0` only
when every reference is `PASS`.

`check-bib` error codes:

- `REFERENCE_RESOLVED`: the reference had no DOI; CrossRef search found a matching record, reported as `resolved_doi`. `WARN` when the year differs by one or the first author differs.
- `REFERENCE_UNMATCHED`: the reference had no DOI and no CrossRef record matched (`status: UNVERIFIED`, `verdict: WARN`). The tool could not confirm it automatically; that does not mean the reference is wrong. Verify it manually.
- `DOI_NOT_IN_CROSSREF`: the DOI is registered with another agency (DataCite for arXiv and Zenodo, KISTI, JaLC, ...), so its metadata was not compared (`status: UNVERIFIED`, `verdict: WARN`). Open the DOI to confirm it.
- `DOI_NOT_FOUND`: neither CrossRef nor doi.org knows the DOI (`REJECT`).
- `PAPER_RETRACTED`, `ROW_CHECK_ERROR`: as for `check-claim` and `check-file`. Other DOI-backed results carry `error_code: null`; read `verdict`, `mismatches`, and `reason`, which names what differs (for example `the year differs (reference: 2009; CrossRef: 2010)`). A plain-text reference whose DOI belongs to a paper it does not mention is `status: MISMATCH`, `verdict: WARN`, with that paper's title in `reason`.

To hand the result to a co-author or supervisor, add `--report` to `check-bib`
or `check-file`. The file extension picks the format:

```bash
ref-verify check-bib references.bib --report report.html
ref-verify check-file claims.jsonl --report report.md
```

The HTML file is self-contained (inline CSS, no scripts, no external resources
other than `https://doi.org/` links). It opens with counts that add up to the
total (one box per verdict as shown), a plain-language line on what each
verdict means and asks you to do, then a "Needs a look" table with every
non-passing reference or claim and a "Passed" table below it. Each row is
coloured (`PASS`/`ACCEPT` green, `WARN` amber, `REJECT` red, `UNVERIFIED`
grey) and shows the reason and evidence. `UNVERIFIED` marks a result the tool
could not confirm automatically; it is not a finding that the reference is
wrong. The Markdown file has the same content. A `--report` path whose folder
does not exist is rejected before any lookup, so a long run is never lost.
`--json` output is unchanged.

> Core rule: every content statement about a paper must come from a live-fetched
> source at the depth the claim requires — abstract for topline claims, full
> text for mechanism, implementation, or procedural claims. If the required
> source is inaccessible, say so. Do not fill the gap from memory.

---

## Examples

**Checking citations you already have**

```text
User: "verify these 3 citations before I submit"

Shahinpoor & Kim (2001) 10.1088/0964-1726/10/4/327 - PASS
Bar-Cohen (2004)        10.1117/3.547465            - WARN  (listed as author; CrossRef: editor)
Carpi et al. (2011)     10.1016/B978-0-08-047488-5.00001-0 - REJECT
```

**Checking a specific claim**

```text
User: "does the Pelrine 2000 paper actually say DEAs reach over 100% strain?"

CONTENT: Supported
"Actuated strains up to 117% were demonstrated with silicone elastomers,
and up to 215% with acrylic elastomers."
[Source: CrossRef raw JSON, not recalled from memory]
```

**Near-miss citation**

A candidate paper may contain "500% strain", but the abstract can show that the
number is a pre-strain condition, not an actuation result. `ref-verify` reports
that as `WARN (PARTIAL)` instead of accepting the citation.

---

## Related

- [decision-kernel](https://github.com/Moonweave-Systems/decision-kernel) - evidence-gated decisions and drift/done checks for coding agents
