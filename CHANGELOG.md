# Changelog

All notable changes to `ref-verify` will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## Unreleased

### Added

- An end-to-end skill evaluation (`benchmarks/e2e/`): eight manuscripts (Markdown, LaTeX + BibTeX, Korean) with 40 planted errors and 65 correct references, a harness that runs each through an isolated `claude -p` session with and without the skill (no user hooks, plugins, or MCP servers), a stdlib scorer, and the 2026-10-09 results: 80/80 planted errors caught with the skill and 77/80 without, no false alarms in either, at about twice the time per run. It needs the network and a logged-in Claude Code, and is not run in CI.
- A browser page (`web/`) that runs `check-bib` on a pasted list or a `.bib`/`.ris`/`.txt` file with no server: the engine runs in Pyodide (pinned 314.0.7 from jsDelivr) inside a Web Worker and calls CrossRef and doi.org directly. It shows progress, the same verdict tables and legend as the HTML report, a Korean/English toggle, and downloads the same HTML report the CLI writes (in English). In Korean, the page shows each reason in Korean from a template table (`web/reasons.js`) with DOIs, years, and titles kept as written, and shows any reason it cannot translate in English marked "(원문)"; `tests/test_web_reasons.py` fails when the engine gains a `check-bib` reason without a Korean template. Nothing is cached or stored in the browser. `scripts/build_web.py` builds the site; `.github/workflows/pages.yml` deploys it once Pages is enabled and the `PAGES_ENABLED` repository variable is `true`.

### Changed

- `SKILL.md` gains a pre-submission sweep that runs the engine for both jobs: `check-bib` on the reference list (text output, or JSON saved to a file because it is too large for one tool result) and `check-file` on the numeric claims, copied exactly as the manuscript has them. Each claim is judged from the abstract sentence the engine returns, not from its label or from memory. Semantic Scholar becomes a last-resort manual source (OpenAlex is the second existence source), a rate limit is no evidence and never softens a verdict, and the answer leads with each problem, its evidence, and the fix, then a short list of items to look up by hand. On the v2 end-to-end set (`benchmarks/e2e/v2/`, condition A, two runs per manuscript), recall stays at 104/104 on Opus 5.5 and goes from 51/52 to 104/104 on Sonnet 5.5. No answer mentions a rate limit (before: 11/16 and 2/8). The engine output overflowed the tool-result limit in 1 of 64 runs (before: 11 of 24).
- README (EN/KO) rewritten for a first-time reader and for AI assistants: what it is and who it is for, a 30-second try on `examples/references.txt` (new; seven labelled references, real 1.3.1 output), how to read each verdict, including how often `UNVERIFIED` was a legitimate but unindexed reference in the test sets, three ways to use it, the scorecard, what is and is not checked, privacy and network use, and a section for AI agents. Commands, modes, error codes, the cache, scope, and examples moved to `docs/REFERENCE.md` and `docs/REFERENCE.ko.md`. The scorecard now reports held-out set v2 measured on 1.3.1; the retracted row of the chart names how many retractions CrossRef cannot mark.

### Fixed

