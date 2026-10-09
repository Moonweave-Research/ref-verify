# Reference-checking benchmark

Two labelled sets of references for measuring how `ref-verify check-bib` judges real,
fabricated, retracted, and unindexed references against live CrossRef.

| Set | Items | Role |
|---|---|---|
| `references-regress-v3.jsonl` | 23 | **Regression set for the search-path and Hangul-title fixes.** Not a held-out score: it holds the failure cases found by the E2E evaluation (#37) and holdout-v2 (a same-title letter or review taken for the paper, an SI component taken for the paper, a book matched to a journal review of it, a Korean reference with a title read as title-less) and close-call controls where the cited record really is a letter, a review, a book, or a preprint. Frozen before the before/after runs. |
| `references-holdout-v2.jsonl` | 99 | **Held-out set v2.** Written and committed before any run, after #30 and #33 were tuned on holdout-v1's misses. It shares no paper (DOI or title) with the other two sets and stresses title-less physics/chemistry citations (13 real, 8 fabricated), group authors, particle surnames, Korean-titled Korean journal papers with Hangul authors, books, conference papers, retractions marked in CrossRef only through Retraction Watch data, and retractions CrossRef cannot mark (KISTI, ISTIC, and DataCite DOIs). Measured once, on 1.3.1; the README scorecard is not yet switched to it. |
| `references-holdout-v1.jsonl` | 86 | **Held-out set v1, now in-sample:** its misses were used to tune #30 and #33. Originally written and committed before the tool was run on it; no paper in it appears in the development set, and it uses other journals, fields, and citation styles (IEEE, Nature, Harvard, Chicago, biblatex, and physics/chemistry styles that omit the article title). The README headline numbers and chart come from this set. |
| `references-v1.jsonl` | 142 | **Development set (used while fixing the tool).** Its misses drove the matching fixes in #27, so its scores are in-sample and are shown only as a secondary line. |

Rules for the held-out set: it is frozen at the commit that added it, and items are
not changed after seeing results, except to correct a gold label that was factually
wrong; every such correction is logged under [Label corrections](#label-corrections)
with its reason. A new held-out set (`references-holdout-v2.jsonl`) is the way to
measure again after the tool is tuned against v1's misses.

## Files

- `references-holdout-v2.jsonl`, `references-holdout-v1.jsonl`, `references-v1.jsonl`: the labelled sets, one reference per line. Holdout-v2 items also carry `style` (citation format, for per-format breakdowns) and `titleless: true` on fabricated citations that omit the article title.
- `results/<YYYY-MM-DD>-<short sha>-<set>.json`: one benchmark run of one set: tool
  version, commit, dataset hash, per-item verdicts and timings, and the aggregates the
  README quotes. Two earlier development-set runs keep the old
  naming: `2026-10-08-34da678.json` (before #27) and `2026-10-08-7910447.json` (after #27,
  before the held-out set existed).
- `../scripts/benchmark_references.py`: runs a set (standard library only).
- `../scripts/render_scorecard.py`: draws `.github/assets/scorecard-{light,dark}.svg`
  from a held-out results file, with the development-set result as a footnote.

## Holdout-v2 measurement (2026-10-09, ref-verify 1.3.1)

All three sets were run once on commit `8170e66` (main `6a13a86` plus the frozen set), each
on a fresh cache without `REF_VERIFY_MAILTO`. Only holdout-v2 is out of sample.

| Set | Real PASS | Real REJECT | Fabricated flagged | Retracted caught* | Unindexed REJECT |
|---|---|---|---|---|---|
| holdout-v2 (out of sample) | 40/45 (77–95%) | 0/45 (0–8%) | 29/29 (88–100%) | 8/8 (68–100%) | 0/13 (0–23%) |
| holdout-v1 (in-sample) | 40/40 (91–100%) | 0/40 (0–9%) | 26/26 (87–100%) | 10/10 (72–100%) | 0/10 (0–28%) |
| v1 (in-sample) | 66/66 (95–100%) | 0/66 (0–6%) | 43/43 (92–100%) | 16/16 (81–100%) | 1/17 (1–27%) |

Parentheses are 95% Wilson intervals. *Retractions CrossRef marks; holdout-v2 also has four
retractions Retraction Watch lists that CrossRef cannot mark (KISTI, ISTIC, and DataCite DOIs,
and a FASEB abstract DOI aliased to its withdrawal notice), reported separately: none of the
four got `PAPER_RETRACTED`. Per-item results:
`results/2026-10-09-8170e66-{holdout-v2,holdout-v1,v1}.json`.

## Item fields

| Field | Meaning |
|---|---|
| `id` | Stable item id (`real-NN`, `fab-<type>-NN`, `retracted-NN`, `notincr-NN`; held-out ids start with `h-`). |
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
python3 scripts/benchmark_references.py --dataset benchmarks/references-holdout-v1.jsonl
python3 scripts/benchmark_references.py --dataset benchmarks/references-v1.jsonl
python3 scripts/render_scorecard.py benchmarks/results/<date>-<sha>-holdout-v1.json \
  --dev benchmarks/results/<date>-<sha>-v1.json
```

The runner checks every item twice with the same settings as `check-bib` (default 4
workers, CrossRef calls taking turns and searches spaced one second apart): once with an
empty HTTP cache in a temporary directory, then again from that cache, and reports both
wall times. A cold run sends about one request per reference (plus a doi.org lookup for each
DOI CrossRef lacks); the cached run sends none. It does not set
`REF_VERIFY_MAILTO`; set it yourself to use CrossRef's polite pool.

Live CrossRef data changes (new records, new retraction notices, edited titles), so a
rerun on the same commit can differ slightly from a stored result.

## Label corrections

None so far for `references-holdout-v1.jsonl`, `references-holdout-v2.jsonl`, or `references-regress-v3.jsonl`.

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
