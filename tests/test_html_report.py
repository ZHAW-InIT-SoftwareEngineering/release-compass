import tempfile
import unittest
from pathlib import Path

from src.adapters.outbound.html_report import HTMLReport


REPORT = Path(__file__).resolve().parents[1] / "data/raw/reports/example_reports/report.html"


class HTMLReportTests(unittest.TestCase):
    def test_ingests_performance_metrics_from_example_report(self):
        result = HTMLReport().ingest(REPORT)

        self.assertEqual(result.report_id, str(REPORT))
        response_time = result.response_time
        outcomes = result.request_outcomes
        throughput = result.throughput
        cpu = result.cpu
        memory = result.memory
        transaction_throughput = result.transactions["Login"].throughput
        assert response_time is not None
        assert outcomes is not None
        assert throughput is not None
        assert cpu is not None
        assert memory is not None
        assert transaction_throughput is not None
        thresholds = response_time.assessment.threshold_configuration
        assert thresholds is not None

        self.assertEqual(response_time.unit, "ms")
        self.assertEqual(response_time.observation_count, 14909)
        self.assertEqual(response_time.assessment.status, 2)
        self.assertEqual(thresholds.amber_violation_rate_percent, 5)
        self.assertTrue(response_time.violation_periods)
        self.assertEqual(outcomes.failed_requests, 1777)
        self.assertEqual(outcomes.passed_requests, 13132)
        self.assertEqual(outcomes.http_code_histogram["404"], 1777)
        self.assertEqual(throughput.unit, "req/s")
        self.assertEqual(throughput.assessment.status, 1)
        self.assertEqual(result.transactions["Login"].nfr_status, 2)
        self.assertEqual(transaction_throughput.target_nfr, 2)
        self.assertEqual(cpu.summary.unit, "cores")
        self.assertEqual(memory.summary.unit, "bytes")
        self.assertEqual(len(result.cpu_components), 4)
        self.assertEqual(len(result.memory_components), 4)
        self.assertIsNotNone(cpu.summary.start_time)

    def test_rejects_html_without_embedded_report_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.html"
            path.write_text("<html></html>", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "No __report_data__"):
                HTMLReport().ingest(path)


if __name__ == "__main__":
    unittest.main()
