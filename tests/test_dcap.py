"""Tests for the Intel DCAP check of TDX quotes in probe.py.

Run: python3 -m unittest discover -s tests
"""
import datetime as dt
import hashlib
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import probe  # noqa: E402

FIX = os.path.join(HERE, "fixtures")
QUOTE = open(os.path.join(FIX, "tdx_quote.bin"), "rb").read()
IN_WINDOW = 1751000000   # 2025-06-27, inside the sample collateral validity window
AFTER_WINDOW = 1760000000  # 2025-10-09, TCB info has expired

try:
    import dcap_qvl
    COLLATERAL = dcap_qvl.QuoteCollateralV3.from_json(open(os.path.join(FIX, "tdx_quote_collateral.json")).read())
except ImportError:  # pragma: no cover
    dcap_qvl = None


@unittest.skipIf(dcap_qvl is None, "dcap-qvl not installed")
class DcapVerifyTest(unittest.TestCase):
    def test_genuine_quote_verifies(self):
        r = probe.dcap_verify(QUOTE, now=IN_WINDOW, collateral=COLLATERAL)
        self.assertEqual(r["status"], "verified")
        self.assertEqual(r["tcb_status"], "UpToDate")
        self.assertEqual(r["advisory_ids"], [])
        self.assertEqual(r["checked_at"], "2025-06-27T04:53:20Z")

    def test_tampered_report_data_fails_signature(self):
        q = bytearray(QUOTE)
        q[48 + 520] ^= 1  # first byte of REPORTDATA, which binds the TLS key
        r = probe.dcap_verify(bytes(q), now=IN_WINDOW, collateral=COLLATERAL)
        self.assertEqual(r["status"], "failed")
        self.assertIn("signature is invalid", r["reason"])

    def test_tampered_measurement_fails_signature(self):
        q = bytearray(QUOTE)
        q[48 + 136] ^= 1  # MRTD, part of the image hash
        r = probe.dcap_verify(bytes(q), now=IN_WINDOW, collateral=COLLATERAL)
        self.assertEqual(r["status"], "failed")

    def test_expired_collateral_fails(self):
        r = probe.dcap_verify(QUOTE, now=AFTER_WINDOW, collateral=COLLATERAL)
        self.assertEqual(r["status"], "failed")
        self.assertIn("expired", r["reason"])


class AttestationCertTest(unittest.TestCase):
    """attestation_check on an RA-TLS style certificate carrying the sample quote."""

    def make_cert(self, quote):
        from cryptography import x509
        from cryptography.hazmat.primitives.asymmetric import ed25519
        from cryptography.x509.oid import NameOID
        key = ed25519.Ed25519PrivateKey.generate()
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
        now = dt.datetime.now(dt.UTC)
        oid = x509.ObjectIdentifier(probe.TDX_QUOTE_OID)
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
                .serial_number(1).not_valid_before(now).not_valid_after(now + dt.timedelta(days=1))
                .add_extension(x509.UnrecognizedExtension(oid, quote), critical=False)
                .sign(key, None))
        from cryptography.hazmat.primitives import serialization
        return cert.public_bytes(serialization.Encoding.DER)

    def test_quote_is_published_and_parsed(self):
        import base64
        a = probe.attestation_check(self.make_cert(QUOTE), dcap=False)
        self.assertEqual(a["tee"], "TDX")
        self.assertEqual(a["quote_version"], 4)
        self.assertEqual(base64.b64decode(a["quote_b64"]), QUOTE)
        self.assertEqual(len(a["image_hash"]), 64)
        # the sample quote was not made for this key
        self.assertFalse(a["reportdata_binds_tls_key"])
        self.assertEqual(a["dcap"]["status"], "not_checked")
        self.assertIsNone(a["quote_signature_verified"])

    def test_image_hash_matches_cocoon_formula(self):
        a = probe.attestation_check(self.make_cert(QUOTE), dcap=False)
        b = 48
        mr = lambda o: QUOTE[b + o: b + o + 48]  # noqa: E731
        expected = hashlib.sha256(mr(136) + mr(184) + mr(232) + mr(280)
                                  + b"".join(mr(328 + 48 * i) for i in range(4)) + b"\0" * 64).hexdigest()
        self.assertEqual(a["image_hash"], expected)


if __name__ == "__main__":
    unittest.main()
