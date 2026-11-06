#!/usr/bin/env python3
"""Cocoon Explorer — live proxy probe (MINIMALAI, block 2).

Performs the client side of the Cocoon proxy handshake WITHOUT paying or registering:
TCP -> proof-of-work -> TLS 1.3 (ephemeral Ed25519 client cert) -> tcp.connect ->
client.connectToProxy (random, never-funded address) -> client.getWorkerTypesV2.

Records: reachability, PoW difficulty and solve time, TLS details, the proxy's server
certificate (SHA-256 and extension OIDs — raw material for TEE attestation checks),
proxy params, and worker types / load if the proxy answers before authorization.

Usage: python3 probe.py 91.108.4.11:8888 [--json]
"""
import base64
import datetime as dt
import hashlib
import json
import os
import secrets
import socket
import ssl
import struct
import sys
import tempfile
import time
import zlib

POW_CHALLENGE_MAGIC = 0x418E1291
POW_RESPONSE_MAGIC = 0x01827319
POW_MAX_DIFFICULTY = 32


def crc(s):
    return zlib.crc32(s.encode())


TCP_PING = crc("tcp.ping id:long = tcp.Packet")
TCP_PONG = crc("tcp.pong id:long = tcp.Packet")
TCP_PACKET = crc("tcp.packet data:bytes = tcp.Packet")
TCP_QUERY_ANSWER = crc("tcp.queryAnswer id:long data:bytes = tcp.Packet")
TCP_QUERY_ERROR = crc("tcp.queryError id:long code:int message:string = tcp.Packet")
TCP_QUERY = crc("tcp.query id:long data:bytes = tcp.Packet")
TCP_CONNECTED = crc("tcp.connected id:long = tcp.Packet")
TCP_CONNECT = crc("tcp.connect id:long = tcp.Packet")

BOOL_FALSE, BOOL_TRUE = 0xBC799737, 0x997275B5
CLIENT_CONNECT_TO_PROXY = 0xFF5FA0F4
CLIENT_CONNECTED_TO_PROXY = 0x95317AD1
CLIENT_GET_WORKER_TYPES_V2 = 0xB2133D72
CLIENT_WORKER_TYPES_V2 = 0x0CF0DC67
AUTH_SHORT, AUTH_LONG = 0xD6FFC5AF, 0x417BF016


# ---------------------------------------------------------------- TL primitives

class W:
    def __init__(self):
        self.b = bytearray()

    def u32(self, v):
        self.b += struct.pack("<I", v & 0xFFFFFFFF); return self

    def i32(self, v):
        self.b += struct.pack("<i", v); return self

    def i64(self, v):
        self.b += struct.pack("<q", v); return self

    def bytes_(self, data):
        n = len(data)
        if n < 0xFE:
            self.b += bytes([n]) + data
            total = 1 + n
        else:
            self.b += bytes([0xFE]) + struct.pack("<I", n)[:3] + data
            total = 4 + n
        self.b += b"\0" * ((4 - total % 4) % 4)
        return self

    def str_(self, s):
        return self.bytes_(s.encode())

    def bool_(self, v):
        return self.u32(BOOL_TRUE if v else BOOL_FALSE)


class R:
    def __init__(self, b):
        self.b, self.p = bytes(b), 0

    def take(self, n):
        if self.p + n > len(self.b):
            raise ValueError("TL: truncated")
        v = self.b[self.p:self.p + n]; self.p += n; return v

    def u32(self):
        return struct.unpack("<I", self.take(4))[0]

    def i32(self):
        return struct.unpack("<i", self.take(4))[0]

    def i64(self):
        return struct.unpack("<q", self.take(8))[0]

    def i256(self):
        return self.take(32)

    def bytes_(self):
        n = self.take(1)[0]
        if n < 0xFE:
            data = self.take(n); total = 1 + n
        else:
            n = int.from_bytes(self.take(3), "little"); data = self.take(n); total = 4 + n
        self.take((4 - total % 4) % 4)
        return data

    def str_(self):
        return self.bytes_().decode("utf-8", "replace")

    def bool_(self):
        v = self.u32()
        if v not in (BOOL_TRUE, BOOL_FALSE):
            raise ValueError(f"TL: bad Bool {v:#x}")
        return v == BOOL_TRUE


# ---------------------------------------------------------------- framing

class Framed:
    def __init__(self, sock):
        self.s, self.out_seq, self.in_seq = sock, 0, 0

    def send(self, payload):
        self.s.sendall(struct.pack("<II", len(payload), self.out_seq) + bytes(payload))
        self.out_seq += 1

    def _read(self, n):
        buf = bytearray()
        while len(buf) < n:
            chunk = self.s.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("closed by proxy")
            buf += chunk
        return bytes(buf)

    def recv(self):
        while True:
            size, seq = struct.unpack("<Ii", self._read(8))
            if size == 0:
                continue  # keepalive
            if size > 16 * 1024 * 1024:
                raise ValueError("frame too large")
            data = self._read(size)
            self.in_seq = seq + 1
            return data


