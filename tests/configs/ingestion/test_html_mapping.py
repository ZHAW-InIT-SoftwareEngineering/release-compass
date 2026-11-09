import dataclasses
import unittest
from pathlib import Path

from pydantic import ValidationError

from src.configs.ingestion.html_mapping import (
    MetricAssessmentMapping,
    MetricSummaryMapping,
    PerformanceGateMapping,
    ReportMapping,
    RequestOutcomesMapping,
    ResourceMetricMapping,
    ResponseTimeMetricMapping,
    ThresholdConfigurationMapping,
    ThroughputMetricMapping,
    TransactionPerformanceMapping,
    Transform,
    ViolationPeriodMapping,
    load_html_mapping,
)
from src.domain.gates.performance.performance_gate import (
    MetricAssessment,
    MetricSummary,
    PerformanceGate,
    RequestOutcomes,
    ResourceMetric,
    ResponseTimeMetric,
    ThresholdConfiguration,
    ThroughputMetric,
    TransactionPerformance,
    ViolationPeriod,
)
from src.domain.report import Report

LOCUST_MAPPING = Path(__file__).resolve().parents[3] / "configs/ingestion/locust.yaml"


class HtmlMappingTests(unittest.TestCase):
    def test_mapping_fields_exist_on_domain_models(self):
        for mapping, domain in (
            (ThresholdConfigurationMapping, ThresholdConfiguration),
            (MetricAssessmentMapping, MetricAssessment),
            (ViolationPeriodMapping, ViolationPeriod),
            (MetricSummaryMapping, MetricSummary),
            (ResponseTimeMetricMapping, ResponseTimeMetric),
            (RequestOutcomesMapping, RequestOutcomes),
            (ThroughputMetricMapping, ThroughputMetric),
            (TransactionPerformanceMapping, TransactionPerformance),
            (ResourceMetricMapping, ResourceMetric),
            (PerformanceGateMapping, PerformanceGate),
            (ReportMapping, Report),
        ):
            with self.subTest(mapping=mapping.__name__):
                domain_fields = {field.name for field in dataclasses.fields(domain)}
                self.assertLessEqual(set(mapping.model_fields), domain_fields)

    def test_loads_locust_mapping(self):
        mapping = load_html_mapping(LOCUST_MAPPING)
        self.assertEqual(mapping.extractor.kind, "js_assignment")
        self.assertIsNone(mapping.performance_gate.cpu)

    def test_requires_every_field_to_be_stated(self):
        data = load_html_mapping(LOCUST_MAPPING).model_dump()
        del data["performance_gate"]["cpu"]
        with self.assertRaisesRegex(ValidationError, "performance_gate.cpu"):
            type(load_html_mapping(LOCUST_MAPPING)).model_validate(data)

    def test_rejects_unknown_fields(self):
        data = load_html_mapping(LOCUST_MAPPING).model_dump()
        data["performance_gate"]["detect"] = "Locust"
        with self.assertRaisesRegex(ValidationError, "detect"):
            type(load_html_mapping(LOCUST_MAPPING)).model_validate(data)

    def test_rejects_wrong_transform_arity(self):
        with self.assertRaisesRegex(ValidationError, "percent takes 2"):
            Transform.model_validate({"transform": "percent", "args": ["a"]})


if __name__ == "__main__":
    unittest.main()
