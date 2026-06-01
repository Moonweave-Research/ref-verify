# Changelog

All notable changes to `ref-verify` will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

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
