#!/bin/bash
# Cocoon worker watcher: counts live workers via a local Cocoon client runner (127.0.0.1:10000) and sends a
# Telegram message when workers appear or disappear. Reads BOT_TOKEN and OWNER_ID from $WATCH_ENV.
set -u
ENVF=${WATCH_ENV:-/root/minimalcult/.env}
STATE=/root/ops/cocoon-watch.state
LOG=/root/ops/cocoon-watch.log
mkdir -p /root/ops
TOKEN=$(grep -E '^BOT_TOKEN=' "$ENVF" | head -1 | cut -d= -f2- | tr -d '"'"'"' \r')
OWNER=$(grep -E '^OWNER_ID=' "$ENVF" | head -1 | cut -d= -f2- | tr -d '"'"'"' \r')
J=$(curl -s -m 30 http://127.0.0.1:10000/v1/models)
W=$(printf '%s' "$J" | python3 -c 'import sys,json
try:
  d=json.load(sys.stdin); print(sum(len(m.get("workers") or []) for m in d.get("data",[])))
except Exception: print(-1)')
PREV=$(cat "$STATE" 2>/dev/null || echo 0)
echo "$(date -u +%FT%TZ) workers=$W" >> "$LOG"
send() { [ -n "$TOKEN" ] && [ -n "$OWNER" ] && curl -s -m 20 "https://api.telegram.org/bot$TOKEN/sendMessage" \
  --data-urlencode "chat_id=$OWNER" --data-urlencode "text=$1" >/dev/null; }
if [ "${1:-}" = "--hello" ]; then
  send "MINIMALAI: слежение за Cocoon включено. Проверка раз в час. Сейчас живых воркеров: $W."
fi
if [ "$W" -gt 0 ] && [ "$PREV" -le 0 ]; then
  send "🟢 Cocoon ожил: живых воркеров $W."
elif [ "$W" -eq 0 ] && [ "$PREV" -gt 0 ]; then
  send "🔴 Cocoon: воркеры пропали (было $PREV, стало 0)."
fi
[ "$W" -ge 0 ] && echo "$W" > "$STATE"
