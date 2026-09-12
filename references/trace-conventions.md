# Trace conventions

`~/memory/trace/trace.md` is the temporal log: what was learned, what changed,
what opened, what closed. It answers "what is the latest knowledge, and how
did we get here?"

## Format

- Append-only, **newest first**. New entries go at the top.
- One entry per significant change, **one line**:
  `- [area] status |type| — what changed (src: where it came from)`
- Every entry cites its source: a daily log, a message, a verified record, or
  the user's own words.

## Types

Each entry carries a type — a retrieval aid, not a taxonomy debate:

| Type | Meaning |
|---|---|
| `fact` | A durable, verifiable fact |
| `preference` | A standing like/dislike or rule the user set |
| `decision` | A choice the user made (or is weighing) |
| `learning` | A conclusion or lesson drawn from experience |
| `relationship` | Something about how people connect |
| `context` | Background that frames other entries |

## Expiry

Facts with a known shelf life carry `valid_until: YYYY-MM-DD` (e.g.
trip-specific plans). The scheduled refine pass auto-expires them:
supersede/close with the date when the date passes. Facts that merely go
stale (follower counts, prices) carry `as of YYYY-MM-DD` instead.

## Statuses

| Status | Meaning |
|---|---|
| `new` | Something learned or created that didn't exist in memory before |
| `updated` | An existing fact changed |
| `superseded` | An old entry replaced by a newer state (old entry stays, points forward) |
| `open` | A task, event, or question not yet resolved |
| `closed` | An open item resolved, or a finished piece of work |

## Lifecycle rules

- **Supersede, don't delete.** Old entries stay in place with a pointer to
  what replaced them, so any event's evolution is readable from the log.
- **Open items stay visible.** Keep an "Open threads" section (or mark
  entries `open`) for anything unresolved: upcoming events, pending
  information, unmade decisions.
- **Closing an item** gets two writes: the open thread becomes
  `[x] YYYY-MM-DD — how it resolved`, plus a `closed` trace entry.
- **Don't close on elapsed time alone.** An event closes when there is
  outcome evidence, not merely because its date passed.

## Human-in-the-loop decisions (the learning signal)

When the system asks the user to judge something (figure flags, stale or
conflicting facts, proposed skill patches, spot-check verdicts), the
user's call is recorded as a `|decision|` entry that carries the full
signal — what was proposed, what was chosen, and why:

`- [area] decision |decision| — <chosen action> (proposed: <what the system recommended>; rationale: <why the user chose it>) (src: user, YYYY-MM-DD)`

These entries are the system's reward signal. Over time they teach the
proposer what the user actually wants — proposals align with recorded
decisions, and repeated overrules on the same question mean the system's
default is wrong and should be patched. This is reinforcement learning
with a human in the loop, minus the neural net: the machine proposes,
the human judges, the decisions compound.

## What earns a trace entry

Significant changes: new durable facts, corrections, completed projects,
decisions, opened/closed threads, preference changes. Not every micro-edit —
routine refinements are covered by the daily log.

Significant changes: new durable facts, corrections, completed projects,
decisions, opened/closed threads, preference changes. Not every micro-edit —
routine refinements are covered by the daily log.
