#!/usr/bin/env python3
"""Cocoon Explorer — indexer (MINIMALAI, block 1).

Reads the live state of the Cocoon network from the TON blockchain and writes
explorer/data/snapshot.json. No wallet, no stake, no keys required.

Sources: tonapi.io (get-methods, raw account data, events). Cell parsing via
pytoniq-core for the registered-proxies dictionary.

Usage:  python3 indexer.py [--out data/snapshot.json] [--months 12]
"""
import argparse
import datetime as dt
import json
import sys
import time
import urllib.request
from collections import Counter, defaultdict

ROOT = "EQCns7bYSp0igFvS1wpb5wsZjCKCV19MD5AVzI4EyxsnU73k"
ROOT_TESTNET = "EQBT4hy4vMEZ9uxSCuhw_gBKh9_AwmHXLe7Wo0O4Vh-4kRjJ"
PROXY_SC = "EQDGkQM7RIWp6yGW79i8oV3zJ-vdnpV68pdZ2W8mrpE3cJ2y"  # from ton-blockchain/abis
TONAPI = "https://tonapi.io/v2"
UA = {"User-Agent": "minimalai-explorer/0.1 (+https://t.me/minimalcult)"}
NANO = 1e9


def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            if i == tries - 1:
                raise
            time.sleep(1.5 * (i + 1))


def run_method(addr, method):
    d = get(f"{TONAPI}/blockchain/accounts/{addr}/methods/{method}")
    if not d.get("success"):
        return None
    return d.get("decoded") or d.get("stack")


def account(addr):
    d = get(f"{TONAPI}/blockchain/accounts/{addr}")
    return {"address": addr, "balance_ton": round(d["balance"] / NANO, 3), "status": d.get("status"),
            "last_activity": iso(d.get("last_activity")) if d.get("last_activity") else None}


def iso(ts):
    return dt.datetime.fromtimestamp(ts, dt.UTC).strftime("%Y-%m-%dT%H:%MZ")


# --- root data cell: proxies / hashes -------------------------------------------------------

def parse_root_data(addr):
    """Parse RootStorage: owner, version, ref0 = data{proxy_hashes, registered_proxies, last_seqno,
    worker_hashes, model_hashes}. Returns proxies list and hash counts."""
    from pytoniq_core import Cell, Slice  # noqa: WPS433

    raw = get(f"{TONAPI}/blockchain/accounts/{addr}")
    data_cell = Cell.one_from_boc(raw["data"])
    s = data_cell.begin_parse()
    s.load_address()  # owner
    version = s.load_uint(32)
    data = s.load_ref().begin_parse()

    def dict_count(sl, keylen):
        d = sl.load_dict(keylen)
        return 0 if d is None else len(d)

    proxy_hashes = dict_count(data, 256)
    reg = data.load_dict(32, value_deserializer=lambda v: v)
    proxies = []
    if reg:
        for seqno, v in reg.items():
            cs = v if isinstance(v, Slice) else v.begin_parse()
            cs.load_bit()  # type bit = 0
            ln = cs.load_uint(7)
            txt = cs.load_bytes(ln).decode("ascii", "replace")
            parts = txt.split()
            proxies.append({"seqno": seqno, "worker_endpoint": parts[0] if parts else txt,
                            "client_endpoint": parts[1] if len(parts) > 1 else None})
    last_proxy_seqno = data.load_uint(32)
    worker_hashes = dict_count(data, 256)
    model_hashes = dict_count(data, 256)
    return {"config_version": version, "proxies": sorted(proxies, key=lambda p: p["seqno"]),
            "proxy_image_hashes": proxy_hashes, "worker_image_hashes": worker_hashes,
            "model_hashes": model_hashes, "last_proxy_seqno": last_proxy_seqno}


# --- events / monthly stats ------------------------------------------------------------------

COMMIT_OP = "0x9a1247c0"  # proxy state commit (from proxy node wallet)


