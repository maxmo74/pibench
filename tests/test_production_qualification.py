import json
import tempfile
import unittest
from pathlib import Path

from issue_production_qualification import evidence
from production_qualification import build_fingerprint, verify_artifact


class QualificationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.inputs = {}
        for name, content in {
            "runtime": b"runtime-v1",
            "model": b"model-v1",
            "service": b"service-v1",
            "environment": b"MTP=1\n",
            "catalog": b"catalog-v1",
            "loop_guard": b"guard-v1",
            "reliability_harness": b"harness-v2",
        }.items():
            path = self.root / name
            path.write_bytes(content)
            self.inputs[name] = path

    def tearDown(self):
        self.temp.cleanup()

    def artifact(self):
        fingerprint = build_fingerprint(self.inputs, "0.84.3")
        return {
            "schema": 1,
            "backend": "peregrine",
            "fingerprint": fingerprint,
            "suites": {
                "reliability": {"passed": True, "runs": 12},
                "cache_hot": {"passed": True, "runs": 2},
                "retained_replay": {"passed": True, "runs": 1},
                "quality": {"passed": True, "runs": 24},
            },
        }

    def test_accepts_matching_complete_artifact(self):
        errors = verify_artifact(self.artifact(), self.inputs, "0.84.3")
        self.assertEqual([], errors)

    def test_rejects_coordinate_drift(self):
        artifact = self.artifact()
        self.inputs["environment"].write_bytes(b"MTP=3\n")
        errors = verify_artifact(artifact, self.inputs, "0.84.3")
        self.assertIn("fingerprint mismatch: environment", errors)

    def test_rejects_failed_or_missing_suite(self):
        artifact = self.artifact()
        artifact["suites"]["cache_hot"]["passed"] = False
        del artifact["suites"]["quality"]
        errors = verify_artifact(artifact, self.inputs, "0.84.3")
        self.assertIn("suite failed: cache_hot", errors)
        self.assertIn("missing suite: quality", errors)

    def test_rejects_insufficient_suite_runs(self):
        artifact = self.artifact()
        artifact["suites"]["reliability"]["runs"] = 11
        errors = verify_artifact(artifact, self.inputs, "0.84.3")
        self.assertIn("insufficient suite runs: reliability", errors)

    def test_rejects_pi_version_drift(self):
        errors = verify_artifact(self.artifact(), self.inputs, "0.84.4")
        self.assertIn("Pi version mismatch", errors)

    def test_accepts_merged_reliability_evidence(self):
        path = self.root / "reliability.json"
        path.write_text(json.dumps({
            "profile": "pi-agent-reliability",
            "results": [
                {"passed": True, "scenarios_total": 4},
                {"passed": True, "scenarios_total": 8},
            ],
        }))
        self.assertEqual(12, evidence(path)["runs"])

    def test_accepts_historical_reliability_evidence(self):
        path = self.root / "reliability-old.json"
        path.write_text(json.dumps({
            "profile": "pi-agent-reliability-v2",
            "results": [{"passed": True, "scenarios_total": 12}],
        }))
        self.assertEqual(12, evidence(path)["runs"])


if __name__ == "__main__":
    unittest.main()
