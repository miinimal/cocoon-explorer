#!/usr/bin/env python3
"""Daily attestation history for the live proxies.

GitHub Pages replaces the whole site on every deploy, so the history is carried
forward through the published site itself: download the previous
attestation-history.json, add (or replace) today's entry per endpoint, write it into
dist/, and attach a per-endpoint summary to the snapshot for the page.

If the previous history cannot be downloaded for any reason other than "not found",
the script exits non-zero so the deploy is skipped and the published history is kept.

Usage: history.py SNAPSHOT_JSON [--prev-url URL | --prev-file PATH]
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

PREV_URL = "https://miinimal.github.io/cocoon-explorer/attestation-history.json"
MAX_ENTRIES = 20000
FIELDS = ("dcap_status", "tcb_status", "advisory_ids", "image_hash", "image_allowed", "key_bound", "alive")


def entry_from_probe(x, date):
    att = (x.get("server_cert") or {}).get("attestation") or {}
    d = att.get("dcap") or {}
    return {
        "date": date,
        "endpoint": x.get("endpoint"),
        "alive": bool(x.get("alive") and x.get("stage") == "done"),
        "dcap_status": d.get("status"),
        "tcb_status": d.get("tcb_status"),
        "advisory_ids": d.get("advisory_ids") or [],
        "reason": d.get("reason"),
        "image_hash": att.get("image_hash"),
        "image_allowed": att.get("image_hash_allowed_by_root"),
        "key_bound": att.get("reportdata_binds_tls_key"),
        "probed_at": x.get("probed_at"),
    }


def merge(prev_entries, live, date):
    """Replace today's entries for the probed endpoints, keep everything else."""
    probed = {x.get("endpoint") for x in live if x.get("endpoint")}
    kept = [e for e in prev_entries if not (e.get("date") == date and e.get("endpoint") in probed)]
    new = [entry_from_probe(x, date) for x in live if x.get("endpoint")]
    out = sorted(kept + new, key=lambda e: (e.get("date") or "", e.get("endpoint") or ""))
    return out[-MAX_ENTRIES:]


def summarize(entries):
    by = {}
    for e in entries:
        s = by.setdefault(e["endpoint"], {"days": 0, "alive_days": 0, "verified_days": 0, "up_to_date_days": 0,
                                          "first": e["date"], "last": e["date"]})
        s["days"] += 1
        s["alive_days"] += 1 if e.get("alive") else 0
        s["verified_days"] += 1 if e.get("dcap_status") == "verified" else 0
        s["up_to_date_days"] += 1 if e.get("tcb_status") == "UpToDate" else 0
        s["first"] = min(s["first"], e["date"])
        s["last"] = max(s["last"], e["date"])
    return by


PARAMS_PREV_URL = "https://miinimal.github.io/cocoon-explorer/params-history.json"


def params_fingerprint(snap):
    """Network parameters tracked for changes: root params, config version and the allow-lists."""
    reg = snap.get("registry") or {}
    out = {f"params.{k}": v for k, v in (snap.get("params") or {}).items()}
    out["config_version"] = reg.get("config_version")
    for key in ("worker_image_hash_list", "proxy_image_hash_list", "model_hash_list"):
        if reg.get(key) is not None:
            out[key] = sorted(reg[key])
    return out


def params_changes(prev_entries, snap, date):
    """Append an entry only when a tracked parameter differs from the last recorded state."""
    cur = params_fingerprint(snap)
    entries = list(prev_entries)
    last = entries[-1]["state"] if entries else None
    if last is None:
        entries.append({"date": date, "kind": "first_observed", "state": cur, "changes": []})
        return entries
    changes = []
    for k in sorted(set(cur) | set(last)):
        a, b = last.get(k), cur.get(k)
        if a == b or b is None:
            continue
        if isinstance(a, list) or isinstance(b, list):
            sa, sb = set(a or []), set(b or [])
            changes.append({"field": k, "added": sorted(sb - sa), "removed": sorted(sa - sb)})
        else:
            changes.append({"field": k, "from": a, "to": b})
    if changes:
        merged = dict(last)
        merged.update({k: v for k, v in cur.items() if v is not None})
        entries.append({"date": date, "kind": "changed", "state": merged, "changes": changes})
    return entries


def params_summary(entries):
    changed = [e for e in entries if e["kind"] == "changed"]
    first = entries[0]["date"] if entries else None
    return {"observed_since": first, "changes": len(changed),
            "last_change": changed[-1]["date"] if changed else None,
            "last_fields": [c["field"] for c in changed[-1]["changes"]] if changed else []}


def load_prev(url=None, path=None, attempts=3):
    if path:
        with open(path) as f:
            return json.load(f).get("entries", [])
    last = None
    for i in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                return json.load(r).get("entries", [])
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return []
            last = e
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(3 * (i + 1))
    raise SystemExit(f"cannot load previous history ({last}); skipping deploy to keep it")


def main(argv):
    snap_path = argv[1]
    url, path = PREV_URL, None
    if "--prev-url" in argv:
        url = argv[argv.index("--prev-url") + 1]
    if "--prev-file" in argv:
        path = argv[argv.index("--prev-file") + 1]
    with open(snap_path) as f:
        snap = json.load(f)
    live = [x for x in (snap.get("live") or []) if x.get("endpoint")]
    today = time.strftime("%Y-%m-%d", time.gmtime())
    date = (snap.get("generated_at") or "")[:10]
    if date != today:
        # the indexer failed and an older snapshot is being republished: keep history unchanged
        print(f"history: snapshot is from {date or 'unknown date'}, not today; no new entries")
        live = []
    entries = merge(load_prev(url, path), live, date or today)
    here = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(os.path.join(here, "dist"), exist_ok=True)
    doc = {"description": "Daily independent attestation checks of Cocoon proxies (RA-TLS key binding, "
                          "root image allow-list, Intel DCAP signature and TCB status). One entry per "
                          "endpoint per UTC day; the latest probe of the day wins.",
           "updated_at": snap.get("generated_at"), "entries": entries}
    with open(os.path.join(here, "dist", "attestation-history.json"), "w") as f:
        json.dump(doc, f, ensure_ascii=False, indent=0)
    snap["attestation_history"] = summarize(entries)

    # network parameter change log, only from a fresh snapshot
    pparams = [] if path else load_prev(PARAMS_PREV_URL)
    if date == today and snap.get("params"):
        pentries = params_changes(pparams, snap, today)
    else:
        pentries = pparams
    with open(os.path.join(here, "dist", "params-history.json"), "w") as f:
        json.dump({"description": "Change log of COCOON root parameters (prices, fees, stakes, delays, contract code "
                                  "hashes), config version and image/model allow-lists, as observed by this map. "
                                  "An entry is added only when something changes.",
                   "updated_at": snap.get("generated_at"), "entries": pentries}, f, ensure_ascii=False, indent=0)
    snap["params_history"] = params_summary(pentries)
    with open(snap_path, "w") as f:
        json.dump(snap, f, ensure_ascii=False)
    print("history:", len(entries), "entries;", json.dumps(snap["attestation_history"]))


if __name__ == "__main__":
    main(sys.argv)
