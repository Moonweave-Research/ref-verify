---
name: Missed hallucination (false negative)
about: The skill failed to catch a real citation error
labels: bug, false-negative
assignees: ''
---

## What happened

The skill returned ACCEPT or WARN but the citation was actually wrong.

**Prompt used:**
```
(paste the prompt you gave the agent)
```

**Skill output:**
```
(paste the VERDICT and CONTENT section)
```

**What was actually wrong:**

- [ ] Wrong DOI (resolves to different paper)
- [ ] Wrong authors
- [ ] Wrong year
- [ ] Content not in abstract (hallucinated description)
- [ ] Near-miss (right number, wrong context)
- [ ] Retracted paper not flagged
- [ ] Other:

**Evidence (CrossRef / DOI / abstract text):**

(paste the live CrossRef or doi.org result that shows the error)

**Expected verdict:** WARN / REJECT
