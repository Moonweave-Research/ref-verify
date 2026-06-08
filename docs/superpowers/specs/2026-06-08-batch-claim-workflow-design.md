# Batch Claim Workflow Design

## Goal

Move `ref-verify` from a single-claim demo flow to a repeatable research workflow by adding batch claim checking, fixture-backed evaluation, and human-readable reporting.

This is not a semantic expansion of the verifier. It keeps the current product boundary: verify DOI-bound, abstract-grounded numeric claims conservatively, and refuse to accept claims that require full-text reading, table/figure parsing, or broad paper understanding.

## User Problem

Researchers and AI agents rarely need to verify only one citation claim. A realistic draft, literature note, or agent output may contain many DOI/claim pairs:

- "This paper reports 95% accuracy."
- "The study included 12 patients."
- "The material retained performance after 5000 cycles."
- "The experiment was conducted at 37 °C."

The current `check-claim` command can verify these one at a time, but that is too slow for repeated use and awkward for agent pipelines. The next product step should make the same conservative verifier usable across many claims without widening the acceptance logic.

## Non-Goals

- Do not add LLM-based semantic inference.
- Do not parse full text, tables, or figures.
- Do not add p-value, AUC/AUROC, F1, hazard ratio, odds ratio, or 95% CI metric binding in this phase.
- Do not judge paper quality, claim importance, or field consensus.
- Do not automatically rewrite claims into a form that can pass.
- Do not silently treat missing abstracts as failures of the user rather than `UNVERIFIABLE` results.

## Proposed CLI

Add a new command:

```bash
ref-verify check-file claims.jsonl
ref-verify check-file claims.csv
ref-verify check-file claims.txt --format jsonl
```

Supported input formats:

- JSONL: one object per line.
- CSV: one row per claim.

Format detection:

- Infer `jsonl` from `.jsonl`.
- Infer `csv` from `.csv`.
- Allow `--format jsonl` or `--format csv` when the extension is absent or nonstandard.
- Reject unknown formats with exit `1`.

Required fields:

- `doi`
- `claim`

Optional fields:

- `id`: caller-provided stable identifier.
- `source`: `auto`, `crossref`, `semantic-scholar`, or `pubmed`.
- `note`: ignored by the verifier but preserved in JSON output when present.

Example JSONL:

```jsonl
{"id":"c1","doi":"10.xxxx/example-a","claim":"This paper reports 95% accuracy."}
{"id":"c2","doi":"10.xxxx/example-b","claim":"This study included 12 patients."}
{"id":"c3","doi":"10.xxxx/example-c","claim":"The material retained performance after 5000 cycles."}
```

Example CSV:

```csv
id,doi,claim
c1,10.xxxx/example-a,This paper reports 95% accuracy.
c2,10.xxxx/example-b,This study included 12 patients.
c3,10.xxxx/example-c,The material retained performance after 5000 cycles.
```

## Output Modes

The default output should be human-readable and compact:

```text
WARN  c2  10.xxxx/example-b
Claim: This study included 12 patients.
Reason: The abstract contains the number, but the subject binding is ambiguous.
Evidence: "...12 patients..."
```

JSON output should remain available for agents and CI:

```bash
ref-verify check-file claims.jsonl --json
```

JSON shape:

```json
{
  "summary": {
    "total": 3,
    "accept": 1,
    "warn": 2,
    "reject": 0,
    "partial": 2,
    "unverifiable": 0,
    "failed": 0
  },
  "results": [
    {
      "id": "c1",
      "doi": "10.xxxx/example-a",
      "claim": "This paper reports 95% accuracy.",
      "verdict": "ACCEPT",
      "status": "SUPPORTED",
      "reason": "...",
      "evidence": "...",
      "abstract_source": "crossref",
      "error_code": "CLAIM_SUPPORTED",
      "source_attempts": []
    }
  ]
}
```

## Exit Codes

Batch mode should distinguish "the command ran" from "every claim was accepted":

- Exit `0`: command completed and every valid row returned `ACCEPT`.
- Exit `2`: command completed, but at least one valid row returned a non-accepting verdict or status, such as `WARN`, `REJECT`, `PARTIAL`, or `UNVERIFIABLE`.
- Exit `1`: command failed due to invalid input, unreadable file, malformed JSON/CSV, missing required fields, or an unexpected runtime error.

Invalid rows should not be silently skipped. If any row is malformed, return exit `1` and include row-level diagnostics. This prevents users from thinking a partial input file was fully checked.

## Result Semantics

Reuse the existing single-claim logic for every row. Batch mode must not introduce a second verdict system.

