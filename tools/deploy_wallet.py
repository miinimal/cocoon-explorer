#!/usr/bin/env python3
"""Deploy an uninitialized Cocoon node wallet (created by `gocoon init`) with a plain signed external message.

Why: on some setups the first external message from gocoon (deploy + client register in one message) never lands,
leaving the funded wallet `uninit`. This tool sends a minimal deploy (no actions), signed with the node key from
wallet.json. It first emulates the message with real signature checks and only broadcasts if emulation succeeds.

Usage: python3 deploy_wallet.py [/root/cocoon/gocoon-data/wallet.json] [--dry-run]
Reads: nodeSecretBase64, ownerAddress, nodeAddress (never prints secrets).
"""
import base64
import json
import sys
import time
import urllib.error
import urllib.request

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from pytoniq_core import Address, Cell, begin_cell

TONAPI = "https://tonapi.io/v2"
UA = {"User-Agent": "minimalai-deploy-wallet/0.1", "Content-Type": "application/json"}


def http(method, url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers=UA, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")[:600]


def load_code():
    status, d = http("GET", "https://raw.githubusercontent.com/TONresistor/gocoon/v0.3.0/pkg/resources/cocoon/cocoon-wallet.code.json")
    if status != 200:
        raise SystemExit(f"cannot fetch official wallet code: HTTP {status}")
    code = Cell.one_from_boc(bytes.fromhex(d["hex"]))
    if code.hash.hex() != "7a48f05ceef40f06cabbaa39c1c5a67b24e8bb59d8cf8a74e49988a5f44cf66a":
        raise SystemExit("wallet code hash mismatch — refusing to continue")
    return code


def main():
    path = next((a for a in sys.argv[1:] if not a.startswith("-")), "/root/cocoon/gocoon-data/wallet.json")
    dry = "--dry-run" in sys.argv or "-n" in sys.argv
    w = json.load(open(path))
    seed = base64.b64decode(w["nodeSecretBase64"])
    seed = seed[:32]
    key = Ed25519PrivateKey.from_private_bytes(seed)
    pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    owner = Address(w["ownerAddress"])
    code = load_code()
    data = (begin_cell().store_int(0, 32).store_int(0, 32).store_bytes(pub).store_uint(0, 32)
            .store_address(owner).end_cell())
    state_init = begin_cell().store_uint(0, 2).store_maybe_ref(code).store_maybe_ref(data).store_uint(0, 1).end_cell()
    addr = Address((0, state_init.hash))
    print("wallet:", addr.to_str(is_bounceable=True))
    if addr.to_str(is_bounceable=True) != Address(w["nodeAddress"]).to_str(is_bounceable=True):
        raise SystemExit("derived address != nodeAddress in wallet.json — refusing to continue")

    st, acc = http("GET", f"{TONAPI}/blockchain/accounts/{addr.to_str()}")
    print("on-chain:", acc.get("status") if isinstance(acc, dict) else acc, "balance:",
          (acc.get("balance", 0) / 1e9) if isinstance(acc, dict) else "?")
    if isinstance(acc, dict) and acc.get("status") == "active":
        print("already deployed — nothing to do")
        return

    body = (begin_cell().store_uint(0, 32).store_uint(int(time.time()) + 600, 32).store_uint(0, 32).end_cell())
    sig = key.sign(body.hash)
    signed = begin_cell().store_bytes(sig).store_slice(body.begin_parse()).end_cell()
    msg = (begin_cell().store_uint(0b10, 2).store_uint(0, 2).store_address(addr).store_coins(0)
           .store_uint(1, 1).store_uint(1, 1).store_ref(state_init)
           .store_uint(1, 1).store_ref(signed).end_cell())
    boc = base64.b64encode(msg.to_boc()).decode()

    st, em = http("POST", f"{TONAPI}/traces/emulate", {"boc": boc})
    if st != 200:
        raise SystemExit(f"emulation rejected (HTTP {st}): {em}")
    tx = em.get("transaction", {})
    cp = tx.get("compute_phase", {})
    print(f"emulation: success={tx.get('success')} exit_code={cp.get('exit_code')} gas={cp.get('gas_used')}")
    if not tx.get("success"):
        raise SystemExit("emulation failed — not broadcasting")
    if dry:
        print("dry run — not broadcasting")
        return

    st, res = http("POST", f"{TONAPI}/blockchain/message", {"boc": boc})
    print("broadcast tonapi:", st, res if res else "ok")
    if st >= 400:
        st2, res2 = http("POST", "https://toncenter.com/api/v2/sendBoc", {"boc": boc})
        print("broadcast toncenter:", st2, res2)

    for _ in range(24):
        time.sleep(5)
        st, acc = http("GET", f"{TONAPI}/blockchain/accounts/{addr.to_str()}")
        s = acc.get("status") if isinstance(acc, dict) else None
        if s == "active":
            print("DEPLOYED: wallet is active, balance", acc.get("balance", 0) / 1e9, "TON")
            return
    print("not active yet — check again in a minute")


if __name__ == "__main__":
    main()
