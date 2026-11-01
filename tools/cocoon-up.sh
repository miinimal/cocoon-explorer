#!/bin/bash
# cocoon-up: connect a Linux server to the Cocoon network (Telegram / TON) as a client in one command.
#
#   curl -sL https://raw.githubusercontent.com/miinimal/cocoon-explorer/main/tools/cocoon-up.sh | bash
#
# Run it twice: the first run installs the client and prints the address to fund (~20 TON, 15 TON of it is a
# refundable stake); the second run, after funding, deploys the wallet, registers the payment channel and starts
# a permanent OpenAI-compatible endpoint on 127.0.0.1:10000.
#
# Fixes built in (found while connecting MINIMALCULT on 2026-11-01):
#  - the first gocoon external message (deploy + register) may never land: the wallet is deployed separately by an
#    emulated-first signed message (tools/deploy_wallet.py);
#  - the bundled lite-server list can silently drop outgoing messages: replaced with https://ton.org/global.config.json;
#  - the runner is installed as a systemd service (auto-restart, survives reboot).
# Built by Aleksandr Shcherbakov (@miinimal), MINIMALCULT. MIT license. No warranty: you are funding a wallet whose keys live in $DIR/wallet.json.
set -euo pipefail

V=${GOCOON_VERSION:-v0.3.0}
DIR=${COCOON_DIR:-/root/cocoon}
DATA=$DIR/gocoon-data
RAW=https://raw.githubusercontent.com/miinimal/cocoon-explorer/main/tools
say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

[ "$(id -u)" = 0 ] || { echo "run as root"; exit 1; }
[ "$(uname -m)" = x86_64 ] || { echo "only linux x86_64 is supported by this script"; exit 1; }
mkdir -p "$DIR"

if ! command -v gocoon >/dev/null || ! gocoon version 2>/dev/null | grep -q "${V#v}"; then
  say "1/5 installing gocoon $V (TONresistor/gocoon, checksum verified)"
  F=gocoon-$V-linux-amd64.tar.gz
  cd "$DIR"
  curl -sSL -o "$F" "https://github.com/TONresistor/gocoon/releases/download/$V/$F"
  curl -sSL -o "$F.sha256" "https://github.com/TONresistor/gocoon/releases/download/$V/$F.sha256"
  sha256sum -c "$F.sha256" >/dev/null 2>&1 || (awk -v f="$F" '{print $1"  "f}' "$F.sha256" | sha256sum -c - >/dev/null)
  tar xzf "$F"
  install -m 755 "$(find "$DIR" -maxdepth 3 -type f -name gocoon | head -1)" /usr/local/bin/gocoon
  install -m 755 "$(find "$DIR" -maxdepth 3 -type f -name gocoon-runner | head -1)" /usr/local/bin/gocoon-runner
else
  say "1/5 gocoon already installed"
fi

if [ ! -f "$DATA/wallet.json" ]; then
  say "2/5 creating Cocoon wallet"
  gocoon init --dir "$DATA" >/dev/null
  chmod 700 "$DATA"; chmod 600 "$DATA"/*.json
else
  say "2/5 wallet exists (not overwriting)"
fi
if [ ! -f "$DATA/ton-config.bak" ]; then
  cp "$DATA/ton-config.json" "$DATA/ton-config.bak"
  curl -sSL -o "$DATA/ton-config.json" https://ton.org/global.config.json
fi

ADDR=$(python3 -c "import json;print(json.load(open('$DATA/wallet.json'))['nodeAddress'])")
ACC=$(curl -s -m 20 "https://tonapi.io/v2/blockchain/accounts/$ADDR")
BAL=$(printf '%s' "$ACC" | python3 -c "import sys,json
try: print(json.load(sys.stdin).get('balance',0))
except Exception: print(0)")
STATUS=$(printf '%s' "$ACC" | python3 -c "import sys,json
try: print(json.load(sys.stdin).get('status','none'))
except Exception: print('none')")
# an already deployed wallet has spent part of its balance on the stake: never ask to fund it again
if [ "$STATUS" != active ] && [ "${BAL:-0}" -lt 19000000000 ]; then
  say "3/5 fund this wallet with 20 TON, then run this command again"
  UQ=$(python3 - "$ADDR" <<'PY'
import base64,sys,binascii
a=sys.argv[1]; b=bytearray(base64.urlsafe_b64decode(a+'='*(-len(a)%4)))
b[0]=0x51  # non-bounceable flag, recompute crc16
def crc16(d):
    c=0
    for x in d:
        c^=x<<8
        for _ in range(8):
            c=((c<<1)^0x1021) if c&0x8000 else c<<1
            c&=0xffff
    return c
b=b[:34]+crc16(b[:34]).to_bytes(2,'big'); print(base64.urlsafe_b64encode(bytes(b)).decode())
PY
)
  echo "  address (use this one): $UQ"
  echo "  amount: 20 TON (15 TON stake is refundable; ~1.7 TON gas; rest = request budget)"
  echo "  current balance: $(python3 -c "print(${BAL:-0}/1e9)") TON"
  exit 0
fi

if [ "$STATUS" != active ]; then
  say "4/5 deploying the wallet (emulate first, then broadcast)"
  curl -sSL -o "$DIR/deploy_wallet.py" "$RAW/deploy_wallet.py"
  if python3 -c "import pytoniq_core, cryptography" 2>/dev/null; then
    python3 "$DIR/deploy_wallet.py" "$DATA/wallet.json"
  elif command -v docker >/dev/null; then
    docker run --rm -v "$DIR:$DIR" python:3.12-slim sh -c \
      "pip install -q --disable-pip-version-check pytoniq-core cryptography >/dev/null 2>&1 && python $DIR/deploy_wallet.py $DATA/wallet.json"
  else
    PIP_BREAK_SYSTEM_PACKAGES=1 python3 -m pip install -q pytoniq-core cryptography && python3 "$DIR/deploy_wallet.py" "$DATA/wallet.json"
  fi
else
  say "4/5 wallet already active"
fi

say "5/5 starting the client as a service (gocoon.service)"
for u in gocoon2 gocoon3; do systemctl stop "$u" 2>/dev/null || true; done
cat > /etc/systemd/system/gocoon.service <<UNIT
[Unit]
Description=Cocoon client runner (gocoon)
After=network-online.target
Wants=network-online.target
[Service]
WorkingDirectory=$DIR
ExecStart=/usr/local/bin/gocoon run -config $DATA/client-config.json -runner /usr/local/bin/gocoon-runner
Restart=always
RestartSec=10
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now gocoon >/dev/null
for i in $(seq 1 36); do
  curl -s -m 5 http://127.0.0.1:10000/v1/models | grep -q '"data"' && break
  sleep 10
done
echo
echo "channel:"; gocoon status 2>/dev/null | python3 -c "import sys,json
d=json.load(sys.stdin); [print('  proxy',c['address'],'ready' if c['is_ready'] else 'not ready') for c in d.get('proxy_connections',[])]" || true
echo "models:";  curl -s -m 20 http://127.0.0.1:10000/v1/models | python3 -c "import sys,json
d=json.load(sys.stdin); [print('  ',m['id'],'workers:',len(m.get('workers') or [])) for m in d.get('data',[])]" || true
echo
echo "OpenAI-compatible endpoint: http://127.0.0.1:10000/v1   (logs: journalctl -u gocoon -f)"
echo "Network map: https://miinimal.github.io/cocoon-explorer/   Built by Aleksandr Shcherbakov (@miinimal), MINIMALCULT — t.me/minimalcult"
