# muse-memory

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![bash](https://img.shields.io/badge/made%20with-bash-4EAA25.svg)](bin/)
[![zero dependencies](https://img.shields.io/badge/dependencies-zero-blue.svg)](bin/)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

**Give your AI assistant a memory that compounds.**

> Chat transcripts are a junk drawer. Vector stores are a black box.
> **muse-memory** is a small, opinionated operating system for long-term
> memory: plain markdown files, a strict routing discipline, and an
> append-only temporal trace — so your assistant remembers what matters,
> forgets what doesn't, and can always tell you *how it knows*.

## The problem

AI assistants forget everything between sessions — or worse, they
"remember" things you can't see, can't correct, and can't trust. The two
usual answers both fail:

- **A pile of chat logs** — searchable in theory, a swamp in practice. Six
  months in, nothing is findable and contradictions pile up silently.
- **A hidden vector store** — convenient, opaque. You can't audit what it
  believes about you, and neither can it.

muse-memory takes a third path: **your memory as files you own.** Every fact
has exactly one home, every change is logged with its source, and history is
superseded rather than deleted — so the whole evolution of any belief stays
readable.

## What it feels like

Six months in, a question about something from last spring:

> **User:** "What did we decide about the home gym?"
>
> **Assistant:** "You ruled out the garage in March — too cold in winter,
> and the space was reserved for the workshop. The decision landed on the
> spare room with a foldable rack, superseding the garage plan on
> 2026-03-14 (sourced from the planning thread). Want to revisit it?"

*(Synthetic example.)* No hallucinated confidence. No "as an AI I don't
have memory of that." The answer carries its own provenance — *what*
changed, *when*, and *where it came from*.

## Clear wins

*(All examples below are synthetic — they show the mechanics, not anyone's
data.)*

**1. The plan that changed — without losing history.**
A trip planned for April moves to October. The trace now reads:

```markdown
- [travel] superseded |decision| — Trip moved from April to October;
  April fares were 2x October's. Replaces the 2026-02-10 plan.
  valid_until: 2026-10-31. (src: user's message, 2026-03-02)
```

Six months later the assistant doesn't quote the dead April plan — and if
asked "wait, didn't we say April?", the full evolution is right there.

**2. The expiry that fired on its own.**
A trace entry carries `valid_until: 2026-05-01` on a hotel promo under
consideration. The weekly audit finds the date has passed, marks the entry
`superseded`, and closes the open thread. Nobody has to remember to clean
it up — the system does, and the log shows exactly when.

**3. The secret that never got written.**
An API key gets pasted into chat during debugging. The drafted memory
update includes it; `bin/memory-guard` scans the draft and exits 1 —
**BLOCKED: secrets detected**. The key never touches a memory file.
Financial figures get the softer treatment: flagged for human review,
never auto-deleted, never silently kept.

**4. The contradiction it refused to bury.**
The calendar shows a dentist appointment Tuesday; later the user says "I
moved the dentist to Thursday." Instead of silently overwriting, the old
entry is marked `superseded` with a pointer to the new one, both
source-cited. When the Tuesday reminder confusion comes up, the answer is
in the log — not in someone's faulty recollection.

## How it works

```
  collect                    organize                     recall
┌──────────┐   route by   ┌─────────────────────┐  index-first  ┌──────────┐
│ daily job │──kind──────▶│ MEMORY.md             │─────────────▶│ answer   │
│ + watcher │             │ people/ groups/       │  ≤3 pages    │ grounded │
└──────────┘   trace every│ topics/               │  verify old  │ in what  │
               change     │ trace/ (append-only)  │  facts       │ changed  │
                          └─────────────────────┘              └──────────┘
```

Three disciplines keep it honest:

- **Write discipline** — the default is *not* to write. A write must be
  durable (matter in 30+ days), grounded in a source, and not duplicated.
  `bin/memory-guard` scans every write: secrets are a hard block, financial
  figures are flagged for human review.
- **Read discipline** — read the index first, load at most 1–3 relevant
  pages, surface nothing rather than noise. Facts older than ~90 days are
  re-verified or labeled stale.
- **Quality discipline** — a weekly audit counts entries per area, expires
  `valid_until` items, surfaces open threads older than 30 days, and runs a
  full guard scan. Mechanical fixes apply automatically; judgment calls go to
  the human.

Every significant change also lands in the **temporal trace** — an
append-only, newest-first log with typed entries (`fact`, `preference`,
`decision`, `learning`, `relationship`, `context`), source citations, and
open/closed status. History is superseded, never deleted. (See "Clear wins"
above for what this looks like in practice.)

## Compared to the alternatives

| | Chat logs | Vector memory services | muse-memory |
|---|---|---|---|
| You can read it | technically | no | yes — it's markdown |
| You can correct it | no | no | yes — edit the file |
| Knows *how* it knows | no | no | yes — every entry cites its source |
| Contradictions | pile up silently | pile up silently | superseded, never deleted |
| Your data leaves your machine | depends | yes | never |
| Dependencies | none | SDK + API + billing | bash |

If you want memory-as-a-service with embeddings and managed infrastructure,
use a memory API. If you want memory-as-files you fully own and can audit
with `grep`, this is it.

## Who it's for

- **For:** people who live in an AI assistant daily and want it to
  genuinely know them — their family, projects, preferences, and history —
  without re-explaining everything every session.
- **For:** the privacy-minded — nothing leaves your machine, and the guard
  blocks secrets and financial figures from ever entering memory.
- **Not for:** anyone who wants zero setup. You write the first page about
  yourself, and you schedule one daily job. After that it runs itself.

## Quickstart

```bash
git clone https://github.com/joonlim-official/muse-memory.git
cd muse-memory

# 1. Create the memory skeleton (never overwrites existing files)
./bin/init-memory

# 2. Fill in MEMORY.md and memory/personalization.md with what you know
#    about the user. Nothing goes in without their approval.

# 3. Schedule the jobs — see references/cron-templates.md:
#    one daily collect/update/refine job, an optional lightweight
#    watcher that surfaces urgent items between runs, and an optional
#    nightly evaluation that audits the system's disciplines. All stay
#    silent unless something is worth the user's attention.
```

Requirements: `bash`, `git`. `ripgrep` optional (falls back to `grep`).
The skill text targets Claude-style agents, but the layout, conventions, and
scripts are assistant-agnostic — any agent that can read markdown and run
shell commands can use them.

After 30 days you have: a curated profile of the user, per-person and
per-topic pages, a temporal log of everything that changed, and a weekly
audit keeping it all honest. After a year, it's the closest thing to an
assistant that actually knows you.

## Layout

```
SKILL.md            the skill: setup, reading, writing, operating rules
references/         layout & routing table · trace conventions ·
                    privacy & validation · cron templates
assets/             starter templates: MEMORY.md, person/group/topic pages,
                    personalization, trace + indexes
bin/
  init-memory       create the directory skeleton (idempotent)
  memory-grep       keyword search across the memory tree (exact identifiers)
  memory-guard      pre-write scanner: secrets block, figures get flagged
  memory-audit      nightly audit: format, expiry, stale threads, drift,
                    dating, watermark — evaluates, never writes
```

The memory itself lives outside this repo (default: the user's home
directory). This repo ships the *system* — blank templates only, no personal
data.

## FAQ

**Why not just use embeddings / a vector DB?**
You can — nothing here forbids it. But retrieval isn't the hard part of
memory; *curation* is. Vectors find similar text; they don't resolve
contradictions, expire stale plans, or tell you where a belief came from.
This system does the curatorial work, in files you can read. Add embeddings
on top later if you want them.

**Does it work with my agent / model?**
If your agent can read markdown and run shell commands, yes. The
conventions are plain text; the scripts are bash. The skill prose targets
Claude-style agents but nothing in the layout is model-specific.

**How big does the memory get?**
Small. The write discipline ("default is not to write") keeps curated files
tight — durable facts only. Day-to-day detail goes in dated logs, and the
weekly audit expires and dedupes. A year of daily use is typically a few
hundred kilobytes of markdown.

**What if the assistant writes something wrong?**
That's what the trace is for. Correct the file, add a `superseded` entry
pointing at the fix, and the mistake stays visible as history instead of
silently corrupting the record.

**Is my data safe?**
The repo contains zero personal data by design — only the system and blank
templates. Your memory lives on your machine. `memory-guard` blocks secrets
and flags financial figures on every write.

## Privacy & safety

- **This repo contains no personal data by design** — only the system and
  blank templates. Your memory never leaves your machine.
- **Never store credentials or exact financial figures** in memory, skills,
  or operational docs. `memory-guard` enforces this on every write.
- **Approval rule:** nothing is saved without the user's approval, except
  standing routines they explicitly requested.
- Every entry must trace to ground truth (a log, a verified extraction, or
  the user's own words). Uncertain items are marked as such, never asserted.

See [references/privacy-and-validation.md](references/privacy-and-validation.md)
and [SECURITY.md](SECURITY.md).

## Contributing

Small, focused PRs are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).
The guiding question for any change: *does this make the memory more
truthful, more findable, or quieter?*

## License

[MIT](LICENSE) — use it, fork it, teach your assistant with it. If it
remembers you well, tell someone.
