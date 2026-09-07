#!/bin/sh
# oc2-sync: member-side auto-pull. Runs every 15 min (LaunchAgent), fetches the
# team bundle, and applies changes allowed by this node's access tier.
# Access lives in ~/.oc2/tier (default: member). The owner pushes by publishing
# a new bundle; nodes pull. Nothing sensitive rides the public manifest.
set -eu

LABS="https://labs.intuitxn.com"
PROFILE="$HOME/.opencode2-profiles/work/config"
STATE="$HOME/.opencode2-profiles/work/state"
TIER="$(cat "$HOME/.oc2/tier" 2>/dev/null || echo member)"
HASH="$STATE/team-bundle.sha256"

mkdir -p "$STATE" "$HOME/.oc2"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

curl -fsSL -m 20 -o "$TMP/team.json" "$LABS/team.json" 2>/dev/null || exit 0
cp "$TMP/team.json" "$STATE/team.json"
curl -fsSL -m 180 -o "$TMP/bundle.tar.gz" "$LABS/oc2-bundle.tar.gz" || exit 0
BUNDLE_SHA="$(shasum -a 256 "$TMP/bundle.tar.gz" | cut -d' ' -f1)"
[ -f "$HASH" ] && [ "$(cat "$HASH")" = "$BUNDLE_SHA" ] && exit 0

tar -xzf "$TMP/bundle.tar.gz" -C "$TMP"

if [ "$TIER" = "member" ]; then
  python3 - "$TMP/profile/opencode" "$TMP/team.json" <<'EOF'
import json, os, sys
pdir, manifest = sys.argv[1], json.load(open(sys.argv[2]))
allow = manifest["access_tiers"]["member"]["plugins"]
if allow != "all":
    for f in os.listdir(os.path.join(pdir, "plugin")):
        if f.endswith(".ts") and f[:-3] not in allow:
            os.remove(os.path.join(pdir, f))
EOF
fi

cp -R "$TMP/profile/opencode/." "$PROFILE/opencode/"
cp -R "$TMP/script/." "$HOME/opencode2/script/"
echo "$BUNDLE_SHA" > "$HASH"

sh "$HOME/opencode2/script/oc2-node.sh" stop >/dev/null 2>&1 || true
sh "$HOME/opencode2/script/oc2-gateway.sh" stop >/dev/null 2>&1 || true
sleep 1
launchctl kickstart -k "gui/$(id -u)/intuitxn.oc2-node" 2>/dev/null || sh "$HOME/opencode2/script/oc2-node.sh" start >/dev/null 2>&1 || true
launchctl kickstart -k "gui/$(id -u)/intuitxn.gateway" 2>/dev/null || true
echo "$(date '+%F %T') synced bundle $BUNDLE_SHA (tier $TIER)" >> "$STATE/team-sync.log"
