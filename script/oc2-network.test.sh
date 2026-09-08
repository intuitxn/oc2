#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
check() {
  actual=$(env -u INTUITXN_NETWORK -u BUZZ_RELAY_URL "$@" /bin/sh -c '. "$1"; printf "%s|%s|%s" "$INTUITXN_NETWORK" "$BUZZ_RELAY_URL" "$INTUITXN_NETWORK_WS"' sh "$ROOT/oc2-network.sh")
  [ "$actual" = "$expected" ] || { printf 'Unexpected network resolution: %s\n' "$actual" >&2; exit 1; }
}
expected='https://intuitxn.communities.buzz.xyz|https://intuitxn.communities.buzz.xyz|wss://intuitxn.communities.buzz.xyz'
check env
expected='http://localhost:3000|http://localhost:3000|ws://localhost:3000'
check env BUZZ_RELAY_URL=http://localhost:3000
expected='https://team.example|https://team.example|wss://team.example'
check env INTUITXN_NETWORK=https://team.example BUZZ_RELAY_URL=http://localhost:3000
if env INTUITXN_NETWORK=wss://invalid /bin/sh -c '. "$1"' sh "$ROOT/oc2-network.sh" 2>/dev/null; then
  echo 'Invalid scheme accepted' >&2; exit 1
fi
printf 'Network defaults, legacy fallback, canonical precedence, WebSocket derivation and invalid scheme: passed\n'
