#!/bin/bash
# Installs cocoon-watch.sh as an hourly systemd timer. Disable: systemctl disable --now cocoon-watch.timer
set -e
mkdir -p /root/ops
curl -sL -o /root/ops/cocoon-watch.sh https://raw.githubusercontent.com/miinimal/cocoon-explorer/main/tools/cocoon-watch.sh
chmod 755 /root/ops/cocoon-watch.sh
printf '[Unit]\nDescription=Cocoon worker watcher\n[Service]\nType=oneshot\nExecStart=/root/ops/cocoon-watch.sh\n' > /etc/systemd/system/cocoon-watch.service
printf '[Unit]\nDescription=Run Cocoon worker watcher hourly\n[Timer]\nOnCalendar=hourly\nRandomizedDelaySec=300\nPersistent=true\n[Install]\nWantedBy=timers.target\n' > /etc/systemd/system/cocoon-watch.timer
systemctl daemon-reload
systemctl enable --now cocoon-watch.timer
/root/ops/cocoon-watch.sh --hello
echo "OK: watcher installed. Next run:"; systemctl list-timers cocoon-watch.timer --no-pager | sed -n 2p
