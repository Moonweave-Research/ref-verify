# Changelog

All notable changes to `ref-verify` will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## Unreleased

### Added

- On-disk HTTP response cache (default 7 days; HTTP 404 kept for 1 day) shared by the CrossRef, OpenAlex, Semantic Scholar, and PubMed clients. Location: `REF_VERIFY_CACHE_DIR`, else `$XDG_CACHE_HOME/ref-verify`, else `~/.cache/ref-verify`. Disable with `--no-cache` or `REF_VERIFY_NO_CACHE=1`; set the lifetime with `REF_VERIFY_CACHE_TTL_DAYS`.
- `check-file --workers N` (default 4) checks rows in parallel; output keeps input order, and CrossRef and Semantic Scholar requests stay one at a time because both public APIs answer parallel requests with 429.
- `check-file` shows a `Checking claims: N/M` counter on stderr while it runs, only when stderr is a terminal and `--json` is not set, so JSON and piped output are unchanged.
- Ctrl-C stops a run at once with a one-line `Interrupted.` message and exit code 130 instead of a Python traceback; queued rows are not checked.
- `ref-verify check-bib <path>` checks a BibTeX, RIS, or plain-text/Markdown reference list. References with a DOI are compared with CrossRef metadata; references without one are looked up with CrossRef bibliographic search (`REFERENCE_RESOLVED` with `resolved_doi`, or `REFERENCE_UNMATCHED` / `UNVERIFIED` when nothing matches). Set `REF_VERIFY_MAILTO` to identify yourself to CrossRef search.
- README (EN/KO) "Check a whole reference list" section near the top: preparing a `.bib` or pasted `.txt` list, installing from GitHub while PyPI 1.2.2 lacks `check-bib`, expected run time, and what each verdict means and asks you to do, including that a made-up reference without a DOI can only show as `UNVERIFIED`.
- `check-bib` terminal output starts with a count line whose numbers add up (`19 references: 11 PASS, 2 WARN, 5 REJECT, 1 UNVERIFIED`), shows `UNVERIFIED` apart from `WARN` like the report, names pasted references by their opening words instead of `ref-7`, prints the reason under each non-`PASS` row only, fits a 100-column terminal (Hangul counted as double width), and ends with a plain-language legend. `--json` is unchanged.
- `check-bib` input errors say what to do next: Word/PDF/HWP files, folders, empty lists, and non-UTF-8 files get a specific message (CP949 text from Korean Windows Notepad is read), and a reference not checked because of HTTP 429 or a network failure says to rerun or check the connection.
- `check-bib` matching (and `verify-doi`, which shares the comparison) accepts the print or online-first year, a title with or without its subtitle, CrossRef's original-language title, Hangul first-author names against romanized ones, and editors for edited books; CrossRef records in `--json` gain `alt_titles` and `alt_years`; CrossRef title markup (`<sub>`, escaped `&lt;title&gt;`) is stripped before comparing. In a live run these had made real references fail: 4 REJECTs in a 36-entry Zotero export and both Korean `.bib` entries with correct DOIs.
- `check-bib` asks doi.org for the registration agency when CrossRef has no record, and reports DataCite (arXiv, Zenodo), KISTI, or JaLC DOIs as `DOI_NOT_IN_CROSSREF` / `UNVERIFIED` instead of a dead-DOI `REJECT`.
- `check-bib` reasons name what differs and the values (`the year differs (reference: 2009; CrossRef: 2010)`), and a plain-text reference whose DOI belongs to a paper it never mentions is shown as `MISMATCH` with that paper's title rather than "not enough text to confirm".
- CrossRef searches are spaced one second apart and all CrossRef calls take turns (three at a time with `REF_VERIFY_MAILTO`), and `check-bib` shows `Checking references: N/M` on a terminal.
- `--report <path.html|path.md>` on `check-bib` and `check-file` writes a self-contained HTML (inline CSS, no scripts, only `doi.org` links) or Markdown verdict report: counts per verdict that add up to the total, a plain-language legend of what each verdict asks the reader to do, a "Needs a look" table of every non-passing row ahead of a "Passed" table, a colour per verdict, reasons, and evidence. Any other extension, or a folder that does not exist, is rejected before lookups start.

### Changed

- All four API clients now share one HTTP layer that retries 429 and 5xx responses up to 3 times with exponential backoff (capped at 10 s) and honours `Retry-After` up to 10 s. Previously only Semantic Scholar retried, once, on 429. Error codes are unchanged.
- `SemanticScholarClient` no longer takes `retry_delay`; its `max_retries` default is now 3.

### Fixed

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
