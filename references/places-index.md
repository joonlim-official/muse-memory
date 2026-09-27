# Places index

## Why

Location questions are among the most repeated in a personal memory:
"when did we last go there?", "what's the address?", "where does the
training happen?". Without a dedicated home, the answers scatter across
daily logs and get re-derived every time — and one-off mentions get
promoted into durable facts by accident.

A places index is the fix: one page per significant, recurring place,
each carrying its address, what happens there, and a dated visit log.
The visit log is the whole point — it turns "when did we last go there?"
from a search into a lookup.

## What it holds

- `locations/INDEX.md`: one line per place — name, page path, one-line
  summary. Ordered most-important-first. This is the map; read it before
  any page.
- One page per significant place (`<slug>.md`): home, workplace, school,
  training venues, frequent restaurants and cafes. Create a page when a
  place **recurs** — never for a one-off mention.
- Page schema:
  - YAML frontmatter: `name`, `summary`, `updated: YYYY-MM-DD`.
  - `# <Name>` title.
  - `## Facts`: address, what happens there, durable facts — each with a
    source; stale-prone facts (hours, prices) dated "as of YYYY-MM-DD".
  - `## Visits`: reverse-chronological dated visit log, one line per
    visit (`YYYY-MM-DD — what happened`). This answers "when did we last
    go there?".
  - `## Related`: links to the person/group/topic pages the place
    connects to.

## The recall procedure

Whenever a location entity comes up in a turn:

1. Read `locations/INDEX.md`.
2. Read the matching page(s) — at most 1–3 per turn, the same budget as
   every other entity area.
3. Answer from the page: address from Facts, recency from Visits. Fall
   back to search only when the page doesn't cover it.

Never promote a one-off mention into a page mid-turn; file it in the
daily log instead.

## Linkage

- Topic pages that involve venues (a sport, travel, dining) carry a
  one-line pointer to the places index.
- Person pages may link a place under Related when the association is
  durable (a coach and their training ground).
- The central profile links the index from its household section.

## Maintenance

- Log visits as they happen — a visit log reconstructed months late is a
  reconstruction, not a record.
- Refresh stale-prone facts when noticed; keep the "as of" dates honest.
- Retire pages for places that stop recurring (supersede, don't delete).
- Place pages are the user's private data: addresses stay on private
  surfaces and are never used in public material. All public examples of
  this pattern stay synthetic and impersonal.

## Synthetic example

A page, impersonal by construction — no real names or addresses needed
to show the shape:

```
---
name: Cafe A
summary: Neighborhood coffee shop; weekend morning regular.
updated: 2026-09-27
---

# Cafe A

## Facts

- 100 Example St, Sampletown. (src: web listing, 2026-09-27)
- Weekend morning coffee spot. Hours as of 2026-09-27: daily 7 AM–3 PM.

## Visits

- 2026-09-27 — coffee with a friend.
- 2026-09-20 — coffee, read the paper.

## Related

- Topic: dining out (synthetic)
```

And its index line:

```
- **Cafe A** — `~/memory/locations/cafe-a.md` — neighborhood coffee shop; weekend morning regular.
```
