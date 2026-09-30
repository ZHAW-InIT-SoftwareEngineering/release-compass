from dataclasses import dataclass
from typing import TypeAlias

from src.domain.gates.gate import Gate


NumericValue: TypeAlias = int | float


@dataclass(frozen=True)
class NumericDelta:
    baseline: NumericValue | None
    current: NumericValue | None
    delta: NumericValue | None


@dataclass(frozen=True)
class GateDeltas:
    gate_type: str
    baseline: Gate
    current: Gate
    numeric_deltas: dict[str, NumericDelta]
