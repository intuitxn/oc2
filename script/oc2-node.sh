#!/bin/sh
# oc2-node: the resident agent node. One opencode2 server, always up, in the
# canonical profile. Everything attaches to it (TUI, harness, other agents).
#
#   oc2-node.sh start|start-fg|stop|status|install|uninstall
#
# `install` registers a macOS LaunchAgent (RunAtLoad + KeepAlive) so the node
# literally is always there: one agent, always.
set -eu

PORT=4096
OC2="$HOME/opencode2/packages/opencode/dist/opencode-darwin-arm64/bin/opencode"
STATE="$HOME/.opencode2-profiles/work"
LOG="$STATE/state/node.log"
PIDFILE="$STATE/state/node.pid"
PWFILE="$STATE/state/node-password"
LABEL="intuitxn.oc2-node"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
export XDG_CONFIG_HOME="$STATE/config"
export XDG_DATA_HOME="$STATE/data"
export XDG_CACHE_HOME="$STATE/cache"
export XDG_STATE_HOME="$STATE/state"

ensure_password() {
  [ -s "$PWFILE" ] || { umask 077; openssl rand -hex 16 > "$PWFILE"; }
}
export OPENCODE_SERVER_PASSWORD="$(cat "$PWFILE" 2>/dev/null || true)"

health() { curl -s -m 2 -u "opencode:$OPENCODE_SERVER_PASSWORD" "http://127.0.0.1:$PORT/global/health" 2>/dev/null || true; }

case "${1:-}" in
  start-fg)
    "$HOME/opencode2/script/oc2-lan.sh" advertise "$PORT" >> "$LOG" 2>&1 &
    exec "$OC2" serve --hostname 0.0.0.0 --port "$PORT"
    ;;
  start)
    ensure_password
    if health | grep -q '"healthy":true'; then
      echo "node already up: http://127.0.0.1:$PORT"
      exit 0
    fi
    mkdir -p "$STATE/state"
    nohup "$OC2" serve --hostname 0.0.0.0 --port "$PORT" >> "$LOG" 2>&1 &
    echo $! > "$PIDFILE"
    for i in 1 2 3 4 5 6 7 8 9 10; do
      health | grep -q '"healthy":true' && { echo "node up: http://127.0.0.1:$PORT (pid $(cat "$PIDFILE"))"; exit 0; }
      sleep 1
    done
    echo "node failed to start; log: $LOG" >&2
    exit 1
    ;;
  stop)
    if launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null; then echo "launchagent removed"; fi
    [ -f "$PIDFILE" ] && kill "$(cat "$PIDFILE")" 2>/dev/null || true
    rm -f "$PIDFILE"
    echo "node stopped"
    ;;
  status)
    H="$(health)"
    if echo "$H" | grep -q '"healthy":true'; then
      LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || true)"
      [ -n "$LAN_IP" ] || LAN_IP="$(hostname -s)"
      echo "node healthy: http://127.0.0.1:$PORT  ($H)"
      echo "lan: http://$LAN_IP:$PORT   attach: opencode attach http://127.0.0.1:$PORT"
    else
      echo "node down ($H)"
      exit 1
    fi
    ;;
  install)
    ensure_password
    mkdir -p "$HOME/Library/LaunchAgents"
    cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array>
    <string>/bin/sh</string><string>$HOME/opencode2/script/oc2-node.sh</string><string>start-fg</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>EnvironmentVariables</key><dict>
    <key>OPENCODE_SERVER_PASSWORD</key><string>$(cat "$PWFILE")</string>
  </dict>
  <key>StandardOutPath</key><string>$STATE/state/node-launchd.log</string>
  <key>StandardErrorPath</key><string>$STATE/state/node-launchd.log</string>
</dict></plist>
EOF
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    [ -f "$PIDFILE" ] && kill "$(cat "$PIDFILE")" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$PLIST"
    echo "installed $LABEL — node runs at login, restarts on crash"
    oc2-node.sh status 2>/dev/null || "$0" status
    ;;
  uninstall)
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    rm -f "$PLIST" "$PIDFILE"
    echo "uninstalled"
    ;;
  *)
    echo "usage: oc2-node.sh start|start-fg|stop|status|install|uninstall" >&2
    exit 1
    ;;
esac
