<div align="center">

<img src=".github/assets/ref-verify-mark-512.png" alt="ref-verify mark" width="96">

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
npx skills add Moonweave-Research/ref-verify -g
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

This is a skill/plugin-level workflow, not an MCP server. The CLI covers the
checks that are currently safe to automate directly:

- CrossRef metadata check: `ref-verify verify-doi`
- CrossRef abstract claim check: `ref-verify check-claim`
- JSON output for agent-readable routing
- Non-zero exit codes for `WARN`, `REJECT`, and `UNVERIFIABLE` results

DOI landing-page checks still use the skill protocol. Still handled by the skill protocol: Semantic Scholar, Unpaywall, arXiv, PubMed fallback checks, two-source existence checks, and retraction checks remain in `SKILL.md`.

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

Run a claim check against the CrossRef abstract:

```bash
ref-verify check-claim 10.1126/science.287.5454.836 \
  --claim "actuation strain above 100%" \
  --json
```

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

For a single DOI-backed claim, the CLI can run the CrossRef abstract portion:

```bash
ref-verify check-claim <doi> --claim "<specific claim>" --json
```

`check-claim` exits `0` only for `ACCEPT`. `WARN`, `PARTIAL`, and
`UNVERIFIABLE` return a non-zero exit code.

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
