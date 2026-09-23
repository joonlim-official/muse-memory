# Agentic improvement — the loop that keeps this system honest

This skill improves itself. The loop below is not a one-off exercise; it
is part of the system, run by the nightly evaluation job, and it covers
**both** the memory system and the leakage-protection layer.

## The loop

```
audit → measure → find gaps → patch → re-validate → commit/push → report
```

Each iteration runs the full validation before claiming anything is
done. A partial check is not a validation.

## Dimensions

Every iteration scores the system on five dimensions:

1. **Correctness** — do the gates return the right verdict on known
   inputs? Measured by the adversarial corpus
   (`muse-leakage-guard/bin/adversarial-corpus.txt`, run with
   `bin/adversarial-run`): every payload must produce its expected
   `rc`. A mismatch is a finding, not an opinion.
2. **Adversarial rigor** — can the detectors be evaded? Each iteration
   extends the corpus with new evasion shapes: new secret formats, new
   obfuscations, new false-positive traps from real usage. The corpus
   only grows; cases are never deleted to make the numbers look good.
3. **Coverage** — does every row in the attack-surface catalog
   (`muse-leakage-guard/references/attack-surface.md`) have a
   corresponding test in `bin/leakage-audit` and an expectation in
   `references/test-matrix.md`? A scenario without a test is an
   unexamined scenario.
4. **Performance** — how fast are the gates? Time
   `memory-egress-check` on a representative payload; a gate that is
   too slow gets routed around, which is a security failure with extra
   steps. Regressions get fixed, not excused.
5. **UX** — can the human actually read the output? Audit reports and
   HTML pages are checked on a phone-width viewport: collapsed cards
   with one-line verdicts, details one tap away, expected-vs-actual
   shown side by side. If the auditor can't understand it at a glance,
   the validation didn't happen.

## Instance problems vs. system problems

For each finding, ask which one it is:

- **Instance problem** (one bad entry, one missed expiry, one
  over-gated literal) → fix the instance, add a trace entry, move on.
- **System problem** (the same class of finding repeats, or a whole
  category of payload evades detection) → the system is wrong, not the
  data. Patch the skill: tighten a pattern, add a corpus case, close a
  coverage gap. Then re-run the **full** validation loop, commit, push,
  and report what changed with the validation result.

The loop closes when a cycle goes clean because the system got better,
not because symptoms were hand-fixed again.

## Authority

Standing rule: system mechanics auto-evolve — apply the patch, run the
full validation loop, commit + push, then report the change with the
validation result. Judgment calls on genuinely private data (personal
amounts, personal contact info, credentials) still reach the human
auditor before action; public information never needs permission.

## What "done" means

An iteration is done when, in order:

1. `bash -n` passes on every changed script.
2. `bin/leakage-audit` is CLEAN (exit 0).
3. `bin/adversarial-run` is 100% (exit 0).
4. New/changed behavior is covered by a test or corpus case.
5. Docs updated (attack-surface, test-matrix, README, or this file).
6. Changes committed and pushed to the skill repos — with the push VERIFIED:
   `git fetch` then `git rev-list --count origin/main..HEAD` must be 0.
   A rejected or partial push is a finding, never a done: prior runs
   claimed "commit + push" while 15 leak-guard commits sat unpushed since
   2026-09-17 (token lacked `workflow` scope for workflow-file changes).
   Surface the remote's exact error to the auditor with remediation.
7. The human got a concise report: what changed, the validation
   result, and whether anything needs their judgment.

## History

- 2026-09-22 (night): third iteration — no-args stdin hang/false-clean in
  both gates. The nightly run wedged: `memory-audit` calls `memory-guard`
  with no args inside `$(...)`, where stdin is a non-tty idle pipe, and
  the old `[ ! -t 0 ]` branch did a blind `cat` that blocked forever
  (the 22:00 run never finished; killed after diagnosis). The same branch
  on a `/dev/null` stdin — the normal cron case — would scan an empty
  temp file and report a false clean. Fix: no-args + non-tty stdin now
  probes for data with a 2s `read -t`; real piped drafts behave as
  before, no data falls back to the documented tree scan (guard) or
  empty input = clean (egress check, where no production caller uses
  stdin). Same hardening applied to `memory-egress-check`'s `INPUT=$(cat)`
  for the identical latent hang. 3 new regression tests in
  `leakage-audit` (idle-pipe fifo: guard finds a planted synthetic secret
  via the tree fallback, clean tree rc=0, egress rc=0 — all timeout-
  guarded). Validation: bash -n clean, leakage-audit CLEAN 97/97,
  adversarial-run 38/38, memory-audit completes (exit 1 only on the
  already-classified figure set). Also instance-fixed the 6th
  UTC-misfiling (a chat session filed verified-extraction blocks under
  2026-09-23.md; merged into 2026-09-22.md, misdated file to recoverable
  trash).
- 2026-09-17 (night): second iteration — over-gating fix for auditor-ruled
  public classes. The nightly audit kept flagging MU stock prices and two
  public business numbers Joon had ruled public that same day
  ('don't ask me for my permission for all public information'), because
  fixed-string allowlists cannot cover values that change daily. Added
  `MEMORY_PUBLIC_PATTERNS` (`~/memory/.public-patterns`, one ERE per line,
  auditor-curated, never auto-populated): `memory-guard` and
  `memory-egress-check` now exempt matching lines from the review tier
  only; the block tier (secrets/SSN/cards) is computed first and never
  affected. Seeded with `MU ~\$[0-9,]+(\.[0-9]+)?`; the two phone numbers
  and the published `$1,600 PT` went to `.figure-allowlist` as fixed
  strings (already in `.egress-allowlist`). 4 new controlled tests in
  `leakage-audit` (pattern exempts / pattern never exempts secrets, on
  both gates); residual note added for the line-scoped caveat. Validation:
  bash -n clean, leakage-audit CLEAN 94/94, adversarial-run 36/36,
  memory-audit clean. Corpus not extended: market-price clean cases are
  installation-dependent (they need the installation's pattern file), and
  the shared corpus must stay installation-independent.
- 2026-09-17: first full iteration. Adversarial corpus built (36
  cases); found 7 detection gaps — Stripe `sk_live_/sk_test_` keys,
  Google `AIza` keys, JWT-shaped tokens, `api key` with a space, bare
  9-digit SSNs, 15-digit Amex, and a `$1` false positive from shell
  variables. All fixed in `memory-egress-check` / `memory-guard`;
  corpus green 36/36; audit CLEAN. Bare 10-digit phone numbers left
  as a documented residual (they collide with confirmation numbers —
  gating them would cause approval fatigue, itself a security risk).
