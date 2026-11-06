"""Tests for the daily attestation history (history.py)."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import history  # noqa: E402


def probe(endpoint, status="verified", tcb="UpToDate", alive=True):
    return {"endpoint": endpoint, "alive": alive, "stage": "done" if alive else "tcp", "probed_at": "t",
            "server_cert": {"attestation": {"image_hash": "ab", "image_hash_allowed_by_root": True,
                                            "reportdata_binds_tls_key": True,
                                            "dcap": {"status": status, "tcb_status": tcb}}}}


class HistoryTest(unittest.TestCase):
    def test_same_day_is_replaced_other_days_kept(self):
        e1 = history.merge([], [probe("a"), probe("b", alive=False)], "2026-11-05")
        e2 = history.merge(e1, [probe("a", status="failed", tcb=None)], "2026-11-05")
        self.assertEqual(len(e2), 2)
        a = [e for e in e2 if e["endpoint"] == "a"][0]
        self.assertEqual(a["dcap_status"], "failed")
        e3 = history.merge(e2, [probe("a")], "2026-11-06")
        self.assertEqual(len(e3), 3)
        self.assertEqual([e["date"] for e in e3], ["2026-11-05", "2026-11-05", "2026-11-06"])

    def test_summary_counts(self):
        e = history.merge([], [probe("a")], "2026-11-05")
        e = history.merge(e, [probe("a", status="failed", tcb=None)], "2026-11-06")
        e = history.merge(e, [probe("a", tcb="OutOfDate")], "2026-11-07")
        s = history.summarize(e)["a"]
        self.assertEqual(s, {"days": 3, "alive_days": 3, "verified_days": 2, "up_to_date_days": 1,
                             "first": "2026-11-05", "last": "2026-11-07"})

    def test_offline_endpoint_recorded(self):
        e = history.merge([], [probe("b", status=None, tcb=None, alive=False)], "2026-11-05")
        self.assertFalse(e[0]["alive"])
        self.assertEqual(history.summarize(e)["b"]["alive_days"], 0)


if __name__ == "__main__":
    unittest.main()
