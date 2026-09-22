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
   overwrites existing files.
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

### 3. Writing memory
- Route each fact to its home — see the routing table in
  `references/layout.md`.
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
- Every successful sync also writes a dated recovery snapshot page.
- Three-way reconciliation (base vs local vs remote): simultaneous edits
  are **conflicts — both versions preserved, neither overwritten**; the sync
  writes nothing until the whole plan is actionable, and a failed apply
  rolls back every completed step (all-or-nothing).
- Deletions are never destructive: an archived Notion page is reported,
  the local file is kept.
- Full contract in `references/notion-sync.md`. Synthetic tests:
  `python3 -m pytest tests/ -q` (fake transport, no credentials).

## Output Contract
- Memory root contains: curated memory file, personalization notes,
  `people/`, `groups/`, `topics/`, `meetings/`, `activities/`, `interests/`,
  `locations/` (each with an `INDEX.md`), `trace/`
  (`INDEX.md` + append-only `trace.md`), and dated daily logs.
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
