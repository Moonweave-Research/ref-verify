# Changelog

All notable changes to `ref-verify` will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## Unreleased

### Added

- Added `ref-verify check-file` for JSONL and CSV DOI/claim batch checks.
- Added fixture-backed numeric claim eval coverage for repeated-use workflows.
- Added DOI-bound OpenAlex abstract fallback before Semantic Scholar and PubMed.

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
