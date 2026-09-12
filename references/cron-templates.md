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
   threads older than 30 days, full guard scan, and a retrieval self-test
   via `bin/memory-retrieval-test` against the installation's query file).

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
   expired items, open threads older than 30 days, full guard scan, and a
   retrieval self-test: run `bin/memory-retrieval-test <query-file>` where
   the query file (kept with the installation, not the skill) lists
   `<query> ||| <expected-file>` lines grounded in real, stable facts.
   A failing query means a fact drifted from its home — fix the routing,
   don't just re-file the fact. Two weeks of failures on the same query
   is a system problem: patch the routing table or the test. Also run 2-3
   concept queries through semantic search by hand and confirm the right
   page ranks — keyword retrieval is machine-testable, semantic is not.]

RETRIEVAL SELF-TEST (weekly, part of the health audit): retrieval is the
one axis the nightly `bin/memory-audit` cannot check deterministically,
so the weekly audit covers it. Keep the query file current: when the
memory moves a fact to a new home, update the expectation — the test
failing after a move is the test working, not the memory breaking.

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
the job that catches drift the daily refresh missed. The skill ships
`bin/memory-audit`, which runs the checks deterministically.

```markdown
Nightly evaluation of the personal memory system. This job evaluates
only — it never writes to memory files. Stay silent unless something
needs the user's attention.

1. Run `bin/memory-audit [memory-root]` (set $MEMORY_WATERMARK_FILE to
   the refresh job's watermark to enable the watermark check). It checks:
   guard scan (secrets = exit 2, figures = exit 1 item), trace entry
   format, expired valid_until items still open, open threads older than
   30 days, duplication drift across curated files, daily-log dating, and
   the refresh watermark. It prints a markdown report and exits 0 clean /
   1 issues / 2 secrets.
2. Review the report. Secrets (exit 2) = alert the user immediately,
   naming file and line.

SELF-FEEDBACK LOOP: the audit doesn't just report — it improves the
system. For each finding, ask: is this an *instance* problem or a
*system* problem?
- Instance problem (one bad entry, one missed expiry) → fix the memory
  files per the routing table and add a trace entry.
- System problem (the same check fails 2+ nights running) → the system
  is wrong, not the data. Patch the skill itself: tighten the doc, fix
  the script, add a routing row. Record it as a |learning| trace entry
  so the fix is visible in the log.
The loop closes when a night goes clean because the system got better,
not because someone hand-fixed the symptoms again.

DELIVERY: one short message, only if something needs the user's
attention (secrets, a system problem worth their approval, a finding
the user should know about). Otherwise stay completely silent — no news
is good news.
```

The loop is what makes the three jobs a system rather than three chores:
the refresh maintains the memory, the audit checks the maintenance, and
the feedback step fixes the maintainer.

HUMAN AUDITOR: the system handles mechanical fixes itself (dedupe,
expiry, format, watermark). Anything requiring *judgment* goes to the
user with evidence and a recommendation — the user decides, the system
does not. That includes: figure-review flags (present what was found and
whether it looks approved; never auto-delete), stale or contradictory
facts (present the conflict and the proposed resolution; apply only on
the user's word), proposed skill patches (propose, wait for go-ahead),
and semantic spot-check verdicts (report what was checked; the user
confirms). Record the user's decision as a `|decision|` trace entry.
This is the backstop that keeps an autonomous memory system aligned:
the machine does the measuring, the human does the judging.

## Notes

- Give each job a stable kebab-case id and a clear title.
- The refresh job owns the watermark files; the watcher owns its own
  watermark so the two never interfere.
- If the platform supports goal-owned schedules, attach both jobs to the
  memory goal so their lifecycle follows it.