# ---------------------------------------------------------------- PoW

def solve_pow(sock, timeout):
    sock.settimeout(timeout)
    ch = b""
    while len(ch) < 24:
        part = sock.recv(24 - len(ch))
        if not part:
            raise ConnectionError("closed before PoW challenge")
        ch += part
    magic, difficulty = struct.unpack("<Ii", ch[:8])
    salt = ch[8:24]
    if magic != POW_CHALLENGE_MAGIC:
        raise ValueError(f"unexpected PoW magic {magic:#x}")
    if not 0 <= difficulty <= POW_MAX_DIFFICULTY:
        raise ValueError(f"PoW difficulty {difficulty} too high")
    t0 = time.monotonic()
    nonce = 0
    sha = hashlib.sha256
    while True:
        h = sha(salt + struct.pack("<q", nonce)).digest()
        v = int.from_bytes(h[:8], "little")
        lz = 64 - v.bit_length()
        if lz >= difficulty:
            break
        nonce += 1
    sock.sendall(struct.pack("<Iq", POW_RESPONSE_MAGIC, nonce))
    return difficulty, round((time.monotonic() - t0) * 1000), nonce


# ---------------------------------------------------------------- TLS

def make_client_cert():
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization  # noqa: F401
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.x509.oid import NameOID

    key = ed25519.Ed25519PrivateKey.generate()
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "cocoon-client"),
                      x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TDLib Development")])
    now = dt.datetime.now(dt.UTC)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - dt.timedelta(hours=1))
            .not_valid_after(now + dt.timedelta(days=1)).sign(key, None))
    d = tempfile.mkdtemp(prefix="cocoon-probe-")
    cp, kp = os.path.join(d, "c.pem"), os.path.join(d, "k.pem")
    with open(cp, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    with open(kp, "wb") as f:
        f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption()))
    os.chmod(kp, 0o600)
    return cp, kp


TDX_QUOTE_OID = "1.3.6.1.4.1.12345.1"
TDX_USER_CLAIMS_OID = "1.3.6.1.4.1.12345.2"


def parse_tdx_quote(q):
    """TDX quote v4: 48-byte header, then the 584-byte TD report body."""
    if len(q) < 632:
        raise ValueError(f"quote too short: {len(q)}")
    ver, key_type, tee_type = struct.unpack("<HHI", q[:8])
    body = 48
    f = lambda o, n: q[body + o: body + o + n]  # noqa: E731
    return {
        "version": ver, "att_key_type": key_type, "tee_type": f"{tee_type:#x}",
        "tee_tcb_svn": f(0, 16).hex(), "mr_seam": f(16, 48).hex(), "td_attributes": f(112, 8).hex(),
        "mr_td": f(136, 48), "mr_config_id": f(184, 48), "mr_owner": f(232, 48), "mr_owner_config": f(280, 48),
        "rtmr": [f(328 + 48 * i, 48) for i in range(4)], "reportdata": f(520, 64),
    }


_COLLATERAL_CACHE = {}


