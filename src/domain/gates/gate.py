from dataclasses import dataclass
from uuid import UUID


@dataclass
class Gate:
    baseline_run_id: UUID | None = None
