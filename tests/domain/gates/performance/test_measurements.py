import unittest

from src.domain.gates.performance.measurements import SUPPORTED, performance_measure
from src.domain.gates.performance.performance_gate import (
    PerformanceGate,
    RequestOutcomes,
    ResponseTimeMetric,
    ThroughputMetric,
    TransactionPerformance,
)
from src.domain.scoring import Measurement


def gate():
    return PerformanceGate(
        throughput=ThroughputMetric("run", "req/s", tps=46.3),
        transactions={
            "B": TransactionPerformance(
                "B",
                ResponseTimeMetric("test", "ms", 100, 60, p90=2000),
                RequestOutcomes(100, 5, 95, 5.0),
            ),
            "A": TransactionPerformance("A", None),
        },
    )


class PerformanceMeasureTests(unittest.TestCase):
    def test_transaction_metrics_are_measured_per_transaction(self):
        measure = performance_measure(gate())
        self.assertEqual(
            measure("response_time", "p90"),
            [
                Measurement("A", "transactions[A].response_time.p90", None, None, None),
                Measurement("B", "transactions[B].response_time.p90", 2000, "ms", 100),
            ],
        )
        self.assertEqual(
            measure("request_outcomes", "failure_rate_percent")[1],
            Measurement(
                "B",
                "transactions[B].request_outcomes.failure_rate_percent",
                5.0,
                "%",
                100,
            ),
        )

    def test_throughput_is_measured_once_for_the_run(self):
        self.assertEqual(
            performance_measure(gate())("throughput", "tps"),
            [Measurement("overall", "throughput.tps", 46.3, "req/s", 1)],
        )

    def test_rejects_unsupported_measures(self):
        measure = performance_measure(gate())
        for metric, aggregation in (("cpu", "mean"), ("throughput", "p90")):
            with self.subTest(metric=metric), self.assertRaises(ValueError):
                measure(metric, aggregation)

    def test_every_supported_measure_is_readable(self):
        measure = performance_measure(gate())
        for metric, aggregations in SUPPORTED.items():
            for aggregation in aggregations:
                with self.subTest(metric=metric, aggregation=aggregation):
                    self.assertTrue(measure(metric, aggregation))


if __name__ == "__main__":
    unittest.main()