`ACCEPT` means the existing verifier found explicit abstract evidence for the DOI-bound claim.

`WARN` is the non-accepting claim verdict currently used for ambiguous or unverifiable claim checks.

`REJECT` should be preserved if the existing single-claim path returns it for a hard mismatch.

`PARTIAL` means the command found some relevant numeric evidence but the subject, unit, comparator, or sentence/clause binding is not clear enough to accept.

`UNVERIFIABLE` means the DOI or abstract evidence could not be checked.

The command may summarize results, but it must not turn `WARN`, `REJECT`, `PARTIAL`, or `UNVERIFIABLE` into softer words such as "probably supported."

## Architecture

Keep `src/ref_verify/cli.py` as the command entry point, but avoid embedding parsing and rendering logic directly into the command branch.

Add:

- `src/ref_verify/batch.py`
  - parse JSONL and CSV inputs
  - validate required fields
  - normalize optional row fields
  - call the existing claim-check flow row by row
  - produce a structured batch result
- `tests/test_batch.py`
  - parser tests
  - row validation tests
  - exit-code tests through the CLI
  - JSON output shape tests
  - human-readable output tests

Keep claim verification centralized. If `check-file` needs the same behavior as `check-claim`, extract a private helper from `cli.py` rather than duplicating DOI lookup and abstract-source selection logic.

## Evaluation Fixture

Add a small fixture-backed eval set:

```text
tests/fixtures/numeric_claim_eval.jsonl
```

Each fixture should contain:

- `id`
- `domain`
- `abstract`
- `claim`
- `expected_verdict`
- `why`

The eval should use local abstract text, not live APIs. Live API checks are already covered separately by the manual smoke workflow; deterministic tests need stable fixtures.

Initial domains:

- materials
- biomedicine
- machine learning
- chemistry
- general science

The eval should intentionally include false-accept defense cases:

- Same sentence with multiple subjects and multiple numbers.
- Correct number but wrong subject.
- Correct unit but wrong comparator.
- Claim that requires full-text/table/figure evidence.
- Abstract with numeric evidence but no clear subject binding.

## Documentation Updates After Implementation

Update both `README.md` and `README.ko.md` with:

- single-claim usage
- batch JSONL usage
- batch CSV usage
- how to read `ACCEPT`, `WARN`/`PARTIAL`, and `UNVERIFIABLE`
- clear "when not to use" boundaries
- a short statement that PyPI installs the CLI package, not the Codex `SKILL.md`

Update `CHANGELOG.md` once the feature lands.

## Implementation Order

1. Add fixture-backed eval tests for batch input and numeric claim outcomes.
2. Add `batch.py` parser and result model helpers.
3. Extract shared single-claim execution from `cli.py`.
4. Add `check-file` CLI command for JSONL.
5. Add CSV support.
6. Add human-readable rendering and JSON summary output.
7. Update README files and changelog.
8. Run unit tests, py_compile, package build, twine check, and package smoke.

## Risk Review

### False Accept Risk

Batch mode can make mistakes more harmful because users may scan summaries instead of individual evidence. The summary must not hide row-level warnings. Human-readable output should show at least the claim, DOI, reason, and evidence for every non-accepted row.

### API Rate Risk

Batch mode may trigger many CrossRef, Semantic Scholar, or PubMed calls. Phase 1 should keep the implementation simple, but the CLI should process rows sequentially and avoid parallel live requests. This reduces accidental load and keeps failures understandable.

### Input Ambiguity Risk

CSV quoting and multiline claims can become messy. Use Python's `csv` module, not manual string splitting. JSONL parse errors should report the line number.

### Scope Creep Risk

Batch mode may tempt users to ask for broader claim interpretation. The command should call the same conservative engine and preserve existing verdict semantics. It should improve throughput, not loosen acceptance.

### Report Misreading Risk

A single summary such as "47 checked" can sound like success. Summaries must include verdict counts, and nonzero warning/unverifiable counts should be visually clear in text output.

## Spec Self-Review

- No LLM, full-text, table, figure, or complex statistical metric expansion is included.
- The new command improves repeated use without changing the core verifier boundary.
- Exit codes are explicit and consistent with the existing `check-claim` behavior.
- The spec separates `verdict` values from `status` values so implementation can reuse `ClaimSupportResult` directly.
- Invalid input handling is fail-closed rather than silently skipping rows.
- Deterministic evals use local abstract fixtures instead of live APIs.
- The main remaining design choice is whether malformed-row diagnostics should be emitted as plain text before JSON parsing errors or as structured JSON when `--json` is present. Implementation should prefer structured JSON for `--json`.
