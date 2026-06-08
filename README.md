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
  - CrossRef first, then DOI-bound Semantic Scholar and PubMed fallback when CrossRef has no abstract
- JSON output for agent-readable routing
- Non-zero exit codes for `WARN`, `REJECT`, and `UNVERIFIABLE` results

Statistical metrics such as p-values, AUC/AUROC, F1 score, hazard ratio, odds ratio, and confidence intervals still use the manual skill protocol. DOI landing-page checks still use the skill protocol. Still handled by the skill protocol: Unpaywall, arXiv, two-source existence checks, and retraction checks remain in `SKILL.md`.

The CLI has zero third-party Python runtime dependencies, but it is not an
offline verifier. Functional checks require outbound HTTPS access to public
academic APIs such as CrossRef, Semantic Scholar, and PubMed.

Install the CLI from a local checkout:

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

By default, `check-claim` uses CrossRef first. If CrossRef has no abstract, it tries DOI-bound Semantic Scholar and PubMed fallback sources. Use `--source crossref`, `--source semantic-scholar`, or `--source pubmed` for source-specific debugging; explicit non-CrossRef source selection bypasses CrossRef.

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

## Modes

**Quick Screen** is for DOIs you already have. It uses CrossRef to compare the
provided DOI, title, first-author surname, and year.

```bash
ref-verify verify-doi <doi> --title "<title>" --first-author <last-name> --year <year> --json
```

`verify-doi` exits `0` only for `PASS`. `WARN` and `REJECT` return a non-zero
exit code, so weak or mismatched metadata cannot silently pass automation gates.

**Full Audit** is for literature search and final pre-submission review. The
skill fetches abstracts through CrossRef, Semantic Scholar, Unpaywall, arXiv,
and PubMed where needed, then checks whether the paper supports the specific
claim being cited.

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
and `note`. Batch mode reuses the same conservative `check-claim` engine:
`ACCEPT` means the abstract explicitly supports the numeric claim. `WARN`,
`PARTIAL`, `REJECT`, or `UNVERIFIABLE` means the claim should not be treated as
verified.

Current `check-claim` error codes:

- `CLAIM_SUPPORTED`: explicit abstract support found.
- `CLAIM_NOT_EXPLICIT`: an abstract was available, but the claim was not explicitly supported.
- `CLAIM_AMBIGUOUS`: numeric evidence or context exists, but binding is ambiguous.
- `NO_ABSTRACT`: attempted DOI-bound sources did not provide abstract text.
- `DOI_NOT_FOUND`: selected source did not find a DOI-bound record.
- `DOI_MISMATCH`: the primary or explicitly selected DOI-bound record did not match the requested DOI.
- `SOURCE_API_ERROR`, `SOURCE_TIMEOUT`, `SOURCE_UNSUPPORTED`: source lookup failed or could not be used.

> Core rule: every content statement about a paper must come from a live-fetched
> abstract. If the abstract is inaccessible after fallback checks, say
> `UNVERIFIABLE`. Do not fill the gap from memory.

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

- [anneal-skill](https://github.com/Moonweave-Systems/anneal-skill) - measure-first decision discipline for AI agents
- [decide-skill](https://github.com/Moonweave-Systems/decide-skill) - decision automation for non-expert domains
