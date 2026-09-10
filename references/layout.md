# Layout

All paths are relative to the memory root (`$PERSONAL_MEMORY_ROOT`, default
`~`). Created by `bin/init-memory`.

```
~/MEMORY.md                  Curated long-term facts, preferences, commitments.
                             Tight: promote only what lasts.
~/memory/personalization.md   Distilled habits, patterns, standing preferences.
~/memory/people/ + INDEX.md   One page per person (family, friends, teachers,
                             coaches, colleagues). Read the matching page
                             whenever that person comes up.
~/memory/groups/ + INDEX.md   Communities and teams the user belongs to.
~/memory/topics/ + INDEX.md   One page per tracked topic (e.g. health,
                             travel, finance, home, hobbies). Read the
                             matching page whenever that topic comes up.
~/memory/trace/ + INDEX.md    Append-only temporal log, newest first.
                             Top = latest knowledge; deeper = history.
~/memory/YYYY-MM-DD.md        Raw daily logs. Day-to-day detail that didn't
                             make the cut for curated files.
~/memory/bank/               Runtime-managed reflections (if the platform
                             provides them). Readable; do not edit directly.
<central-profile>            One document describing the user (+ household),
                             the single source of truth. Lives wherever the
                             user keeps documents (e.g. a workspace
                             your_files/ directory); link it from the
                             memory INDEX.md.
```

## Routing table: where a new fact goes

| Kind of fact | Home |
|---|---|
| About a specific person | `~/memory/people/<person>.md` |
| About a community / team | `~/memory/groups/<group>.md` |
| About a tracked topic | `~/memory/topics/<topic>.md` |
| Durable user fact or commitment | `~/MEMORY.md` + central profile |
| Preference or habit pattern | `~/memory/personalization.md` |
| Day-to-day detail | `~/memory/<date>.md` |
| Something changed / opened / closed | `~/memory/trace/trace.md` (plus the fact's home) |

## Principles

- **One home per fact.** Family facts live in the central profile; topic
  detail lives on topic pages. When the same fact appears in two places and
  they drift, delete the copy and keep the canonical one.
- **Curated files stay tight.** If a detail is only useful today, it belongs
  in the daily log, not in a curated file.
- **Stale-prone facts carry dates.** Anything that can go stale (levels,
  counts, prices, schedules) is written as "as of YYYY-MM-DD".
- **Indexes are the map.** Each `INDEX.md` lists every page in its directory
  with a one-line description, closest/most important first.
