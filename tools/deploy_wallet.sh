#!/bin/bash
# One-liner: curl -sL https://raw.githubusercontent.com/miinimal/cocoon-explorer/main/tools/deploy_wallet.sh | bash
set -e
W=/root/cocoon/gocoon-data/wallet.json
curl -sL -o /root/cocoon/deploy_wallet.py https://raw.githubusercontent.com/miinimal/cocoon-explorer/main/tools/deploy_wallet.py
echo "== stopping gocoon runner while deploying"
systemctl stop gocoon2 2>/dev/null || true
systemctl stop gocoon 2>/dev/null || true
echo "== deploying Cocoon wallet (emulate first, then broadcast)"
docker run --rm -v /root/cocoon:/root/cocoon python:3.12-slim sh -c \
  "pip install -q --disable-pip-version-check pytoniq-core cryptography >/dev/null 2>&1 && python /root/cocoon/deploy_wallet.py $W"
echo "== restarting gocoon runner"
systemctl reset-failed gocoon3 2>/dev/null || true
systemd-run -u gocoon3 -p Restart=always -p RestartSec=10 /usr/local/bin/gocoon run -config /root/cocoon/gocoon-data/client-config.json -runner /usr/local/bin/gocoon-runner
echo "== done; check logs in ~3 min: journalctl -u gocoon3 -n 30 | cat"
