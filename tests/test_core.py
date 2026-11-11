import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import GraftError, Store, evaluate, normalize_task, validate_spec

BASE = json.loads((Path(__file__).resolve().parents[1] / "examples/release-room.json").read_text())


class FakeKanboard:
    origin = "http://127.0.0.1:8460"
    username = "graft"
    def __init__(self):
        self.raw = {"id": "4", "title": "Actual task", "project_id": "1", "owner_id": "1", "date_due": "0", "date_modification": "42"}
        self.writes = 0
        self.fail_after_write = False
    def task(self, ident):
        return dict(self.raw)
    def call(self, method, **params):
        if method == "getTimezone": return "America/New_York"
        return {"1": "Ada", "2": "Grace"}
    def update(self, ident, changes):
        self.writes += 1
        self.raw.update({k: str(v) for k, v in changes.items()})
        if self.fail_after_write: raise TimeoutError("Response lost after success")


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.spec = copy.deepcopy(BASE)
        now = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)
        self.rows = [normalize_task({"id": n, "title": f"Task {n}", "project_id": 1, "owner_id": 1 if n % 2 else 0,
                         "date_due": 1794268800 if n < 4 else 0, "time_estimated": n}, "Launch", {"1": "Ada"}, {}, now)
                     for n in range(1, 7)]
    def test_metrics_use_all_matching_records_even_when_table_limited(self):
        self.spec["query"]["limit"] = 2
        view = evaluate(self.spec, self.rows)
        self.assertEqual(view["widgets"][0]["cards"][0]["value"], 6)
        self.assertEqual(sum(s["value"] for s in view["widgets"][1]["series"]), 21)
        self.assertEqual(len(view["widgets"][2]["rows"]), 2)
    def test_missing_date_is_not_treated_as_due_today(self):
        self.spec["query"]["filters"] = [{"field": "due_in_days", "op": "lte", "value": 0}]
        result = evaluate(self.spec, self.rows)
        self.assertEqual(result["matched"], 3)
    def test_unknown_executable_properties_refused(self):
        for prop in ["script", "html", "javascript", "url"]:
            bad = copy.deepcopy(self.spec); bad[prop] = "alert(1)"
            with self.assertRaises(GraftError): validate_spec(bad)
    def test_invalid_field_and_widget_shapes_fail_cleanly(self):
        for value in [None, [], {}, "made_up"]:
            bad = copy.deepcopy(self.spec); bad["widgets"][2]["columns"] = [value]
            with self.assertRaises(GraftError): validate_spec(bad)
    def test_numbers_are_not_coerced_from_ambiguous_text(self):
        self.spec["query"]["filters"] = [{"field": "effort", "op": "gt", "value": "2"}]
        with self.assertRaises(GraftError): evaluate(self.spec, self.rows)
    def test_average_of_no_values_is_unknown_not_zero(self):
        self.spec["query"]["filters"] = [{"field": "owner", "op": "eq", "value": "Nobody"}]
        self.spec["widgets"][0]["metrics"] = [{"label": "Average", "op": "avg", "field": "effort"}]
        self.assertIsNone(evaluate(self.spec, self.rows)["widgets"][0]["cards"][0]["value"])
    def test_due_day_uses_app_timezone(self):
        row = normalize_task({"id": 1, "title": "x", "project_id": 1, "date_due": 1794412800}, "p", {}, {},
                             datetime(2026, 11, 11, 2, tzinfo=timezone.utc), tz="America/New_York")
        self.assertEqual(row["due"], "2026-11-11")
        self.assertEqual(row["due_in_days"], 1)


class ChangeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "graft.db")
        self.adapter = FakeKanboard()
        self.feature = self.store.save(BASE, self.adapter.origin)
    def review(self):
        return self.store.prepare(self.adapter, self.feature["id"], 4, "reassign", 2)
    def test_preparing_change_never_writes(self):
        review = self.review()
        self.assertEqual(review["before"], "Ada")
        self.assertEqual(review["after"], "Grace")
        self.assertEqual(self.adapter.writes, 0)
    def test_apply_writes_once_and_replay_is_refused(self):
        review = self.review()
        self.assertTrue(self.store.apply(self.adapter, review["id"])["ok"])
        with self.assertRaises(GraftError): self.store.apply(self.adapter, review["id"])
        self.assertEqual(self.adapter.writes, 1)
    def test_changed_task_invalidates_review(self):
        review = self.review(); self.adapter.raw["title"] = "Changed by someone else"
        with self.assertRaisesRegex(GraftError, "changed since review"): self.store.apply(self.adapter, review["id"])
        self.assertEqual(self.adapter.writes, 0)
    def test_changed_feature_invalidates_review(self):
        review = self.review(); self.store.save(BASE, self.adapter.origin, self.feature["id"])
        with self.assertRaisesRegex(GraftError, "feature changed"): self.store.apply(self.adapter, review["id"])
    def test_changed_account_invalidates_review(self):
        review = self.review(); self.adapter.username = "another_user"
        with self.assertRaisesRegex(GraftError, "connector changed"): self.store.apply(self.adapter, review["id"])
        self.assertEqual(self.adapter.writes, 0)
    def test_lost_response_does_not_repeat_a_successful_write(self):
        review = self.review(); self.adapter.fail_after_write = True
        with self.assertRaisesRegex(GraftError, "could not be confirmed"): self.store.apply(self.adapter, review["id"])
        with self.assertRaises(GraftError): self.store.apply(self.adapter, review["id"])
        self.assertEqual(self.adapter.writes, 1)
    def test_removed_action_cannot_be_prepared(self):
        spec = copy.deepcopy(BASE); spec["widgets"][2]["actions"] = []
        self.store.save(spec, self.adapter.origin, self.feature["id"])
        with self.assertRaises(GraftError): self.review()
    def test_feature_survives_store_reopen(self):
        reopened = Store(Path(self.temp.name) / "graft.db")
        self.assertEqual(reopened.get(self.feature["id"])["spec"]["title"], "Release room")


if __name__ == "__main__": unittest.main()
