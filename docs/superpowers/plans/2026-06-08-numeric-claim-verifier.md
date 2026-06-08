# Numeric Claim Verifier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a conservative, cross-domain numeric claim checker for explicit abstract evidence.

**Architecture:** Create `src/ref_verify/numeric_claim.py` to parse numeric claims and evidence clauses, then route numeric claims through it from `claim_check.py`. Keep existing text fallback and actuation-strain false-accept guards.

**Tech Stack:** Python 3.10 standard library, `unittest`, existing dataclass result model.

---

### Task 1: Add Numeric Claim Engine Skeleton

**Files:**
- Create: `src/ref_verify/numeric_claim.py`
- Create: `tests/test_numeric_claim.py`

- [ ] **Step 1: Write failing tests for percent and unit claim extraction**

Add tests that call `check_numeric_claim_support()` with abstracts and claims:

```python
def test_accepts_subject_matched_percent_claim():
    result = check_numeric_claim_support("Device efficiency reached 95%.", "device efficiency above 90%")
    self.assertEqual(result.status, "SUPPORTED")

def test_accepts_subject_matched_unit_claim():
    result = check_numeric_claim_support("The actuator survived 5000 cycles.", "actuator survived at least 4000 cycles")
    self.assertEqual(result.status, "SUPPORTED")
```

- [ ] **Step 2: Run tests and verify failure**

Run: `PYTHONPATH=src python3 -m unittest tests.test_numeric_claim -v`

Expected: import or missing-function failure.

- [ ] **Step 3: Implement minimal public API**

Create `NumericClaimResult` and `check_numeric_claim_support(abstract: str, claim: str)`.

- [ ] **Step 4: Run tests and verify pass**

Run: `PYTHONPATH=src python3 -m unittest tests.test_numeric_claim -v`

Expected: all new tests pass.

### Task 2: Add Subject Binding and False-Accept Guards

**Files:**
- Modify: `src/ref_verify/numeric_claim.py`
- Modify: `tests/test_numeric_claim.py`

- [ ] **Step 1: Write failing tests for mixed-subject sentences**

Add cases where the supporting number belongs to the wrong subject:

```python
def test_rejects_wrong_subject_number_in_same_sentence():
    result = check_numeric_claim_support(
        "Device efficiency reached 80%, and response rate was 95%.",
        "device efficiency above 90%",
    )
    self.assertEqual(result.status, "PARTIAL")
```

- [ ] **Step 2: Run tests and verify failure**

Run: `PYTHONPATH=src python3 -m unittest tests.test_numeric_claim -v`

Expected: wrong-subject test fails before guard implementation.

- [ ] **Step 3: Require subject terms in the same clause**

Split evidence into clauses before extracting evidence. Accept only when claim subject terms appear in the clause that owns the numeric value.

- [ ] **Step 4: Run tests and verify pass**

Run: `PYTHONPATH=src python3 -m unittest tests.test_numeric_claim -v`

Expected: positive and false-accept tests pass.

### Task 3: Route Numeric Claims Through Claim Check

**Files:**
- Modify: `src/ref_verify/claim_check.py`
- Modify: `tests/test_claim_check.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing integration tests**

Add `check_claim_support()` and CLI tests for unit/count claims:

```python
def test_unit_claim_is_supported_when_subject_and_unit_match():
    record = PaperRecord(..., abstract="The actuator survived 5000 cycles.")
    result = check_claim_support(record, "actuator survived at least 4000 cycles")
    self.assertEqual(result.status, "SUPPORTED")
```

- [ ] **Step 2: Run integration tests and verify failure**

Run: `PYTHONPATH=src python3 -m unittest tests.test_claim_check tests.test_cli -v`

Expected: unit/count integration tests fail before routing.

- [ ] **Step 3: Call numeric engine before text fallback**

In `claim_check.py`, call `check_numeric_claim_support(record.abstract, claim)`. Convert `SUPPORTED` to `ClaimSupportResult(status="SUPPORTED", verdict="ACCEPT", ...)`; otherwise continue existing fallback.

- [ ] **Step 4: Run integration tests and verify pass**

Run: `PYTHONPATH=src python3 -m unittest tests.test_claim_check tests.test_cli -v`

Expected: all integration tests pass.

### Task 4: Update Documentation and Final Verification

**Files:**
- Modify: `README.md`
- Modify: `README.ko.md`
- Modify: `tests/test_skill_docs.py`

- [ ] **Step 1: Write docs assertions**

Assert README mentions explicit numeric evidence, percent claims, unit/count claims, and deferred statistical metrics.

- [ ] **Step 2: Update README copy**

Describe Phase 1 CLI scope as explicit numeric evidence only. Do not imply semantic paper understanding.

- [ ] **Step 3: Run full verification**

Run:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
tmpdir=$(mktemp -d /tmp/ref-verify-install-test.XXXXXX) && python3 -m venv "$tmpdir/venv" && "$tmpdir/venv/bin/python" -m pip install -e . && "$tmpdir/venv/bin/ref-verify" --help
```

Expected: all tests pass and editable install exposes `ref-verify --help`.
