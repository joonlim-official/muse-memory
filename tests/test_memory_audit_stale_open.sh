#!/usr/bin/env bash
# Test: memory-audit check 4 (stale open threads) flags only entries whose
# typed status token is `open` and whose date is >30 days old. Entries that
# merely mention the word "open" in the body (audit summaries, resolved
# threads, "closes the open thread" notes) must NOT flag — regression test
# for the 2026-10-13 false-positive class (3 flags in one night, all
# Sep 11-12 body mentions of already-resolved threads).
set -u

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export PERSONAL_MEMORY_ROOT="$TMP"
export MEMORY_AUDIT_TZ="America/Los_Angeles"
export MEMORY_AUDIT_TRASH_DIR="$TMP/trash"
TODAY="$(TZ=America/Los_Angeles date +%F)"
OLD="$(TZ=America/Los_Angeles date -d '45 days ago' +%F)"
RECENT="$(TZ=America/Los_Angeles date -d '5 days ago' +%F)"

mkdir -p "$TMP/memory/trace" "$TMP/memory/people" "$TMP/memory/groups" "$TMP/memory/topics"
printf '# MEMORY.md\n\n## Identity\n\n- **Test User** — test@example.com\n' > "$TMP/MEMORY.md"
printf '# %s\n' "$TODAY" > "$TMP/memory/$TODAY.md"

fail=0

# Case 1: body mentions only — no stale-open flag, audit stays clean on §4.
cat > "$TMP/memory/trace/trace.md" <<EOF
- [memory] updated |fact| — Nightly evaluation: open threads, daily-log dating all healthy. (src: this run, $OLD)
- [swim] new |fact| — Swim schedule found; partially closes the swimming open thread. (src: sweep, $OLD)
- [soccer] closed |fact| — Game played; closes the open thread from last month. (src: this run, $OLD)
- [family] open |context| — A genuinely unresolved question. (src: chat, $RECENT)
EOF
out="$("$SKILL_DIR/bin/memory-audit" "$TMP" 2>&1)"
echo "$out" | grep -q "stale open thread" \
  && { echo "FAIL: body-mention entries flagged as stale open"; echo "$out"; fail=1; }
echo "$out" | grep -q "no open thread older than 30 days" \
  || { echo "FAIL: §4 ok line missing for body-mention case"; echo "$out"; fail=1; }

# Case 2: a true stale open entry (typed status `open`, date >30d) MUST flag.
cat > "$TMP/memory/trace/trace.md" <<EOF
- [family] open |context| — A genuinely unresolved old question. (src: chat, $OLD)
- [memory] updated |fact| — Nightly evaluation: open threads all healthy. (src: this run, $OLD)
EOF
out="$("$SKILL_DIR/bin/memory-audit" "$TMP" 2>&1)"
echo "$out" | grep -q "stale open thread (src date $OLD): - \[family\] open" \
  || { echo "FAIL: true stale open entry not flagged"; echo "$out"; fail=1; }
# Exactly one flag: the body-mention line must not add a second.
n="$(echo "$out" | grep -c "stale open thread")"
[ "$n" -eq 1 ] || { echo "FAIL: expected exactly 1 stale flag, got $n"; echo "$out"; fail=1; }

[ "$fail" -eq 0 ] && echo "PASS: memory-audit stale-open precision"
exit "$fail"
