import unittest

from src.domain.gates.gate import Gate
from src.domain.gates.performance.measurements import SUPPORTED, performance_measure
from src.domain.gates.registry import gate_kind, gate_measurements
from tests.adapters.outbound.ontology.examples import performance_gate


class RegistryTests(unittest.TestCase):
    def test_yields_every_supported_measurement(self):
        gate = performance_gate()
        measure = performance_measure(gate)
        expected = [
            (metric, statistic, measurement)
            for metric, statistics in SUPPORTED.items()
            for statistic in statistics
            for measurement in measure(metric, statistic)
        ]
        self.assertEqual(list(gate_measurements(gate)), expected)
        self.assertEqual(gate_kind(gate).name, "performance")

    def test_rejects_unknown_gate_types(self):
        with self.assertRaisesRegex(ValueError, "Unsupported gate type Gate"):
            gate_kind(Gate())


if __name__ == "__main__":
    unittest.main()
