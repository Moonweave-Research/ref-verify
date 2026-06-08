# Numeric Claim Verifier Design

## Goal

Expand `ref-verify` into a general-purpose research numeric claim verifier while keeping it a conservative citation guard.

## Positioning

`ref-verify` is not a tool that semantically understands papers. It helps AI agents check whether an abstract contains explicit numeric evidence before attaching a citation.

## Core Principles

- Do not add LLM semantic inference.
- Do not parse full text, tables, or figures.
- Check only numbers, units, and comparator language explicitly present in the abstract.
- Return `ACCEPT` only when the subject, numeric value, unit, and comparator clearly match.
- Return `PARTIAL`/`WARN` when a number is present but subject binding or context is ambiguous.
- Return `UNVERIFIABLE` when no abstract evidence is available.

## Phase 1 Scope

Phase 1 covers common numeric claims used across research fields:

- Percent claims, such as `95%`, `above 90%`, and `below 10%`.
- Simple unit and count claims, such as `5000 cycles`, `12 patients`, `3.2 V`, `37 °C`, and `10 mg/mL`.
- Basic comparators: `>`, `>=`, `<`, `<=`, `at least`, `more than`, `below`, and `up to`.
- Subject binding in the same sentence or clause.
- Conservative handling when a sentence mixes multiple subjects or numbers.

## Deferred Scope

Phase 2 will handle statistical metrics that require tighter contextual binding:

- `p < 0.05`
- `AUC` / `AUROC`
- `F1 score`
- `hazard ratio`
- `odds ratio`
- `95% CI`

## Architecture

Create `src/ref_verify/numeric_claim.py` for numeric extraction and matching. It should extract numeric claims from user claims, extract numeric evidence from abstract clauses, compare values through comparator entailment, and require subject terms to match in the same clause before accepting.

Keep `src/ref_verify/claim_check.py` as the verdict router. It should call the numeric engine first, preserve existing actuation-strain near-miss guards, and retain the literal text-claim fallback.

Add `tests/test_numeric_claim.py` for focused numeric behavior across materials, biomedicine, ML, and general science examples. Keep false-accept tests at least as prominent as positive tests.

## Verdict Criteria

`ACCEPT`: subject plus number/unit/comparator clearly match abstract evidence.

`PARTIAL`/`WARN`: a number exists, but subject binding is ambiguous, the wrong subject has the supporting value, multiple numbers create mismatch risk, or semantic paraphrase would be needed.

`UNVERIFIABLE`: no abstract is available or evidence cannot be checked.

## Product Copy

`ref-verify` is not a tool that "understands" papers. It is a conservative citation guard that makes AI agents verify whether an abstract actually contains explicit numeric evidence before citing a paper.
