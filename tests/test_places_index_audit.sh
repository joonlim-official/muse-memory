#!/usr/bin/env bash
# Test: memory-audit catches dangling index refs and locations schema
# violations, and init-memory seeds the locations scaffold.
# Phase A: locations/INDEX.md references a missing page -> exit 1, flagged.
# Phase B: page present but missing ## Visits -> exit 1, flagged.
# Phase C: fully valid -> exit 0, clean.
# Phase D: init-memory into a fresh root creates locations/ + INDEX.md.
set -u

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export PERSONAL_MEMORY_ROOT="$TMP"
export MEMORY_AUDIT_TZ="America/Los_Angeles"
TODAY="$(TZ=America/Los_Angeles date +%F)"

fail=0

write_base() {
  mkdir -p "$TMP/memory/locations" "$TMP/memory/trace"
  printf -- '- [test] new |fact| — places test entry (src: test)\n' \
    > "$TMP/memory/trace/trace.md"
  printf '# memory\n' > "$TMP/MEMORY.md"
  printf '# %s\n' "$TODAY" > "$TMP/memory/$TODAY.md"
}

write_cafe_full() {
  cat > "$TMP/memory/locations/cafe-a.md" <<'EOF'
---
name: Cafe A
summary: Neighborhood coffee shop.
updated: 2026-09-27
---

# Cafe A

## Facts

- 100 Example St, Sampletown. (src: test)

## Visits

- 2026-09-27 — coffee. (src: test)

## Related

- Topic: none in fixture.
EOF
}

write_cafe_no_visits() {
  cat > "$TMP/memory/locations/cafe-a.md" <<'EOF'
---
name: Cafe A
summary: Neighborhood coffee shop.
updated: 2026-09-27
---

# Cafe A

## Facts

- 100 Example St, Sampletown. (src: test)

## Related

- Topic: none in fixture.
EOF
}

# --- Phase A: dangling ref ---------------------------------------------
write_base
write_cafe_full
cat > "$TMP/memory/locations/INDEX.md" <<'EOF'
# Locations Index

- **Cafe A** — `~/memory/locations/cafe-a.md` — neighborhood coffee shop.
- **Ghost Place** — `~/memory/locations/ghost-place.md` — does not exist.
EOF

out="$("$SKILL_DIR/bin/memory-audit" "$TMP" 2>&1)"
status=$?
[ "$status" -eq 1 ] || { echo "FAIL A: exit $status (want 1)"; echo "$out"; fail=1; }
echo "$out" | grep -q "dangling ref in locations/INDEX.md" \
  || { echo "FAIL A: dangling ref not reported"; echo "$out"; fail=1; }

# --- Phase B: schema violation (missing ## Visits) ----------------------
cat > "$TMP/memory/locations/INDEX.md" <<'EOF'
# Locations Index

- **Cafe A** — `~/memory/locations/cafe-a.md` — neighborhood coffee shop.
EOF
write_cafe_no_visits

out="$("$SKILL_DIR/bin/memory-audit" "$TMP" 2>&1)"
status=$?
[ "$status" -eq 1 ] || { echo "FAIL B: exit $status (want 1)"; echo "$out"; fail=1; }
echo "$out" | grep -q "missing ## Visits" \
  || { echo "FAIL B: missing ## Visits not reported"; echo "$out"; fail=1; }

# --- Phase C: fully valid -> clean --------------------------------------
write_cafe_full

out="$("$SKILL_DIR/bin/memory-audit" "$TMP" 2>&1)"
status=$?
[ "$status" -eq 0 ] || { echo "FAIL C: exit $status (want 0)"; echo "$out"; fail=1; }
echo "$out" | grep -q "no dangling index refs" \
  || { echo "FAIL C: clean bill not reported"; echo "$out"; fail=1; }

# --- Phase E: template placeholders are not dangling refs -----------------
cat > "$TMP/memory/locations/INDEX.md" <<'EOF'
# Locations Index

Filename convention: `YYYY-MM-DD-<slug>.md`.

- **Cafe A** — `~/memory/locations/cafe-a.md` — neighborhood coffee shop.
EOF
write_cafe_full

out="$("$SKILL_DIR/bin/memory-audit" "$TMP" 2>&1)"
status=$?
[ "$status" -eq 0 ] || { echo "FAIL E: exit $status (want 0)"; echo "$out"; fail=1; }
echo "$out" | grep -q "! dangling ref" \
  && { echo "FAIL E: template placeholder reported as dangling"; echo "$out"; fail=1; }

# --- Phase F: auxiliary *_INDEX.md files are exempt from place schema ----
cat > "$TMP/memory/locations/IMAGE_INDEX.md" <<'EOF'
# Image Index

A directory of photos, not a place page — no frontmatter, no sections.
EOF

out="$("$SKILL_DIR/bin/memory-audit" "$TMP" 2>&1)"
status=$?
[ "$status" -eq 0 ] || { echo "FAIL F: exit $status (want 0)"; echo "$out"; fail=1; }
echo "$out" | grep -q "IMAGE_INDEX.md" \
  && { echo "FAIL F: auxiliary index flagged against place schema"; echo "$out"; fail=1; }

# --- Phase D: init-memory seeds the locations scaffold ------------------
TMP2="$(mktemp -d)"
"$SKILL_DIR/bin/init-memory" "$TMP2" >/dev/null 2>&1
[ -d "$TMP2/memory/locations" ] \
  || { echo "FAIL D: locations/ not created"; fail=1; }
grep -q "Locations Index" "$TMP2/memory/locations/INDEX.md" 2>/dev/null \
  || { echo "FAIL D: locations/INDEX.md not seeded"; fail=1; }
grep -q "Visits" "$TMP2/memory/locations/INDEX.md" 2>/dev/null \
  || { echo "FAIL D: seeded INDEX.md lacks the Visits-log pointer"; fail=1; }
rm -rf "$TMP2"

[ "$fail" -eq 0 ] && echo "PASS: places index audit"
exit "$fail"
