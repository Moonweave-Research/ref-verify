# Agent Usage Contract

This document defines how an AI agent should call `ref-verify` when checking citation claims.

`ref-verify` is a verifier, not a claim extractor. The agent is responsible for extracting DOI-bound numeric claim candidates from the draft, chat session, markdown file, or other working context. `ref-verify` then checks those candidates against DOI-bound abstracts.

## When To Use

Use `ref-verify` when a citation includes:

- a DOI, and
- a numeric claim about that DOI's paper.

Examples:

- `This paper reports 95% accuracy.`
- `The study included 12 patients.`
- `The device survived 5000 cycles.`
- `Samples were incubated at 37 °C.`

Do not use `ref-verify` to judge paper quality, field consensus, full-text claims, table values, figure values, or complex statistical interpretation.

## Agent Workflow

1. Extract candidate `{doi, claim}` pairs from the working context.
2. Keep only claims that contain explicit numeric evidence candidates.
3. Write a JSONL file with one object per candidate.
4. Run:

```bash
ref-verify check-file claims.jsonl --json
```

5. Treat only `verdict == "ACCEPT"` as verified.
6. Treat every other result as not verified for citation support.
7. Do not rewrite `WARN`, `PARTIAL`, `REJECT`, `UNVERIFIABLE`, or `failed > 0` into acceptance.

## Input Contract

Preferred agent input is JSONL:

```jsonl
{"id":"claim-1","doi":"10.xxxx/example-a","claim":"This paper reports 95% accuracy."}
{"id":"claim-2","doi":"10.xxxx/example-b","claim":"The study included 12 patients.","note":"draft paragraph 4"}
```

Required fields:

- `doi`
- `claim`

Optional fields:

- `id`: stable identifier for mapping results back to the draft.
- `source`: one of `auto`, `crossref`, `openalex`, `semantic-scholar`, or `pubmed`.
- `note`: any caller context. It is preserved in JSON output.

CSV is supported for user-created files, but agents should prefer JSONL because it avoids CSV quoting ambiguity.

## Exit Code Contract

- Exit `0`: command completed and every row was `ACCEPT`.
- Exit `2`: command completed, but one or more rows were not accepted.
- Exit `1`: input or runtime failure prevented normal batch processing.

Agents must inspect JSON output even when the exit code is non-zero. Exit `2` can still contain useful row-level results.

## JSON Output Contract

`check-file --json` returns:

```json
{
  "summary": {
    "total": 2,
    "accept": 1,
    "warn": 1,
    "reject": 0,
    "partial": 0,
    "unverifiable": 1,
    "failed": 1
  },
  "results": [
    {
      "row_number": 1,
      "id": "claim-1",
      "doi": "10.xxxx/example-a",
      "claim": "This paper reports 95% accuracy.",
      "verdict": "ACCEPT",
      "status": "SUPPORTED",
      "reason": "...",
      "evidence": "...",
      "abstract_source": "crossref",
      "source_attempts": [],
      "error_code": "CLAIM_SUPPORTED"
    },
    {
      "row_number": 2,
      "id": "claim-2",
      "doi": "10.xxxx/example-b",
      "claim": "The study included 12 patients.",
      "verdict": "WARN",
      "status": "UNVERIFIABLE",
      "reason": "Row could not be checked: ...",
      "evidence": "",
      "abstract_source": null,
      "source_attempts": [],
      "error_code": "ROW_CHECK_ERROR"
    }
  ]
}
```

Summary categories are diagnostic counts, not mutually exclusive buckets. For
example, a failed row can also be `WARN` and `UNVERIFIABLE`.

Agents should route results by `error_code`, `verdict`, and `status`.

Common routing:

- `CLAIM_SUPPORTED`: verified citation claim.
- `CLAIM_AMBIGUOUS`: numeric evidence exists, but binding is ambiguous.
- `CLAIM_NOT_EXPLICIT`: abstract does not explicitly support the claim.
- `NO_ABSTRACT`: no trusted DOI-bound abstract evidence was available.
- `DOI_NOT_FOUND`: selected source did not find a DOI-bound record.
- `DOI_MISMATCH`: selected DOI-bound record did not match the requested DOI.
- `SOURCE_API_ERROR`, `SOURCE_TIMEOUT`, `SOURCE_RATE_LIMITED`, `SOURCE_UNSUPPORTED`: source lookup failed, timed out, was rate-limited, or could not be used.
- `ROW_CHECK_ERROR`: one row could not be checked, but other rows may still have results.

## Agent Must Not

- Do not accept a claim because the DOI exists.
- Do not accept a claim because a related number appears under a different subject.
- Do not accept a claim when `verdict` is `WARN` or `REJECT`.
- Do not accept a claim when `status` is `PARTIAL` or `UNVERIFIABLE`.
- Do not treat `failed > 0` as harmless.
- Do not fill missing abstract evidence from memory or model knowledge.
- Do not infer full-text, table, or figure support from an abstract-only check.

## Minimal Agent Prompt

```text
Extract DOI-bound numeric citation claims from this draft.
Write claims.jsonl with {id, doi, claim, note}.
Run ref-verify check-file claims.jsonl --json.
Treat only verdict ACCEPT as verified.
Report every WARN, PARTIAL, REJECT, UNVERIFIABLE, or failed result as not verified.
Do not use memory to fill missing abstract evidence.
```

## Safe Interpretation

`ref-verify` is a conservative citation guard. It does not prove that a paper is good, important, unretracted, or that the full paper supports a broader statement. It only checks whether the DOI-bound abstract explicitly supports the submitted numeric claim.
