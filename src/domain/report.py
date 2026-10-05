from dataclasses import dataclass, field
from uuid import UUID, uuid4

from src.domain.gates.gate import Gate


@dataclass
class Report:
    report_id: UUID = field(default_factory=uuid4)
    source_path: str | None = None
    generated_at_date: str | None = None
    generated_at_time: str | None = None
    gates: list[Gate] = field(default_factory=list)
