#!/bin/sh
# oc2-agent: the harness-callable agent entry.
# Headless opencode run against the canonical profile — this is what a harness
# (desk, nudge, cron, another agent) calls to put an agent on a task.
#
# Usage:
#   oc2-agent.sh "task text" [--agent NAME] [--dir DIR] [--model provider/model] [--sandbox] [--node]
#
# --sandbox runs the whole agent under the macOS seatbelt profile
# (script/sandbox/oc2-job.sb): writes confined to the job directory and the
# node's runtime dirs, secrets unreadable. Use it for user-sourced jobs.
# --node routes through the resident node (http://127.0.0.1:4096) instead of
# spawning a fresh local server.
set -eu

OC2="$HOME/opencode2/packages/opencode/dist/opencode-darwin-arm64/bin/opencode"
SB_TEMPLATE="$HOME/opencode2/script/sandbox/oc2-job.sb"
STATE="$HOME/.opencode2-profiles/work"
NODE_PORT=4096

export XDG_CONFIG_HOME="$STATE/config"
export XDG_DATA_HOME="$STATE/data"
export XDG_CACHE_HOME="$STATE/cache"
export XDG_STATE_HOME="$STATE/state"

AGENT=""; DIR=""; MODEL=""; SANDBOX=0; NODE=0; TASK=""
while [ $# -gt 0 ]; do
  case "$1" in
    --agent) AGENT="$2"; shift 2 ;;
    --dir) DIR="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    --sandbox) SANDBOX=1; shift ;;
    --node) NODE=1; shift ;;
    *) TASK="${TASK:+$TASK }$1"; shift ;;
  esac
done
[ -n "$TASK" ] || { echo 'usage: oc2-agent.sh "task" [--agent NAME] [--dir DIR] [--model p/m] [--sandbox] [--node]' >&2; exit 1; }

ARGS=""
[ -n "$AGENT" ] && ARGS="$ARGS --agent $AGENT"
[ -n "$MODEL" ] && ARGS="$ARGS --model $MODEL"
[ -n "$DIR" ] && ARGS="$ARGS --dir $DIR"

if [ "$NODE" = 1 ]; then
  PW="$(cat "$STATE/state/node-password" 2>/dev/null || true)"
  exec "$OC2" run --attach "http://127.0.0.1:$NODE_PORT" ${PW:+-p "$PW"} $ARGS "$TASK"
fi

if [ "$SANDBOX" = 1 ]; then
  WORK="${DIR:-$PWD}"
  [ -d "$WORK" ] || { echo "no such dir: $WORK" >&2; exit 1; }
  SB="$(mktemp /tmp/oc2-job-XXXXXX)"
  sed -e "s|@WORKTREE@|$WORK|g" -e "s|@STATE@|$STATE|g" "$SB_TEMPLATE" > "$SB"
  exec sandbox-exec -f "$SB" "$OC2" run $ARGS "$TASK" < /dev/null
fi

exec "$OC2" run $ARGS "$TASK" < /dev/null
