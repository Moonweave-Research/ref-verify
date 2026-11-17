# Security Policy

## Scope

`ref-verify` includes instructions for AI agents, an executable Python CLI, and an optional browser interface. The CLI queries CrossRef, doi.org, OpenAlex, Semantic Scholar, and PubMed. The manual skill workflow can also consult publisher pages, Unpaywall, and arXiv.

The CLI reads the reference or claim files selected by the user. Bibliographic search sends reference-derived text to CrossRef; DOI and abstract lookups send identifiers to the relevant public APIs. It writes an on-disk HTTP response cache by default and writes HTML or Markdown reports when `--report` is requested. Use `--no-cache` or `REF_VERIFY_NO_CACHE=1` to disable the cache. Reports can contain the user's reference and claim text.

The CLI reads optional API keys and contact emails from environment variables and sends them to their designated API providers. It does not provision or persist those credentials. The browser interface runs the Python engine in Pyodide, loads its runtime from jsDelivr, and queries CrossRef and doi.org directly. Uploaded files are processed in browser memory; the page does not persist them after it is closed. Downloading a report writes the selected output through the browser.

**In scope for security reports:**

- The skill instructing an agent to send user data to an unexpected third-party endpoint
- A prompt injection vector in the skill instructions that could be exploited via a malicious paper abstract
- Any behavior that could leak the user's research content to an unintended destination

**Out of scope:**

- Vulnerabilities in CrossRef, Semantic Scholar, or other upstream APIs
- Rate limiting or API availability issues
- Incorrect verification results (those are bugs, not security issues — use a regular issue)

## Reporting

Do not open a public issue for security vulnerabilities. Email the maintainer directly or use [GitHub's private vulnerability reporting](https://github.com/Moonweave-Research/ref-verify/security/advisories/new).

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
