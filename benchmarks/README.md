# Reference-checking benchmark

A small, labelled set of references for measuring how `ref-verify check-bib` judges
real, fabricated, retracted, and unindexed references against live CrossRef. The
README scorecard is generated from the newest file in [`results/`](results/).

## Files

- `references-v1.jsonl`: the labelled set, one reference per line.
- `results/<YYYY-MM-DD>-<short sha>.json`: one benchmark run: tool version, commit,
  dataset hash, per-item verdicts and timings, and the aggregates the README quotes.
- `../scripts/benchmark_references.py`: runs the set (standard library only).
- `../scripts/render_scorecard.py`: draws `.github/assets/scorecard-{light,dark}.svg`
  from a results file.

## Item fields

| Field | Meaning |
|---|---|
| `id` | Stable item id (`real-NN`, `fab-<type>-NN`, `retracted-NN`, `notincr-NN`). |
| `category` | `REAL`, `FABRICATED`, `RETRACTED`, or `NOT_IN_CROSSREF`. |
| `subtype` | Citation style for real and retracted items (`bib_doi`, `apa_nodoi`, `vancouver_doi`, `ris`, ...); hallucination type for fabricated items; kind of source for unindexed items. |
| `expected` | `PASS`, `FLAG` (anything except a clean PASS), `REJECT` (`PAPER_RETRACTED`), or `NOT_REJECT`. |
| `input_format` | `bib`, `ris`, or `txt`: the file type the item is checked in. |
| `reference` | The reference exactly as a user would paste it. Metadata only, no abstracts. |
| `notes` | What makes the item interesting (markup in the CrossRef title, LaTeX accents, swapped DOI, ...). |
| `source` | Where the item comes from: the DOI, a public page, or a published report. |
| `verified` | How the label was checked, and when. |
| `truth_doi` | The DOI of the real work, when there is one. |
| `field` | Research field of a real paper. |
| `crossref_marks_retraction` | Retracted items only: whether CrossRef carries an `updated-by` retraction notice. |

## Categories and how each is scored

| Category | What it is | Counted as correct when |
|---|---|---|
| `REAL` | Papers confirmed in CrossRef across materials science, chemistry, physics, biomedicine, machine learning, social science, and Korean journals, written in BibTeX (with and without DOI), APA, Vancouver, and RIS. | the verdict is `PASS`. `WARN` is reported as "needs a manual check", `REJECT` as "called wrong". |
| `FABRICATED` | References that do not exist, built the way language models get them wrong: (a) invented DOI on a plausible title with real authors and journal, (b) plausible title without DOI, (c) a real DOI attached to another paper's title and authors, (d) a real title with the wrong first author or a year off by three or more, (e) hallucinated references reported publicly. | the verdict is anything except `PASS`. |
| `RETRACTED` | Well-known retracted papers (Wakefield 1998, the STAP papers, Hwang, Schön, Surgisphere, Dias, ...), cited without the "RETRACTED" prefix. | the error code is `PAPER_RETRACTED`. Only items whose CrossRef record carries a retraction notice count; any others are reported separately as a data limitation. |
| `NOT_IN_CROSSREF` | Legitimate references CrossRef does not index: NeurIPS/ICLR papers, arXiv preprints (one with a DataCite DOI), JMLR papers, textbooks, a technical report, Korean theses (two with KISTI DOIs), and KCI papers without DOIs. | the verdict is not `REJECT`. `WARN`/`UNVERIFIED` is the honest answer here. |

Rates come with 95% Wilson score intervals; with n between 9 and 65 per category the
intervals are wide, and the README prints them next to every rate.

A row the tool could not check at all (`ROW_CHECK_ERROR`, for example a CrossRef 429
that outlasts the retry budget) says nothing about its judgement. The runner re-checks
such rows once, alone, after a 15-second pause, lists them under
`first_attempt_infra_errors`, and leaves any row that still fails out of every rate
(`aggregates.infra_errors`).

## How items were verified

- Real and retracted items: each DOI was fetched from the CrossRef REST API on the
  date in `verified`; the reference text was written from that record and then
  restyled the way people write citations (initials, abbreviated journals, sentence
  case, LaTeX accents, PubMed-style titles, a dropped subtitle).
- Invented DOIs: each returned HTTP 404 from CrossRef on the date in `verified`.
- Fabricated titles without a DOI: a CrossRef bibliographic search returned no record
  with that title.
- Unindexed items: the source URL resolves to the work, and a CrossRef bibliographic
  search did not return it as a work with a matching title and year.
- Publicly reported hallucinations (GPTZero's NeurIPS 2025 and ICLR 2026
  investigations, the May 2025 MAHA report, a 2024 expert declaration in Kohls v.
  Ellison): the exact reference string is copied from the page linked in `source`.

## Rerun

The benchmark makes live requests, so it is not part of CI.

```bash
python3 scripts/benchmark_references.py           # writes benchmarks/results/<date>-<sha>.json
python3 scripts/render_scorecard.py benchmarks/results/<date>-<sha>.json
```

The runner checks every item twice with the same settings as `check-bib` (default 4
workers, CrossRef calls taking turns and searches spaced one second apart): once with an
empty HTTP cache in a temporary directory, then again from that cache, and reports both
wall times. A cold run sends about one request per reference (roughly 155 for this set,
counting the doi.org lookups for DOIs CrossRef lacks); the cached run sends none. It does not set
`REF_VERIFY_MAILTO`; set it yourself to use CrossRef's polite pool.

Live CrossRef data changes (new records, new retraction notices, edited titles), so a
rerun on the same commit can differ slightly from a stored result.

## What this does not measure

- Performance on references the checker was not tuned on. Fixes for misses this set
  exposed (#27) were developed against it, so the stored results are in-sample; a new,
  held-out set is the honest next measurement.

- Whether a paper supports a claim (`check-claim`); only reference existence and
  metadata are scored here.
- Non-English literature beyond a handful of Korean items (journal papers, theses, and
  one paper cited by its Korean title).
- Full text, page numbers, volume/issue, or journal names: `check-bib` compares title,
  first author, year, and DOI.
- How often each failure appears in real reference lists; the mix of items here is
  chosen to cover cases, not to match any real-world frequency.
