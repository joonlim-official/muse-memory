---
name: "personal_memory_system"
description: "Set up and operate a durable personal memory for an AI assistant: memory scanning, retrieval, management, indexing, organization, and evolution — with a built-in data-protection layer, validated by the muse-leakage-guard add-on."
---

# Personal Memory System

## Purpose
Give an AI assistant a long-term memory that stays organized, searchable,
and current. The skill covers the full lifecycle: **scanning** (collecting
from the user's surfaces), **retrieval** (searching before answering),
**management** (routing each fact to its home), **indexing** (entity
profiles: people, groups, topics, meetings, activities, interests,
locations), **organization** (curated files plus an append-only
temporal trace), **evolution** (scheduled collect/update/refine and
evaluation), and **protection** (a data-protection layer — egress gates,
send shims, briefing policy — validated by the muse-leakage-guard
add-on).

## Workflow

### 1. Set up
1. Run `bin/init-memory` — creates the directory skeleton and starter files
   under the memory root (`$PERSONAL_MEMORY_ROOT`, default `~`). Never
   overwrites existing files. Every tool honors the root, including
   `bin/memory-log-append` (daily logs land under
   `${PERSONAL_MEMORY_ROOT:-$HOME}/memory`; `MEMORY_LOG_ROOT` overrides).
2. Fill in the central profile and personalization notes from what you know
   about the user. Nothing goes into memory without the user's approval
   (see `references/privacy-and-validation.md`).
3. Schedule the refresh (see `references/cron-templates.md`): one daily
   collect/update/refine job, an optional lightweight watcher that
   surfaces urgent items between runs, and an optional nightly evaluation
   that audits the system's disciplines.

### 2. Reading memory
- Search BEFORE answering anything about prior work, decisions, dates,
  people, preferences, todos, ongoing work, or the user's history — and
  before recommending anything, even when the request mentions no history.
- Search BEFORE asking, too: before asking the user for any fact (a name,
  a date, a number), run the memory search/read first. If the answer is in
  memory — or in a file the index points to — use it and cite the source;
  ask only when memory genuinely doesn't have it.
- Concepts ("what do we know about X?") → semantic search over the memory
  files (on Muse: `muse.memory_search`).
- Exact identifiers (names, dates, confirmation numbers, addresses) →
  `bin/memory-grep <pattern>` (keyword search across the whole tree).
- Contextual retrieval: every turn, resolve the entities in play — person,
  group, topic, meeting, activity, interest, or location — against the
  matching `INDEX.md` and read the matching page(s) in addition to searching.
  The turn's entities decide what gets read: a place name pulls its location
  profile, a meeting reference pulls its meeting profile, and so on.
  Nicknames and aliases resolve via the INDEX descriptions and
  `bin/memory-grep`. Budget: index first, at most 1–3 pages per turn.
- Photo identification: the assistant keeps no visual memory between
  turns. Maintain a visual index (reference photos + stable features)
  per `references/visual-index.md`; when the user sends a photo asking
  who is who, read the index and load the reference photos into context
  before matching — never identify from the text description alone.
- Place recall: the assistant keeps no running sense of "where".
  Maintain a places index (one page per significant place, with a dated
  visit log) per `references/places-index.md`; when a location entity
  comes up, resolve it against `locations/INDEX.md` and read the matching
  page — index first, at most 1–3 pages per turn. Never promote a one-off
  mention into a page.

### 3. Writing memory
- Route each fact to its SINGLE home — see the routing table in
  `references/layout.md`. Every fact lives exactly once, in the indexed
  file that owns it: person facts on the person's page, topic facts on the
  topic page, the user's tastes/habits in personalization, operating rules
  in the assistant's operating notes — never duplicated in `MEMORY.md` or
  the central profile. `MEMORY.md` is a thin router (identity + pointers),
  and the central profile is a derived human-readable view of the indexed
  pages, never an independent fact store.
- Every significant change gets a dated trace entry, newest first — see
  `references/trace-conventions.md`.
- Follow `references/privacy-and-validation.md`: the approval rule, what
  never goes into memory, and the validate-against-ground-truth rule.
- Follow `references/data-protection.md`: the three data tiers and the
  egress rule — run `bin/memory-egress-check` on anything leaving the
  user's private surfaces.

### 4. Optional: Notion two-way sync

An opt-in, stdlib-only Python component (`lib/notion_sync/`,
`bin/memory-notion-sync`) keeps the memory in two-way sync with Notion:

- Notion hosts a persistent **live page tree** (one page per managed file)
  that a human can read and edit; Markdown files remain operational storage.
- Local edits push to Notion; manual Notion edits pull back (guard-scanned).
- Pushes are incremental block diffs (changed blocks updated in place,
  ids preserved; zero write calls when nothing changed), and local →
  Notion → local round-trips byte-identical except for documented
  normalizations (H4–H6 → H3 is the only lossy case).
- Every successful sync also writes a dated recovery snapshot page.
- Three-way reconciliation (base vs local vs remote): simultaneous edits
  are **conflicts — both versions preserved, neither overwritten**; the sync
  writes nothing until the whole plan is actionable, and a failed apply
  rolls back every completed step (all-or-nothing).
- Deletions are never destructive: an archived Notion page is reported,
  the local file is kept.
- Full contract in `references/notion-sync.md`. Synthetic tests:
  `python3 -m pytest tests/ -q` (fake transport, no credentials).

### 5. Optional: Feed personalization

An opt-in default: ground the user's Muse Feed in the memory system so
posts personalize from the profile, entity pages, and past coverage —
every post says concretely why it matters to *this* user.

- Read the profile, personalization notes, and the entity `INDEX.md`
  files (`people/`, `groups/`, `topics/`, `interests/`, `locations/`,
  `meetings/`, `activities/`); compose a feed prompt from the durable
  interests, projects, routines, and money habits you find there.
- Apply with `feed.prompt_update` (a real change starts a fresh
  generation immediately). Re-ground when memory changes materially —
  a monthly check inside the daily refresh is plenty.
- The prompt is derived from memory, never new memory itself; public
  examples stay synthetic and impersonal.
- Full playbook in `references/feed-personalization.md`.

### 6. Optional: Task queue with completion-enforcing watchdog

An opt-in FIFO task system that keeps the assistant's work executing until
full completion — nothing stalls silently and nothing is dropped:

- **Queue file** at the memory root (`todo.md`): `In Progress` (at most
  one), `Queued (FIFO)`, `Blocked`, `Done`.
- **Plan first:** every task gets a plan in `todo-plans/<slug>.md` before
  any work starts; the queue links to the plan.
- **Lifecycle:** work FIFO unless explicitly overridden; mark the active
  task `in_progress` with the worker/activity reference; dequeue it to
  Done (with the output link) when complete.
- **Enforcer watchdog (scheduled job, e.g. every 5 minutes):** reads the
  queue and the referenced plan/output files. It stays silent when the
  queue is empty or the active task shows recent activity. When the active
  task shows no file activity past the stall threshold (e.g. 45 minutes)
  AND no live worker is on it, the watchdog re-drives the task: re-reads
  the plan and respawns the worker from the next incomplete step. When
  queued tasks wait with nothing in progress, it promotes the next FIFO
  task and starts it. The threshold is a tripwire — it reports "may be
  stalled," not "failed" — because the watchdog sees files, not live
  agent state, so it checks for a running worker before re-driving.
- **Re-drive cap:** after N re-drives (e.g. 3) with no completion, stop
  and report to the user with the task slug and the plan's next step —
  never loop forever.
- Keep the schedule, thresholds, and cap in the cron body (see
  `references/cron-templates.md`, Job 5), not in this skill.

## Output Contract
- Memory root contains: a thin-router `MEMORY.md` (identity + pointers —
  never a fact store), personalization notes, `people/`, `groups/`,
  `topics/`, `meetings/`, `activities/`, `interests/`, `locations/` (each
  with an `INDEX.md`), `trace/` (`INDEX.md` + append-only `trace.md`),
  and dated daily logs.
- `trace/trace.md` is append-only, newest first, every entry source-cited.
- Three scheduled jobs keep the memory current: one daily collect/update/
  refine job, an optional lightweight watcher that surfaces urgent items
  between runs, and an optional nightly evaluation that audits the
  system's disciplines. All stay silent unless something is worth the
  user's attention.

## Operating Rules
1. The user's memory is private: never copy it into chats, logs, or shared
   artifacts beyond what the task needs.
2. Supersede, don't delete — history stays readable so any event's evolution
   can be followed.
3. Uncertain items are marked as such, never asserted.
4. Keep installation-specific details (account names, CLI commands, schedule
   times) in the local cron bodies and operating notes, not in this skill.
5. Validate the privacy protections with the muse-leakage-guard add-on after
   any change to the protection layer, and re-run its audit on a schedule —
   a protection nobody re-tests is a protection nobody has.
