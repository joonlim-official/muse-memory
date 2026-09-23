# Feed personalization from memory

A Muse **Feed** (the user's personal newspaper in the Feed tab) can be
grounded in the memory system so every post says concretely why it
matters to *this* user. Without grounding, the feed prompt is generic
("make me a feed about my interests") and posts lean on generic hooks.
With grounding, posts read from the reader's profile, entity pages, and
past coverage — the feed becomes a default benefit of having memory, not
a second prompt the user has to engineer by hand.

## Procedure

1. Read the memory profile (`MEMORY.md` / the central profile), the
   personalization notes, and the `INDEX.md` files under
   `people/`, `groups/`, `topics/`, `meetings/`, `activities/`,
   `interests/`, and `locations/`. Skim at most a few matching pages —
   enough to name the reader's durable interests, routines, projects,
   and money habits.
2. Compose the feed prompt from that reading:
   - Name the concrete beats: interests with their specific angles
     (e.g. "eval design for agentic AI", not "AI"), ongoing projects,
     family routines, money habits (itemized tracking, pending charges,
     fee/spike flags), and the reader's own tone wishes.
   - Require a concrete "why it matters to me" in every post: tied to a
     specific interest, project, or routine — never a generic hook.
   - Keep the standing tone: clear and direct, quick to skim, no
     clickbait.
3. Apply it with the feed tools (`feed.prompt_update` on Muse). A real
   change to the prompt starts a fresh generation immediately.
4. Re-ground when memory changes materially: a new durable interest, a
   new project, a routine that shifted. A monthly check inside the
   daily refresh is plenty; don't churn the prompt over transient news.

## Rules

- The feed prompt is **derived from memory, never new memory itself**:
  nothing about the user goes into memory files without their approval
  (see `references/privacy-and-validation.md`). The prompt may quote
  approved memory freely — it lives inside the user's Muse account.
- Public docs and examples stay **synthetic and impersonal**: never
  publish a real user's feed prompt or post excerpts. Illustrate with a
  fictional reader (e.g. someone who follows Formula 1 and sourdough
  baking).
- Financial figures belong in the feed only where the reader's own
  rules allow them (their feed is a private surface, like chat).
- Past posts count: the writer avoids repeats, so a grounded prompt
  gets sharper over time as coverage accumulates.

## Example (synthetic)

A fictional reader's memory shows: Formula 1 (tactics, not celebrity),
sourdough (crumb structure experiments), two kids in weekend soccer.

Grounded prompt (excerpt):

> Write me a daily paper grounded in what you know about me. I follow
> F1 for race strategy and tyre calls, and I bake sourdough chasing an
> open crumb. My kids play weekend youth soccer. Every post must say
> concretely why it matters to me — a strategy decision that maps to a
> race I watched, a technique that fixes a bake I attempted — never a
> generic hook. Keep every unit clear and direct, quick to skim, no
> clickbait.

The same beats without memory would have been "motorsport, cooking,
family" — and the posts would read like it.
