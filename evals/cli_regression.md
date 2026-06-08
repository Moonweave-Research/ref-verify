# CLI regression corpus (ship-gate)

`cli_regression.jsonl` is a labeled, deterministic regression set for the
`check-file` engine. It complements `evals.json` (which evaluates skill-level LLM
behavior); this one pins **machine-checkable verdicts** so unit/source/matcher
changes can be regression-tested without an LLM in the loop.

Each row carries the claim **plus** ground-truth labels:

| field | meaning |
|---|---|
| `expected_verdict` | the verdict the engine *should* reach |
| `must_accept` | invariant: this row must end `ACCEPT` on every commit |
| `must_not_accept` | invariant: this row must **never** end `ACCEPT` |
| `gated_on` | open issues that currently block `expected_verdict` |
| `reachable_via` | where an abstract exists: `crossref` / `openalex` / `none` |
| `category` | `numeric_supported`, `fabricated_control`, `relational_out_of_scope`, `unreachable_ceiling`, `dead_doi_control`, `over_acceptance_regression` |

## Two invariant classes

**SAFETY (release blocker).** `must_accept` rows must stay `ACCEPT`; `must_not_accept`
rows must never become `ACCEPT`. This is the tool's core promise — no fabricated,
relational, unreachable, or over-accepting claim is waved through, and the one
clean supported claim stays green. A break here fails the gate (non-zero exit).

**PROGRESS (informational).** Gated rows do not yet reach `expected_verdict`
because a fix has not landed. They are reported, not failed, and flip to PASS as
their `gated_on` issue is resolved. This is how the corpus tracks the roadmap.

## How to run

```bash
PYTHONPATH=src python3 evals/run_cli_regression.py
```

Exit code is non-zero iff a SAFETY invariant is violated. (Live network: CrossRef /
OpenAlex / Semantic Scholar / PubMed. Semantic-Scholar free-tier 429 only affects
PROGRESS rows that depend on it, never SAFETY rows.)

## What the corpus encodes (snapshot, latest `main`)

- **1 supported happy path** — `A1` (`>220 °C` entails `>200 °C`): ACCEPT today, must stay.
- **5 never-accept controls** — `B1` fabricated number, `C1`/`C2` relational, `D1`/`D2`
  unreachable (Elsevier / old Nature, abstract-only ceiling), `E1` dead DOI.
- **Gated false-negatives** (target ACCEPT once fixed): `A3` → #14, `B2` → #10,
  `A2` → #13 **and** #14 (physical-science values are reachable *and* scope-blocked —
  the two are coupled), `E2` → up-to comparator.
- **Over-acceptance regression** — `B3`: `>220` evidence currently ACCEPTs an exact
  `220` claim; target `PARTIAL` once #11 lands. Listed `must_not_accept` so it also
  guards against the bug regressing.

The verdict labels for `A2`/`A3`/`B2` were grounded by fetching the live abstracts
(CrossRef + OpenAlex) and confirming the value appears verbatim; no label asserts
support that is not in a fetched abstract.
