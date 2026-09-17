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

Free-share zones: Joon's Google Drive, his Notion notes, and within the
Muse account (chat, memory, dashboard). Content moves freely between
these. EVERYTHING else is default-deny for private data.

Before a draft leaves the free-share zones — a Gmail/Messenger send, a
public commit, a shared artifact, a Drive share with others — it passes
the egress gate:

- exit 1 (secrets, SSNs, card-like sequences) = blocked, fix first.
- exit 2 (financial figures, phone numbers, denylisted literals) = needs
  the user's explicit approval.
- exit 0 = clean.

## Enforcement (not just documentation)

`bin/shims/` shadows the send-capable CLIs (`hatch_gws_cli`,
`hatch_messenger_cli`). Put it first on `PATH` in every agent shell
context:

  export PATH="<skill>/bin/shims:$PATH"

Gmail sends (`+send`/`+reply`/`+forward`, raw `users messages send`),
Messenger `send`/`edit`, and Drive `permissions create` are intercepted
and run through `bin/egress-gate`, which decides: block (1), refuse
pending approval (2), or allow (0). `--draft` and `--dry-run` are not
sends and pass through; all other subcommands (reads, his own Drive,
labels) are untouched. Every gate decision is appended to an audit log
(`$MOCHI_EGRESS_LOG`, default `~/workspace/memory-sync/egress-gate.log`).

`MOCHI_EGRESS_APPROVED=1` overrides a review-tier refusal — set it only
after the user's explicit approval in chat, never from scheduled workers.
The override is logged. Bypassing the shims via the real binaries'
absolute paths is forbidden.

Known limit: browser-task sends run on a separate VM the shims cannot
reach — those briefs must carry the egress rule as instruction, and the
underlying skill's send-approval rule still applies.

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
