# Contributing to muse-memory

Thanks for considering a contribution. This is a small, opinionated project —
the bar for changes is: *does this make the memory more truthful, more
findable, or quieter?*

## Ground rules

- **No personal data, ever.** Not in code, comments, tests, or examples.
  Use obvious placeholders (`Jane Doe`, `jane@example.com`) in any sample
  content.
- **Keep it portable.** Scripts are POSIX-flavored bash; avoid GNU-only or
  macOS-only flags without a fallback (see `memory-grep`'s `rg` → `grep`
  fallback as the pattern to follow).
- **Match the tone of the docs.** Plain language, concrete examples, no
  filler. If a section doesn't earn its place, cut it.
- **Run `bin/memory-guard`** on anything you add before opening a PR.

## What makes a good PR

- A bug fix in a script, with a note on how you tested it.
- A clearer sentence in the docs (small doc PRs are genuinely welcome).
- A new reference or asset template, if it fills a real gap — open an issue
  first to discuss whether it belongs.

## What probably doesn't belong

- New dependencies. The whole point is zero-dependency bash + markdown.
- Features that add noise: telemetry, dashboards, analytics. The quality
  discipline already covers auditing; anything beyond that is out of scope.
- Changes to the trace entry format without discussion — it's the one
  backward-compatibility surface in the project.

## Process

1. Fork, branch, commit with a clear message.
2. Test scripts with `bash -n` and a real run (`init-memory` into a temp dir
   is the standard smoke test — it's idempotent by design).
3. Open the PR with a short description of *why*, not just *what*.
