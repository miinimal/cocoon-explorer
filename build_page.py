#!/usr/bin/env python3
"""Build a self-contained explorer page: template.html + data/snapshot.json -> dist/index.html."""
import json
import os
import sys

here = os.path.dirname(os.path.abspath(__file__))
snap_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "data", "snapshot.json")
with open(snap_path) as f:
    snap = json.load(f)
with open(os.path.join(here, "template.html")) as f:
    html = f.read()
payload = json.dumps(snap, ensure_ascii=False).replace("</", "<\\/")
html = html.replace("/*__SNAPSHOT__*/null", payload)
os.makedirs(os.path.join(here, "dist"), exist_ok=True)
out = os.path.join(here, "dist", "index.html")
with open(out, "w") as f:
    f.write(html)
print("ok ->", out, len(html), "bytes")
