
from dataclasses import dataclass, field

from src.domain.gates.gate import Gate


@dataclass
class Report:
    report_id: str | None = None
    gates: list[Gate] = field(default_factory=list)
