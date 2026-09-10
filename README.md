# muse-memory

A durable personal memory system for an AI assistant: organized facts by
person and topic, a temporal trace of what changed, search tooling, and a
scheduled collect/update/refine job. Built to be shared — it contains no
personal data, only the system.

## What it is

Most assistant "memory" is either a pile of notes or a black box. This is a
small, opinionated operating system for long-term memory:

- **Curated facts, routed by kind** — people, groups, topics, preferences,
  and commitments each have a home, so nothing is duplicated and everything
  is findable.
- **Temporal trace** — an append-only, newest-first log of what changed,
  with typed entries (`fact`, `preference`, `decision`, `learning`,
  `relationship`, `context`), source citations, expiry dates, and open/closed
  thread tracking. History is superseded, never deleted.
- **Read discipline** — index first, load at most 1–3 relevant pages, surface
  nothing rather than noise, and re-verify facts older than ~90 days.
- **Write discipline** — the default is *not* to write. A write must be
  durable (matter in 30+ days), grounded, and not duplicated. `bin/memory-guard`
  blocks secrets and flags financial figures before anything is written.
- **Quality discipline** — a weekly health audit (entry counts, expired items,
  stale open threads, duplicate drift, full guard scan).

## Layout

```
SKILL.md            # the skill: setup, reading, writing, operating rules
references/         # layout, trace conventions, privacy & validation, cron templates
assets/             # starter templates: MEMORY.md, person/group/topic pages, trace
bin/
  init-memory       # create the directory skeleton (never overwrites)
  memory-grep       # keyword search across the whole memory tree
  memory-guard      # pre-write secret/figure scanner (exit 0 clean, 1 secrets, 2 figures)
```

## Quick start

1. Run `bin/init-memory` — creates the skeleton under `$PERSONAL_MEMORY_ROOT`
   (default `~`). Existing files are never overwritten.
2. Fill in the central profile and personalization notes from what you know
   about the user. **Nothing goes into memory without the user's approval.**
3. Schedule the refresh (see `references/cron-templates.md`): one daily
   collect/update/refine job, plus an optional lightweight watcher for
   urgent items between runs. Both stay silent unless something is worth
   attention.

## Privacy

This repo is the *system*, not anyone's *memory*. It ships with blank
templates only. The operating rules are strict:

- Never store credentials or exact financial figures in memory, skills, or
  operational docs.
- Every trace/fact entry must trace to ground truth; uncertain items are
  marked as such, never asserted.
- `memory-guard` scans new content for secrets (hard block) and figures
  (flag for human review) before writing.

## License

MIT — see [LICENSE](LICENSE).
