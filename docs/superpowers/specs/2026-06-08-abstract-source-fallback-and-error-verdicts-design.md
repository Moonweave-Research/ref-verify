# Abstract Source Fallback and Error Verdicts Design

## Goal

Make `ref-verify check-claim` useful across more research domains by reducing false `UNVERIFIABLE` results caused by missing CrossRef abstracts, and by returning clearer machine-readable reasons when evidence cannot be checked.

This is the next practical layer after the numeric claim verifier. The numeric engine can only help when an abstract is available. In real use, the bigger bottleneck is often source coverage and vague failure reporting.

## Positioning

`ref-verify` remains a conservative abstract-grounded citation guard.

Fallback sources are allowed only to find an abstract for the same DOI. They must not broaden the tool into paper discovery, title search, semantic retrieval, full-text parsing, or claim inference.

## Current Problem

The current CLI fetches a CrossRef work and checks its abstract. This creates three practical gaps:

- Many valid DOIs do not expose an abstract through CrossRef.
- `UNVERIFIABLE` can mean multiple different things: no abstract, DOI mismatch, failed API call, missing record, or unsupported source behavior.
- Agents and downstream tools cannot reliably decide whether to retry, try another source, ask a human, or reject the citation.

## Non-Goals

- Do not use LLMs to infer paper meaning.
- Do not parse full text, tables, figures, supplements, or PDFs.
- Do not search by title or author in Phase 1.
- Do not accept an abstract unless it is tied to the requested DOI.
- Do not let fallback abstracts override CrossRef metadata verification.
- Do not add statistical metric support in this phase.

## Source Policy

CrossRef remains the primary metadata source. Fallback sources are abstract sources only.

Recommended source order:

1. CrossRef work by DOI.
2. Semantic Scholar paper lookup by DOI.
3. PubMed lookup by DOI, when the DOI maps cleanly to a PubMed record.

The implementation should verify exact API contracts against official documentation before coding. The design requirement is source behavior, not a fixed endpoint string.

## DOI Binding Rules

An abstract source can be used only if one of these is true:

- The returned record explicitly contains the normalized requested DOI.
- The source lookup was a DOI-only endpoint or DOI-only query and returns a single unambiguous record whose DOI matches after normalization.

If the returned source has no DOI, multiple records, or a DOI mismatch, the source attempt must be recorded but ignored for claim verification.

No title-based rescue is allowed in this phase because it risks attaching claims to the wrong paper.

## Data Model

Add a source-attempt structure that can be serialized in CLI JSON:

```text
AbstractSourceAttempt
- source: crossref | semantic_scholar | pubmed
- status: FOUND | NO_ABSTRACT | NOT_FOUND | DOI_MISMATCH | API_ERROR | TIMEOUT | UNSUPPORTED
- reason: short human-readable explanation
- record_id: optional source record identifier
- doi: optional normalized DOI returned by source
- elapsed_ms: optional timing field
```

Add an abstract lookup result:

```text
AbstractLookupResult
- record: PaperRecord
- abstract_source: crossref | semantic_scholar | pubmed | none
- attempts: list[AbstractSourceAttempt]
- error_code: optional final error code
```

`PaperRecord` may stay as the canonical claim-check input. If so, source metadata should be attached at the CLI/result layer rather than forcing every claim-check unit test to construct source attempts.

## Error Codes

Use explicit error codes in JSON output. These codes should be stable enough for agents to branch on.

```text
NO_ABSTRACT
DOI_NOT_FOUND
DOI_MISMATCH
SOURCE_API_ERROR
SOURCE_TIMEOUT
SOURCE_UNSUPPORTED
CLAIM_NOT_EXPLICIT
CLAIM_AMBIGUOUS
CLAIM_SUPPORTED
```

Mapping:

- `CLAIM_SUPPORTED` maps to `status=SUPPORTED`, `verdict=ACCEPT`, exit `0`.
- `CLAIM_AMBIGUOUS` maps to `status=PARTIAL`, `verdict=WARN`, non-zero exit.
- `CLAIM_NOT_EXPLICIT` maps to `status=PARTIAL`, `verdict=WARN`, non-zero exit.
- `NO_ABSTRACT`, `DOI_NOT_FOUND`, `DOI_MISMATCH`, API, timeout, and unsupported-source codes map to `status=UNVERIFIABLE`, `verdict=WARN`, non-zero exit.

Do not collapse source errors into `CLAIM_NOT_EXPLICIT`. A claim cannot be evaluated when no trusted abstract is available.

## CLI Behavior

`ref-verify check-claim <doi> --claim "<claim>" --json` should:

1. Normalize the requested DOI.
2. Fetch CrossRef metadata.
3. Use CrossRef abstract if available and DOI matches.
4. If CrossRef has no abstract, try fallback abstract sources in order.
5. Run the existing claim checker against the selected abstract.
6. Return JSON containing the selected `abstract_source`, all `source_attempts`, and the final `error_code`.

Human-readable output should stay short:

```text
WARN UNVERIFIABLE: no abstract found for DOI after CrossRef, Semantic Scholar, and PubMed attempts.
```

JSON output should include enough detail for an agent:

