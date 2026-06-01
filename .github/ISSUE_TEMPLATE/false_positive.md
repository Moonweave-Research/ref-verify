---
name: False positive
about: The skill flagged something that was actually correct
labels: bug, false-positive
assignees: ''
---

## What happened

The skill returned WARN or REJECT but the citation was correct.

**Prompt used:**
```
(paste the prompt you gave the agent)
```

**Skill output:**
```
(paste the VERDICT and the specific flag/warning)
```

**Why the flag was wrong:**

(explain what the correct metadata or content is, with a source)

**Evidence:**

- CrossRef record: (URL or paste)
- doi.org result: (URL)
- Abstract source: (CrossRef / S2 / PubMed link)

**Expected verdict:** ACCEPT / WARN (lower severity)
