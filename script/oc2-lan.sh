#!/bin/sh
# oc2-lan: LAN participation for the oc2 node.
#
#   oc2-lan.sh advertise            advertise this node via Bonjour (oc2-node calls it)
#   oc2-lan.sh discover [timeout]   find LAN nodes, probe them, cache to state
#
# Discovered nodes are other machines running `oc2-node.sh start` on the same
# LAN. The buzz relay stays the human surface; the LAN is the agent fabric —
# any agent on the LAN can attach to any node it can reach.
set -eu

SERVICE="_oc2-node._tcp"
STATE="$HOME/.opencode2-profiles/work/state"

case "${1:-}" in
  advertise)
    PORT="${2:-4096}"
    NAME="oc2-$(hostname -s)"
    exec dns-sd -R "$NAME" "$SERVICE" local "$PORT"
    ;;
  discover)
    MAX="${2:-3}"
    FOUND="$(mktemp)"
    dns-sd -B "$SERVICE" local 2>/dev/null | awk '/_oc2-node/ {print $NF}' > "$FOUND.tmp" &
    BPID=$!
    sleep "$MAX"
    kill "$BPID" 2>/dev/null || true
    mv "$FOUND.tmp" "$FOUND" 2>/dev/null || true

    ENTRIES="[]"
    ENTRIES="$(python3 - "$FOUND" "$STATE" <<'EOF'
import json, os, socket, subprocess, sys, time, urllib.request, base64

found_file, state_dir = sys.argv[1], sys.argv[2]
instances = [l.strip() for l in open(found_file) if l.strip() and l.strip() != "0"]
pwfile = os.path.join(state_dir, "node-password")
pw = open(pwfile).read().strip() if os.path.exists(pwfile) else ""
auth = "Basic " + base64.b64encode(f"opencode:{pw}".encode()).decode() if pw else ""

nodes = []
for name in dict.fromkeys(instances):
    try:
        out = subprocess.run(["dns-sd", "-L", name, "_oc2-node._tcp", "local"],
                             capture_output=True, text=True, timeout=4).stdout
        port = out.split("port ")[1].split(",")[0].strip() if "port " in out else ""
        host = out.split("can be reached at ")[1].split(" ")[0].rstrip(".") if "can be reached at " in out else ""
    except Exception:
        continue
    if not (port and host):
        continue
    try:
        ip = socket.gethostbyname(host)
    except Exception:
        ip = ""
    url = f"http://{ip}:{port}"
    node = {"instance": name, "url": url, "host": host, "reachable": False}
    try:
        req = urllib.request.Request(url + "/global/health")
        if auth: req.add_header("Authorization", auth)
        r = urllib.request.urlopen(req, timeout=2)
        node["reachable"] = True
        node["health"] = json.loads(r.read().decode())
    except Exception as e:
        node["reachable"] = "auth required" in str(e) or getattr(e, "code", None) == 401
    nodes.append(node)

out_file = os.path.join(state_dir, "lan-nodes.json")
os.makedirs(state_dir, exist_ok=True)
json.dump({"discovered": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "nodes": nodes},
          open(out_file, "w"), indent=1)
print(json.dumps(nodes, indent=1))
EOF
)"
    rm -f "$FOUND"
    echo "$ENTRIES"
    ;;
  *)
    echo "usage: oc2-lan.sh advertise [port] | discover [timeout]" >&2
    exit 1
    ;;
esac
