#!/bin/sh
# oc2-labs: the simplest live surface for Intuitxn Labs.
#
#   oc2-labs.sh workspace   open the private product/thread workspace on :4100
#   oc2-labs.sh gen         regenerate index.html from live node state
#   oc2-labs.sh serve       serve labs/ on 127.0.0.1:4098
#   oc2-labs.sh publish     named cloudflared tunnel -> labs.intuitxn.com
#   oc2-labs.sh stop        stop serve + tunnel
#   oc2-labs.sh install     LaunchAgent: serve + regen every 5 min, always on
#
# The page is a static snapshot of the real harness: node, agents, plugins,
# runtimes, ships, updates. The harness keeps running and doing tasks; the
# page just tells the truth about it.
set -eu

LABS="$HOME/.opencode2-profiles/work/labs"
STATE="$HOME/.opencode2-profiles/work/state"
PORT=4098
HOSTNAME_PUBLIC="labs.intuitxn.com"
TUNNEL="intuitxn-labs"
NODE_PORT=4096

ensure_dirs() { mkdir -p "$LABS" "$STATE"; }

node_health() {
  PW="$(cat "$STATE/node-password" 2>/dev/null || true)"
  curl -s -m 3 -u "opencode:$PW" "http://127.0.0.1:$NODE_PORT/global/health" 2>/dev/null || true
}

ships() {
  python3 -c "
import json,os
try: print(json.dumps(json.load(open('$STATE/ship.json'))[-8:], indent=1))
except Exception: print('[]')" 2>/dev/null
}

agents_list() {
  ls "$HOME/.opencode2-profiles/work/config/opencode/agent/" 2>/dev/null | sed 's/\.md$//' | tr '\n' ' '
}

plugins_list() {
  ls "$HOME/.opencode2-profiles/work/config/opencode/plugin/" 2>/dev/null | sed 's/\.ts$//' | tr '\n' ' '
}

