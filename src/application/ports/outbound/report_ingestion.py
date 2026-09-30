from typing import Protocol

from src.domain.gates.performance.models import PerformanceGate


class ReportIngestionPort(Protocol): 
    def ingest(self, report_id) -> PerformanceGate: 
        ...