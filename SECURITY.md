# Security policy

## Scope

This repository ships the **memory system only** — blank templates, scripts,
and conventions. It is designed to contain zero personal data, zero
credentials, and zero financial figures.

## Reporting a vulnerability

If you find a way this repo could leak secrets (e.g. a guard bypass, an
example containing real-looking credentials), please open an issue. There is
no bug bounty; there is gratitude.

## For users of the system

- `bin/memory-guard` scans content before it is written to memory: secrets
  are a **hard block** (exit 1), financial figures are **flagged for human
  review** (exit 2). Run it on new content and in your scheduled audits.
- Never store credentials of any kind in memory files, skills, or
  operational docs. Never store exact financial figures there either —
  they belong in chat and the private finance dashboard only.
- The trace format records *sources*, not secret *values*. If you paste an
  API response into memory, redact it first.
