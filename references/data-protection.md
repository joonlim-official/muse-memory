# Data protection

Three tiers decide where information may live and travel. The tiers are
about *surfaces*, not about hiding things from the user — inside their
own private surfaces, everything is visible.

## Tiers

- **Public.** Anything the whole world could read: the public skill repo,
  GitHub, messages sent to anyone except the user, shared artifacts. Only
  synthetic, impersonal examples live here. Never a real name, address,
  figure, or identifier belonging to the user or their family.
- **Memory.** Curated memory files (profile, personalization, people,
  groups, topics, trace, daily logs). May hold personal facts the user
  explicitly approved for memorization (home address, family details).
  Financial figures may live in ONE place only: the installation's finance
  index (`MEMORY_FINANCE_INDEX`, default `~/memory/finance-index.md`) —
  dated headline facts the user approved, refreshed from the dashboard,
  never edited by hand to guess. Everywhere else in memory: never figures,
  credentials, government IDs, account numbers. `bin/memory-guard`
  enforces this before writes and in the audit — the finance index is
  exempt from figure-flagging, but secrets still hard-block there.
- **Private.** The conversation with the user and their private dashboard.
  Everything may appear here, including financial figures. Figures still
  do not get *promoted* from here into memory — the guard flags them.

## The egress rule

Before a draft leaves the private surfaces — a public commit, a message
sent through the user's accounts, a shared artifact, pasted content —
run it through `bin/memory-egress-check`:

- exit 1 (secrets, SSNs, card-like sequences) = blocked, fix first.
- exit 2 (financial figures, phone numbers, denylisted literals) = needs
  the user's explicit approval.
- exit 0 = clean.

Review-tier judgment applies to *private* information only. Public
information — stock and market prices, public business phone numbers,
published prices, anything anyone could look up — is not sensitive and
never needs the user's permission. Do not escalate it; handle it
mechanically.

## Installation-specific lists

Two hand-curated files live with the installation, never in the public
skill repo:

- `.figure-allowlist` — figures and personal-data strings the user already
  reviewed and approved; the guard stops flagging them.
- `.egress-denylist` — sensitive literals (street address, etc.) that must
  never appear outside private surfaces; the egress check flags them and
  the audit verifies the public skill repo contains none of them.

Both are curated by the user alone. Nothing auto-populates them.
