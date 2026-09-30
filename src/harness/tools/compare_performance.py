from uuid import UUID

from langchain.tools import tool

from src.application.ports.outbound.report_reader import ReportReader
from src.adapters.outbound.sqlite_report_repository import SQLiteReportRepository


@tool
def compare_performance(run_id: UUID, baseline_run_id: UUID): 
    reportRepo: ReportReader = SQLiteReportRepository()

    baseline_run_metrics = reportRepo.get_by_id(baseline_run_id)
    current_run_metrics = reportRepo.get_by_id(run_id)

    deltas = compute_report_deltas(current_run_metrics, baseline_run_metrics)
