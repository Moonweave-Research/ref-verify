# Contributing to ref-verify

Thank you for helping improve citation verification. Contributions of all kinds are welcome — new failure modes, broader API coverage, improved trigger descriptions, and additional test cases.

---

## Ways to contribute

### Report a hallucination case

If `ref-verify` missed a real error (false negative) or flagged something incorrectly (false positive), open an issue with:

- The prompt you used
- What the skill returned
- What the correct result should have been
- The DOI or paper title involved

These are the most valuable contributions. Real failure cases are how the skill improves.

### Add a test case

Test cases live in `evals/evals.json`. A good test case:

- Uses a real DOI that can be independently verified
- Tests a specific failure mode (wrong author, hallucinated content, near-miss, retracted paper)
- Has a clear `expected_output` description

See the existing three cases for format reference.

### Improve the skill

`SKILL.md` is the skill itself — the instructions the agent follows. Improvements should:

- Solve a documented problem (link to an issue or test case)
- Not add scope beyond citation verification
- Keep the two-mode design intact (Quick Screen and Full Audit)
- Preserve the core rule: every content statement must be verbatim from a fetched abstract

### Extend API coverage

Currently covers: CrossRef, Semantic Scholar, Unpaywall, arXiv, PubMed.

Additions worth considering: Retraction Watch API, DOAJ for open-access status, IEEE Xplore for conference papers, bioRxiv for life-science preprints.

---

## Submitting changes

1. Fork the repository
2. Create a branch: `git checkout -b fix/description-near-miss` or `feat/retraction-watch-api`
3. Make your change
4. Test it: run the skill on the `evals/evals.json` cases and verify outputs look correct
5. Open a pull request — use the template provided

Pull requests that include a new test case or a documented before/after example are much easier to review and merge.

---

## What not to change

- Do not weaken the core rule (verbatim abstract traceability)
- Do not merge Quick Screen and Full Audit into a single mode
- Do not add verification for non-academic sources (web pages, blog posts) — that is a different problem

---

## Questions

Open a [GitHub Discussion](https://github.com/Moonweave-Research/ref-verify/discussions) for anything that isn't a bug or a concrete feature request.
