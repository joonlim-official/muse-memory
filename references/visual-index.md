# Visual index

## Why

The assistant keeps no persistent visual memory between turns: an image
arrives as tokens in the current context window and is gone afterwards.
There is no face database and no embedding search — recognition is a
per-turn, in-context judgment over what is visible right now, combined
with whatever the text memory says about who people are.

A visual index is the workaround: a small "dictionary" of reference
photos plus stable visual features that gets loaded into context whenever
a new photo needs identifying. Without it, matching runs on the text
description alone ("the younger child"), which decays fast as people —
especially children — change.

## What it holds

- One index file, kept next to the user's reference photos. Per person
  it records: each reference photo (who is who in it), stable features
  (relative age/size, hair — coarse, never biometric templates), and
  dated volatile anchors (clothing, accessories — strong short-term
  signals that expire as wardrobes change).
- The reference photos themselves, under stable filenames.
- The index's own recall procedure (below), so any future turn follows
  the same steps.

## The recall procedure

Whenever the user sends a photo asking who is who — or a new photo where
identities matter:

1. Read the index.
2. Read the reference photo(s) for the people in question into context.
3. Compare in-context: bind names via stable features first, volatile
   anchors second.
4. Never assert an identity off a single weak cue; say when unsure.

Never identify from the text description alone when reference photos
exist.

## Linkage

- Person pages carry an `Appearance` pointer section with their reference
  photo paths, so the normal entity-resolution flow surfaces them.
- Topic pages where visual identification matters (a sport the children
  play, family travel, school) carry a one-line pointer to the index.
- The central profile links the index from its household section.

## Maintenance

- Refresh reference photos as people change (children grow: roughly
  yearly, or when appearance changes noticeably); retire stale volatile
  anchors rather than letting them mislead.
- Reference photos are the user's private data: they stay on private
  surfaces and are never used in public material. All public examples of
  this pattern stay synthetic and impersonal.

## Synthetic example

An index entry is impersonal by construction — no real names needed to
show the shape:

```
Person A (older child)
  refs: park-2026.jpg (left, red cap); lake-2026.jpg (right, blue jacket)
  stable: taller of the two children, short dark hair
  volatile (2026-05): red cap — strong while current
```
