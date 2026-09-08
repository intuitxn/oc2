#!/bin/sh
# Source this before invoking Buzz. The legacy URL remains a fallback/CLI alias.
export INTUITXN_NETWORK="${INTUITXN_NETWORK:-${BUZZ_RELAY_URL:-https://intuitxn.communities.buzz.xyz}}"
export BUZZ_RELAY_URL="$INTUITXN_NETWORK"
case "$INTUITXN_NETWORK" in
  https://*) export INTUITXN_NETWORK_WS="wss://${INTUITXN_NETWORK#https://}" ;;
  http://*) export INTUITXN_NETWORK_WS="ws://${INTUITXN_NETWORK#http://}" ;;
  *) echo 'INTUITXN_NETWORK must use http:// or https://' >&2; return 1 ;;
esac
