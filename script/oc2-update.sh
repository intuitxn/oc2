#!/bin/sh
# oc2-update: pull, install, build the latest opencode2, verify, draft changelog.
set -eu

REPO="$HOME/opencode2"
DIST_BIN="$REPO/packages/opencode/dist/opencode-darwin-arm64/bin/opencode"
DRAFTS="$HOME/.opencode2-profiles/CHANGELOG-DRAFTS"

cd "$REPO"
OLD_REV="$(git rev-parse --short HEAD 2>/dev/null || echo none)"
git pull --ff-only
NEW_REV="$(git rev-parse --short HEAD)"

if [ "$OLD_REV" != "$NEW_REV" ]; then
  bun install
  OPENCODE_CHANNEL=local OPENCODE_VERSION=2.0.0 bun run --cwd packages/opencode build
else
  echo "already up to date at $NEW_REV (no rebuild)"
fi

if "$DIST_BIN" --version >/dev/null 2>&1; then
  VER="$("$DIST_BIN" --version)"
  echo "verified: opencode $VER at rev $NEW_REV"
else
  echo "REFUSING: new build failed --version; last good dist kept" >&2
  exit 1
fi

mkdir -p "$DRAFTS"
ENTRY="$DRAFTS/$(date +%Y-%m-%d)-rev-$NEW_REV.md"
if [ ! -f "$ENTRY" ]; then
  {
    printf -- '---\ntitle: "oc2 update rev %s"\ndate: %s\nstatus: draft\n---\n\n' "$NEW_REV" "$(date +%Y-%m-%dT%H:%M:%S%z)"
    printf -- '- opencode2 updated %s -> %s (%s).\n' "$OLD_REV" "$NEW_REV" "$VER"
    printf -- '- Plugin set and charters synced from ~/opencode2/specs.\n'
    printf -- '- Draft only: post to buzz `changelog` from the owner environment.\n'
  } > "$ENTRY"
  echo "changelog draft: $ENTRY"
fi
