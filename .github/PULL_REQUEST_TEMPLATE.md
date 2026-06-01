## What this changes

(one paragraph — what problem does this PR solve?)

## Type of change

- [ ] Bug fix — skill was producing wrong verdicts
- [ ] New API source (e.g. Retraction Watch, IEEE Xplore)
- [ ] Trigger description improvement
- [ ] New test case in `evals/evals.json`
- [ ] Documentation

## Evidence

For skill changes: show a before/after example with a real DOI.

```
Before (without this change):
[verdict or behavior]

After (with this change):
[verdict or behavior]
```

For trigger changes: show which queries now correctly trigger (or don't) that didn't before.

## Checklist

- [ ] The core rule is preserved (verbatim abstract traceability, UNVERIFIABLE instead of guessing)
- [ ] Quick Screen and Full Audit remain distinct modes
- [ ] SKILL.md is under 500 lines
- [ ] If adding a test case: the DOI is real and independently verifiable
- [ ] CHANGELOG.md updated under `[Unreleased]`
