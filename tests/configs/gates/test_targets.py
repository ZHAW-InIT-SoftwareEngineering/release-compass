import unittest
from pathlib import Path

from pydantic import ValidationError

from src.configs.gates.targets import GateTargetsConfig, load_gate_targets_config

CONFIG = (
    Path(__file__).resolve().parents[3]
    / "configs/gates/performance/performance_gate.yaml"
)


class GateTargetsConfigTests(unittest.TestCase):
    def test_loads_project_performance_targets(self):
        config = load_gate_targets_config(CONFIG)
        self.assertEqual(
            set(config.metrics), {"response_time", "request_outcomes", "throughput"}
        )
        self.assertEqual(config.metrics["response_time"].target.aggregation, "p90")
        self.assertIsNone(config.metrics["throughput"].target.max)

    def test_requires_both_bounds_to_be_stated(self):
        data = load_gate_targets_config(CONFIG).model_dump()
        del data["metrics"]["throughput"]["target"]["max"]
        with self.assertRaisesRegex(ValidationError, "max"):
            GateTargetsConfig.model_validate(data)

    def test_rejects_unknown_keys_and_out_of_range_scores(self):
        data = load_gate_targets_config(CONFIG).model_dump()
        data["metrics"]["response_time"]["operator"] = ">="
        with self.assertRaisesRegex(ValidationError, "operator"):
            GateTargetsConfig.model_validate(data)
        data = load_gate_targets_config(CONFIG).model_dump()
        data["metrics"]["response_time"]["score"] = 1.1
        with self.assertRaisesRegex(ValidationError, "score"):
            GateTargetsConfig.model_validate(data)


if __name__ == "__main__":
    unittest.main()
