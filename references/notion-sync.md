# Notion two-way sync

Optional, stdlib-only Python component (`lib/notion_sync/`) that keeps a
muse-memory installation in two-way sync with Notion. The Bash core stays
zero-dependency; this is an opt-in layer for users who want Notion as a
human-friendly editing surface.

## Model

- **Notion is the editor, Markdown is the storage.** The memory's Markdown
  files remain the operational source of truth. Notion hosts a persistent
  **live page tree** (one page per managed file, titled by its relpath, e.g.
  `memory/people/jane-doe.md`) that a human can read and edit.
- **Two-way sync.** Local Markdown edits push to Notion; manual Notion edits
  pull back into the Markdown files (after a `bin/memory-guard` scan).
- **Dated snapshots.** Every successful sync also writes a dated recovery
  snapshot page (`Memory backup — YYYY-MM-DD`) with one child page per file.
  Snapshots are for recovery only — the live tree is what syncs.
- **Three-way reconciliation.** Per file, the engine compares the last
  synced base against the current local file and the current Notion page
  (canonical structural comparison, so formatting-only differences are not
  changes):

  | local changed | remote changed | action |
  |---|---|---|
  | no | no | clean |
  | yes | no | push local → Notion |
  | no | yes | pull Notion → local (guard-scanned) |
  | yes | yes | **conflict — preserve both, write neither** |

- **All-or-nothing.** The full plan (including every guard scan) is computed
  first. If anything is a conflict, hold, block, deletion, or error, **nothing
  is written** — no local files, no Notion edits, no snapshot, no state
  advancement. Only a fully actionable plan is applied, in order: pull →
  push → adopt → snapshot → advance state transactionally.
- **Deletions are never destructive.** A Notion page archived or deleted for
  a mapped file is reported; the local file is preserved.
- **New pages are adopted safely.** An unmapped hub child titled like a valid
  relpath is adopted as a local file only after route validation (no absolute
  paths, no `..` traversal, must stay under the memory root, known entity
  directories only), collision checks, and a guard scan.

## Setup

1. Create a Notion internal integration and copy its token.
2. Create (or pick) the hub page that will host the live tree, and share it
   with the integration. Copy the page ID.
3. Export the environment:

```bash
export NOTION_SYNC_MEMORY_ROOT="$HOME/memory"   # your memory installation
export NOTION_API_KEY="secret_..."              # integration token
export NOTION_HUB_ID="..."                      # hub page ID
# optional:
export NOTION_STATE_DIR="$HOME/.notion-sync"    # default: <root>/.notion-sync
export NOTION_TZ="America/Los_Angeles"          # snapshot title dates
export NOTION_SYNC_EXCLUDE="memory/bank/*"      # comma-separated globs
```

4. Initialize once: `bin/memory-notion-sync init`
5. Sync: `bin/memory-notion-sync sync`

## Commands

- `init` — first-time setup: maps each managed file to a hub page (adopting
  an existing same-titled page without overwriting, or creating it), pushes
  content, and establishes the three-way base. Guard-scans everything first.
- `sync` — full two-way sync. Exit 0: applied cleanly. Exit 1: conflicts /
  holds / blocks / deletions / errors — nothing was written; resolve and
  re-run. Exit 2: operational failure.
- `status [--json]` — show the computed plan without writing anything.
  Exit 1 when the plan is not fully actionable.
- `restore <snapshot-page-id> <staging-dir>` — restore a dated snapshot
  into a staging directory (never touches live files), with exact
  accounting: total files, byte-identical, canonically equivalent, genuine
  mismatches, live-only files.
- `version` — print the version.

## Guard integration

Incoming Notion content and outgoing Markdown content are both scanned with
`bin/memory-guard`:

- Exit 1 (secrets/credentials) → **hard block**, the file is excluded and the
  sync does not apply.
- Exit 2 (figures/personal data needing review) → **hold for human review**,
  the file is excluded and the sync does not apply.

Pass `--no-guard` only for tests or emergencies.

## Cron

The weekly backup job must stop immediately on any nonzero exit — never
back up, push, or advance state after a conflict, hold, block, or failure:

```bash
bin/memory-notion-sync sync || exit 1
```

See `references/cron-templates.md` for the full job template.

## State

All sync state lives under `NOTION_STATE_DIR` (default `<root>/.notion-sync`,
never inside the managed tree):

- `pages.json` — relpath → Notion page ID mapping
- `base/` — last-synced per-file content (the three-way base)
- `conflicts.json`, `deletions.json` — records needing human attention
- `snapshots.json` — date → snapshot page ID

## Tests

`tests/test_notion_sync.py` runs the full suite against the in-memory fake
transport — no credentials, no network: `python3 -m pytest tests/ -q`.
