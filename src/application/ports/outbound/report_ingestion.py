from typing import Protocol
from pathlib import Path

from src.domain.report import Report


class ReportIngestionPort(Protocol): 
    def ingest(self, report_path: str | Path) -> Report: ...
