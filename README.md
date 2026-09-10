# muse-memory

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![bash](https://img.shields.io/badge/made%20with-bash-4EAA25.svg)](bin/)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

Your AI assistant's long-term memory — as a system, not a junk drawer.

> Most assistant memory is either a pile of notes or a black box.
> **muse-memory** is a small, opinionated operating system for remembering
> what matters, forgetting what doesn't, and knowing the difference.

## Why

Assistants forget. When they do remember, it's usually one of two failure
modes: a sprawling dump of chat logs nobody can search, or a hidden vector
store nobody can audit. This takes a third path — **plain markdown files,
a strict routing discipline, and a temporal log** — so the memory stays
organized, searchable, and human-inspectable for years.

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
open/closed status. History is superseded, never deleted, so any event's
evolution stays readable.

## Quickstart

```bash
git clone https://github.com/joonlim-official/muse-memory.git
cd muse-memory

# 1. Create the memory skeleton (never overwrites existing files)
./bin/init-memory

# 2. Fill in MEMORY.md and memory/personalization.md with what you know
#    about the user. Nothing goes in without their approval.

# 3. Schedule the refresh — see references/cron-templates.md:
#    one daily collect/update/refine job, plus an optional lightweight
#    watcher that surfaces urgent items between runs. Both stay silent
#    unless something is worth the user's attention.
```

Requirements: `bash`, `git`. `ripgrep` optional (falls back to `grep`).
The skill text targets Claude-style agents, but the layout, conventions, and
scripts are assistant-agnostic — any agent that can read markdown and run
shell commands can use them.

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
```

The memory itself lives outside this repo (default: the user's home
directory). This repo ships the *system* — blank templates only, no personal
data.

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

[MIT](LICENSE) — use it, fork it, teach your assistant with it.
