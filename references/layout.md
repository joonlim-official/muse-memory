# Layout

All paths are relative to the memory root (`$PERSONAL_MEMORY_ROOT`, default
`~`). Created by `bin/init-memory`.

Memory is organized by **entity** — people, groups, topics, interests,
locations, events — not by date. Each entity gets one page that
accumulates over time; one fact lives in exactly one home.

## The stores

| Store | Holds | One page per… | Read when… |
|---|---|---|---|
| `~/MEMORY.md` | Curated long-term facts, preferences, commitments. Tight: promote only what lasts. | — | The durable core is needed |
| `~/memory/personalization.md` | Distilled habits, patterns, standing preferences the system learned. | — | Behavior or taste is in play |
| `~/memory/people/` + `INDEX.md` | Who someone is and how they relate to the user: family, friends, teachers, coaches, colleagues. | Identifiable person | That person comes up |
| `~/memory/groups/` + `INDEX.md` | Communities and teams the user belongs to. | Community / team | That group comes up |
| `~/memory/topics/` + `INDEX.md` | Tracked topics followed over time (e.g. health, travel, finance, home, hobbies). | Topic | That topic comes up |
| `~/memory/interests/` + `INDEX.md` | Interests proven by **repeated** time/attention or a clearly stated interest. A page is created only with real evidence — never from a passing mention. | Proven interest | That interest comes up |
| `~/memory/locations/` + `INDEX.md` | Significant places (home, school, venues, workplaces, frequent destinations): address, what happens there, durable facts. | Recurring place | That place comes up |
| `~/memory/meetings/` + `INDEX.md` | Significant meetings, calls, or recorded conversations: date, participants, source, summary, decisions, commitments, follow-ups. | Event with other people | That meeting comes up |
| `~/memory/activities/` + `INDEX.md` | Notable non-meeting memos or recordings: voice memos, errands, workout or lesson notes. | Solo memo / recording | That activity comes up |
| `~/memory/trace/` + `INDEX.md` | Append-only temporal log, newest first. Top = latest knowledge; deeper = history. | — | "What changed / when did we decide…" |
| `~/memory/YYYY-MM-DD.md` | Raw daily logs. Day-to-day detail that didn't make the cut for curated files. Writers append via `bin/memory-log-append` — never hand-compute the filename (UTC hosts misfile). | — | Day-level detail is needed |
| `~/memory/bank/` | Runtime-managed reflections (if the platform provides them). Readable; do not edit directly. | — | — |
| `<central-profile>` | One document describing the user (+ household), the single source of truth. Lives wherever the user keeps documents (e.g. a workspace your_files/ directory); link it from the memory INDEX.md. | — | The full user picture is needed |

## Environment

Every tool resolves paths from the memory root (`$PERSONAL_MEMORY_ROOT`,
default `~`). The daily-log helper follows it too: `bin/memory-log-append`
writes under `${PERSONAL_MEMORY_ROOT:-$HOME}/memory` — set `MEMORY_LOG_ROOT`
explicitly only to override that.

## Distinctions that matter:- **Topics vs interests.** A topic is *tracked* (health, finance, travel) —
  the system watches it. An interest is *proven* (repeated time/attention)
  — the user demonstrated it. A passing mention of Formula 1 creates no
  interest page; six months of race-strategy reading does.
- **People vs groups.** A person is an individual with a relationship to
  the user; a group is a community the user belongs to. A coach is a
  person; the cycling club is a group.
- **Meetings vs activities.** A meeting involves other people and ends in
  decisions or follow-ups; an activity is a solo memo or recording
  (voice note, workout log). Both are events, filed by date slug.

## Routing table: where a new fact goes

| Kind of fact | Home |
|---|---|
| About a specific person | `~/memory/people/<person>.md` |
| About a community / team | `~/memory/groups/<group>.md` |
| About a tracked topic | `~/memory/topics/<topic>.md` |
| About a significant meeting/call | `~/memory/meetings/YYYY-MM-DD-<slug>.md` |
| About a non-meeting memo/recording | `~/memory/activities/YYYY-MM-DD-<slug>.md` |
| Evidence of a user interest | `~/memory/interests/<slug>.md` (only with real evidence — repeated time/attention or a clearly stated interest) |
| About a significant place | `~/memory/locations/<slug>.md` (only for recurring places, not one-off mentions) |
| Durable user fact or commitment | `~/MEMORY.md` + central profile |
| Preference or habit pattern | `~/memory/personalization.md` |
| Day-to-day detail | `~/memory/<date>.md` |
| Something changed / opened / closed | `~/memory/trace/trace.md` (plus the fact's home) |
| Time-bound plan or event (trip, project, deadline) | `~/memory/trace/trace.md` as an **open thread** with `valid_until`; detail lives on the relevant topic page; curated files (`MEMORY.md`, central profile, personalization) keep a one-line pointer only — never the full itinerary |

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
- **Entities accumulate.** People, groups, topics, meetings, activities,
  interests, and locations are entity profiles that build up over time:
  every new source (scan, note, recording, conversation) files its entities
  into the matching pages and cross-links them. Never invent a person page
  for someone who can't be identified — mark them `(unidentified …)` in the
  meeting profile instead.
- **Dated plans decay.** A time-bound plan kept in full in a curated file
  will rot there. The trace's `valid_until` + open thread is the mechanism
  that retires it; the curated files only point at it.
