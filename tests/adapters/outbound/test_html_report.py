import tempfile
import unittest
from pathlib import Path
from uuid import UUID

from src.adapters.outbound.html_report import HTMLReport
from src.configs.ingestion.html_mapping import HtmlMappingConfig, load_html_mapping
from src.domain.gates.performance.performance_gate import PerformanceGate

ROOT = Path(__file__).resolve().parents[3]
LOCUST_REPORT = (
    ROOT
    / "data/raw/reports/example_reports/TeaStoreReports/Locust"
    / "Locust_TeaStore_Report_Original.html"
)
LOCUST_MAPPING = ROOT / "configs/ingestion/locust.yaml"


def _metric(**overrides):
    fields = [
        "start_time",
        "end_time",
        "mean",
        "p50",
        "p90",
        "maximum",
        "target_nfr",
        "violation_count",
        "violation_rate_percent",
        "violation_periods",
    ]
    return {
        "source": {"const": "fixture"},
        "unit": {"const": "ms"},
        "observation_count": "count",
        "duration_seconds": {"const": 1},
        **dict.fromkeys(fields),
        "supporting_evidence": {},
        "assessment": None,
        **overrides,
    }


def _mapping(extractor, **gate):
    sections = [
        "response_time",
        "throughput",
        "request_outcomes",
        "transactions",
    ]
    return HtmlMappingConfig.model_validate(
        {
            "extractor": extractor,
            "report": {"generated_at_date": None, "generated_at_time": None},
            "performance_gate": {**dict.fromkeys(sections), **gate},
        }
    )


class HTMLReportTests(unittest.TestCase):
    def ingest_html(self, html, mapping):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.html"
            path.write_text(html, encoding="utf-8")
            return HTMLReport({"fixture": mapping}).ingest(path, "fixture")

    def test_ingests_locust_report(self):
        report = HTMLReport({"locust": load_html_mapping(LOCUST_MAPPING)}).ingest(
            LOCUST_REPORT, "locust"
        )

        self.assertIsInstance(report.report_id, UUID)
        self.assertEqual(report.source_path, str(LOCUST_REPORT))
        self.assertEqual(report.generated_at_date, "2026-11-10")
        self.assertEqual(report.generated_at_time, "10:02:29")
        (gate,) = report.gates
        assert isinstance(gate, PerformanceGate)
        response_time = gate.response_time
        outcomes = gate.request_outcomes
        throughput = gate.throughput
        assert response_time is not None
        assert outcomes is not None
        assert throughput is not None

        self.assertEqual(response_time.unit, "ms")
        self.assertEqual(response_time.observation_count, 194700)
        self.assertEqual(response_time.duration_seconds, 600)
        self.assertEqual(response_time.p50, 130)
        self.assertEqual(response_time.p90, 230)
        self.assertEqual(response_time.maximum, 1154)
        self.assertEqual(response_time.supporting_evidence["p95"], 250)
        history = response_time.supporting_evidence["history"]
        assert isinstance(history, list)
        self.assertEqual(len(history), 118)
        self.assertEqual(outcomes.failed_requests, 0)
        self.assertEqual(outcomes.passed_requests, 194700)
        self.assertAlmostEqual(outcomes.failure_rate_percent, 0)
        self.assertAlmostEqual(throughput.tps or 0, 324.3405, places=4)

        self.assertEqual(len(gate.transactions), 1129)
        self.assertNotIn("Aggregated", gate.transactions)
        health = gate.transactions["/tools.descartes.teastore.webui/"]
        assert health.response_time is not None
        self.assertEqual(health.name, "/tools.descartes.teastore.webui/")
        self.assertEqual(health.response_time.p90, 170)
        self.assertEqual(health.response_time.start_time, "2026-11-10T09:52:29Z")

    def test_reads_json_from_html_attribute(self):
        mapping = _mapping(
            {"kind": "attribute", "attribute": "data-raw"},
            response_time=_metric(),
        )
        report = self.ingest_html(
            '<div id="x" data-raw="{&quot;count&quot;: 3}"></div>', mapping
        )
        assert isinstance(report.gates[0], PerformanceGate)
        assert report.gates[0].response_time is not None
        self.assertEqual(report.gates[0].response_time.observation_count, 3)

    def test_builds_list_collections(self):
        period = {
            "start_time": "start",
            "end_time": "end",
            "duration_seconds": {"const": 5},
            "mean_value": None,
            "max_value": None,
            "violation_type": None,
        }
        mapping = _mapping(
            {"kind": "js_assignment", "variable": "window.data"},
            response_time=_metric(
                violation_periods={"for_each": "periods", "item": period}
            ),
        )
        report = self.ingest_html(
            '<script>window.data = {"count": 1, "periods": '
            '[{"start": "a", "end": "b"}]};</script>',
            mapping,
        )
        gate = report.gates[0]
        assert isinstance(gate, PerformanceGate)
        assert gate.response_time is not None
        (violation,) = gate.response_time.violation_periods
        self.assertEqual((violation.start_time, violation.end_time), ("a", "b"))
        self.assertEqual(violation.duration_seconds, 5)

    def test_rejects_unconfigured_source(self):
        with self.assertRaisesRegex(ValueError, "No ingestion mapping.*'unknown'"):
            HTMLReport({}).ingest(LOCUST_REPORT, "unknown")

    def test_rejects_html_without_configured_data(self):
        mapping = _mapping({"kind": "js_assignment", "variable": "window.data"})
        with self.assertRaisesRegex(ValueError, "No assignment to window.data"):
            self.ingest_html("<html></html>", mapping)

    def test_reports_missing_mapped_fields(self):
        mapping = _mapping(
            {"kind": "js_assignment", "variable": "window.data"},
            response_time=_metric(),
        )
        with self.assertRaisesRegex(ValueError, "Key 'count' not found"):
            self.ingest_html("<script>window.data = {};</script>", mapping)


if __name__ == "__main__":
    unittest.main()
