# Privacy and validation

## Approval rule

Nothing is saved to memory without the user's approval. Standing exceptions
must be granted explicitly (e.g. "keep the central profile current", "run the
daily refresh"). When in doubt, ask.

## Never in memory

These live elsewhere, never in memory files, skills, or operational docs:

- **Financial figures** — balances, income, transaction amounts. They belong
  in the user's private dashboard / chat only.
- **Credentials** — passwords, API keys, tokens, secrets. Secure vault only.
- **Government IDs, account numbers** — note that the item exists and where
  it lives, never the value.

## Validation rule

Every trace entry and curated fact must trace to ground truth: a log, a
message, a verified record, or the user's own words. Before writing:

1. Check the fact against its source — quote or cite it.
2. If a new fact contradicts an old one, supersede the old entry; never
   silently overwrite.
3. Uncertain items are marked as such ("likely", "unverified", "inferred"),
   never asserted as fact.
4. After writing, spot-check: no figures, no secrets, dates valid, every
   entry sourced.

## Write discipline

**Signal gate.** The default is NOT to write. A memory write must be
durable (will matter in 30+ days), grounded (traceable to a source), and
not already recorded. Do NOT save: transient chit-chat, raw message
quotes, one-off tool outputs, anything the user can re-derive in seconds,
duplicates.

**Guard.** The skill ships `bin/memory-guard`: run it on new content
before writing. Secrets are a hard block (fix first); financial figures
are flagged for the user's review, never auto-deleted. Exit 0 = clean,
1 = secrets found, 2 = figures only.

## Read discipline

Context is a finite budget — load the smallest high-signal set:

- **Index first, bodies on demand.** Read the index, then at most 1–3
  pages relevant to the turn. Never preload the whole tree.
- **Quality gate.** Surface nothing rather than noise. If search returns
  nothing clearly relevant, say so instead of stretching a weak match.
- **Age-aware verification.** Facts older than ~90 days get re-verified
  against a fresh source before being asserted; otherwise present them as
  stale ("as of …").

## Quality

The scheduled refine job should run a deeper health audit weekly: entry
counts per area, expired `valid_until` items, open threads older than
30 days, duplicate drift between the profile and topic pages, and a full
guard scan. Mechanical fixes (expiry, dedupe) are applied; judgment calls
are reported to the user.

## Delivery rule for scheduled jobs

Background memory work stays silent unless something is meaningfully new AND
worth the user's attention right now. Routine runs update the files and say
nothing — the files are the record.
