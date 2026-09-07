#!/bin/sh
# oc2-ship: serve a directory and expose it on a public URL via a cloudflared
# quick tunnel. Detaches and records state. Live in seconds.
#
# Usage:
#   oc2-ship <dir> [port]        serve static files (needs index.html)
#   oc2-ship --cmd "<cmd>" <dir> [port]   run a dev server command, tunnel its port
#
# Output: the public URL. State: ~/.opencode2-profiles/work/state/ship.json
# Stop with: oc2-ship-stop <url|port>
set -eu

STATE="$HOME/.opencode2-profiles/work/state/ship.json"
MODE="static"
CMD=""
if [ "${1:-}" = "--cmd" ]; then MODE=cmd; CMD="$2"; shift 2; fi

DIR="$(cd "$1" && pwd)"

# pick a free high port (skip anything already listening)
PORT=""
for try in 1 2 3 4 5; do
  CAND="${2:-$(( (RANDOM % 4000) + 40000 ))}"
  if ! lsof -nP -iTCP:"$CAND" -sTCP:LISTEN 2>/dev/null | grep -q LISTEN; then
    PORT="$CAND"
    break
  fi
  [ -n "${2:-}" ] && break
done
[ -n "$PORT" ] || { echo "no free port found" >&2; exit 1; }

if [ "$MODE" = "static" ] && [ ! -f "$DIR/index.html" ]; then
  echo "no index.html in $DIR — build first or use --cmd" >&2
  exit 1
fi

if [ "$MODE" = "static" ]; then
  python3 -m http.server "$PORT" --directory "$DIR" >/dev/null 2>&1 &
else
  (cd "$DIR" && sh -c "$CMD") >/dev/null 2>&1 &
fi
SERVER=$!

# verify our own server answers before opening the tunnel
sleep 1
ORIGIN=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$PORT/" 2>/dev/null || echo 000)
if [ "$MODE" = "static" ] && [ "$ORIGIN" != "200" ]; then
  echo "origin check failed ($ORIGIN) on port $PORT" >&2
  kill "$SERVER" 2>/dev/null || true
  exit 1
fi

TLOG="$(mktemp)"
cloudflared tunnel --url "http://127.0.0.1:$PORT" --no-autoupdate >"$TLOG" 2>&1 &
TUNNEL=$!

URL=""
i=0
while [ $i -lt 30 ]; do
  URL="$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$TLOG" | head -1)"
  [ -n "$URL" ] && break
  kill -0 "$TUNNEL" 2>/dev/null || break
  i=$((i + 1))
  sleep 1
done

if [ -z "$URL" ]; then
  echo "tunnel failed:" >&2
  cat "$TLOG" >&2
  kill "$SERVER" 2>/dev/null || true
  exit 1
fi

python3 - "$PORT" "$URL" "$DIR" "$SERVER" "$TUNNEL" "$STATE" "$TLOG" <<'EOF'
import json, os, sys, time
port, url, directory, server, tunnel, state, tlog = sys.argv[1:8]
try:
    entries = json.load(open(state))
except Exception:
    entries = []
entries.append({
    "url": url, "port": int(port), "dir": directory,
    "server_pid": int(server), "tunnel_pid": int(tunnel),
    "tunnel_log": tlog, "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
})
open(state, "w").write(json.dumps(entries, indent=1))
EOF

rm -f "$TLOG.tmp" 2>/dev/null || true
echo "$URL"
