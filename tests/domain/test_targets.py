import unittest

from src.domain.targets import MetricTarget, TargetRange, check_targets

SUPPORTED = {"latency": ("p90",), "rate": ("mean",)}


def target(metric, aggregation="p90"):
    return MetricTarget(metric, aggregation, "ms", TargetRange(None, 1), 0.8)


class TargetRangeTests(unittest.TestCase):
    def test_one_and_two_sided_bounds_are_inclusive(self):
        upper = TargetRange(None, 10)
        lower = TargetRange(5, None)
        both = TargetRange(5, 10)
        self.assertTrue(upper.contains(10))
        self.assertFalse(upper.contains(10.1))
        self.assertTrue(lower.contains(5))
        self.assertFalse(lower.contains(4.9))
        self.assertTrue(both.contains(5) and both.contains(10))
        self.assertFalse(both.contains(4) or both.contains(11))

    def test_rejects_unbounded_and_inverted_ranges(self):
        with self.assertRaisesRegex(ValueError, "at least one bound"):
            TargetRange(None, None)
        with self.assertRaisesRegex(ValueError, "min must not exceed max"):
            TargetRange(10, 5)


class MetricTargetTests(unittest.TestCase):
    def test_rejects_score_outside_unit_interval(self):
        with self.assertRaisesRegex(ValueError, "between 0 and 1"):
            MetricTarget("latency", "p90", "ms", TargetRange(None, 1), 1.5)


class CheckTargetsTests(unittest.TestCase):
    def test_accepts_one_supported_target_per_metric(self):
        check_targets(
            {"latency": target("latency"), "rate": target("rate", "mean")}, SUPPORTED
        )

    def test_rejects_missing_unexpected_mismatched_and_unsupported(self):
        cases = (
            ({"latency": target("latency")}, "missing \\['rate'\\]"),
            (
                {
                    "latency": target("latency"),
                    "rate": target("rate", "mean"),
                    "cpu": target("cpu"),
                },
                "unexpected \\['cpu'\\]",
            ),
            (
                {"latency": target("rate"), "rate": target("rate", "mean")},
                "names metric 'rate'",
            ),
            (
                {"latency": target("latency", "mean"), "rate": target("rate", "mean")},
                "cannot aggregate on 'mean'",
            ),
        )
        for targets, message in cases:
            with (
                self.subTest(message=message),
                self.assertRaisesRegex(ValueError, message),
            ):
                check_targets(targets, SUPPORTED)


if __name__ == "__main__":
    unittest.main()
