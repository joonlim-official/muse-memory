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
  push → adopt → snapshot → advance state transactionally. Every mutation is
  journaled before it happens: if a write fails mid-apply, completed steps
  are rolled back (local files restored, remote pages restored to their prior
  blocks or archived when newly created) before the error surfaces, so a
  failed sync never leaves a half-applied state.
- **Push is incremental.** A local edit is diffed against the page's current
  blocks and only the difference is applied: changed blocks are updated in
  place (block ids preserved), new blocks appended, removed blocks
  archived. Blocks the sync cannot represent (child pages, images, embeds,
  …) are never touched. Per-block comments or history on replaced or
  archived blocks are not preserved. When the canonical content is
  unchanged the push makes zero write API calls.
- **Reorder is positional.** The differ aligns blocks positionally — blank
  lines anchor the alignment only where they sit at the same index on
  both sides, so adding/removing a blank line never cascades churn into
  later blocks; same-type blocks at aligned positions are updated in
  place, so reorders keep every block id stable. The Notion API has no
  move operation.
- **Round-trip fidelity.** Local → Notion → local is byte-identical except
  for documented normalizations: H4–H6 map to H3 (Notion has three heading
  levels — the only lossy case, deterministic and stable on re-parse);
  `*`/`+` bullets become `-`, list indentation becomes 2 spaces per level,
  and numbered values restart at 1 (Notion stores no marker, indentation,
  or numbered value — `canonical()` treats all of these as equal, so they
  never churn a sync); `***`/`___` dividers become `---`, `:---` table
  alignment becomes `---`, `__bold__` becomes `**bold**`; Notion
  normalizes link URLs on write (lowercases scheme/host, appends `/` to
  bare domains — `canonical()` treats pre/post forms as equal, so this
  never churns a sync; after a pull the local file carries Notion's
  form); trailing blank lines collapse to the single final newline.
  Blank-line runs, nested-list structure, code-block indentation, leading
  whitespace, quotes, todos, dividers, tables, and inline formatting all
  survive byte-identical. No invisible characters are used anywhere in
  the encoding.
- **Live API notes (verified 2026-09-23).** The append endpoint rejects
  nested `children` in the payload (400), so child blocks are appended
  to their created parent in a second pass, recursively; a table block
  can only be created with its rows nested inside `table.children`;
  prepending uses the typed position object `{"position":
  {"type": "start"}}` (omitting `after` appends at the end).
- **Deletions are never destructive.** A Notion page archived or deleted for
  a mapped file is reported; the local file is preserved.
- **New pages are adopted safely.** An unmapped hub child titled like a valid
  relpath is adopted as a local file only after route validation (no absolute
  paths, no `..` traversal, no hidden directories, must stay under the memory
  root, known entity directories only), collision checks (including
  case-insensitive), reserved-name checks (`INDEX.md` is never adopted), and
  a guard scan. Titles pointing at `memory/bank/` (runtime-managed) or
  date-stamped daily logs (`memory/YYYY-MM-DD.md`) are never adopted. A
  successful adoption also appends the new file to its directory's `INDEX.md`
  (when one exists; otherwise it is reported).

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

- `init` — first-time setup: maps each managed file to a hub page. A
  same-titled page that is empty is seeded with the local content; one whose
  content matches is adopted without rewriting; one whose content *differs*
  is reported (exit 1) and left untouched on both sides — a human aligns the
  contents and re-runs. Guard-scans everything first.
- `sync` — full two-way sync. Exit 0: applied cleanly. Exit 1: conflicts /
  holds / blocks / deletions / errors — nothing was written; resolve and
  re-run. Exit 2: operational failure (a mid-apply failure rolls back every
  completed step before surfacing).
- `status [--json]` — show the computed plan without writing anything.
  Exit 1 when the plan is not fully actionable.
- `restore <snapshot-page-id> <staging-dir>` — restore a dated snapshot
  into a staging directory (never touches live files), with exact
  accounting: total files restored, byte-identical, canonically equivalent,
  genuine mismatches, snapshot-only files (in the snapshot but not live),
  live-only files (live but not in the snapshot). Exit 1 when any file
  genuinely mismatches.
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
That includes end-to-end CLI runs through the real `bin/memory-notion-sync`
wrapper (the fake persists across subprocesses via `NOTION_SYNC_FAKE_FILE`),
covering exit codes 0/1/2 for init, sync, status, and restore.
