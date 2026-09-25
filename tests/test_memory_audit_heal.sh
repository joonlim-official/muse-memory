#!/usr/bin/env bash
# Test: memory-audit auto-heals a UTC-misfiled future daily log.
# A future-dated log is merged into today's log with a provenance marker,
# the misdated file is moved to a recoverable trash dir, and the audit
# reports clean. A second run must not duplicate the merge.
set -u

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export PERSONAL_MEMORY_ROOT="$TMP"
export MEMORY_AUDIT_TZ="America/Los_Angeles"
export MEMORY_AUDIT_TRASH_DIR="$TMP/trash"
TODAY="$(TZ=America/Los_Angeles date +%F)"
TOMORROW="$(TZ=America/Los_Angeles date -d 'tomorrow' +%F 2>/dev/null \
  || TZ=America/Los_Angeles date -v+1d +%F)"

mkdir -p "$TMP/memory/trace"
printf -- '- [test] new |fact| — heal test entry (src: test)\n' \
  > "$TMP/memory/trace/trace.md"
printf '# memory\n' > "$TMP/MEMORY.md"
printf -- '- healed entry one\n- healed entry two\n' > "$TMP/memory/$TOMORROW.md"
printf '# %s\n' "$TODAY" > "$TMP/memory/$TODAY.md"

fail=0
out="$("$SKILL_DIR/bin/memory-audit" "$TMP" 2>&1)"
status=$?
[ "$status" -eq 0 ] || { echo "FAIL: exit $status (want 0)"; echo "$out"; fail=1; }
grep -q "healed entry one" "$TMP/memory/$TODAY.md" \
  || { echo "FAIL: future content not merged into today's log"; fail=1; }
grep -q "auto-heal" "$TMP/memory/$TODAY.md" \
  || { echo "FAIL: provenance marker missing"; fail=1; }
[ ! -e "$TMP/memory/$TOMORROW.md" ] \
  || { echo "FAIL: future log still in place"; fail=1; }
[ -f "$TMP/trash/$TOMORROW.md" ] \
  || { echo "FAIL: misdated file not in trash dir"; fail=1; }
echo "$out" | grep -q "healed" \
  || { echo "FAIL: heal not reported in output"; fail=1; }

# Idempotency: a second run stays clean and does not duplicate the merge.
out2="$("$SKILL_DIR/bin/memory-audit" "$TMP" 2>&1)"
status2=$?
[ "$status2" -eq 0 ] || { echo "FAIL: second run exit $status2 (want 0)"; fail=1; }
[ "$(grep -c 'healed entry one' "$TMP/memory/$TODAY.md")" -eq 1 ] \
  || { echo "FAIL: duplicate merge on re-run"; fail=1; }

# Past logs are history: a yesterday-dated log must be left untouched.
YESTERDAY="$(TZ=America/Los_Angeles date -d 'yesterday' +%F 2>/dev/null \
  || TZ=America/Los_Angeles date -v-1d +%F)"
printf -- '- old entry stays\n' > "$TMP/memory/$YESTERDAY.md"
"$SKILL_DIR/bin/memory-audit" "$TMP" >/dev/null 2>&1
[ -f "$TMP/memory/$YESTERDAY.md" ] \
  || { echo "FAIL: past log was moved"; fail=1; }
grep -q "old entry stays" "$TMP/memory/$TODAY.md" \
  && { echo "FAIL: past log content leaked into today's log"; fail=1; }

[ "$fail" -eq 0 ] && echo "PASS: memory-audit auto-heal"
exit "$fail"
