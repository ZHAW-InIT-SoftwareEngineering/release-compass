from typing import Protocol

from src.domain.report import Report


class ReportWriter(Protocol):
    def save(self, report: Report) -> None: ...