```json
{
  "status": "UNVERIFIABLE",
  "verdict": "WARN",
  "error_code": "NO_ABSTRACT",
  "abstract_source": null,
  "source_attempts": [
    {"source": "crossref", "status": "NO_ABSTRACT", "reason": "CrossRef record had no abstract."},
    {"source": "semantic_scholar", "status": "NO_ABSTRACT", "reason": "Record found, but no abstract was provided."},
    {"source": "pubmed", "status": "NOT_FOUND", "reason": "No PubMed record matched the DOI."}
  ]
}
```

## `verify-doi` Behavior

`verify-doi` should remain a CrossRef metadata check in this phase.

Fallback abstract sources must not make a bad title, author, year, or DOI match pass. If future versions expose fallback metadata, that must be designed separately with stricter provenance rules.

## Conservative Acceptance Rules

Fallback only changes whether an abstract is available. It must not weaken claim acceptance.

The same claim checker, numeric matcher, subject-binding rules, comparator rules, and ambiguity guards apply regardless of abstract source.

If two sources provide different abstracts, use the first DOI-bound source in the configured order and record later sources only if explicitly requested by a diagnostic option. Do not merge abstracts from multiple sources in this phase.

## Test Plan

Use fake source clients. Do not depend on live network in tests.

Required cases:

- CrossRef abstract exists: no fallback source is queried.
- CrossRef has metadata but no abstract, Semantic Scholar has DOI-bound abstract: claim check uses Semantic Scholar.
- CrossRef and Semantic Scholar have no abstract, PubMed has DOI-bound abstract: claim check uses PubMed.
- All sources lack abstracts: result is `UNVERIFIABLE` with `error_code=NO_ABSTRACT` and all attempts listed.
- A fallback source returns a different DOI: attempt is `DOI_MISMATCH`, source is ignored, and checking continues.
- A fallback source returns an API error: attempt is `API_ERROR`, checking continues to the next source.
- A fallback source times out: attempt is `TIMEOUT`, checking continues to the next source.
- A fallback abstract is available but claim is not explicit: result is claim-level `WARN`, not source-level `UNVERIFIABLE`.
- `verify-doi` output is unchanged except for any explicitly documented error-code field.

## Documentation Updates

Update README and README.ko to say:

- `check-claim` is DOI-only.
- CrossRef is primary.
- Fallback abstract sources can be used when CrossRef has no abstract.
- `ACCEPT` means explicit abstract support, not paper-level truth.
- `WARN` and `UNVERIFIABLE` are expected conservative outcomes, not necessarily tool failures.

Avoid product copy that implies paper understanding or source completeness.

## Implementation Shape

Recommended modules:

- `src/ref_verify/abstract_lookup.py`
  - orchestrates source order
  - returns `AbstractLookupResult`
- `src/ref_verify/sources.py`
  - source client protocols and source-attempt models
- `src/ref_verify/semantic_scholar.py`
  - DOI-bound abstract adapter
- `src/ref_verify/pubmed.py`
  - DOI-bound abstract adapter
- `src/ref_verify/cli.py`
  - wires fallback into `check-claim`

Keep `claim_check.py` focused on claim support. It should not know how abstracts are fetched.

## Rollout Strategy

Phase A: introduce data models and source attempt JSON for CrossRef only.

Phase B: add Semantic Scholar fallback with fake-client tests and one optional live smoke command documented for maintainers.

Phase C: add PubMed fallback after DOI binding behavior is verified.

Phase D: update README examples and skill instructions.

This staging keeps the CLI stable and avoids mixing fallback networking with claim-matching changes.

## Risks

- Fallback sources may return stale, truncated, or license-filtered abstracts.
- DOI matching can be inconsistent across sources.
- PubMed DOI mapping can be indirect for some biomedical records.
- More source attempts can make CLI latency worse.
- Detailed error codes can become a compatibility burden if named too casually.

Mitigation:

- DOI-only lookup.
- No abstract merging.
- Stable source-attempt records.
- Timeouts per source.
- Tests for source mismatch and source failure before positive fallback tests.

## Open Decisions

Resolved for the first implementation:

- Fallback is enabled by default for `check-claim`.
- `--source crossref|semantic-scholar|pubmed` is available for debugging source-specific behavior; explicit non-CrossRef source selection bypasses CrossRef.
- CI tests use fake clients and parser fixtures only; live smoke tests are excluded from CI.
- `UNVERIFIABLE` remains `verdict=WARN`; JSON `error_code` distinguishes source absence from weak evidence.

Still open:

- Whether to add a maintainer-only live smoke command later.
- Whether future versions should introduce a verdict separate from `WARN` for source absence.

## Revision Notes

Implemented decisions:

- Added a CrossRef-first abstract lookup layer with DOI-bound Semantic Scholar and PubMed fallback.
- Kept `verify-doi` as CrossRef metadata verification only.
- Added `abstract_source`, `source_attempts`, and `error_code` to `check-claim` JSON output.
- Added explicit source debugging that can isolate Semantic Scholar or PubMed when CrossRef is unavailable.
- Added fake-client flow tests and source parser tests without live network dependency.
