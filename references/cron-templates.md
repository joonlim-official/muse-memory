# Cron templates

Three jobs. Adapt the bracketed placeholders to the installation: account
names, CLI commands, schedule times, and the user's timezone. Keep
installation-specific detail in the job bodies, not in the skill.

## Job 1 — Daily refresh: collect, update, refine

Runs once a day (morning is typical). One job that:

1. **Collects** — re-reads the user's connected sources for what's new
   since a watermark date: email (signal categories only — define which
   are signal vs noise for this user), calendar (past week / next two
   weeks), notes app, social accounts (the user's own activity only), and
   any secondary AI the user uses (ask it what changed since the watermark).
2. **Updates** — folds genuinely new, durable facts into the curated files
   per the routing table (`references/layout.md`); appends a daily log;
   adds trace entries for significant changes.
3. **Refines** — supersedes outdated entries instead of deleting them;
   dates stale-prone facts ("as of YYYY-MM-DD"); expires facts whose
   `valid_until` passed; resolves open trace threads that new evidence
   closes; deduplicates facts that drifted into multiple files; runs the
   `bin/memory-guard` scan; validates everything against ground truth.
   A weekly run adds a health audit (entry counts, expired items, open
   threads older than 30 days, full guard scan).

Template body (adapt freely):

```markdown
Each morning, refresh the user's memory from their connected sources and
refine it.

STANDING RULES:
- [Define signal vs noise per source, e.g. which inbox categories matter.]
- Only the user's own activity is signal on social sources.
- Never extract secrets, credentials, account numbers, government IDs.

WORKFLOW:
1. Read the watermark file [path] (ISO date). If missing, use the last 2 days.
2. [Source 1: e.g. email — search for durable new facts since the watermark.]
3. [Source 2: e.g. calendar — scan for new recurring patterns.]
4. [Source 3: e.g. notes — read changed pages, extract durable facts.]
5. [Optional: secondary AI delta sync — ask what changed since the watermark.]
6. Merge what's new AND refine (edit in place, keep file structure):
   Signal gate: default is NOT to write. Write only what is durable (will
   matter in 30+ days), grounded (traceable to a source), and not already
   recorded. Never save transient chit-chat, raw quotes, or duplicates.
   - [curated files per routing table]
   - [daily log] — dated entry of what changed.
   - [trace] — one dated entry per significant change, newest first, one
     line: `[area] status |type| — what changed (src: source)`. Types:
     fact / preference / decision / learning / relationship / context.
   Refine pass: supersede contradictions (never silently overwrite); date
   stale-prone facts; expire entries whose `valid_until` passed; close
   resolved open threads; deduplicate drifted copies; run
   `bin/memory-guard` (secrets = block, figures = flag for user review);
   never write figures or credentials into memory; validate every entry
   against ground truth.
7. Update the watermark with today's date.
8. [Optional: on one run per week, a health audit — entry counts per area,
   expired items, open threads older than 30 days, full guard scan.]

CORRECTION WATCHER (recommended): when scanning recent conversations,
watch for corrections ("no", "actually", "that's wrong", "don't") — each
one is a learning. Update the wrong memory, add a `|learning|` trace entry,
and record what the correction teaches about the user's preferences.

DATING DISCIPLINE: the daily log filename is always the user's *local*
date (`YYYY-MM-DD` in their timezone), never UTC. A run that crosses
midnight still files under the date the user experienced.

WATERMARKS: each job owns its watermark file (ISO date or datetime, one
value, no prose). The refresh job and the watcher use *separate* watermark
files so the two never interfere. A missing watermark means "look back 2
days", not "start from zero".

READ DISCIPLINE (for the agent using this memory): read the index first,
then at most 1–3 pages relevant to the task — never preload the whole
tree. Surface nothing rather than noise. Re-verify facts older than ~90
days before asserting them.

DELIVERY: Stay silent unless something is meaningfully new AND worth the
user's attention right now. Routine runs update the files and say nothing.
```

## Job 2 — Watcher: urgent items between refreshes (optional)

A lightweight interval job (e.g. every 4 hours) for time-sensitive
awareness. It never writes to memory files and never runs heavy syncs.

```markdown
Lightweight check for genuinely urgent new items. Never writes to memory
files, never runs heavy syncs.

WORKFLOW:
1. Read the watermark [path] (ISO datetime). If missing, look back [interval + 1h].
2. [Fast source scan, e.g. email signal categories] for items newer than
   the watermark.
3. Flag ONLY genuinely urgent, time-sensitive items: [define for the user —
   e.g. school notices requiring action today, travel disruptions].
4. Update the watermark with the current time.

DELIVERY: Stay silent unless something is truly urgent. Between [quiet hours],
only interrupt for what cannot wait until morning; hold the rest for the
daily refresh. When urgent, send one short message naming what it is and
what action is needed — nothing else.
```

## Job 3 — Nightly evaluation (optional but recommended)

A short nightly audit that verifies the memory system is holding its
disciplines. It EVALUATES ONLY — it never writes to memory files. This is
the job that catches drift the daily refresh missed.

```markdown
Nightly evaluation of the personal memory system. This job evaluates
only — it never writes to memory files. Stay silent unless something
needs the user's attention.

CHECKS (run each night):
1. Guard scan: run `bin/memory-guard` over the memory tree. Secrets
   (exit 1) = alert immediately, naming file and line. Figures (exit 2) =
   include in the report for the user's review.
2. Trace format: read the top 40 lines of the trace log. Every entry must
   be one line, carry a |type|, and cite a source (src:). List malformed
   entries.
3. Expiry: find `valid_until` dates in the past on entries still marked
   open/new/updated. List them — the daily refresh should have expired
   them.
4. Open threads older than 30 days: list them.
5. Duplication drift: check whether the same long passage (3+ lines)
   appears verbatim in more than one curated file. List duplicates found.
6. Daily log check: confirm today's daily log exists and is filed under
   the user's local date (never UTC). Flag missing or future-dated logs.
7. Refresh-job check: read the refresh job's watermark file. If missing
   or older than yesterday, the daily refresh may have missed a run —
   flag it. (Skip this check until the refresh job has had its first
   scheduled run.)

DELIVERY: one short message, only if something above needs attention
(secrets, malformed entries, missed refresh, new duplication drift).
Otherwise stay completely silent — no news is good news.
```

## Notes

- Give each job a stable kebab-case id and a clear title.
- The refresh job owns the watermark files; the watcher owns its own
  watermark so the two never interfere.
- If the platform supports goal-owned schedules, attach both jobs to the
  memory goal so their lifecycle follows it.
