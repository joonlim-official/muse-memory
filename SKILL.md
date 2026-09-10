---
name: "personal_memory_system"
description: "Set up and operate a durable personal memory for an AI assistant: organized facts by person and topic, a temporal trace of what changed, search tooling, and a scheduled collect/update/refine job."
---

# Personal Memory System

## Purpose
Give an AI assistant a long-term memory that stays organized, searchable, and
current: curated facts by topic and person, a temporal log of what changed and
what is still open, and a scheduled job that collects, updates, and refines it.

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
- When a person, group, or topic is in play, read their page in addition to
  searching.

### 3. Writing memory
- Route each fact to its home — see the routing table in
  `references/layout.md`.
- Every significant change gets a dated trace entry, newest first — see
  `references/trace-conventions.md`.
- Follow `references/privacy-and-validation.md`: the approval rule, what
  never goes into memory, and the validate-against-ground-truth rule.

## Output Contract
- Memory root contains: curated memory file, personalization notes,
  `people/`, `groups/`, `topics/` (each with an `INDEX.md`), `trace/`
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
