import tempfile
import unittest
from pathlib import Path

from src.adapters.outbound.yaml_target_source import YamlTargetSource
from src.domain.targets import TargetRange

CONFIG = """
metrics:
  response_time:
    target: {aggregation: p90, unit: ms, min: null, max: 3000}
    score: 0.8
  request_outcomes:
    target: {aggregation: failure_rate_percent, unit: "%", min: null, max: 1}
    score: 0.8
  throughput:
    target: {aggregation: tps, unit: req/s, min: 40, max: null}
    score: 0.8
"""


class YamlTargetSourceTests(unittest.TestCase):
    def source(self, text):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "performance_gate.yaml"
        path.write_text(text, encoding="utf-8")
        return YamlTargetSource(path)

    def test_builds_domain_targets(self):
        targets = self.source(CONFIG).targets()
        self.assertEqual(
            set(targets), {"response_time", "request_outcomes", "throughput"}
        )
        self.assertEqual(targets["throughput"].range, TargetRange(40, None))
        self.assertEqual(targets["response_time"].min_score, 0.8)

    def test_rejects_invalid_ranges(self):
        with self.assertRaisesRegex(ValueError, "min must not exceed max"):
            self.source(
                CONFIG.replace("min: null, max: 3000", "min: 5000, max: 3000")
            ).targets()


if __name__ == "__main__":
    unittest.main()
