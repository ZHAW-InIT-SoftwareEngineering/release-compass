from src.domain.report import Report


def system_prompt(current_report: Report, last_report: Report) -> str: 
    return(
        f"The current report UUID is {current_report.report_id}. "
        f"The baseline report UUID is {last_report.report_id}"
        "For comparisons, use this as the current report and ask the user "
        "for a baseline report UUID if they have not provided one. Never invent IDs."
    )