def monthly_stats(addr, months):
    now = dt.datetime.now(dt.UTC)
    out = []
    y, m = now.year, now.month
    for _ in range(months):
        start = dt.datetime(y, m, 1, tzinfo=dt.UTC)
        end = dt.datetime(y + (m == 12), (m % 12) + 1, 1, tzinfo=dt.UTC) - dt.timedelta(seconds=1)
        evs, lt, pages = [], None, 0
        while pages < 20:
            u = (f"{TONAPI}/accounts/{addr}/events?limit=100&start_date={int(start.timestamp())}"
                 f"&end_date={int(end.timestamp())}" + (f"&before_lt={lt}" if lt else ""))
            d = get(u)
            batch = d.get("events", [])
            if not batch:
                break
            evs += batch
            lt = d.get("next_from")
            pages += 1
            if not lt:
                break
            time.sleep(0.25)
        ops, clients, ton_in, payouts, commits = Counter(), set(), 0, 0, 0
        for e in evs:
            for a in e.get("actions", []):
                if a.get("type") != "SmartContractExec":
                    continue
                sc = a["SmartContractExec"]
                op = sc.get("operation", "")
                if op == COMMIT_OP:
                    commits += 1
                    continue
                ops[op] += 1
                if op == "CocoonClientProxyRequest":
                    clients.add(sc["executor"]["address"])
                    ton_in += sc.get("ton_attached", 0)
                if "Payout" in op:
                    payouts += sc.get("ton_attached", 0)
        out.append({"month": f"{y}-{m:02d}", "events": len(evs), "truncated": pages >= 20,
                    "proxy_commits": commits, "client_wallets": len(clients),
                    "client_deposits_ton": round(ton_in / NANO, 2), "payouts_ton": round(payouts / NANO, 2),
                    "ops": dict(ops)})
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(out))


def admin_timeline(addr, limit=100):
    d = get(f"{TONAPI}/blockchain/accounts/{addr}/transactions?limit={limit}")
    items = []
    for t in d.get("transactions", []):
        m = t.get("in_msg") or {}
        op = m.get("decoded_op_name")
        if not op or not op.startswith("cocoon_"):
            continue
        items.append({"time": iso(t["utime"]), "op": op, "from": (m.get("source") or {}).get("address", "")[:12]})
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/snapshot.json")
    ap.add_argument("--months", type=int, default=8)
    a = ap.parse_args()

    snap = {"generated_at": iso(int(time.time())), "source": "tonapi.io", "network": "mainnet",
            "root": account(ROOT), "proxy_contract": account(PROXY_SC)}
    snap["root"].update(run_method(ROOT, "get_cocoon_data") or {})
    snap["params"] = run_method(ROOT, "get_cur_params") or {}
    try:
        snap["registry"] = parse_root_data(ROOT)
    except Exception as e:  # noqa: BLE001
        snap["registry"] = {"error": str(e)[:200]}
    p = snap["params"]
    ppt = int(p.get("price_per_token", 0))
    mult = {"prompt": 10000, "cached": int(p.get("cached_tokens_price_multiplier", 10000)),
            "completion": int(p.get("completion_tokens_price_multiplier", 80000)),
            "reasoning": int(p.get("reasoning_tokens_price_multiplier", 80000))}
    snap["pricing"] = {"price_per_token_nano": ppt,
                       "ton_per_1k_tokens": {k: round(ppt * v / 10000 * 1000 / NANO, 6) for k, v in mult.items()},
                       "proxy_fee_percent": round((1 - int(p.get("worker_fee_per_token", ppt)) / ppt) * 100, 1) if ppt else None,
                       "client_min_stake_ton": int(p.get("min_client_stake", 0)) / NANO,
                       "client_close_delay_hours": int(p.get("client_delay_before_close", 0)) / 3600,
                       "note": "completion multiplier is assumed 80000 if the get-method omits it; verify with a live request"}
    # live probe of every registered proxy (+ the historic second proxy), no payment, no registration
    try:
        import probe as _probe
        eps = [p["client_endpoint"] for p in snap["registry"].get("proxies", []) if p.get("client_endpoint")]
        for extra in ("91.108.4.12:8888",):
            if extra not in eps:
                eps.append(extra)
        ver = int(snap["registry"].get("config_version") or snap["root"].get("version") or 0)
        snap["live"] = [_probe.probe(e, root_config_version=ver, timeout=20) for e in eps]
    except Exception as e:  # noqa: BLE001
        snap["live"] = [{"error": f"probe unavailable: {str(e)[:160]}"}]
    snap["monthly"] = monthly_stats(PROXY_SC, a.months)
    snap["admin_timeline"] = admin_timeline(ROOT)
    import os
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w") as f:
        json.dump(snap, f, ensure_ascii=False, indent=1)
    print(f"ok -> {a.out}: proxies={len(snap['registry'].get('proxies', []))} months={len(snap['monthly'])} "
          f"admin_ops={len(snap['admin_timeline'])} root_balance={snap['root']['balance_ton']} TON")


if __name__ == "__main__":
    sys.exit(main())
