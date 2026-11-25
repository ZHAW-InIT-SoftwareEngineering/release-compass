import unittest

from src.domain.comparison import MeasurementChange, compare_measurements
from src.domain.scoring import Measurement


def measured(source, value, unit="ms"):
    return Measurement(source, f"transactions.{source}", value, unit, 1)


class CompareMeasurementsTests(unittest.TestCase):
    def test_matches_sources_in_both_runs_ordered_by_source(self):
        changes = compare_measurements(
            [measured("slow", 300), measured("fast", 150), measured("new", 10)],
            [measured("fast", 100), measured("slow", 300), measured("gone", 5)],
        )
        self.assertEqual(
            changes,
            [
                MeasurementChange("fast", "ms", "ms", 150, 100, 50),
                MeasurementChange("slow", "ms", "ms", 300, 300, 0),
            ],
        )

    def test_no_delta_without_comparable_values(self):
        cases = {
            "different units": (measured("a", 1, "s"), measured("a", 1000)),
            "missing unit": (measured("a", 1, None), measured("a", 1, None)),
            "missing current": (measured("a", None), measured("a", 1)),
            "missing baseline": (measured("a", 1), measured("a", None)),
        }
        for name, (current, baseline) in cases.items():
            with self.subTest(name):
                (change,) = compare_measurements([current], [baseline])
                self.assertIsNone(change.delta)
                self.assertEqual(change.current, current.value)
                self.assertEqual(change.baseline, baseline.value)


if __name__ == "__main__":
    unittest.main()
