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


class ParamsHistoryTest(unittest.TestCase):
    def snap(self, price="20", workers=("aa", "bb"), version=91):
        return {"params": {"price_per_token": price, "min_proxy_stake": "15000000000"},
                "registry": {"config_version": version, "worker_image_hash_list": list(workers),
                             "proxy_image_hash_list": ["pp"], "model_hash_list": ["mm"]}}

    def test_first_observation_then_no_entry_without_change(self):
        e = history.params_changes([], self.snap(), "2026-11-06")
        self.assertEqual([x["kind"] for x in e], ["first_observed"])
        e = history.params_changes(e, self.snap(), "2026-11-07")
        self.assertEqual(len(e), 1)

    def test_value_and_list_changes_are_recorded(self):
        e = history.params_changes([], self.snap(), "2026-11-06")
        e = history.params_changes(e, self.snap(price="25", workers=("bb", "cc"), version=92), "2026-11-08")
        self.assertEqual(e[-1]["kind"], "changed")
        ch = {c["field"]: c for c in e[-1]["changes"]}
        self.assertEqual(ch["params.price_per_token"], {"field": "params.price_per_token", "from": "20", "to": "25"})
        self.assertEqual(ch["config_version"]["to"], 92)
        self.assertEqual(ch["worker_image_hash_list"]["added"], ["cc"])
        self.assertEqual(ch["worker_image_hash_list"]["removed"], ["aa"])
        s = history.params_summary(e)
        self.assertEqual((s["observed_since"], s["changes"], s["last_change"]), ("2026-11-06", 1, "2026-11-08"))

    def test_missing_field_is_not_a_change(self):
        e = history.params_changes([], self.snap(), "2026-11-06")
        snap = self.snap()
        del snap["registry"]["model_hash_list"]
        e = history.params_changes(e, snap, "2026-11-07")
        self.assertEqual(len(e), 1)


if __name__ == "__main__":
    unittest.main()
