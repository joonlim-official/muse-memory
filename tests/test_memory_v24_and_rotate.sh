#!/usr/bin/env bash
# Regression tests for ranking v2.4 (H2/H3 subsection heading boost, YAML aliases,
# trace tier demotion) and memory-trace-rotate (archives old closed entries,
# preserves recent + open entries).
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/memory/topics" "$TMP/memory/trace"
cat > "$TMP/memory/topics/soccer.md" <<'EOF'
---
title: Youth Soccer & Futsal
aliases: MVLA, Cal North ODP
---
# Soccer
Covers: MVLA, NorCal, Mogility
EOF

cat > "$TMP/memory/personalization.md" <<'EOF'
# Personalization

## Estate planning — living trust (Littorno Law Group)
Trust notes here.
EOF

{
  echo "# Trace"
  for i in $(seq 1 15); do
    echo "- [misc] new |fact| — living trust MVLA mention $i (src: chat, 2026-08-10)"
  done
  echo "- [family] open |context| — Unresolved old question (src: chat, 2026-08-10)"
  echo "- [misc] new |fact| — Recent entry (src: chat, 2026-11-27)"
} > "$TMP/memory/trace/trace.md"

cat > "$TMP/queries.jsonl" <<'EOF'
{"id":"q1","query":"living trust","stratum":"fact","expected":["personalization.md"],"rationale":"H2 subsection heading boost beats trace volume","added":"2026-11-27","suite_version":"v2.4","split":"dev"}
{"id":"q2","query":"MVLA","stratum":"topic","expected":["topics/soccer.md"],"rationale":"YAML aliases + Covers match class 1","added":"2026-11-27","suite_version":"v2.4","split":"dev"}
EOF

# 1. Verify v2.4 retrieval passes both queries at rank 1
out="$("$SKILL_DIR/bin/memory-retrieval-test" --v2 "$TMP/queries.jsonl" --memory-root "$TMP")"
echo "$out" | grep -q "RESULT: 2 passed, 0 failed" || { echo "FAIL v2.4 retrieval:"; echo "$out"; exit 1; }
echo "$out" | grep -q "MRR:           1.000" || { echo "FAIL expected MRR 1.000:"; echo "$out"; exit 1; }

# 2. Verify memory-trace-rotate archives old closed entries and keeps open + recent
rot="$("$SKILL_DIR/bin/memory-trace-rotate" --keep-months 2 "$TMP")"
echo "$rot" | grep -q "archived=15" || { echo "FAIL trace rotate count: $rot"; exit 1; }
[ -f "$TMP/memory/trace/archive/2026-08.md" ] || { echo "FAIL archive file missing"; exit 1; }
grep -q "Unresolved old question" "$TMP/memory/trace/trace.md" || { echo "FAIL old open entry must stay in trace.md"; exit 1; }
grep -q "Recent entry" "$TMP/memory/trace/trace.md" || { echo "FAIL recent entry must stay in trace.md"; exit 1; }

echo "PASS: v2.4 retrieval (H2/H3 + aliases + trace tier) and memory-trace-rotate"
