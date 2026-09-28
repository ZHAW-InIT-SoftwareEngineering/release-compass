from typing import Protocol

from src.domain.gates.performance.models import (
    MetricSummary
)


class ReportIngestionPort(Protocol): 
    def ingest(self, report_id): 
        ...