from pathlib import Path
from typing import Protocol

from src.domain.report import Report


class ReportIngestionPort(Protocol):
    def ingest(self, report_path: str | Path, source: str) -> Report: ...