gen() {
  ensure_dirs
  H="$(node_health)"
  if echo "$H" | grep -q healthy; then
    NODE_STATUS="healthy — serving agents on this LAN at port $NODE_PORT"
    NODE_CLASS="ok"
  else
    NODE_STATUS="down — check ~/opencode2/script/oc2-node.sh start"
    NODE_CLASS="down"
  fi
  cp "$HOME/opencode2/script/oc2-join.sh" "$LABS/oc2-join.sh"
  REV="$(git -C "$HOME/opencode2" rev-parse --short HEAD 2>/dev/null || echo '?')"
  AGENTS="$(agents_list)"
  PLUGINS="$(plugins_list)"
  SHIPS="$(ships)"
  NOW="$(date '+%Y-%m-%d %H:%M %z')"
  cat > "$LABS/index.html" <<HTMLEOF
<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Intuitxn Labs — agent harness</title>
<style>
:root{color-scheme:dark}
body{font:16px/1.6 -apple-system,sans-serif;max-width:860px;margin:48px auto;padding:0 24px;background:#0b0d10;color:#d6dde6}
h1{font-size:28px;margin:0 0 4px} h2{font-size:18px;margin:32px 0 8px;color:#8ab4ff;border-bottom:1px solid #1d232b;padding-bottom:4px}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:13px;font-weight:600}
.ok{background:#103b2c;color:#4ade80}.down{background:#3b1010;color:#f87171}
table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:6px 10px;border-bottom:1px solid #1d232b;text-align:left;vertical-align:top}
code,pre{background:#12161c;border-radius:6px;padding:2px 6px;font:13px ui-monospace,Menlo,monospace}
pre{padding:12px;overflow:auto} footer{margin-top:40px;color:#5b6672;font-size:13px}
li{margin:4px 0}
</style></head><body>
<h1>Intuitxn Labs</h1>
<p>Agents of Intuitxn Labs, running and doing tasks. One node, everything a plugin, humans accept.</p>

<h2>Node</h2>
<table>
<tr><th>Status</th><td><span class="badge $NODE_CLASS">$NODE_STATUS</span></td></tr>
<tr><th>Runtime</th><td>opencode2 <code>2.0.0</code> @ source rev <code>$REV</code> — latest local build, updated by <code>oc2_update</code></td></tr>
<tr><th>Resident agent</th><td><code>oc2-node</code> — one agent, always (LaunchAgent, KeepAlive, LAN-visible)</td></tr>
</table>

<h2>Agent nodes</h2>
<table><tr><th>Node</th><th>JTBD</th><th>Charter</th></tr>
<tr><td><code>telepathy</code> (primary)</td><td>route</td><td>Routes intent to the narrowest node; owns the routing memory</td></tr>
<tr><td><code>atlas</code></td><td>propose, scope</td><td>Human intent → reviewable job proposal</td></tr>
<tr><td><code>forge</code></td><td>implement, verify</td><td>Tested candidate + evidence, in worktree</td></tr>
<tr><td><code>ledger</code></td><td>resolve, project, learn</td><td>Receipts, changelog, lessons</td></tr>
<tr><td><code>scout</code></td><td>research</td><td>Evidence-backed dossiers with source maps</td></tr>
<tr><td><code>diplomat</code></td><td>draft-external</td><td>Reviewed external-conversation drafts</td></tr>
<tr><td><code>pilot</code></td><td>ship, go-live, demo</td><td>Anything → public URL in seconds, then draft announcement</td></tr>
</table>
<p style="color:#5b6672;font-size:13px">charter files: $AGENTS</p>

<h2>Everything is a plugin</h2>
<table><tr><th>Plugin</th><th>Surface</th></tr>
<tr><td><code>nodes</code></td><td>agent map + routing (<code>nodes_map</code>, <code>nodes_route</code>)</td></tr>
<tr><td><code>runtimes</code></td><td>harness adapters (<code>runtime_run</code>: opencode, opencode-sandbox, codex)</td></tr>
<tr><td><code>buzz</code></td><td>relay surface, draft-only (<code>buzz_channels_list</code>, <code>buzz_draft</code>)</td></tr>
<tr><td><code>launch</code></td><td>go-live (<code>ship_static</code>, <code>ship_cmd</code>, <code>ship_list</code>, <code>ship_stop</code>)</td></tr>
<tr><td><code>updates</code></td><td>update-over-network (<code>oc2_update</code>, <code>oc2_status</code>)</td></tr>
<tr><td><code>nudge</code></td><td>typed Markdown programs (<code>nudge_compile</code>, <code>nudge_run</code>, <code>nudge_skills</code>)</td></tr>
<tr><td><code>navigate</code></td><td>web reading (<code>navigate_url</code>)</td></tr>
</table>
<p style="color:#5b6672;font-size:13px">plugin files: $PLUGINS</p>

<h2>Gateway (LAN intake)</h2>
<table>
<tr><th>Status</th><td>http://127.0.0.1:4099 → LAN :4099 — token auth, job queue, sandboxed execution</td></tr>
<tr><th>Submit</th><td><code>curl -X POST -H "authorization: Bearer \$OC2_TOKEN" -d '{"task":"...","dir":"...","agent":"pilot"}' http://node:4099/job</code></td></tr>
<tr><th>Poll</th><td><code>GET /job/&lt;id&gt;</code> → queued | running | done | error + output</td></tr>
<tr><th>Platforms</th><td>buzz adapter pending relay identity (hermes gateway still owns live platform connections); LAN HTTP live today</td></tr>
</table>

<h2>Isolation tiers (OS level)</h2>
<table><tr><th>Tier</th><th>What</th><th>Use for</th></tr>
<tr><td><code>seatbelt</code></td><td>macOS sandbox-exec — writes confined to job dir, secrets unreadable</td><td>default for user-sourced agent jobs</td></tr>
<tr><td><code>docker</code></td><td>container per run, worktree mounted at /work</td><td>programs needing other OS userlands</td></tr>
<tr><td><code>vm</code></td><td>full guest OS via lima (scratch VM; never the prod coolify VM)</td><td>programs needing a whole OS</td></tr>
</table>

<h2>Send a task (agents of Intuitxn Labs)</h2>
<p>Jobs arrive from the Buzz relay. An authorized human posts in the program's
home channel:</p>
<pre>/intuitxn {"repository":0,"request":"What to build or fix","acceptance":"How it is verified","runtime":"opencode"}</pre>
<p>Desk jobs run in separate Git worktrees. Use the gateway or the explicit
<code>--sandbox</code> entry below for macOS seatbelt isolation. Agents draft; humans accept.</p>
<pre>oc2-agent.sh "task" --agent pilot --dir ~/project --sandbox   # harness entry
oc2-node.sh status                                            # resident agent
oc2-lan.sh discover                                           # LAN nodes</pre>

<h2>Live ships</h2>
<pre>$(echo "$SHIPS" | head -20)</pre>

<h2>Join the team</h2>
<table>
<tr><th>Install a node</th><td><code>curl -fsSL https://labs.intuitxn.com/join/oc2-join.sh | sh</code> — one command: binary + profile + agents + plugins + resident node + gateway, always on</td></tr>
<tr><th>Auto-updates</th><td><code>oc2-sync</code> pulls the team manifest every 15 min; the owner pushes by publishing, nodes pull, access tier decides what applies</td></tr>
<tr><th>Access tiers</th><td><code>member</code> (read + sandbox jobs) · <code>builder</code> (+ all plugins) · <code>steward</code> (+ changelog posting) — set by the owner in the manifest</td></tr>
<tr><th>buzz</th><td>owner admits your identity in Buzz Desktop; your key never leaves your machine</td></tr>
</table>

<h2>Design principle</h2>
<ol>
<li><code>opencode</code> is always the latest local build.</li>
<li>Everything is a plugin — nodes, runtimes, network, updates, programs.</li>
<li>Updates are part of the design; never ship an unverified binary.</li>
<li>Tools prepare, humans accept.</li>
</ol>

<footer>generated $NOW · intuitxn labs · <a style="color:#8ab4ff" href="https://github.com/anomalyco/opencode">opencode</a> · relay: buzz · domain: $HOSTNAME_PUBLIC</footer>
</body></html>
HTMLEOF
  echo "generated: $LABS/index.html ($(wc -c < "$LABS/index.html") bytes)"
}

case "${1:-}" in
  workspace)
    shift
    exec python3 "$(dirname "$0")/labs/server.py" "$@"
    ;;
  gen) gen ;;
  serve)
    ensure_dirs
    exec python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$LABS"
    ;;
  publish)
    ensure_dirs
    if ! cloudflared tunnel list 2>/dev/null | grep -q "$TUNNEL"; then
      cloudflared tunnel create "$TUNNEL"
    fi
    cloudflared tunnel route dns -f "$TUNNEL" "$HOSTNAME_PUBLIC"
    TID="$(cloudflared tunnel list 2>/dev/null | awk -v t="$TUNNEL" '$2==t {print $1}')"
    CRED="$HOME/.cloudflared/$TID.json"
    [ -f "$CRED" ] || { echo "credentials missing: $CRED" >&2; exit 1; }
    cat > "$HOME/.cloudflared/config-labs.yml" <<EOF
tunnel: $TID
credentials-file: $CRED
ingress:
  - hostname: $HOSTNAME_PUBLIC
    service: http://127.0.0.1:$PORT
  - service: http_status:404
EOF
    "$0" stop >/dev/null 2>&1 || true
    nohup cloudflared tunnel --protocol http2 --config "$HOME/.cloudflared/config-labs.yml" run "$TUNNEL" >> "$STATE/labs-tunnel.log" 2>&1 &
    echo $! > "$STATE/labs-tunnel.pid"
    sleep 3
    echo "published: https://$HOSTNAME_PUBLIC (tunnel pid $(cat "$STATE/labs-tunnel.pid"))"
    ;;
  stop)
    [ -f "$STATE/labs-tunnel.pid" ] && kill "$(cat "$STATE/labs-tunnel.pid")" 2>/dev/null || true
    rm -f "$STATE/labs-tunnel.pid"
    pkill -f "config-labs.yml" 2>/dev/null; pkill -f "tunnel run intuitxn-labs" 2>/dev/null || true
    pkill -f "http.server $PORT" 2>/dev/null || true
    echo "labs stopped"
    ;;
  install)
    PLIST="$HOME/Library/LaunchAgents/intuitxn.labs.plist"
    cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>intuitxn.labs</string>
  <key>ProgramArguments</key><array>
    <string>/bin/sh</string><string>$HOME/opencode2/script/oc2-labs.sh</string><string>run</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>EnvironmentVariables</key><dict>
    <key>PATH</key><string>$HOME/.local/bin:$HOME/.hermes/node/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>StandardOutPath</key><string>$STATE/labs-launchd.log</string>
  <key>StandardErrorPath</key><string>$STATE/labs-launchd.log</string>
</dict></plist>
EOF
    launchctl bootout "gui/$(id -u)/intuitxn.labs" 2>/dev/null || true
    "$0" stop >/dev/null 2>&1 || true
    launchctl bootstrap "gui/$(id -u)" "$PLIST"
    echo "installed intuitxn.labs — page lives at https://$HOSTNAME_PUBLIC, regenerates every 5 min"
    ;;
  run)
    # launchd entrypoint: gen, ensure tunnel, ensure serve, sleep loop
    gen >/dev/null 2>&1 || true
    if ! curl -s -m 2 "http://127.0.0.1:$PORT/" | grep -q "Intuitxn Labs"; then
      python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$LABS" >> "$STATE/labs-launchd.log" 2>&1 &
    fi
    if ! pgrep -f "intuitxn-labs" >/dev/null 2>&1; then
      cloudflared tunnel --protocol http2 --config "$HOME/.cloudflared/config-labs.yml" run intuitxn-labs >> "$STATE/labs-tunnel.log" 2>&1 &
    fi
    sleep 300
    exec "$0" run
    ;;
  *)
    echo "usage: oc2-labs.sh workspace [--port PORT]|gen|serve|publish|stop|install|run" >&2
    exit 1
    ;;
esac
