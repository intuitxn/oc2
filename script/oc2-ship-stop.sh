#!/bin/sh
# oc2-ship-stop: stop a shipped site by URL or port, or --all.
set -eu
STATE="$HOME/.opencode2-profiles/work/state/ship.json"
[ -f "$STATE" ] || { echo "nothing shipped"; exit 0; }

if [ "${1:-}" = "--all" ]; then
  python3 - "$STATE" <<'EOF'
import json, os, signal, sys
state = sys.argv[1]
entries = json.load(open(state))
for e in entries:
    for key in ("tunnel_pid", "server_pid"):
        try: os.kill(e[key], signal.SIGTERM)
        except Exception: pass
open(state, "w").write("[]")
print(f"stopped {len(entries)} ship(s)")
EOF
  exit 0
fi

TARGET="${1:?usage: oc2-ship-stop <url|port|--all>}"
python3 - "$STATE" "$TARGET" <<'EOF'
import json, os, signal, sys
state, target = sys.argv[1], sys.argv[2]
entries = json.load(open(state))
keep = []
stopped = 0
for e in entries:
    hit = target in (e["url"], str(e["port"]))
    if hit:
        for key in ("tunnel_pid", "server_pid"):
            try: os.kill(e[key], signal.SIGTERM)
            except Exception: pass
        stopped += 1
    else:
        keep.append(e)
open(state, "w").write(json.dumps(keep, indent=1))
print(f"stopped {stopped} ship(s); {len(keep)} still live")
EOF
