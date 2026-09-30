#!/usr/bin/env bash
# Test: memory-audit check 10 (router integrity) flags a MEMORY.md that has
# accumulated a substantive ## Facts section, and stays clean for a thin
# router (identity + pointers, no fact sections).
set -u

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export PERSONAL_MEMORY_ROOT="$TMP"
export MEMORY_AUDIT_TZ="America/Los_Angeles"
export MEMORY_AUDIT_TRASH_DIR="$TMP/trash"
TODAY="$(TZ=America/Los_Angeles date +%F)"

mkdir -p "$TMP/memory/trace"
printf -- '- [test] new |fact| — router test entry (src: test)\n' \
  > "$TMP/memory/trace/trace.md"
printf '# %s\n' "$TODAY" > "$TMP/memory/$TODAY.md"

fail=0

# Case 1: bloated router — ## Facts with 6 lines must be flagged.
cat > "$TMP/MEMORY.md" <<'EOF'
# MEMORY.md

## Facts
- name is Test User
- lives at 123 Test Lane
- works at TestCorp
- likes coffee
- owns a dog
- born 1990-01-01
EOF
out="$("$SKILL_DIR/bin/memory-audit" "$TMP" 2>&1)"
status=$?
[ "$status" -eq 1 ] || { echo "FAIL: exit $status (want 1 for bloated router)"; echo "$out"; fail=1; }
echo "$out" | grep -q "substantive '## Facts' section" \
  || { echo "FAIL: router-integrity flag missing"; echo "$out"; fail=1; }

# Case 2: thin router — no fact sections, must not flag.
cat > "$TMP/MEMORY.md" <<'EOF'
# MEMORY.md

## Identity

- **Test User** — test@example.com

## Where everything lives

| What | Where |
|---|---|
| People | `~/memory/people/INDEX.md` |
EOF
out="$("$SKILL_DIR/bin/memory-audit" "$TMP" 2>&1)"
status=$?
[ "$status" -eq 0 ] || { echo "FAIL: exit $status (want 0 for thin router)"; echo "$out"; fail=1; }
echo "$out" | grep -q "MEMORY.md is a thin router" \
  || { echo "FAIL: thin-router ok line missing"; echo "$out"; fail=1; }

[ "$fail" -eq 0 ] && echo "PASS: memory-audit router integrity"
exit "$fail"
