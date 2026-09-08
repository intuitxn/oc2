#!/bin/sh
# oc2-team: the team distribution loop.
#
#   oc2-team.sh gen      write labs/team.json (what a member gets, by tier)
#   oc2-team.sh pack     bundle profile + scripts + binary into labs/
#   oc2-team.sh publish  gen + pack (labs tunnel serves everything)
#
# The loop: owner publishes here -> labs.intuitxn.com serves -> member nodes
# auto-pull (oc2-sync) -> access tier decides what each node applies.
set -eu

LABS="$HOME/.opencode2-profiles/work/labs"
STATE="$HOME/.opencode2-profiles/work/state"
REPO="$HOME/opencode2"
PROFILE="$HOME/.opencode2-profiles/work/config/opencode"
DIST="$REPO/packages/opencode/dist/opencode-darwin-arm64/bin/opencode"
LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || hostname)"

# --- owner-maintained: what new members get, and who gets how much ---
CHANNELS='"telepathy","sansara","iktara","intuitxn-general","changelog","shared-files"'
PROGRAMS='"telepathy","sansara","iktara"'
TIERS='{
    "member":  {"agents": "all", "plugins": ["nodes", "runtimes", "navigate", "updates"], "sandbox_jobs": "always", "push": "manifest-pull"},
    "builder": {"agents": "all", "plugins": "all", "sandbox_jobs": "always", "push": "manifest-pull + gateway-token-jobs"},
    "steward": {"agents": "all", "plugins": "all", "sandbox_jobs": "always", "push": "manifest-pull + gateway-token-jobs + changelog-post"}
  }'
# ---------------------------------------------------------------------

ensure_dirs() { mkdir -p "$LABS/join" "$LABS/dist"; }

gen() {
  ensure_dirs
  REV="$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo '?')"
  AGENTS="$(ls "$PROFILE/agent/" 2>/dev/null | sed 's/\.md$//' | paste -sd, -)"
  PLUGINS="$(ls "$PROFILE/plugin/" 2>/dev/null | sed 's/\.ts$//' | paste -sd, -)"
  cat > "$LABS/team.json" <<EOF
{
  "org": "intuitxn-labs",
  "generated": "$(date '+%Y-%m-%dT%H:%M:%S%z')",
  "labs": "https://labs.intuitxn.com",
  "node": { "lan": "http://$LAN_IP:4096", "gateway": "http://$LAN_IP:4099", "health": "/global/health" },
  "runtime": {
    "version": "2.0.0",
    "source_rev": "$REV",
    "binary_rev": "$REV",
    "source": "https://github.com/anomalyco/opencode",
    "binary": "/dist/opencode-darwin-arm64",
    "update": "labs release — owner publishes; member nodes pull the binary + bundle",
    "fallback": "git clone the source, then: OPENCODE_CHANNEL=local OPENCODE_VERSION=2.0.0 bun run --cwd packages/opencode build"
  },
  "install": "curl -fsSL https://labs.intuitxn.com/join/oc2-join.sh | sh",
  "sync": "installed by join; pulls this manifest every 15 min; access tier decides what applies",
  "channels": [$CHANNELS],
  "programs": [$PROGRAMS],
  "agents": ["$(echo "$AGENTS" | sed 's/,/","/g')"],
  "plugins": ["$(echo "$PLUGINS" | sed 's/,/","/g')"],
  "access_tiers": $TIERS,
  "buzz": {
    "identity": "owner admits your agent identity in Buzz Desktop (Nest)",
    "then": "buzz channels join <name> for each channel above; your key never leaves your machine"
  },
  "boundary": "tools prepare, humans accept. jobs from the relay run sandboxed. agents draft, owners send."
}
EOF
  echo "team.json -> $LABS/team.json"
}

pack() {
  ensure_dirs
  TAR="$(mktemp /tmp/oc2-bundle-XXXXXX.tar.gz)"
  BUNDLE_ROOT="$(mktemp -d /tmp/oc2-bundle-XXXXXX)"
  mkdir -p "$BUNDLE_ROOT/profile" "$BUNDLE_ROOT/script/sandbox"
  cp -R "$PROFILE" "$BUNDLE_ROOT/profile/opencode"
  rm -rf "$BUNDLE_ROOT/profile/opencode/node_modules"
  cp "$REPO"/script/oc2-network.sh "$REPO"/script/oc2-node.sh "$REPO"/script/oc2-gateway.py "$REPO"/script/oc2-gateway.sh \
     "$REPO"/script/oc2-lan.sh "$REPO"/script/oc2-agent.sh "$REPO"/script/oc2-update.sh \
     "$REPO"/script/oc2-ship.sh "$REPO"/script/oc2-ship-stop.sh "$BUNDLE_ROOT/script/"
  cp "$REPO"/script/sandbox/oc2-job.sb "$BUNDLE_ROOT/script/sandbox/"
  tar -czf "$TAR" -C "$BUNDLE_ROOT" profile script
  mv "$TAR" "$LABS/oc2-bundle.tar.gz"
  rm -rf "$BUNDLE_ROOT"
  cp "$DIST" "$LABS/dist/opencode-darwin-arm64"
  cp "$REPO/script/oc2-join.sh" "$LABS/join/oc2-join.sh"
  cp "$REPO/script/oc2-sync.sh" "$LABS/join/oc2-sync.sh"
  echo "bundle: $LABS/oc2-bundle.tar.gz ($(du -h "$LABS/oc2-bundle.tar.gz" | cut -f1)), binary: $(du -h "$LABS/dist/opencode-darwin-arm64" | cut -f1)"
}

case "${1:-}" in
  gen) gen ;;
  pack) pack ;;
  publish) gen && pack ;;
  *) echo "usage: oc2-team.sh gen|pack|publish" >&2; exit 1 ;;
esac
