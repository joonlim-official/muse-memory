# Memory Index

Map of the whole memory system. See the skill's `references/layout.md` for
what lives where.

- **Curated memory** — `~/MEMORY.md` — durable facts, preferences, commitments.
- **Personalization** — `~/memory/personalization.md` — habits and patterns.
- **Central profile** — [path to the user's profile document] — the single
  source of truth for the user (+ household).
- **People** — `~/memory/people/` ([INDEX.md](people/INDEX.md)) — one page
  per person.
- **Groups** — `~/memory/groups/` ([INDEX.md](groups/INDEX.md)) — communities
  and teams.
- **Topics** — `~/memory/topics/` ([INDEX.md](topics/INDEX.md)) — one page
  per tracked topic.
- **Trace** — `~/memory/trace/` ([INDEX.md](trace/INDEX.md)) — temporal log,
  newest first.
- **Daily logs** — `~/memory/YYYY-MM-DD.md` — day-to-day detail.

## Search

- Concepts ("what do we know about X?") → semantic search over these files.
- Exact identifiers (names, dates, confirmation numbers, addresses) →
  `bin/memory-grep <pattern>`.
