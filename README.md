<div align="center">

<img src="https://raw.githubusercontent.com/Moonweave-Research/ref-verify/main/.github/assets/ref-verify-mark-512.png" alt="ref-verify mark" width="96">

</div>

# ref-verify

[English](https://github.com/Moonweave-Research/ref-verify/blob/main/README.md) | [한국어](https://github.com/Moonweave-Research/ref-verify/blob/main/README.ko.md)

**Check a reference list before you submit it, and find the references that do not exist, point to a different paper, or were retracted.**

Reference lists drafted by AI assistants, or copied from one manuscript to the next, pick up
references that do not exist, DOIs that belong to another paper, and papers that were
retracted. ref-verify compares each reference with CrossRef and tells you which ones to look at.

- **Who it is for:** researchers and students finishing a paper, thesis, or proposal, and the AI assistants that help them.
- **What you get:** one verdict per reference (`PASS`, `WARN`, `REJECT`, `UNVERIFIED`) with the reason, in the terminal, as JSON, or as an HTML report.
- **How it runs:** as an agent skill for citation verification (Claude Code, Cursor, Codex) or as a command-line tool. No server setup is required, and no account or API key.

---

## Try it in 30 seconds

You need Python 3.10 or newer.

```bash
pipx install ref-verify            # or run without installing: uvx ref-verify check-bib ...
curl -O https://raw.githubusercontent.com/Moonweave-Research/ref-verify/main/examples/references.txt
ref-verify check-bib references.txt
```

[`examples/references.txt`](https://github.com/Moonweave-Research/ref-verify/blob/main/examples/references.txt)
holds seven references, and a comment above each one says what it really is: three real papers,
one real paper cited with the wrong year, one made-up reference, one retracted paper, and a
Korean doctoral thesis that CrossRef does not index. This is the output of ref-verify 1.3.1:

```text
7 references: 3 PASS, 1 WARN, 2 REJECT, 1 UNVERIFIED

VERDICT     REFERENCE                                   DOI
PASS        1. Pelrine, R., Kornbluh, R., Pei, Q., &…   10.1126/science.287.5454.836
PASS        2. Watts, D. J., & Strogatz, S. H. (1998)…  10.1038/30918 (resolved)
PASS        3. 김가은 (2024). IPA 분석을 통한 프로스…   10.5392/jkca.2024.24.09.361
WARN        4. Hochreiter, S., & Schmidhuber, J. (199…  10.1162/neco.1997.9.8.1735
            DOI matches, but the year differs (reference: 1999; CrossRef: 1997).
REJECT      5. Pelrine, R., Kornbluh, R., & Pei, Q. (…  10.1002/adma.200390974
            CrossRef has no record for this DOI (HTTP 404), and doi.org does not list it either.
REJECT      6. Wakefield, A. J., Murch, S. H., Anthon…  10.1016/s0140-6736(97)11096-0
            CrossRef records this paper as retracted (notice DOI 10.1016/s0140-6736(10)60175-4); do
            not use it as a source.
UNVERIFIED  7. 강동휘 (2025). 폴리(비닐피리딘) 기반…    -
            No matching CrossRef record was found; verify this reference manually.

PASS: matches CrossRef. WARN: check the difference named under it. REJECT: dead DOI, a different
paper, or retracted. UNVERIFIED: could not be confirmed automatically; that alone does not mean the
reference is wrong.
```

The command exits with code `2` because not every reference passed. CrossRef's data changes
over time, so a later run can differ slightly. To check your own list, export it from Zotero,
EndNote, or Mendeley as BibTeX or RIS, or paste it into a `.txt` file, and run
`ref-verify check-bib <file>`.

---

## How to read a result

| Verdict | What it means | What to do |
|---|---|---|
| `PASS` | Title, first author, and year match the CrossRef record for the DOI, or for the record found by search. | Nothing. |
| `WARN` | The reference was found, but something differs. The line under it says what: the year, the first author, or the title of the paper the DOI really belongs to. | Compare that reference with the source. |
| `REJECT` | The DOI exists nowhere, belongs to a different paper, or the paper is retracted. | Fix the reference or remove it. |
| `UNVERIFIED` | ref-verify could not confirm the reference automatically. This is not a finding that it is wrong. | Look it up yourself. |

`UNVERIFIED` needs care. A made-up reference without a DOI can only come out as `UNVERIFIED`,
never `REJECT`, because there is nothing to disprove. A real thesis, KCI paper, book, or preprint
that CrossRef does not index comes out the same way. In our three test sets, run with
ref-verify 1.3.1 on 2026-10-09, the `UNVERIFIED` results were:

| Test set | `UNVERIFIED` | Made up | Legitimate, not in CrossRef | Retracted, not in CrossRef | Real paper |
|---|---|---|---|---|---|
| [Held-out v2](https://github.com/Moonweave-Research/ref-verify/blob/main/benchmarks/results/2026-10-09-8170e66-holdout-v2.json) | 29 | 13 | 12 | 3 | 1 |
| [Held-out v1](https://github.com/Moonweave-Research/ref-verify/blob/main/benchmarks/results/2026-10-09-8170e66-holdout-v1.json) | 22 | 14 | 8 | 0 | 0 |
| [Development](https://github.com/Moonweave-Research/ref-verify/blob/main/benchmarks/results/2026-10-09-8170e66-v1.json) | 31 | 15 | 16 | 0 | 0 |
| Total | 82 | 42 | 36 | 3 | 1 |

Roughly half were made up and half were genuine, so look each `UNVERIFIED` reference up once,
for example in Google Scholar, RISS, or KCI. These proportions come from how the test sets were
built, not from real reference lists.

---

## Three ways to use it

### As an agent skill

```bash
# requires npx (comes with Node.js)
npx skills add Moonweave-Research/ref-verify -g \
  --skill ref-verify \
  --agent claude-code cursor codex \
  -y
```

Then ask your agent in plain words, for example:

```text
check every reference in references.bib with ref-verify
```

The skill carries its own copy of the command-line engine and runs it with `python3` (3.10 or
newer), so nothing else needs to be installed. The Python package is CLI-only: it does not install `SKILL.md`, so install the agent skill from GitHub with the command above.
More example requests: [Agent skill](https://github.com/Moonweave-Research/ref-verify/blob/main/docs/REFERENCE.md#agent-skill).

### From the command line

| Command | Checks |
|---|---|
| `ref-verify check-bib references.bib` | A reference list: BibTeX, RIS, or plain text and Markdown (`.txt`, `.md`). |
| `ref-verify verify-doi <doi> --title "..." --first-author <name> --year <year>` | One DOI against the title, first author, and year you give. |
| `ref-verify check-claim <doi> --claim "..."` | Whether the paper's abstract explicitly states a specific number or phrase. |
| `ref-verify check-file claims.jsonl` | Many DOI and claim pairs at once (JSONL or CSV). |

Add `--json` for machine-readable output. All commands, options, and error codes:
[Command-line engine](https://github.com/Moonweave-Research/ref-verify/blob/main/docs/REFERENCE.md#command-line-engine).

### As a saved report

```bash
ref-verify check-bib references.bib --report report.html
```

This writes a single HTML file you can send to a supervisor or co-author. It opens with a count
per verdict, lists the references that need a look first, and links each DOI to
`https://doi.org/`; it loads nothing else. Use `--report report.md` for Markdown. Details:
[Saved reports](https://github.com/Moonweave-Research/ref-verify/blob/main/docs/REFERENCE.md#saved-reports).

---

## Scorecard

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Moonweave-Research/ref-verify/main/.github/assets/scorecard-dark.svg">
  <img src="https://raw.githubusercontent.com/Moonweave-Research/ref-verify/main/.github/assets/scorecard-light.svg" alt="Bar chart of check-bib verdicts on 99 held-out references: real papers 89% passed cleanly, fabricated references 100% flagged, 8 of 8 CrossRef-marked retractions caught, 0 of 13 unindexed references rejected." width="830">
</picture>

Held-out set v2: 99 references written and committed before the tool was run on them, sharing
no paper with the earlier sets. It was measured once with ref-verify 1.3.1 against live
CrossRef on 2026-10-09.

| What was measured (held-out set v2) | Result | n | 95% CI |
|---|---|---|---|
| Real papers passed cleanly (`PASS`) | **89%** (40) | 45 | 77–95% |
| Real papers sent for a manual check (`WARN`) | 11% (5) | 45 | 5–23% |
| Real papers wrongly rejected (`REJECT`) | 0% (0) | 45 | 0–8% |
| Made-up references flagged (`WARN` or `REJECT`) | **100%** (29) | 29 | 88–100% |
| Retractions CrossRef records, caught as `PAPER_RETRACTED` | **100%** (8) | 8 | 68–100% |
| Legitimate references CrossRef does not index, wrongly rejected | 0% (0) | 13 | 0–23% |

- Made-up references by type: invented DOI 6/6, no DOI 6/6, DOI of another paper 5/5, wrong author or year 5/5, publicly reported cases 7/7.
- Four more retractions are listed by Retraction Watch but cannot be marked in CrossRef (DOIs registered with KISTI, ISTIC, or DataCite, and one conference-abstract DOI that resolves to its withdrawal notice). None got `PAPER_RETRACTED`: three came out `UNVERIFIED` and one `REJECT` as a different paper.
- The five real papers sent to `WARN`: a title-less citation with an abbreviated journal name, two citations under a group author, one matched to an unrelated record, and a book cited by its print year.
- One unindexed book (Feynman Lectures) passed by matching a 1964 journal review that has the book's title.
- Time for all 99 references: 97 s on an empty cache (1.1 s median per reference), 0.1 s from the cache.
- In-sample sets, used while tuning the tool and therefore optimistic: held-out v1 (86 references) real 40/40 `PASS`, made-up 26/26 flagged, retracted 10/10, unindexed 0/10 rejected; development set (142) real 66/66, made-up 43/43, retracted 16/16, unindexed 1/17 rejected.

Method: each set is checked with `check-bib` as BibTeX, RIS, and plain-text lists, on an empty
cache, and every item's verdict is stored in a results file
([held-out v2](https://github.com/Moonweave-Research/ref-verify/blob/main/benchmarks/results/2026-10-09-8170e66-holdout-v2.json)).
Not measured: whether a paper supports a claim (beyond a small numeric fixture), non-English
literature other than Korean, and full text. Dataset, method, and how to rerun:
[benchmarks/README.md](https://github.com/Moonweave-Research/ref-verify/blob/main/benchmarks/README.md).

---

## What it checks and what it does not

| Question | Checked? | How |
|---|---|---|
| Does the DOI exist? | Yes | CrossRef, then doi.org for DOIs registered elsewhere (arXiv, Zenodo, KISTI): those are `UNVERIFIED`, not dead. |
| Do the title, first author, and year match the DOI? | Yes | Compared with the CrossRef record. |
| Is a reference without a DOI real? | Partly | Found by CrossRef search when it is indexed; otherwise `UNVERIFIED`, never `REJECT`. |
| Was the paper retracted? | When CrossRef records it | A retraction notice in CrossRef, including the Retraction Watch data CrossRef carries. Retractions of papers CrossRef does not hold are missed. |
| Does the abstract state a specific number or phrase? | Yes, abstract only | `check-claim` and `check-file`, with CrossRef, OpenAlex, Semantic Scholar, and PubMed as abstract sources. |
| Full text, figures, tables, supplementary data | No | |
| Statistics such as p-values, AUC, or odds ratios | No | Left to the skill's manual protocol. |
| Paper quality, novelty, or field consensus | No | |

More on the limits: [Scope](https://github.com/Moonweave-Research/ref-verify/blob/main/docs/REFERENCE.md#scope-optional-cli-versus-manual-audit).

---

## Privacy and network use

ref-verify has zero third-party Python runtime dependencies, but it is not an offline verifier:
it needs outbound HTTPS access to public academic APIs. It contacts only these services:

| Service | When | What is sent |
|---|---|---|
| CrossRef (`api.crossref.org`) | Every command | The DOI, or, for a reference without a DOI, the reference text as a search query |
| doi.org | When CrossRef has no record of a DOI | The DOI |
| OpenAlex, Semantic Scholar, and PubMed (NCBI) | `check-claim` and `check-file`, when CrossRef has no abstract | The DOI (an arXiv DOI goes to Semantic Scholar as its arXiv ID) |

- Your files and claim texts are not uploaded anywhere: claims are compared with the abstract on your machine, and nothing is sent to any other service.
- Every request carries the user agent `ref-verify/<version> (+https://github.com/Moonweave-Research/ref-verify)`. Your email address is sent to CrossRef only if you set `REF_VERIFY_MAILTO`. OpenAlex requests carry `REF_VERIFY_OPENALEX_MAILTO`, which defaults to a placeholder (`verify@ref-verify.local`). A Semantic Scholar key is sent only if you set `SEMANTIC_SCHOLAR_API_KEY`.
- Responses are cached on disk for 7 days (a DOI that was not found, for 1 day) in `$REF_VERIFY_CACHE_DIR`, else `$XDG_CACHE_HOME/ref-verify`, else `~/.cache/ref-verify`. Each cache file holds the request URL, which includes the DOI or the reference text, and the response.
- Turn the cache off with `--no-cache` or `REF_VERIFY_NO_CACHE=1`, and clear it by deleting that folder. Details: [Cache](https://github.com/Moonweave-Research/ref-verify/blob/main/docs/REFERENCE.md#cache).

---

## For AI agents

Facts an assistant needs to call ref-verify correctly. The full contract is in
[AGENT_USAGE.md](https://github.com/Moonweave-Research/ref-verify/blob/main/AGENT_USAGE.md), and the
skill's own instructions are in [SKILL.md](https://github.com/Moonweave-Research/ref-verify/blob/main/SKILL.md).

**Commands**

```bash
ref-verify check-bib references.bib --json     # a reference list
ref-verify check-file claims.jsonl --json      # DOI and claim pairs
ref-verify verify-doi <doi> --title "..." --first-author <name> --year <year> --json
ref-verify check-claim <doi> --claim "..." --json
# inside the installed skill, run the bundled engine:
PYTHONPATH="$SKILL_DIR/src" python3 -m ref_verify.cli check-bib references.bib --json
```

**Exit codes**

| Code | Meaning |
|---|---|
| `0` | Every item is `PASS` (`check-bib`, `verify-doi`) or `ACCEPT` (`check-claim`, `check-file`). |
| `2` | The run completed, but at least one item did not pass. Read the JSON anyway. |
| `1` | Input or runtime error. |

- **Inputs:** `.bib`, `.ris`, `.txt`, `.md` for `check-bib` (`--format bib|ris|txt` for other extensions); JSONL rows `{"doi": ..., "claim": ..., "id": ..., "note": ...}` for `check-file` (`doi` and `claim` required).
- **JSON keys that matter:** `summary` (`total`, `pass`, `warn`, `reject`, `unverified`, `failed` for `check-bib`), and per result `verdict`, `status`, `error_code`, `resolved_doi`, `mismatches`, `reason`.
- **Never report these as verified:** `WARN`, `REJECT`, or `UNVERIFIED` from `check-bib`; `WARN`, `PARTIAL`, `REJECT`, or `UNVERIFIABLE` from claim checks; any run with `failed > 0`. Treat only `PASS` (references) and `ACCEPT` (claims) as confirmed.
- **Wording:** `REFERENCE_UNMATCHED` means CrossRef search found no match. Report it as unverified and ask the user to check it; never call it fabricated. `DOI_NOT_IN_CROSSREF` means the DOI is registered elsewhere; it is unverified, not dead. For `REFERENCE_RESOLVED`, use `resolved_doi` as the reference's DOI.
- **Do not** fill a missing abstract from memory, or infer full-text, table, or figure support from an abstract-only check.

---

## More documentation

- [docs/REFERENCE.md](https://github.com/Moonweave-Research/ref-verify/blob/main/docs/REFERENCE.md): every command, mode, error code, the cache, the limits, and worked examples.
- [AGENT_USAGE.md](https://github.com/Moonweave-Research/ref-verify/blob/main/AGENT_USAGE.md): the contract for agents calling the CLI.
- [SKILL.md](https://github.com/Moonweave-Research/ref-verify/blob/main/SKILL.md): the agent skill itself.
- [benchmarks/README.md](https://github.com/Moonweave-Research/ref-verify/blob/main/benchmarks/README.md): the test sets and how to rerun them.
- [CHANGELOG.md](https://github.com/Moonweave-Research/ref-verify/blob/main/CHANGELOG.md): what changed in each release.

---

## Contributing, license, and related projects

- Issues and pull requests are welcome. Run the tests with `PYTHONPATH=src python3 -m unittest discover -s tests` before sending a change.
- License: [MIT](https://github.com/Moonweave-Research/ref-verify/blob/main/LICENSE).
- Related: [decision-kernel](https://github.com/Moonweave-Systems/decision-kernel), evidence-gated decisions and drift and done checks for coding agents.