- `check-bib` no longer attaches a reference without a DOI to a different CrossRef record that shares its title. Supplementary-information components are never taken as the cited work; replies, comments, and retraction or correction notices ("Retraction—<title>", "Authors' reply") join review reports as records about another work; when several records match, the one whose first author agrees wins over search order (a 1998 *Lancet* letter titled like Wakefield's paper no longer hides the retraction); a title that only mostly appears in the reference must come with an agreeing first author; a reference that reads as a book (publisher or edition, no journal volume and page) matches only book records, not journal reviews of the book; and a reference that says preprint prefers the preprint record.
- A Korean (or Chinese/Japanese) reference with a title is no longer treated as title-less: the title-less check counts Hangul words and CJK runs, not only Latin words, and leaves out a leading list of Hangul or Han author names. A Korean reference whose title disagrees with the Korean title CrossRef stores for its DOI is reported as naming another paper; before, it was explained as "The reference has no article title".

## [1.3.1] — 2026-10-08

### Changed

- `ref_verify.http` sends requests through a swappable backend (`set_backend`), so a browser build can supply its own transport. The default is still `urllib`; CLI requests, retries, `Retry-After`, and the cache are unchanged.

### Fixed

- `check-bib` judges citations that omit the article title (common in physics and chemistry: `A. Author et al., Phys. Rev. Lett. 98, 123456 (2007)`) on the evidence they carry: journal (full name or abbreviation), volume, first page or article number, year, and first author. With a DOI they pass when all agree, instead of a `MISMATCH` saying "the DOI may point to a different paper"; when they disagree the reason names each differing field. Without a DOI the CrossRef search result is accepted on the same agreement and the reference stays `UNVERIFIED` otherwise. A citation that does carry a title that does not match keeps the old behaviour.
- The first-author check reads only the first name in the author list, so a reference that lists a co-author first ("Perlmutter S, Riess AG" for a paper by Riess) no longer passes; initials-first names and particles ("A. G. Riess", "J. D. van der Waals", "Le Cunff, A.") still do. A group author ("Writing Group for the ... Investigators") that opens the reference is matched as a whole.
- `verify-doi`, `check-claim`, and `check-file` no longer report DataCite (arXiv, Zenodo), KISTI, or JaLC DOIs as dead. When CrossRef has no record they ask doi.org for the registration agency, as `check-bib` does: `verify-doi` returns `verdict: WARN`, `status: UNVERIFIED`, `error_code: DOI_NOT_IN_CROSSREF`; `check-claim` looks for the abstract in OpenAlex, Semantic Scholar, and PubMed and judges the claim if one has it, otherwise returns `UNVERIFIABLE` with `DOI_NOT_IN_CROSSREF`. A DOI doi.org does not know is still `REJECT` / `DOI_NOT_FOUND`.
- Semantic Scholar looks up an arXiv DOI (`10.48550/arXiv.<id>`) by its arXiv identifier, which it resolves while the DOI itself returns 404, and binds the record to that DOI only when the arXiv identifiers match.
- A title-less citation without a DOI that CrossRef's plain search ranks out of reach (`A. G. Riess et al., Astron. J. 116, 1009 (1998).`: the paper is not in the top 20) gets a second search, sent only when the reference looks title-less (at most five non-author words before a volume and a page number) and carries a year, by first author (`query.author`), the rest of the citation without the bare year, and a publication-date filter for the cited year and the year before. It is accepted only on the same journal/volume/page/year/first-author agreement, so the reference otherwise stays `UNVERIFIED`. A title-less match to a retracted paper is now reported as `PAPER_RETRACTED` instead of `PASS`.

## [1.3.0] — 2026-10-08

### Added

- On-disk HTTP response cache (default 7 days; HTTP 404 kept for 1 day) shared by the CrossRef, OpenAlex, Semantic Scholar, and PubMed clients. Location: `REF_VERIFY_CACHE_DIR`, else `$XDG_CACHE_HOME/ref-verify`, else `~/.cache/ref-verify`. Disable with `--no-cache` or `REF_VERIFY_NO_CACHE=1`; set the lifetime with `REF_VERIFY_CACHE_TTL_DAYS`.
- `check-file --workers N` (default 4) checks rows in parallel; output keeps input order, and CrossRef and Semantic Scholar requests stay one at a time because both public APIs answer parallel requests with 429.
- `check-file` shows a `Checking claims: N/M` counter on stderr while it runs, only when stderr is a terminal and `--json` is not set, so JSON and piped output are unchanged.
- Ctrl-C stops a run at once with a one-line `Interrupted.` message and exit code 130 instead of a Python traceback; queued rows are not checked.
- `ref-verify check-bib <path>` checks a BibTeX, RIS, or plain-text/Markdown reference list. References with a DOI are compared with CrossRef metadata; references without one are looked up with CrossRef bibliographic search (`REFERENCE_RESOLVED` with `resolved_doi`, or `REFERENCE_UNMATCHED` / `UNVERIFIED` when nothing matches). Set `REF_VERIFY_MAILTO` to identify yourself to CrossRef search.
- README (EN/KO) "Check a whole reference list" section near the top: preparing a `.bib` or pasted `.txt` list, installing from PyPI, expected run time, and what each verdict means and asks you to do, including that a made-up reference without a DOI can only show as `UNVERIFIED`.
- `check-bib` terminal output starts with a count line whose numbers add up (`19 references: 11 PASS, 2 WARN, 5 REJECT, 1 UNVERIFIED`), shows `UNVERIFIED` apart from `WARN` like the report, names pasted references by their opening words instead of `ref-7`, prints the reason under each non-`PASS` row only, fits a 100-column terminal (Hangul counted as double width), and ends with a plain-language legend. `--json` is unchanged.
- `check-bib` input errors say what to do next: Word/PDF/HWP files, folders, empty lists, and non-UTF-8 files get a specific message (CP949 text from Korean Windows Notepad is read), and a reference not checked because of HTTP 429 or a network failure says to rerun or check the connection.
- `check-bib` matching (and `verify-doi`, which shares the comparison) accepts the print or online-first year, a title with or without its subtitle, CrossRef's original-language title, Hangul first-author names against romanized ones, and editors for edited books; CrossRef records in `--json` gain `alt_titles` and `alt_years`; CrossRef title markup (`<sub>`, escaped `&lt;title&gt;`) is stripped before comparing. In a live run these had made real references fail: 4 REJECTs in a 36-entry Zotero export and both Korean `.bib` entries with correct DOIs.
- `check-bib` asks doi.org for the registration agency when CrossRef has no record, and reports DataCite (arXiv, Zenodo), KISTI, or JaLC DOIs as `DOI_NOT_IN_CROSSREF` / `UNVERIFIED` instead of a dead-DOI `REJECT`.
- `check-bib` reasons name what differs and the values (`the year differs (reference: 2009; CrossRef: 2010)`), and a plain-text reference whose DOI belongs to a paper it never mentions is shown as `MISMATCH` with that paper's title rather than "not enough text to confirm".
- CrossRef searches are spaced one second apart and all CrossRef calls take turns (three at a time with `REF_VERIFY_MAILTO`), and `check-bib` shows `Checking references: N/M` on a terminal.
- `--report <path.html|path.md>` on `check-bib` and `check-file` writes a self-contained HTML (inline CSS, no scripts, only `doi.org` links) or Markdown verdict report: counts per verdict that add up to the total, a plain-language legend of what each verdict asks the reader to do, a "Needs a look" table of every non-passing row ahead of a "Passed" table, a colour per verdict, reasons, and evidence. Any other extension, or a folder that does not exist, is rejected before lookups start.
- A labelled reference benchmark (`benchmarks/references-holdout-v1.jsonl`, a held-out set frozen before any run, and `benchmarks/references-v1.jsonl`, the development set used while fixing the tool: real, fabricated, retracted, and CrossRef-unindexed references), a stdlib runner (`scripts/benchmark_references.py`) that checks it against live CrossRef with and without the HTTP cache, and a scorecard chart (`scripts/render_scorecard.py`) shown near the top of both READMEs. The benchmark needs the network and is not run in CI.

### Changed

- All four API clients now share one HTTP layer that retries 429 and 5xx responses up to 3 times with exponential backoff (capped at 10 s) and honours `Retry-After` up to 10 s. Previously only Semantic Scholar retried, once, on 429. Error codes are unchanged.
- `SemanticScholarClient` no longer takes `retry_delay`; its `max_retries` default is now 3.

### Fixed

- `check-bib` no longer rejects or flags legitimate references found by the labelled reference benchmark (128 items): a Wiley SICI DOI with `<...>` is read whole instead of being cut at `<` (was a dead-DOI `REJECT`); a citation that drops CrossRef's `- Subtitle` or `, Second Edition` matches (was `REJECT`); in plain text the publication year is the one followed by punctuation (`2020;395`), not a year inside the title (`2019 novel coronavirus`); search results that are peer-review reports, Faculty Opinions recommendations, or addenda/corrections of a paper are skipped and five results are read instead of three.
- BibTeX TeX math becomes plain text (`amyloid-$\beta$` → `amyloid-β`, `$\mu$m` → `μm`) instead of an empty `$$`, so the retracted Lesné 2006 paper cited without a DOI is found and rejected as retracted.
- A reference whose CrossRef lookup still hits HTTP 429 after the HTTP layer's retries is checked once more after the requested pause (`Retry-After`, at most 60 s; 15 s when none is given) before it is reported as not checked.
- A CrossRef record whose first date field is `[[null]]` no longer fails the lookup; the year is read from the next date field.

## [1.2.2] — 2026-10-01

### Fixed

- A citation that itself carries the publisher's "RETRACTED:" title prefix is no longer reported as a title mismatch on top of the retraction (`mismatches: ["retracted"]`, not `["title", "retracted"]`).

## [1.2.1] — 2026-10-01 (GitHub release only; not published to PyPI)

### Changed

- `SKILL.md` now runs the engine bundled with the skill by absolute path (`$SKILL_DIR/src`). Agents that installed the skill with `npx skills add` previously could not run the CLI at all: the console script is not installed, and the relative `PYTHONPATH=src` fallback only worked from inside the skill folder. `uvx --from 'ref-verify>=1.2.1'` is the third option.
- README documents `uvx ref-verify` and `pipx install ref-verify`.

### Fixed

- `verify-doi` and `check-claim` now return `REJECT` for a DOI that CrossRef records as retracted (read from `updated-by`), and a `RETRACTED:` title prefix no longer masquerades as a title mismatch.
- Numeric claims: evidence bounded from one side ("below 50 MPa", "at most 100 MV/m") no longer supports a claim bounded from the other side.
- Numeric claims: `mV`/`MV`, `mA`/`MA`, `mPa`/`MPa` and similar prefixes are no longer treated as the same unit; an all-lowercase unit stays ambiguous.
- A dead DOI (CrossRef 404) now yields a JSON payload with `verdict: REJECT` and `error_code: DOI_NOT_FOUND` instead of a bare error.

## [1.2.0] — 2026-06-08

### Added

- Added `ref-verify check-file` for JSONL and CSV DOI/claim batch checks.
- Added fixture-backed numeric claim eval coverage for repeated-use workflows.
- Added DOI-bound OpenAlex abstract fallback before Semantic Scholar and PubMed.
- Added a CLI regression corpus and manual Live Smoke ship gate for release-readiness checks.
- Added English and Korean scope guidance that explains what the tool verifies, what it does not verify, and how to interpret non-`ACCEPT` verdicts.

### Fixed

- Fixed composite scientific units such as `MV/m` being misread as numerator-only units.
- Added numeric claim support for common physical-science units such as `eV`, `Ω·cm`, `S/m`, and `MPa`.
- Treated `estimated to be <value>` as a reported numeric value while keeping predictive `estimated to exceed` frames conservative.
- Prevented comparative evidence such as `>220 °C` from accepting an exact `220 °C` claim.
- Allowed physical measurement conditions such as `1.7 eV in the temperature range` and `5 S/m at 1 kHz` without relaxing count-claim scope guards.
- Separated Semantic Scholar `429` rate limits into `SOURCE_RATE_LIMITED` and retried once before marking the source unavailable.
- Clarified that `npx skills add` installs the agent skill but does not pip-install the Python CLI.
- Fixed comma-clause splitting so current-study result sentences can bind a number to a subject across descriptive commas when no same-unit competing value is present.
- Recognized claim-side `up to <value>` comparators for percentage and unit/count claims while keeping exact-claim guards conservative.
- Treated temperature measurements followed by physical range/field conditions as measurement context, and allowed generic `Measurements...` sentences to inherit subject context from the immediately preceding sentence.

## [1.1.2] — 2026-06-08

### Changed

- Added release automation guardrails for CI, wheel smoke testing, manual live API smoke checks, and PyPI trusted publishing.
- Updated GitHub Actions workflows to current Node runtime-compatible action versions.

## [1.1.1] — 2026-06-08

### Changed

- Updated Python packaging metadata to the current SPDX license format.
- Clarified that zero runtime dependencies means zero third-party Python packages; CLI verification still requires outbound HTTPS access to public academic APIs.
- Clarified that the Python package is the CLI engine only. Install the agent skill from GitHub with `npx skills add`.

## [1.1.0] — 2026-06-07

### Added

- Python package scaffold with zero third-party Python runtime dependencies.
- `ref-verify verify-doi` CLI for CrossRef-backed DOI metadata checks.
- `ref-verify check-claim` CLI for abstract-grounded claim support checks.
- Machine-readable JSON output for downstream manuscript preflight, MCP, and Zotero integrations.
- Offline unit tests for DOI metadata comparison, CrossRef parsing, claim support verdicts, and CLI output.

### Changed

- Documented the executable engine path alongside the existing agent skill workflow.
- Updated the skill instructions to prefer the CLI when it is installed, while keeping the manual verification protocol as fallback.

## [1.0.0] — 2026-06-01

### Added

- **5-layer verification protocol**: Existence → Metadata → Content Traceability → DOI Resolution → Retraction Check
- **Two-mode design**: Quick Screen (seconds per paper, for DOI spot-checks) and Full Audit (abstract fetch + claim verification, for search tasks and pre-submission review)
- **Content traceability rule**: every content statement must come from a live-fetched abstract quoted verbatim — never from training data recall
- **Open-access fallback chain**: CrossRef JSON → Semantic Scholar → Unpaywall → arXiv → PubMed, in order
- **Near-miss detection**: evaluates whether the abstract supports the *specific claim* being cited, not just whether the paper exists
- **Automatic mode selection**: decision tree based on task type (search vs. spot-check vs. audit)
- **Structured verdicts**: ACCEPT / WARN / REJECT with explicit per-layer evidence
- Trigger description optimized for Claude Code, Cursor, and Codex auto-detection
- Evaluation suite: 3 test cases with real-world hallucination examples from materials science literature

### Verified catches

- Content hallucination: AI described paper content not present in the CrossRef abstract (Nemat-Nasser 2002)
- Wrong DOI: citation resolved to different paper, different authors, wrong year (Carpi 2011)
- Near-miss: "500% strain" in abstract was a measurement condition, not an actuation result (Kofod 2003)
