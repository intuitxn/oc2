#!/bin/sh
# oc2-gateway: manage the lean gateway intake (LaunchAgent, always on).
#   start|stop|status|install|uninstall|token
set -eu

GW="$HOME/opencode2/script/oc2-gateway.py"
STATE="$HOME/.opencode2-profiles/work/state"
LABEL="intuitxn.gateway"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PORT="${OC2_GATEWAY_PORT:-4099}"

health() { curl -s -m 2 "http://127.0.0.1:$PORT/health" 2>/dev/null || true; }

case "${1:-}" in
  install)
    mkdir -p "$HOME/Library/LaunchAgents"
    [ -s "$STATE/gateway-token" ] || { umask 077; openssl rand -hex 16 > "$STATE/gateway-token"; }
    cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array>
    <string>/usr/bin/python3</string><string>$GW</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$STATE/gateway-launchd.log</string>
  <key>StandardErrorPath</key><string>$STATE/gateway-launchd.log</string>
</dict></plist>
EOF
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$PLIST"
    sleep 2
    "$0" status
    ;;
  uninstall)
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
    echo "gateway uninstalled"
    ;;
  stop)
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    echo "gateway stopped"
    ;;
  status)
    H="$(health)"
    if [ -n "$H" ]; then
      echo "gateway up: http://127.0.0.1:$PORT  ($H)"
    else
      echo "gateway down"
      exit 1
    fi
    ;;
  token)
    cat "$STATE/gateway-token"
    ;;
  start|*)
    echo "usage: oc2-gateway.sh install|uninstall|stop|status|token (LaunchAgent manages start)" >&2
    [ "${1:-}" = "start" ] && exit 1
    exit 1
    ;;
esac
