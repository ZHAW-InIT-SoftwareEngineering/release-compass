from dataclasses import dataclass
from uuid import UUID


@dataclass
class Gate:
    baseline_report_id: UUID | None = None
