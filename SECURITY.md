# Security Policy

## Scope

`ref-verify` is a skill (prompt instructions) for AI agents. It makes read-only HTTP requests to public academic APIs — CrossRef, Semantic Scholar, Unpaywall, arXiv, and PubMed. It does not execute code, store credentials, or write files.

**In scope for security reports:**

- The skill instructing an agent to send user data to an unexpected third-party endpoint
- A prompt injection vector in the skill instructions that could be exploited via a malicious paper abstract
- Any behavior that could leak the user's research content to an unintended destination

**Out of scope:**

- Vulnerabilities in CrossRef, Semantic Scholar, or other upstream APIs
- Rate limiting or API availability issues
- Incorrect verification results (those are bugs, not security issues — use a regular issue)

## Reporting

Do not open a public issue for security vulnerabilities. Email the maintainer directly or use [GitHub's private vulnerability reporting](https://github.com/moonweave/ref-verify/security/advisories/new).

Include:
- A description of the vulnerability
- Steps to reproduce
- The potential impact

You will receive a response within 72 hours.

## Prompt injection risk

This skill fetches content from external sources (paper abstracts) and includes it in the agent's context. A maliciously crafted abstract could theoretically contain text designed to manipulate the agent's behavior. The skill mitigates this by:

- Quoting abstract content verbatim (rather than acting on it)
- Only fetching from established academic APIs with stable content policies
- Not executing any content from fetched sources

If you discover a prompt injection vector in fetched abstract content, please report it.
