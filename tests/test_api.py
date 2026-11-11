"""Contract tests. This tests our API, not Hermes's outer authentication layer."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HAS_API = importlib.util.find_spec("fastapi") is not None and importlib.util.find_spec("httpx") is not None
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(HAS_API, "Install fastapi and httpx in a test environment to run API tests.")
class ApiTests(unittest.TestCase):
    def setUp(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        spec = importlib.util.spec_from_file_location("graft_api_under_test", ROOT / "dashboard/plugin_api.py")
        self.api = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.api)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store = self.api.core.Store(Path(self.tmp.name) / "graft.db")
        self.feature = self.store.save(json.loads((ROOT / "examples/release-room.json").read_text()), "http://127.0.0.1:8460")
        core = self.api.core
        class Adapter:
            token = "test-only-placeholder"
            username = "graft"
            url = origin = "http://127.0.0.1:8460"
            raw = {"id": "1", "title": "Demo task", "project_id": "1", "owner_id": "1", "date_due": "0"}
            writes = 0
            def dataset(self):
                return {"rows": [core.normalize_task(self.raw, "Launch", {"1": "Ada", "2": "Grace"}, {})], "assignable": {"1": {"1": "Ada", "2": "Grace"}}}
            def task(self, ident): return copy.deepcopy(self.raw)
            def call(self, method, **kwargs): return {"1": "Ada", "2": "Grace"}
            def update(self, ident, changes): self.writes += 1; self.raw = {**self.raw, **{k: str(v) for k,v in changes.items()}}
        self.adapter = Adapter()
        self.api.runtime.context = lambda: (self.store, self.adapter)
        self.api.runtime.event = lambda *args: None
        app = FastAPI(); app.include_router(self.api.router, prefix="/api/plugins/graft")
        self.client = TestClient(app)
    def review(self):
        response = self.client.post("/api/plugins/graft/review", json={"feature_id": self.feature["id"], "task_id": 1, "action": "reassign", "value": 2})
        self.assertEqual(response.status_code, 200); return response.json()
    def test_status_never_returns_the_secret(self):
        response = self.client.get("/api/plugins/graft/status")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.adapter.token, response.text)
    def test_packet_contains_live_connector_values(self):
        response = self.client.get(f"/api/plugins/graft/features/{self.feature['id']}/packet")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["view"]["widgets"][2]["rows"][0]["title"], "Demo task")
        self.assertNotIn(self.adapter.token, response.text)
    def test_unknown_feature_is_a_clear_error(self):
        response = self.client.get("/api/plugins/graft/features/missing/packet")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Feature not found", response.json()["detail"])
    def test_missing_explicit_confirmation_never_writes(self):
        review = self.review()
        for body in [{}, {"confirmed": False}, {"confirmed": 1}, {"confirmed": "true"}]:
            response = self.client.post(f"/api/plugins/graft/review/{review['id']}/apply", json=body)
            self.assertEqual(response.status_code, 400)
        self.assertEqual(self.adapter.writes, 0)
    def test_review_apply_and_duplicate_request(self):
        review = self.review()
        response = self.client.post(f"/api/plugins/graft/review/{review['id']}/apply", json={"confirmed": True})
        self.assertEqual(response.status_code, 200)
        again = self.client.post(f"/api/plugins/graft/review/{review['id']}/apply", json={"confirmed": True})
        self.assertEqual(again.status_code, 400)
        self.assertEqual(self.adapter.writes, 1)
    def test_untrusted_extra_action_properties_are_refused(self):
        response = self.client.post("/api/plugins/graft/review", json={"feature_id": self.feature["id"], "task_id": 1, "action": "reassign", "value": 2, "url": "https://example.com"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.adapter.writes, 0)


if __name__ == "__main__": unittest.main()
