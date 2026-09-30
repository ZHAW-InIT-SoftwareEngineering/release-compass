from uuid import UUID

from src.domain.report import Report


class SQLiteReportRepository: 
    def get_by_id(self, report_id: UUID) -> Report | None:
        sqlite_client = get_sqlite_client()
