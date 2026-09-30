# MEMORY.md

<!-- Thin router. Identity + pointers only.
Single-home rule: every fact lives exactly once, in the indexed file that
owns it — never duplicated here. If a fact belongs to a topic, person,
group, or place page, it lives there. -->

## Identity

- **(name)** — add birthdate, timezone, contact lines only if genuinely durable.

## Where everything lives

| What | Where |
|---|---|
| People | `~/memory/people/INDEX.md` |
| Groups & communities | `~/memory/groups/INDEX.md` |
| Topics | `~/memory/topics/INDEX.md` |
| Places | `~/memory/locations/INDEX.md` |
| Preferences & habits — about the user | `~/memory/personalization.md` |
| How the assistant operates — rules & conventions | (your operating notes file) |
| Temporal trace (what changed, when) | `~/memory/trace/trace.md` |
| Day-to-day detail | `~/memory/YYYY-MM-DD.md` |
| Central profile (derived human-readable view) | (your documents directory) |

## Reading this memory

- Index first, then read at most 1–3 pages relevant to the turn. Never
  preload the whole tree.
- **Search before answering AND before asking** — semantic search for
  concepts, `bin/memory-grep` for exact identifiers.
