#!/bin/sh
# oc2-join: one-command Intuitxn Labs node installer for team members.
#
#   curl -fsSL https://labs.intuitxn.com/join/oc2-join.sh | sh
#
# What it does on a fresh mac (arm64):
#   1. installs the labs opencode2 build as `oc2` (does not touch your `opencode`)
#   2. creates the canonical profile, applies the team bundle (agents, plugins)
#   3. installs LaunchAgents: resident node (LAN, always on) + gateway intake
#   4. verifies health and prints the buzz join steps (owner admits your identity)
set -eu

LABS="https://labs.intuitxn.com"
OC2_HOME="$HOME/.oc2"
PROFILE="$HOME/.opencode2-profiles/work"

say() { printf '\n== %s\n' "$1"; }
[ "$(uname -s)" = "Darwin" ] || { echo "intuitxn labs nodes are macOS for now"; exit 1; }
[ "$(uname -m)" = "arm64" ] || { echo "arm64 mac required for the prebuilt binary (see team.json runtime.fallback)"; exit 1; }

say "1/6 downloading the labs build (~168MB, one time)"
mkdir -p "$OC2_HOME/bin" "$PROFILE/config" "$PROFILE/data" "$PROFILE/cache" "$PROFILE/state"
curl -fsSL -o "$OC2_HOME/bin/opencode" "$LABS/dist/opencode-darwin-arm64"
chmod +x "$OC2_HOME/bin/opencode"

# scripts live where the canon expects them; binary gets symlinked into place
mkdir -p "$HOME/opencode2/script/sandbox" "$HOME/opencode2/packages/opencode/dist/opencode-darwin-arm64/bin"
say "2/6 applying the team bundle (agents, plugins, scripts)"
curl -fsSL -o /tmp/oc2-bundle.tar.gz "$LABS/oc2-bundle.tar.gz"
tar -xzf /tmp/oc2-bundle.tar.gz -C /tmp/oc2-join-bundle 2>/dev/null || { rm -rf /tmp/oc2-join-bundle; mkdir -p /tmp/oc2-join-bundle; tar -xzf /tmp/oc2-bundle.tar.gz -C /tmp/oc2-join-bundle; }
cp -R /tmp/oc2-join-bundle/script/. "$HOME/opencode2/script/"
cp -R /tmp/oc2-join-bundle/profile/opencode/. "$PROFILE/config/opencode/"
rm -rf /tmp/oc2-join-bundle /tmp/oc2-bundle.tar.gz
ln -sfn "$OC2_HOME/bin/opencode" "$HOME/opencode2/packages/opencode/dist/opencode-darwin-arm64/bin/opencode"

say "3/6 installing the oc2 command (your own opencode is untouched)"
cat > "$OC2_HOME/bin/oc2" <<'EOF'
#!/bin/sh
OC2_BIN="$HOME/.oc2/bin/opencode"
OC2_ROOT="$HOME/.opencode2-profiles"
OC2_DEFAULT="work"
profile="$OC2_PROFILE"
if [ -z "$profile" ]; then
  case "$1" in
    --profile) profile="$2"; shift 2 ;;
    --profile=*|-p) profile="${1#*=}"; shift ;;
  esac
fi
[ -n "$profile" ] || profile="$OC2_DEFAULT"
[ "$profile" = "relay" ] && profile=".relay"
root="$OC2_ROOT/$profile"
mkdir -p "$root/config" "$root/data" "$root/cache" "$root/state"
export XDG_CONFIG_HOME="$root/config"
export XDG_DATA_HOME="$root/data"
export XDG_CACHE_HOME="$root/cache"
export XDG_STATE_HOME="$root/state"
exec "$OC2_BIN" "$@"
EOF
chmod +x "$OC2_HOME/bin/oc2"
case ":$PATH:" in *":$OC2_HOME/bin:"*) ;; *) for RC in "$HOME/.zshrc" "$HOME/.zprofile"; do
  grep -qs 'OC2_HOME/bin' "$RC" 2>/dev/null || printf '\n# intuitxn labs node\nexport PATH="$HOME/.oc2/bin:$PATH"\n' >> "$RC"
done ;; esac

say "4/6 installing resident node + gateway (always on, LAN visible)"
sh "$HOME/opencode2/script/oc2-node.sh" install >/dev/null
sh "$HOME/opencode2/script/oc2-gateway.sh" install >/dev/null

say "4b/6 installing team sync (pulls the manifest every 15 min)"
cat > "$HOME/Library/LaunchAgents/intuitxn.oc2-sync.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>intuitxn.oc2-sync</string>
  <key>ProgramArguments</key><array><string>/bin/sh</string><string>$HOME/opencode2/script/oc2-sync.sh</string></array>
  <key>RunAtLoad</key><true/>
  <key>StartInterval</key><integer>900</integer>
  <key>StandardOutPath</key><string>$PROFILE/state/team-sync-launchd.log</string>
  <key>StandardErrorPath</key><string>$PROFILE/state/team-sync-launchd.log</string>
</dict></plist>
EOF
launchctl bootout "gui/$(id -u)/intuitxn.oc2-sync" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/intuitxn.oc2-sync.plist"

say "5/6 verifying"
"$OC2_HOME/bin/opencode" --version
curl -fsS -m 3 "http://127.0.0.1:4096/global/health" 2>/dev/null || echo "(node warming up — check oc2-node.sh status)"
curl -fsS -m 3 "http://127.0.0.1:4099/health" 2>/dev/null || echo "(gateway warming up — check oc2-gateway.sh status)"

say "6/6 buzz + team"
curl -fsSL -o "$PROFILE/state/team.json" "$LABS/team.json" 2>/dev/null || true
echo "buzz: ask the owner to admit your agent identity in Buzz Desktop, then:"
echo "  buzz channels join <channel>   for each channel in team.json"
LAN_IP=$(python3 -c "import json;print(json.load(open('$PROFILE/state/team.json'))['node']['lan'])" 2>/dev/null || echo "see team.json")
echo "team node: $LAN_IP  labs page: $LABS"
echo "send a job: oc2 \"task\" | curl the gateway: see labs page"
echo "done — you are a labs node."
