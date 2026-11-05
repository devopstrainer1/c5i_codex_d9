import copy
import json
import unittest
from pathlib import Path
from core import Store, VoiceController, ExtractionPipeline, ScreenPolicy, validate_claim

ROOT = Path(__file__).resolve().parents[1]
def load(name):
    return json.loads((ROOT / "fixtures" / (name + ".json")).read_text())

class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.now = 0
        self.voice = VoiceController(self.store, lambda: self.now)
    def test_confirm_once(self):
        self.assertEqual(self.voice.handle("move Underwriting"), "AWAITING_CONFIRM")
        self.assertEqual(self.voice.handle("confirm"), "EXECUTED")
        self.assertEqual(self.voice.handle("confirm"), "NO_PENDING")
        self.assertEqual(self.store.claims["CLM-000101"]["version"], 1)
    def test_cancel_no_write(self):
        self.voice.handle("move Underwriting")
        self.assertEqual(self.voice.handle("yes but wait"), "CANCELLED")
        self.assertEqual(self.store.claims["CLM-000101"]["stage"], "Review")
    def test_expiry(self):
        self.voice.handle("move Underwriting")
        self.now = 11
        self.assertEqual(self.voice.handle("confirm"), "EXPIRED")
    def test_stale(self):
        self.voice.handle("move Underwriting")
        self.store.move("CLM-000101", "Approved", 0)
        self.assertEqual(self.voice.handle("confirm"), "STALE")
        self.assertEqual(self.store.claims["CLM-000101"]["stage"], "Approved")
    def test_second_pending(self):
        self.voice.handle("move Underwriting")
        self.assertEqual(self.voice.handle("move Approved"), "PENDING_EXISTS")

class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.c = load("clean")
        self.source = (ROOT / "fixtures/source.txt").read_text()
        self.store = Store()
        self.pipeline = ExtractionPipeline(self.store)
    def test_review_required(self):
        self.assertEqual(self.pipeline.process(self.c, self.source)["status"], "AWAITING_REVIEW")
        self.assertEqual(len(self.store.accepted), 0)
    def test_review_then_save(self):
        token = self.pipeline.review(self.c, self.source, "test-reviewer")
        self.assertEqual(self.pipeline.process(self.c, self.source, token)["status"], "SAVED")
    def test_changed_candidate(self):
        token = self.pipeline.review(self.c, self.source, "test-reviewer")
        self.c["claimant_name"] = "Changed Person"
        self.assertNotEqual(self.pipeline.process(self.c, self.source, token)["status"], "SAVED")
    def test_bad_values(self):
        checks = validate_claim(load("bad"), self.source)
        self.assertEqual(checks["arithmetic"]["status"], "FAIL")
        self.assertEqual(checks["policy_checksum"]["status"], "FAIL")
    def test_arithmetic_independent(self):
        self.c["total_amount"] = "7580.00"
        self.c["evidence"]["total_amount"] = "7580.00"
        checks = validate_claim(self.c, self.source + "\n7580.00")
        self.assertEqual([k for k,v in checks.items() if v["status"] != "PASS"], ["arithmetic"])
    def test_changed_source_invalidates_review(self):
        token = self.pipeline.review(self.c, self.source, "test-reviewer")
        self.assertEqual(self.pipeline.process(self.c, self.source + " revision", token)["status"], "AWAITING_REVIEW")

class ScreenTests(unittest.TestCase):
    def test_origin(self):
        p = ScreenPolicy()
        for url in ("https://127.0.0.1:5050", "http://127.0.0.1:5050.evil.example", "http://user@127.0.0.1:5050"):
            self.assertFalse(p.allowed_url(url))
        self.assertTrue(p.allowed_url("http://127.0.0.1:5050/legacy"))
    def test_denial_stops(self):
        r = ScreenPolicy().run(load("screen_plan"), [True, False])
        self.assertEqual(r["status"], "DENIED")
        self.assertEqual(r["events"][-1]["action"], "submit")
    def test_step_limit(self):
        self.assertEqual(ScreenPolicy().run([{"action":"read"}]*16)["status"], "STEP_LIMIT")

if __name__ == "__main__":
    unittest.main()