def dcap_verify(quote, now=None, collateral=None):
    """Verify the Intel DCAP signature chain of a TDX quote.

    Uses Phala's dcap-qvl (MIT): checks the quote signature by the attestation key, the
    QE report, the PCK certificate chain up to the Intel SGX Root CA, the CRLs, and
    evaluates the TCB level against Intel TCB info. Collateral is fetched from Intel PCS
    (api.trustedservices.intel.com) and cached per FMSPC for the lifetime of the process.
    Returns a dict with status "verified", "failed" or "not_checked"."""
    out = {"status": "not_checked", "collateral_source": None}
    try:
        import dcap_qvl
    except Exception:  # noqa: BLE001
        out["reason"] = "dcap-qvl not installed"
        return out
    now = int(now if now is not None else time.time())
    try:
        if collateral is None:
            key = None
            try:
                key = dcap_qvl.parse_quote(quote).fmspc()
            except Exception:  # noqa: BLE001
                key = None
            collateral = _COLLATERAL_CACHE.get(key) if key else None
            if collateral is None:
                import asyncio
                collateral = asyncio.run(dcap_qvl.get_collateral_from_pcs(quote))
                if key:
                    _COLLATERAL_CACHE[key] = collateral
            out["collateral_source"] = "Intel PCS"
        else:
            out["collateral_source"] = "provided"
    except Exception as e:  # noqa: BLE001
        out["reason"] = f"collateral unavailable: {str(e)[:160]}"
        return out
    try:
        report = dcap_qvl.verify(quote, collateral, now)
    except Exception as e:  # noqa: BLE001
        out["status"] = "failed"
        out["reason"] = str(e).replace("Verification failed: ", "")[:200]
        return out
    out["status"] = "verified"
    out["tcb_status"] = report.status
    out["advisory_ids"] = list(report.advisory_ids or [])
    out["checked_at"] = dt.datetime.fromtimestamp(now, dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return out


def attestation_check(der, dcap=True):
    """Independent RA-TLS check following TelegramMessenger/cocoon tee/cocoon/RATLS.cpp:
    reportdata == sha512(TLS Ed25519 public key); user_claims == public key;
    image_hash = sha256(mr_td|mr_config_id|mr_owner|mr_owner_config|rtmr0..3|zero64);
    plus the Intel DCAP signature chain of the quote (dcap_verify)."""
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    c = x509.load_der_x509_certificate(der)
    pub = c.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    ext = {e.oid.dotted_string: getattr(e.value, "value", None) for e in c.extensions}
    q, claims = ext.get(TDX_QUOTE_OID), ext.get(TDX_USER_CLAIMS_OID)
    out = {"tee": None, "public_key": pub.hex()}
    if not q:
        out["result"] = "no TDX quote in certificate"
        return out
    t = parse_tdx_quote(q)
    out["tee"] = "TDX" if t["tee_type"] == "0x81" else t["tee_type"]
    out["quote_version"] = t["version"]
    out["quote_size"] = len(q)
    out["mr_td"] = t["mr_td"].hex()
    out["rtmr"] = [r.hex() for r in t["rtmr"]]
    out["tee_tcb_svn"] = t["tee_tcb_svn"]
    out["reportdata_binds_tls_key"] = t["reportdata"] == hashlib.sha512(pub).digest()
    out["user_claims_match_key"] = (claims == pub) if claims is not None else None
    img = hashlib.sha256(t["mr_td"] + t["mr_config_id"] + t["mr_owner"] + t["mr_owner_config"]
                         + b"".join(t["rtmr"]) + b"\0" * 64).hexdigest()
    out["image_hash"] = img
    out["quote_b64"] = base64.b64encode(q).decode()
    if dcap and out["tee"] == "TDX":
        out["dcap"] = dcap_verify(q)
    else:
        out["dcap"] = {"status": "not_checked", "reason": "not a TDX quote" if dcap else "disabled"}
    out["quote_signature_verified"] = {"verified": True, "failed": False}.get(out["dcap"]["status"])
    return out


def describe_cert(der):
    out = {"sha256": hashlib.sha256(der).hexdigest(), "size": len(der)}
    try:
        out["attestation"] = attestation_check(der)
    except Exception as e:  # noqa: BLE001
        out["attestation"] = {"error": str(e)[:200]}
    try:
        from cryptography import x509
        c = x509.load_der_x509_certificate(der)
        out["subject"] = c.subject.rfc4514_string()
        out["issuer"] = c.issuer.rfc4514_string()
        out["not_before"] = c.not_valid_before_utc.isoformat()
        out["not_after"] = c.not_valid_after_utc.isoformat()
        out["public_key_type"] = type(c.public_key()).__name__.replace("_", "")
        exts = []
        for e in c.extensions:
            raw = getattr(e.value, "value", None)
            exts.append({"oid": e.oid.dotted_string, "critical": e.critical,
                         "size": len(raw) if isinstance(raw, (bytes, bytearray)) else None})
        out["extensions"] = exts
        out["custom_extension_bytes"] = sum(x["size"] or 0 for x in exts if not x["oid"].startswith("2.5.29."))
    except Exception as e:  # noqa: BLE001
        out["parse_error"] = str(e)[:200]
    return out


# ---------------------------------------------------------------- probe

def random_wallet_address():
    """A syntactically valid, never-funded address: the proxy only derives a client-contract
    address from it and asks for on-chain registration, which we never send."""
    try:
        from pytoniq_core import Address
        return Address("0:" + secrets.token_hex(32)).to_str(is_user_friendly=True, is_bounceable=True)
    except Exception:  # noqa: BLE001
        return "0:" + secrets.token_hex(32)


def query(fr, body, timeout_s, sock):
    qid = secrets.randbits(63)
    fr.send(W().u32(TCP_QUERY).i64(qid).bytes_(body).b)
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        sock.settimeout(max(0.5, deadline - time.monotonic()))
        r = R(fr.recv())
        cid = r.u32()
        if cid == TCP_PING:
            fr.send(W().u32(TCP_PONG).i64(r.i64()).b); continue
        if cid == TCP_QUERY_ANSWER:
            aid = r.i64(); data = r.bytes_()
            if aid == qid:
                return {"ok": True, "data": data}
            continue
        if cid == TCP_QUERY_ERROR:
            aid = r.i64(); code = r.i32(); msg = r.str_()
            if aid == qid:
                return {"ok": False, "code": code, "message": msg}
            continue
        # tcp.packet / others: ignore while waiting for our answer
    return {"ok": False, "code": -1, "message": "timeout"}


def decode_connected(data):
    r = R(data)
    cid = r.u32()
    if cid != CLIENT_CONNECTED_TO_PROXY:
        return {"unexpected_constructor": f"{cid:#x}"}
    flags = r.u32()
    pub = r.i256().hex()
    owner = r.str_()
    sc = r.str_()
    out = {"proxy_public_key": pub, "proxy_owner_address": owner, "proxy_sc_address": sc}
    if flags & 1:
        out["is_test"] = r.bool_()
    if flags & 2:
        out["proto_version"] = r.i32()
    out["client_sc_address_derived"] = r.str_()
    aid = r.u32()
    out["auth_required"] = {AUTH_SHORT: "short (secret)", AUTH_LONG: "long (on-chain register)"}.get(aid, f"{aid:#x}")
    return out


def decode_worker_types(data):
    r = R(data)
    cid = r.u32()
    if cid != CLIENT_WORKER_TYPES_V2:
        return {"unexpected_constructor": f"{cid:#x}"}
    types = []
    for _ in range(r.i32()):
        name = r.str_()
        workers = []
        for _ in range(r.i32()):
            r.u32()  # flags
            workers.append({"coefficient": r.i32(), "active_requests": r.i32(), "max_active_requests": r.i32()})
        types.append({"model": name, "workers": len(workers),
                      "active_requests": sum(w["active_requests"] for w in workers),
                      "capacity": sum(w["max_active_requests"] for w in workers),
                      "coefficients": sorted({w["coefficient"] for w in workers}), "instances": workers})
    return {"models": types}


def probe(endpoint, root_config_version=91, timeout=20):
    host, port = endpoint.rsplit(":", 1)
    res = {"endpoint": endpoint, "probed_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "stage": "tcp"}
    t0 = time.monotonic()
    try:
        raw = socket.create_connection((host, int(port)), timeout=timeout)
        res["tcp_ms"] = round((time.monotonic() - t0) * 1000)
        res["stage"] = "pow"
        diff, ms, _ = solve_pow(raw, timeout)
        res["pow"] = {"difficulty": diff, "solve_ms": ms}
        res["stage"] = "tls"
        cp, kp = make_client_cert()
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE  # attestation is evaluated from the certificate below, not by CA chain
        ctx.minimum_version = ssl.TLSVersion.TLSv1_3
        ctx.load_cert_chain(cp, kp)
        tls = ctx.wrap_socket(raw, server_hostname=None)
        tls.settimeout(timeout)
        res["tls"] = {"version": tls.version(), "cipher": tls.cipher()[0] if tls.cipher() else None}
        der = tls.getpeercert(binary_form=True)
        if der:
            res["server_cert"] = describe_cert(der)
        fr = Framed(tls)
        res["stage"] = "tcp.connect"
        cid = secrets.randbits(63)
        fr.send(W().u32(TCP_CONNECT).i64(cid).b)
        while True:
            r = R(fr.recv())
            k = r.u32()
            if k == TCP_CONNECTED:
                break
            if k == TCP_PING:
                fr.send(W().u32(TCP_PONG).i64(r.i64()).b)
        res["stage"] = "connectToProxy"
        body = (W().u32(CLIENT_CONNECT_TO_PROXY).u32(0x3).str_(random_wallet_address()).bool_(False)
                .i32(1).i32(4).i32(root_config_version).b)
        a = query(fr, body, timeout, tls)
        if not a["ok"]:
            res["connect_error"] = {k: a[k] for k in ("code", "message")}
        else:
            res["proxy"] = decode_connected(a["data"])
        res["stage"] = "getWorkerTypesV2"
        a = query(fr, W().u32(CLIENT_GET_WORKER_TYPES_V2).b, timeout, tls)
        if a["ok"]:
            res["worker_types"] = decode_worker_types(a["data"])
        else:
            res["worker_types_error"] = {k: a[k] for k in ("code", "message")}
        res["stage"] = "done"
        res["alive"] = True
        try:
            tls.close()
        except Exception:  # noqa: BLE001
            pass
    except Exception as e:  # noqa: BLE001
        res["alive"] = res.get("stage") not in ("tcp", "pow") and "tls" in res
        res["error"] = f"{type(e).__name__}: {str(e)[:200]}"
    res["total_ms"] = round((time.monotonic() - t0) * 1000)
    return res


if __name__ == "__main__":
    eps = [a for a in sys.argv[1:] if not a.startswith("--")] or ["91.108.4.11:8888"]
    out = [probe(e) for e in eps]
    print(json.dumps(out, indent=1, ensure_ascii=False))
