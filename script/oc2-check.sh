#!/bin/sh
# oc2-check.sh — consistency guard for the agent harness.
# Catches drift between the delegation graph (plugin/nodes.ts), charter files
# (agent/*.md), the routing table (telepathy.md '## Route first'), and the
# rendered page. Plain POSIX shell, no node/python deps.
set -eu

BASE="/Users/a3fckxmini/.opencode2-profiles/work/config/opencode"
NODES="$BASE/plugin/nodes.ts"
AGENT_DIR="$BASE/agent"
TELEPATHY="$AGENT_DIR/telepathy.md"

FAIL=0
pass() { printf 'PASS: %s\n' "$1"; }
fail() { printf 'FAIL: %s\n' "$1"; FAIL=1; }

# ---------------------------------------------------------------------------
# Check 1: every node id in nodes.ts has an existing charter file, and every
#          charter points at a real file whose basename matches a node id.
# ---------------------------------------------------------------------------
ids=$(grep -E '^    id: "' "$NODES" | sed -E 's/.*"([a-z]+)".*/\1/')
charters=$(grep -E '^    charter: "' "$NODES" | sed -E 's/.*"([^"]+)".*/\1/')

c1_ok=1
for id in $ids; do
  if [ ! -f "$AGENT_DIR/$id.md" ]; then
    echo "  missing charter file for id '$id': $AGENT_DIR/$id.md"
    c1_ok=0
  fi
done

for c in $charters; do
  if [ ! -f "$BASE/$c" ]; then
    echo "  charter path does not exist: $c"
    c1_ok=0
  fi
  base=$(basename "$c" .md)
  if ! grep -qE "^    id: \"$base\"" "$NODES"; then
    echo "  charter '$c' has no matching node id '$base'"
    c1_ok=0
  fi
done

if [ "$c1_ok" -eq 1 ]; then
  pass "every node id has a matching, existing charter file"
else
  fail "node id -> charter file mismatch"
fi

# ---------------------------------------------------------------------------
# Check 2: routing table lists exactly the same subagent ids as delegatesTo.
# ---------------------------------------------------------------------------
delegated=$(grep -E 'delegatesTo: \[' "$NODES" | grep -oE '"[a-z]+"' | tr -d '"' | sort -u)
routed=$(awk '/## Route first/{f=1;next} f && /^## /{exit} f' "$TELEPATHY" | grep -oE '@[a-z]+' | tr -d '@' | sort -u)

if [ "$delegated" = "$routed" ]; then
  pass "routing table == delegatesTo ($(echo $routed | tr '\n' ' '))"
else
  fail "routing table != delegatesTo"
  echo "  delegatesTo: $delegated"
  echo "  routing:     $routed"
fi

# ---------------------------------------------------------------------------
# Check 3: no legacy v1 node name appears as a node id or charter filename.
# ---------------------------------------------------------------------------
legacy="prime build steward research relationships ship"
c3_ok=1
for name in $legacy; do
  if grep -qE "^    id: \"$name\"" "$NODES"; then
    echo "  legacy node id '$name' present in nodes.ts"
    c3_ok=0
  fi
  if grep -qE "^    charter: \"agent/$name\\.md\"" "$NODES"; then
    echo "  legacy charter '$name.md' referenced in nodes.ts"
    c3_ok=0
  fi
  if [ -f "$AGENT_DIR/$name.md" ]; then
    echo "  legacy charter file exists: $AGENT_DIR/$name.md"
    c3_ok=0
  fi
  if grep -rqE "@$name($|[^a-z])" "$AGENT_DIR" 2>/dev/null; then
    echo "  legacy node reference '@$name' in agent/*.md"
    c3_ok=0
  fi
done

if [ "$c3_ok" -eq 1 ]; then
  pass "no legacy v1 node names (prime/build/steward/research/relationships/ship)"
else
  fail "legacy v1 node names detected"
fi

# ---------------------------------------------------------------------------
exit "$FAIL"
