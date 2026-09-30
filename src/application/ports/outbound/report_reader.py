from typing import Protocol
from uuid import UUID

from src.domain.report import Report


class ReportReader(Protocol):
    def get_by_id(self, report_id: UUID) -> Report | None: ...
