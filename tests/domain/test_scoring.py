import unittest

from src.domain.scoring import Measurement, score_gate, score_metric
from src.domain.targets import MetricTarget, TargetRange

LATENCY = MetricTarget("latency", "p90", "ms", TargetRange(None, 1000), 0.8)
RATE = MetricTarget("rate", "mean", "req/s", TargetRange(40, None), 0.8)


def measured(source, value, weight=1, unit="ms"):
    return Measurement(source, f"{source}.value", value, unit, weight)


class ScoreMetricTests(unittest.TestCase):
    def test_score_is_weighted_share_inside_the_range(self):
        result = score_metric(
            [measured("A", 500, 900), measured("B", 2000, 100)], LATENCY
        )
        self.assertAlmostEqual(result.score or 0, 0.9)
        self.assertEqual(result.outcome, "pass")
        self.assertEqual(result.threshold, 0.8)
        self.assertEqual(result.source, "latency")
        failing = result.sources[1]
        self.assertEqual(failing.penalty, 1)
        self.assertEqual(
            failing.evidence, {"value": 2000, "unit": "ms", "min": None, "max": 1000}
        )

    def test_score_below_minimum_fails(self):
        result = score_metric(
            [measured("A", 500, 100), measured("B", 2000, 900)], LATENCY
        )
        self.assertAlmostEqual(result.score or 0, 0.1)
        self.assertEqual(result.outcome, "fail")

    def test_lower_bound(self):
        self.assertEqual(
            score_metric([measured("run", 39, unit="req/s")], RATE).score, 0
        )
        self.assertEqual(
            score_metric([measured("run", 40, unit="req/s")], RATE).score, 1
        )

    def test_zero_weight_is_excluded_and_recorded(self):
        result = score_metric(
            [measured("A", 500, 10), measured("idle", 9000, 0)], LATENCY
        )
        self.assertEqual(result.score, 1)
        self.assertTrue(result.sources[1].excluded)
        self.assertEqual(result.sources[1].reason, "No observations")

    def test_missing_value_weight_or_unit_mismatch_is_unknown(self):
        for measurement, reason in (
            (measured("A", None), "Missing measured value"),
            (measured("A", 500, None), "Missing measured value"),
            (measured("A", 0.5, unit="s"), "Unit 's' does not match"),
        ):
            with self.subTest(reason=reason):
                result = score_metric([measured("B", 500), measurement], LATENCY)
                self.assertEqual(result.outcome, "unknown")
                self.assertIsNone(result.score)
                self.assertIn(reason, result.sources[1].reason or "")

    def test_no_measurements_is_unknown(self):
        result = score_metric([], LATENCY)
        self.assertEqual(result.outcome, "unknown")
        self.assertEqual(result.reason, "No eligible sources")


class ScoreGateTests(unittest.TestCase):
    def measure(self, values):
        return lambda metric, aggregation: values[(metric, aggregation)]

    def test_scores_every_target_and_requires_all_to_pass(self):
        targets = {"latency": LATENCY, "rate": RATE}
        measure = self.measure(
            {
                ("latency", "p90"): [measured("A", 500)],
                ("rate", "mean"): [measured("run", 50, unit="req/s")],
            }
        )
        result = score_gate(targets, measure)
        self.assertEqual(set(result.metrics), {"latency", "rate"})
        self.assertEqual(result.outcome, "pass")

    def test_fail_outranks_unknown(self):
        measure = self.measure(
            {
                ("latency", "p90"): [measured("A", None)],
                ("rate", "mean"): [measured("run", 1, unit="req/s")],
            }
        )
        result = score_gate({"latency": LATENCY, "rate": RATE}, measure)
        self.assertEqual(result.metrics["latency"].outcome, "unknown")
        self.assertEqual(result.outcome, "fail")


if __name__ == "__main__":
    unittest.main()
